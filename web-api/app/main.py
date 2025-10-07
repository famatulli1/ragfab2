"""
Application principale FastAPI pour RAGFab Web Interface
"""
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, BackgroundTasks, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from typing import List, Optional
from datetime import datetime
from uuid import UUID
import logging
import os
import shutil
import asyncio
import sys
import io
import json
import httpx
from threading import Lock

# Ajouter le path du rag-app pour importer les modules
sys.path.insert(0, "/app/rag-app")

from .config import settings
from . import database
from .database import initialize_database, close_database
from .auth import get_current_admin_user, get_current_user
from .models import (
    LoginRequest, TokenResponse, User,
    Document, DocumentStats, ChunkResponse,
    Conversation, ConversationCreate, ConversationUpdate, ConversationWithStats,
    MessageResponse, ChatRequest, ChatResponse,
    RatingCreate, Rating,
    IngestionJob,
    ExportRequest
)
from .routes import auth

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Variable globale thread-safe pour stocker les sources trouvées par le tool
_tool_sources: List[dict] = []
_tool_sources_lock = Lock()

# Créer l'application FastAPI avec limite d'upload augmentée
app = FastAPI(
    title="RAGFab Web API",
    description="API pour l'interface web de RAGFab - Chat et Administration",
    version="1.0.0",
    # Augmenter la limite de taille de requête à 100 MB
    swagger_ui_parameters={"defaultModelsExpandDepth": -1}
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclure les routes
app.include_router(auth.router)


# ============================================================================
# Event Handlers
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialisation au démarrage"""
    logger.info("🚀 Démarrage de l'API RAGFab...")
    await initialize_database()

    # Créer le répertoire d'uploads
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    logger.info("✅ API RAGFab prête")


@app.on_event("shutdown")
async def shutdown_event():
    """Nettoyage à l'arrêt"""
    logger.info("Arrêt de l'API RAGFab...")
    await close_database()


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "database": "connected" if database.db_pool else "disconnected",
        "timestamp": datetime.utcnow().isoformat()
    }


# ============================================================================
# Documents Routes
# ============================================================================

@app.get("/api/documents", response_model=List[DocumentStats])
async def list_documents(
    limit: int = 100,
    offset: int = 0,
    current_user: dict = Depends(get_current_admin_user)
):
    """Liste tous les documents avec stats"""
    async with database.db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM document_stats
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit, offset
        )
        return [DocumentStats(**dict(row)) for row in rows]


@app.get("/api/documents/{document_id}", response_model=DocumentStats)
async def get_document(
    document_id: UUID,
    current_user: dict = Depends(get_current_admin_user)
):
    """Récupère un document par ID"""
    async with database.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM document_stats WHERE id = $1",
            document_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Document not found")
        return DocumentStats(**dict(row))


@app.get("/api/documents/{document_id}/chunks", response_model=List[ChunkResponse])
async def get_document_chunks(
    document_id: UUID,
    limit: int = 100,
    offset: int = 0,
    current_user: dict = Depends(get_current_admin_user)
):
    """Récupère les chunks d'un document"""
    async with database.db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, content, chunk_index, token_count, metadata
            FROM chunks
            WHERE document_id = $1
            ORDER BY chunk_index
            LIMIT $2 OFFSET $3
            """,
            document_id, limit, offset
        )
        # Parser le metadata JSON stocké comme string
        chunks = []
        for row in rows:
            chunk_dict = dict(row)
            if isinstance(chunk_dict.get('metadata'), str):
                chunk_dict['metadata'] = json.loads(chunk_dict['metadata'])
            chunks.append(ChunkResponse(**chunk_dict))
        return chunks


@app.get("/api/documents/{document_id}/view")
async def get_document_view(document_id: UUID):
    """Récupère le document complet avec tous ses chunks pour visualisation"""
    async with database.db_pool.acquire() as conn:
        # Récupérer le document
        doc_row = await conn.fetchrow(
            "SELECT * FROM documents WHERE id = $1",
            document_id
        )
        if not doc_row:
            raise HTTPException(status_code=404, detail="Document not found")

        # Récupérer tous les chunks triés par index
        chunks_rows = await conn.fetch(
            """
            SELECT id, content, chunk_index
            FROM chunks
            WHERE document_id = $1
            ORDER BY chunk_index
            """,
            document_id
        )

        return {
            "document": {
                "id": str(doc_row["id"]),
                "title": doc_row["title"],
                "source": doc_row["source"],
                "content": doc_row["content"],
                "created_at": doc_row["created_at"].isoformat(),
            },
            "chunks": [
                {
                    "id": str(row["id"]),
                    "content": row["content"],
                    "chunk_index": row["chunk_index"],
                }
                for row in chunks_rows
            ]
        }


@app.post("/api/documents/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_admin_user)
):
    """Upload et ingestion d'un document (traitement en arrière-plan)"""

    # Vérifier la taille
    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size: {settings.MAX_UPLOAD_SIZE} bytes"
        )

    # Sauvegarder le fichier
    upload_path = os.path.join(settings.UPLOAD_DIR, file.filename)
    with open(upload_path, "wb") as f:
        f.write(content)

    # Créer un job d'ingestion
    async with database.db_pool.acquire() as conn:
        job_id = await conn.fetchval(
            """
            INSERT INTO ingestion_jobs (filename, file_size, status)
            VALUES ($1, $2, 'pending')
            RETURNING id
            """,
            file.filename, len(content)
        )

    # Lancer l'ingestion en arrière-plan
    background_tasks.add_task(process_ingestion, job_id, upload_path, file.filename)

    return {
        "job_id": str(job_id),
        "filename": file.filename,
        "status": "pending",
        "message": "Upload successful, processing started"
    }


