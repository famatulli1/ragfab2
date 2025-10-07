"""
Application principale FastAPI pour RAGFab Web Interface
"""
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, BackgroundTasks, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from typing import List, Optional, Dict
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

# Variable globale pour stocker les sources de la requête en cours
# Plus fiable que ContextVar qui peut être perdu dans les appels async de PydanticAI
# Note: Pas de problème de concurrence car FastAPI traite les requêtes séquentiellement avec async
_current_request_sources: List[dict] = []

# Rate limiter configuration
limiter = Limiter(key_func=get_remote_address)

# Créer l'application FastAPI avec limite d'upload augmentée
app = FastAPI(
    title="RAGFab Web API",
    description="""
    ## API pour RAGFab - Système RAG Français Dual-Provider

    ### Fonctionnalités
    - 🔐 **Authentification JWT** avec rate limiting
    - 💬 **Chat RAG** avec providers Mistral & Chocolatine
    - 📄 **Gestion documentaire** avec ingestion multi-format
    - 🔍 **Recherche vectorielle** avec PostgreSQL + PGVector
    - 📊 **Administration** des conversations et documents

    ### Rate Limits
    - Login: 5 tentatives/minute
    - Chat: 20 messages/minute
    - Upload: 10 fichiers/heure
    """,
    version="1.0.0",
    docs_url="/api/docs",  # Swagger UI
    redoc_url="/api/redoc",  # ReDoc alternative
    contact={
        "name": "RAGFab Support",
        "url": "https://github.com/famatulli1/ragfab",
    },
    license_info={
        "name": "MIT",
    },
    swagger_ui_parameters={"defaultModelsExpandDepth": -1}
)

# Add rate limit state and handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Upload de documents désactivé en production.

    L'ingestion nécessite des packages lourds (docling, transformers, torch ~3GB)
    qui ne sont pas installés en production pour garder le backend léger.

    Pour ingérer des documents:
    1. En local: `docker-compose run --rm rag-app python -m ingestion.ingest`
    2. Les chunks seront automatiquement dans PostgreSQL
    3. Le backend Coolify les utilisera immédiatement (lecture seule)
    """
    raise HTTPException(
        status_code=501,
        detail="Document upload is disabled in production. Use 'docker-compose run rag-app' for ingestion."
    )


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
@limiter.limit("20/minute")  # Max 20 messages per minute
async def send_message(request: Request, chat_request: ChatRequest):
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
            chat_request.conversation_id
        )
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

    # Déterminer le provider à utiliser
    provider = chat_request.provider or conversation["provider"]
    use_tools = chat_request.use_tools if chat_request.use_tools is not None else conversation["use_tools"]

    # Créer le message utilisateur
    async with database.db_pool.acquire() as conn:
        user_message = await conn.fetchrow(
            """
            INSERT INTO messages (conversation_id, role, content)
            VALUES ($1, 'user', $2)
            RETURNING *
            """,
            chat_request.conversation_id, chat_request.message
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
            chat_request.conversation_id, user_message["id"]
        )

    # Exécuter le RAG agent
    try:
        assistant_response = await execute_rag_agent(
            message=chat_request.message,
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
            chat_request.conversation_id,
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

# FONCTION DÉSACTIVÉE: Ingestion nécessite des packages lourds (docling, transformers, torch)
# non installés en production pour garder le build léger (<1 min au lieu de 3+ min)
# L'ingestion se fait uniquement en local via: docker-compose run --rm rag-app
# Les chunks ingérés sont automatiquement disponibles sur Coolify (lecture depuis PostgreSQL)
# async def process_ingestion(job_id: UUID, file_path: str, filename: str):
#     """Traite l'ingestion d'un document en arrière-plan"""
#     pass


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
    global _current_request_sources
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
            _current_request_sources = []
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
        _current_request_sources = sources.copy()
        logger.info(f"✅ {len(sources)} sources sauvegardées dans _current_request_sources")

        return "Résultats trouvés dans la base de connaissances:\n\n" + "\n---\n".join(response_parts)

    except Exception as e:
        logger.error(f"Erreur dans search_knowledge_base_tool: {e}", exc_info=True)
        _current_request_sources = []
        return f"Erreur lors de la recherche: {str(e)}"


async def reformulate_question_with_context(
    current_question: str,
    history: List[dict],
    max_history_pairs: int = 2
) -> str:
    """
    Reformule une question en intégrant le contexte conversationnel nécessaire.

    Args:
        current_question: Question actuelle posée par l'utilisateur
        history: Historique de la conversation (messages alternés user/assistant)
        max_history_pairs: Nombre maximum de paires question/réponse à considérer

    Returns:
        Question reformulée de manière autonome et compréhensible sans contexte
    """
    # Si pas d'historique ou question déjà complète, retourner telle quelle
    if not history or len(history) < 2:
        logger.info(f"🔄 Pas de reformulation nécessaire (historique vide)")
        return current_question

    # Détecter si la question contient des références contextuelles
    contextual_keywords = ["celle", "celui", "ceux", "ça", "cela", "ce", "cette", "il", "elle", "ils", "elles", "le", "la", "les", "y", "en"]
    has_reference = any(word in current_question.lower().split() for word in contextual_keywords)

    if not has_reference:
        logger.info(f"🔄 Pas de reformulation nécessaire (pas de référence détectée)")
        return current_question

    logger.info(f"🔄 Reformulation nécessaire (référence contextuelle détectée)")

    # Extraire les derniers échanges pertinents
    num_pairs = min(max_history_pairs, len(history) // 2)
    recent_history = history[-(num_pairs * 2):]

    # Construire le contexte pour la reformulation
    context_lines = []
    for i in range(0, len(recent_history), 2):
        if i + 1 < len(recent_history):
            user_msg = recent_history[i]["content"][:300]
            assistant_msg = recent_history[i + 1]["content"][:300]
            context_lines.append(f"Question précédente: {user_msg}")
            context_lines.append(f"Réponse: {assistant_msg}")

    context_str = "\n".join(context_lines)

    # Prompt de reformulation
    reformulation_prompt = f"""Tu es un assistant qui reformule des questions pour les rendre autonomes.