@app.get("/api/documents/jobs/{job_id}", response_model=IngestionJob)
async def get_ingestion_job(
    job_id: UUID,
    current_user: dict = Depends(get_current_admin_user)
):
    """Récupère le statut d'un job d'ingestion"""
    async with database.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM ingestion_jobs WHERE id = $1",
            job_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Job not found")
        return IngestionJob(**dict(row))


@app.delete("/api/documents/{document_id}")
async def delete_document(
    document_id: UUID,
    current_user: dict = Depends(get_current_admin_user)
):
    """Supprime un document et ses chunks"""
    async with database.db_pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM documents WHERE id = $1",
            document_id
        )
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Document not found")

    return {"message": "Document deleted successfully"}


# ============================================================================
# Conversations Routes
# ============================================================================

@app.get("/api/conversations", response_model=List[ConversationWithStats])
async def list_conversations(
    limit: int = 50,
    offset: int = 0,
    include_archived: bool = False
):
    """Liste toutes les conversations"""
    async with database.db_pool.acquire() as conn:
        query = """
            SELECT * FROM conversation_stats
            WHERE ($3 = true OR archived = false)
            ORDER BY updated_at DESC
            LIMIT $1 OFFSET $2
        """
        rows = await conn.fetch(query, limit, offset, include_archived)
        return [ConversationWithStats(**dict(row)) for row in rows]


@app.post("/api/conversations", response_model=Conversation)
async def create_conversation(request: ConversationCreate):
    """Crée une nouvelle conversation"""
    async with database.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO conversations (title, provider, use_tools)
            VALUES ($1, $2, $3)
            RETURNING *
            """,
            request.title, request.provider, request.use_tools
        )
        return Conversation(**dict(row))


@app.get("/api/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: UUID):
    """Récupère une conversation par ID"""
    async with database.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM conversations WHERE id = $1",
            conversation_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return Conversation(**dict(row))


@app.patch("/api/conversations/{conversation_id}", response_model=Conversation)
async def update_conversation(
    conversation_id: UUID,
    request: ConversationUpdate
):
    """Met à jour une conversation"""
    updates = []
    values = []
    param_count = 1

    if request.title is not None:
        updates.append(f"title = ${param_count}")
        values.append(request.title)
        param_count += 1

    if request.is_archived is not None:
        updates.append(f"archived = ${param_count}")
        values.append(request.is_archived)
        param_count += 1

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    values.append(conversation_id)
    query = f"""
        UPDATE conversations
        SET {', '.join(updates)}
        WHERE id = ${param_count}
        RETURNING *
    """

    async with database.db_pool.acquire() as conn:
        row = await conn.fetchrow(query, *values)
        if not row:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return Conversation(**dict(row))


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: UUID):
    """Supprime une conversation et ses messages"""
    async with database.db_pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM conversations WHERE id = $1",
            conversation_id
        )
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Conversation not found")

    return {"message": "Conversation deleted successfully"}


# ============================================================================
# Messages & Chat Routes
# ============================================================================

@app.get("/api/conversations/{conversation_id}/messages", response_model=List[MessageResponse])
async def get_conversation_messages(
    conversation_id: UUID,
    limit: int = 100,
    offset: int = 0
):
    """Récupère les messages d'une conversation"""
    async with database.db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT m.*, mr.rating
            FROM messages m
            LEFT JOIN message_ratings mr ON m.id = mr.message_id
            WHERE m.conversation_id = $1
            ORDER BY m.created_at
            LIMIT $2 OFFSET $3
            """,
            conversation_id, limit, offset
        )
        # Décoder les champs JSON
        messages = []
        for row in rows:
            msg_dict = dict(row)
            if msg_dict.get('sources') and isinstance(msg_dict['sources'], str):
                msg_dict['sources'] = json.loads(msg_dict['sources'])
            if msg_dict.get('token_usage') and isinstance(msg_dict['token_usage'], str):
                msg_dict['token_usage'] = json.loads(msg_dict['token_usage'])
            messages.append(MessageResponse(**msg_dict))
        return messages


@app.post("/api/chat", response_model=ChatResponse)
async def send_message(request: ChatRequest):
    """
    Envoie un message et obtient une réponse du RAG agent

    Cette route:
    1. Crée le message utilisateur
    2. Récupère l'historique de la conversation
    3. Exécute le RAG agent avec le provider approprié
    4. Sauvegarde la réponse
    5. Retourne le tout
    """
    # Récupérer la conversation
    async with database.db_pool.acquire() as conn:
        conversation = await conn.fetchrow(
            "SELECT * FROM conversations WHERE id = $1",
            request.conversation_id
        )
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

    # Déterminer le provider à utiliser
    provider = request.provider or conversation["provider"]
    use_tools = request.use_tools if request.use_tools is not None else conversation["use_tools"]

    # Créer le message utilisateur
    async with database.db_pool.acquire() as conn:
        user_message = await conn.fetchrow(
            """
            INSERT INTO messages (conversation_id, role, content)
            VALUES ($1, 'user', $2)
            RETURNING *
            """,
            request.conversation_id, request.message
        )

    # Récupérer l'historique (pour le context)
    async with database.db_pool.acquire() as conn:
        history = await conn.fetch(
            """
            SELECT role, content
            FROM messages
            WHERE conversation_id = $1
            AND id != $2
            ORDER BY created_at
            """,
            request.conversation_id, user_message["id"]
        )

    # Exécuter le RAG agent
    try:
        assistant_response = await execute_rag_agent(
            message=request.message,
            history=[{"role": msg["role"], "content": msg["content"]} for msg in history],
            provider=provider,
            use_tools=use_tools
        )
    except Exception as e:
        logger.error(f"Erreur RAG agent: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing message: {str(e)}"
        )

    # Sauvegarder la réponse de l'assistant
    async with database.db_pool.acquire() as conn:
        # Convertir sources et token_usage en JSON si ce sont des listes/dicts
        sources_json = json.dumps(assistant_response.get("sources")) if assistant_response.get("sources") else None
        token_usage_json = json.dumps(assistant_response.get("token_usage")) if assistant_response.get("token_usage") else None

        assistant_message = await conn.fetchrow(
            """
            INSERT INTO messages (
                conversation_id, role, content, sources,
                provider, model_name, token_usage
            )
            VALUES ($1, 'assistant', $2, $3, $4, $5, $6)
            RETURNING *
            """,
            request.conversation_id,
            assistant_response["content"],
            sources_json,
            provider,
            assistant_response.get("model_name"),
            token_usage_json
        )

    # Retourner la réponse complète
    # Décoder les champs JSON depuis la base de données
    assistant_dict = dict(assistant_message)
    if assistant_dict.get('sources') and isinstance(assistant_dict['sources'], str):
        assistant_dict['sources'] = json.loads(assistant_dict['sources'])
    if assistant_dict.get('token_usage') and isinstance(assistant_dict['token_usage'], str):
        assistant_dict['token_usage'] = json.loads(assistant_dict['token_usage'])

    return ChatResponse(
        user_message=MessageResponse(**dict(user_message), rating=None),
        assistant_message=MessageResponse(**assistant_dict, rating=None),
        conversation=Conversation(**dict(conversation))
    )


@app.post("/api/messages/{message_id}/regenerate", response_model=MessageResponse)
async def regenerate_message(message_id: UUID):
    """Régénère une réponse assistant"""
    # Récupérer le message original
    async with database.db_pool.acquire() as conn:
        original = await conn.fetchrow(
            "SELECT * FROM messages WHERE id = $1 AND role = 'assistant'",
            message_id
        )
        if not original:
            raise HTTPException(status_code=404, detail="Message not found or not an assistant message")

        # Récupérer le message utilisateur précédent
        user_msg = await conn.fetchrow(
            """
            SELECT * FROM messages
            WHERE conversation_id = $1
            AND created_at < $2
            AND role = 'user'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            original["conversation_id"], original["created_at"]
        )

        if not user_msg:
            raise HTTPException(status_code=400, detail="No user message found to regenerate from")

        # Récupérer conversation
        conversation = await conn.fetchrow(
            "SELECT * FROM conversations WHERE id = $1",
            original["conversation_id"]
        )

    # Exécuter le RAG agent à nouveau
    try:
        assistant_response = await execute_rag_agent(
            message=user_msg["content"],
            history=[],  # TODO: Récupérer l'historique correct
            provider=conversation["provider"],
            use_tools=conversation["use_tools"]
        )
    except Exception as e:
        logger.error(f"Erreur RAG agent: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error regenerating message: {str(e)}")

    # Sauvegarder la nouvelle réponse
    async with database.db_pool.acquire() as conn:
        # Convertir sources et token_usage en JSON
        sources_json = json.dumps(assistant_response.get("sources")) if assistant_response.get("sources") else None
        token_usage_json = json.dumps(assistant_response.get("token_usage")) if assistant_response.get("token_usage") else None

        new_message = await conn.fetchrow(
            """
            INSERT INTO messages (
                conversation_id, role, content, sources,
                provider, model_name, token_usage,
                is_regenerated, parent_message_id
            )
            VALUES ($1, 'assistant', $2, $3, $4, $5, $6, true, $7)
            RETURNING *
            """,
            original["conversation_id"],
            assistant_response["content"],
            sources_json,
            conversation["provider"],
            assistant_response.get("model_name"),
            token_usage_json,
            message_id
        )

    # Décoder les champs JSON avant de retourner
    msg_dict = dict(new_message)
    if msg_dict.get('sources') and isinstance(msg_dict['sources'], str):
        msg_dict['sources'] = json.loads(msg_dict['sources'])
    if msg_dict.get('token_usage') and isinstance(msg_dict['token_usage'], str):
        msg_dict['token_usage'] = json.loads(msg_dict['token_usage'])

    return MessageResponse(**msg_dict, rating=None)