CONTEXTE DE LA CONVERSATION:
{context_str}

NOUVELLE QUESTION (contient des références au contexte):
{current_question}

TÂCHE:
Reformule la nouvelle question pour qu'elle soit complète et compréhensible SANS le contexte ci-dessus.
Remplace les références (celle, celui, ça, ce, etc.) par les termes explicites du contexte.

RÈGLES:
- Réponds UNIQUEMENT avec la question reformulée
- Pas d'explications, pas de préambule
- Garde le même sens et la même intention
- Reste concis

Question reformulée:"""

    try:
        # Appel API Mistral direct pour la reformulation
        from utils.mistral_provider import get_mistral_model

        model = get_mistral_model()
        api_url = model.api_url.rstrip('/')

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{api_url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {model.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model.model_name,
                    "messages": [{"role": "user", "content": reformulation_prompt}],
                    "temperature": 0.3,
                    "max_tokens": 200
                }
            )
            response.raise_for_status()
            result = response.json()

            reformulated = result["choices"][0]["message"]["content"].strip()
            logger.info(f"✅ Question reformulée: '{current_question}' → '{reformulated}'")

            return reformulated

    except Exception as e:
        logger.warning(f"⚠️ Erreur lors de la reformulation: {e}")
        logger.info(f"🔄 Fallback: utilisation de la question originale")
        return current_question


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

        global _current_request_sources

        # Initialiser les sources pour cette requête
        _current_request_sources = []
        sources = []

        # Pour Chocolatine : recherche manuelle + injection dans le prompt
        if provider == "chocolatine":
            # Faire la recherche avec notre tool local (stocke les sources dans la variable globale)
            search_results = await search_knowledge_base_tool(message, limit=5)
            # Récupérer les sources stockées par le tool
            sources = _current_request_sources.copy()

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
            # Mistral sans tools: faire recherche manuelle et injecter contexte (comme Chocolatine)
            logger.info(f"🔍 Mistral sans tools: recherche manuelle activée")
            search_results = await search_knowledge_base_tool(message, limit=5)
            sources = _current_request_sources.copy()
            logger.info(f"📚 {len(sources)} sources récupérées (recherche manuelle)")

            system_prompt = f"""Tu es un assistant intelligent.

CONTEXTE DE LA BASE DE CONNAISSANCES:
{search_results}

INSTRUCTIONS:
- Utilise UNIQUEMENT les informations du contexte ci-dessus pour répondre
- Si l'information n'est pas dans le contexte, dis-le clairement
- Réponds en français de manière concise et précise"""

            model = get_mistral_model()
            agent = Agent(model, system_prompt=system_prompt)

        # Pour Mistral avec tools: reformuler la question avec le contexte conversationnel
        # puis envoyer SANS historique pour forcer l'appel du tool
        if provider == "mistral" and use_tools:
            # Reformuler la question pour intégrer les références contextuelles
            reformulated_message = await reformulate_question_with_context(message, history)

            # Envoyer la question reformulée SANS historique pour forcer l'appel du tool
            logger.info(f"🎯 Mistral avec tools: question reformulée envoyée sans historique")
            result = await agent.run(reformulated_message, message_history=[])
        else:
            # Pour Chocolatine et Mistral sans tools: on peut injecter un résumé du contexte
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

            result = await agent.run(enhanced_message, message_history=[])

        # Pour Mistral avec tools, récupérer les sources depuis la variable globale
        # (le tool les a sauvegardées lors de son exécution)
        if provider == "mistral" and use_tools:
            sources = _current_request_sources.copy()
            logger.info(f"📚 Sources récupérées du tool (function calling): {len(sources)} sources")

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