@app.post("/api/messages/{message_id}/rate", response_model=Rating)
async def rate_message(message_id: UUID, request: RatingCreate):
    """Note un message (thumbs up/down)"""
    async with database.db_pool.acquire() as conn:
        # Vérifier que le message existe
        message = await conn.fetchrow(
            "SELECT id FROM messages WHERE id = $1",
            message_id
        )
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")

        # Insérer ou mettre à jour la notation
        rating = await conn.fetchrow(
            """
            INSERT INTO message_ratings (message_id, rating, feedback)
            VALUES ($1, $2, $3)
            ON CONFLICT (message_id) DO UPDATE
            SET rating = $2, feedback = $3, created_at = CURRENT_TIMESTAMP
            RETURNING *
            """,
            message_id, request.rating, request.feedback
        )

    return Rating(**dict(rating))


# ============================================================================
# Export Routes
# ============================================================================

@app.post("/api/conversations/{conversation_id}/export")
async def export_conversation(
    conversation_id: UUID,
    request: ExportRequest
):
    """Exporte une conversation en Markdown ou PDF"""
    # Récupérer la conversation et ses messages
    async with database.db_pool.acquire() as conn:
        conversation = await conn.fetchrow(
            "SELECT * FROM conversations WHERE id = $1",
            conversation_id
        )
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        messages = await conn.fetch(
            """
            SELECT * FROM messages
            WHERE conversation_id = $1
            ORDER BY created_at
            """,
            conversation_id
        )

    if request.format == "markdown":
        # Générer Markdown
        content = f"# {conversation['title']}\n\n"
        content += f"**Date:** {conversation['created_at'].strftime('%Y-%m-%d %H:%M')}\n\n"
        content += f"**Provider:** {conversation['provider']}\n\n"
        content += "---\n\n"

        for msg in messages:
            role = "🧑 Vous" if msg["role"] == "user" else "🤖 Assistant"
            content += f"## {role}\n\n{msg['content']}\n\n"

        # Retourner le fichier
        return StreamingResponse(
            iter([content]),
            media_type="text/markdown",
            headers={
                "Content-Disposition": f"attachment; filename=conversation_{conversation_id}.md"
            }
        )

    elif request.format == "pdf":
        # TODO: Implémenter l'export PDF avec reportlab
        raise HTTPException(status_code=501, detail="PDF export not yet implemented")

    else:
        raise HTTPException(status_code=400, detail="Invalid format. Use 'markdown' or 'pdf'")


# ============================================================================
# Helper Functions
# ============================================================================

async def process_ingestion(job_id: UUID, file_path: str, filename: str):
    """Traite l'ingestion d'un document en arrière-plan en appelant directement le pipeline Python"""
    try:
        # Mettre à jour le statut
        async with database.db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE ingestion_jobs
                SET status = 'processing', started_at = CURRENT_TIMESTAMP, progress = 10
                WHERE id = $1
                """,
                job_id
            )

        logger.info(f"📤 Démarrage ingestion de {filename}")

        # Progress 30%
        async with database.db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE ingestion_jobs SET progress = 30 WHERE id = $1",
                job_id
            )

        # Créer un dossier temporaire pour ce fichier
        upload_dir = settings.UPLOAD_DIR
        doc_folder = os.path.join(upload_dir, f"job_{job_id}")
        os.makedirs(doc_folder, exist_ok=True)

        # Déplacer le fichier dans le dossier temporaire
        doc_path = os.path.join(doc_folder, filename)
        if os.path.exists(file_path) and file_path != doc_path:
            import shutil
            shutil.move(file_path, doc_path)

        logger.info(f"📁 Fichier sauvegardé: {doc_path}")

        # Progress 50%
        async with database.db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE ingestion_jobs SET progress = 50 WHERE id = $1",
                job_id
            )

        # Importer et utiliser le pipeline d'ingestion directement
        # Les modules rag-app sont montés dans /app/rag-app avec PYTHONPATH=/app
        sys.path.insert(0, "/app/rag-app")
        from ingestion.ingest import DocumentIngestionPipeline
        from utils.models import IngestionConfig

        # Configuration d'ingestion
        config = IngestionConfig(
            chunk_size=1000,
            chunk_overlap=200,
            max_chunk_size=2000,
            use_semantic_chunking=True
        )

        # Créer et initialiser le pipeline
        pipeline = DocumentIngestionPipeline(
            config=config,
            documents_folder=doc_folder,
            clean_before_ingest=False  # Ne pas nettoyer la BD
        )

        await pipeline.initialize()

        # Progress 60%
        async with database.db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE ingestion_jobs SET progress = 60 WHERE id = $1",
                job_id
            )

        logger.info(f"🔄 Ingestion du document via pipeline...")

        # Lancer l'ingestion
        results = await pipeline.ingest_documents()

        await pipeline.close()

        # Progress 80%
        async with database.db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE ingestion_jobs SET progress = 80 WHERE id = $1",
                job_id
            )

        # Compter les chunks créés
        total_chunks = sum(r.chunks_created for r in results)

        logger.info(f"✅ Ingestion terminée: {total_chunks} chunks créés")

        # Marquer comme terminé
        async with database.db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE ingestion_jobs
                SET status = 'completed', completed_at = CURRENT_TIMESTAMP,
                    progress = 100, chunks_created = $2
                WHERE id = $1
                """,
                job_id, total_chunks
            )

        # Nettoyer le dossier temporaire
        import shutil
        if os.path.exists(doc_folder):
            shutil.rmtree(doc_folder)

        logger.info(f"✅ Job {job_id} terminé avec succès")

    except Exception as e:
        logger.error(f"❌ Erreur lors de l'ingestion: {e}", exc_info=True)

        # Marquer comme échoué
        async with database.db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE ingestion_jobs
                SET status = 'failed', error_message = $2, completed_at = CURRENT_TIMESTAMP
                WHERE id = $1
                """,
                job_id, str(e)
            )


async def get_search_sources(query: str, limit: int = 5) -> List[dict]:
    """Récupère les sources structurées depuis la base de connaissances"""
    try:
        # Générer l'embedding via le service HTTP
        embeddings_url = os.getenv("EMBEDDINGS_API_URL", "http://ragfab-embeddings:8001")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{embeddings_url}/embed",
                json={"text": query},
                timeout=30.0
            )
            response.raise_for_status()
            query_embedding = response.json()["embedding"]

        embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"

        # Rechercher dans la BD
        async with database.db_pool.acquire() as conn:
            results = await conn.fetch(
                """
                SELECT
                    c.id as chunk_id,
                    c.content,
                    c.chunk_index,
                    d.id as document_id,
                    d.title as document_title,
                    d.source as document_source,
                    1 - (c.embedding <=> $1::vector) as similarity
                FROM chunks c
                JOIN documents d ON c.document_id = d.id
                ORDER BY c.embedding <=> $1::vector
                LIMIT $2
                """,
                embedding_str,
                limit
            )

        # Formater les sources
        sources = []
        for row in results:
            sources.append({
                "chunk_id": str(row["chunk_id"]),
                "document_id": str(row["document_id"]),
                "document_title": row["document_title"],
                "document_source": row["document_source"],
                "chunk_index": row["chunk_index"],
                "content": row["content"][:200] + "..." if len(row["content"]) > 200 else row["content"],
                "similarity": float(row["similarity"])
            })

        return sources
    except Exception as e:
        logger.error(f"Erreur récupération sources: {e}", exc_info=True)
        return []


async def search_knowledge_base_tool(query: str, limit: int = 5) -> str:
    """Tool pour rechercher dans la base de connaissances - version web-api sans docling"""
    logger.info(f"🔍 Tool search_knowledge_base_tool appelé avec query: {query}")
    try:
        # Générer l'embedding via le service
        embeddings_url = os.getenv("EMBEDDINGS_API_URL", "http://ragfab-embeddings:8001")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{embeddings_url}/embed",
                json={"text": query},
                timeout=30.0
            )
            response.raise_for_status()
            query_embedding = response.json()["embedding"]

        embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"

        # Rechercher dans la BD avec métadonnées complètes
        async with database.db_pool.acquire() as conn:
            results = await conn.fetch(
                """
                SELECT
                    c.id as chunk_id,
                    c.content,
                    c.chunk_index,
                    d.id as document_id,
                    d.title as document_title,
                    d.source as document_source,
                    1 - (c.embedding <=> $1::vector) as similarity
                FROM chunks c
                JOIN documents d ON c.document_id = d.id
                ORDER BY c.embedding <=> $1::vector
                LIMIT $2
                """,
                embedding_str,
                limit
            )

        if not results:
            global _tool_sources
            with _tool_sources_lock:
                _tool_sources = []
            return "Aucune information pertinente trouvée dans la base de connaissances."

        # Stocker les sources avec métadonnées pour le frontend
        sources = []
        response_parts = []
        for row in results:
            sources.append({
                "chunk_id": str(row["chunk_id"]),
                "document_id": str(row["document_id"]),
                "document_title": row["document_title"],
                "document_source": row["document_source"],
                "chunk_index": row["chunk_index"],
                "content": row["content"][:200] + "..." if len(row["content"]) > 200 else row["content"],
                "similarity": float(row["similarity"])
            })
            response_parts.append(f"[Source: {row['document_title']}]\n{row['content']}\n")

        # Sauvegarder les sources dans la variable globale
        with _tool_sources_lock:
            _tool_sources = sources.copy()
        logger.info(f"✅ {len(sources)} sources sauvegardées (global)")

        return "Résultats trouvés dans la base de connaissances:\n\n" + "\n---\n".join(response_parts)

    except Exception as e:
        logger.error(f"Erreur dans search_knowledge_base_tool: {e}", exc_info=True)
        with _tool_sources_lock:
            _tool_sources = []
        return f"Erreur lors de la recherche: {str(e)}"


async def execute_rag_agent(
    message: str,
    history: List[dict],
    provider: str,
    use_tools: bool
) -> dict:
    """Exécute le RAG agent et retourne la réponse"""
    try:
        from utils.chocolatine_provider import get_chocolatine_model
        from utils.mistral_provider import get_mistral_model
        from pydantic_ai import Agent, RunContext

        # Initialiser les sources à vide
        global _tool_sources
        with _tool_sources_lock:
            _tool_sources = []
        sources = []

        # Pour Chocolatine : recherche manuelle + injection dans le prompt
        if provider == "chocolatine":
            # Faire la recherche avec notre tool local (stocke les sources dans le contexte)
            search_results = await search_knowledge_base_tool(message, limit=5)
            # Récupérer les sources stockées par le tool
            with _tool_sources_lock:
                sources = _tool_sources.copy()

            # Créer le system prompt avec le contexte
            system_prompt = f"""Tu es un assistant intelligent basé sur la documentation Medimail Webmail.

CONTEXTE DE LA BASE DE CONNAISSANCES:
{search_results}

INSTRUCTIONS:
- Utilise UNIQUEMENT les informations du contexte ci-dessus pour répondre
- Si l'information n'est pas dans le contexte, dis-le clairement
- Réponds en français de manière concise et précise
- Cite toujours tes sources entre crochets [Source: ...]"""

            model = get_chocolatine_model()
            agent = Agent(model, system_prompt=system_prompt)

        elif provider == "mistral" and use_tools:
            # Mistral avec tools
            model = get_mistral_model()
            system_prompt = """Tu es un assistant qui répond UNIQUEMENT en utilisant une base de connaissances documentaire.

RÈGLES ABSOLUES - AUCUNE EXCEPTION :
1. Pour CHAQUE question de l'utilisateur, tu DOIS OBLIGATOIREMENT appeler l'outil 'search_knowledge_base_tool' AVANT de répondre
2. Tu ne peux répondre QU'avec les informations retournées par l'outil - JAMAIS avec tes connaissances générales
3. Si l'outil ne retourne aucune information pertinente, tu dois dire : "Je n'ai pas trouvé cette information dans la base de connaissances"
4. Ne cite PAS les sources dans ta réponse (pas de [Source: ...]) car elles sont affichées séparément
5. Même si tu penses connaître la réponse, tu DOIS d'abord chercher dans la base de connaissances

INTERDIT :
❌ Répondre sans avoir appelé l'outil de recherche
❌ Utiliser tes connaissances générales ou pré-entraînées
❌ Inventer ou supposer des informations
❌ Répondre de manière générique
❌ Ajouter [Source: ...] dans la réponse

Réponds en français de manière concise en te basant UNIQUEMENT sur les résultats de recherche."""
            logger.info(f"🔧 Création agent Mistral avec tools: {[search_knowledge_base_tool]}")
            agent = Agent(model, system_prompt=system_prompt, tools=[search_knowledge_base_tool])
            logger.info(f"✅ Agent Mistral créé avec {len(agent._function_tools)} tools")
        else:
            # Mistral sans tools
            model = get_mistral_model()
            agent = Agent(model, system_prompt="Tu es un assistant qui répond en français.")

        # NE PAS passer l'historique complet à Mistral car il décide alors de ne pas appeler les tools
        # À la place, on injecte seulement un résumé du contexte dans le message actuel
        if history and len(history) > 0:
            # Prendre seulement les 2 derniers échanges pour le contexte
            recent_history = history[-4:] if len(history) >= 4 else history
            context_summary = "\n".join([
                f"{'Utilisateur' if msg['role'] == 'user' else 'Assistant'}: {msg['content'][:200]}"
                for msg in recent_history
            ])
            enhanced_message = f"Contexte récent:\n{context_summary}\n\nNouvelle question: {message}"
        else:
            enhanced_message = message

        # Exécuter l'agent SANS historique pour forcer l'appel du tool à chaque fois
        result = await agent.run(enhanced_message, message_history=[])

        # Pour Mistral avec tools, récupérer les sources depuis la variable globale
        # (le tool les a sauvegardées lors de son exécution)
        if provider == "mistral" and use_tools:
            with _tool_sources_lock:
                sources = _tool_sources.copy()
            logger.info(f"📚 Sources récupérées du tool: {len(sources)} sources")

        return {
            "content": result.data,
            "sources": sources,
            "model_name": provider,
            "token_usage": None
        }

    except Exception as e:
        logger.error(f"Erreur RAG agent: {e}", exc_info=True)
        return {
            "content": f"Erreur: {str(e)}",
            "sources": [],
            "model_name": provider,
            "token_usage": None
        }

