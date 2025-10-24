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
from .routes import admin
from .routes import images
from .routes import users

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration Mistral API
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
MISTRAL_MODEL_NAME = os.getenv("MISTRAL_MODEL_NAME", "mistral-small-latest")

# Variables globales pour stocker le contexte de la requête en cours
# Plus fiables que ContextVar qui peuvent être perdus dans les appels async de PydanticAI
# Note: Pas de problème de concurrence car FastAPI traite les requêtes séquentiellement avec async
_current_request_sources: List[dict] = []
_current_conversation_id: Optional[UUID] = None
_current_reranking_enabled: Optional[bool] = None

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
app.include_router(admin.router)
app.include_router(images.router, prefix="/api", tags=["images"])
app.include_router(users.router)


# ============================================================================
# Event Handlers
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialisation au démarrage"""
    logger.info("🚀 Démarrage de l'API RAGFab...")
    await initialize_database()

    # Créer le répertoire d'uploads et images
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(os.path.join(settings.UPLOAD_DIR, "images"), exist_ok=True)

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
    include_archived: bool = False,
    current_user: dict = Depends(get_current_user)
):
    """Liste les conversations de l'utilisateur courant"""
    async with database.db_pool.acquire() as conn:
        query = """
            SELECT * FROM conversation_stats
            WHERE user_id = $1
            AND ($4 = true OR archived = false)
            ORDER BY updated_at DESC
            LIMIT $2 OFFSET $3
        """
        rows = await conn.fetch(query, current_user['id'], limit, offset, include_archived)
        return [ConversationWithStats(**dict(row)) for row in rows]


@app.post("/api/conversations", response_model=Conversation)
async def create_conversation(
    request: ConversationCreate,
    current_user: dict = Depends(get_current_user)
):
    """Crée une nouvelle conversation liée à l'utilisateur courant"""

    # Si reranking_enabled n'est pas spécifié, utiliser la variable d'environnement
    reranking_enabled = request.reranking_enabled
    if reranking_enabled is None:
        reranking_enabled = os.getenv("RERANKER_ENABLED", "false").lower() == "true"

    # Logs de débogage pour diagnostiquer le problème du toggle
    logger.info(f"🎚️ RERANKER_ENABLED env var: {os.getenv('RERANKER_ENABLED')}")
    logger.info(f"🎚️ request.reranking_enabled: {request.reranking_enabled}")
    logger.info(f"🎚️ Final reranking_enabled value: {reranking_enabled}")

    async with database.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO conversations (title, provider, use_tools, reranking_enabled, user_id)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING *
            """,
            request.title, request.provider, request.use_tools, reranking_enabled, current_user['id']
        )
        return Conversation(**dict(row))


@app.get("/api/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(
    conversation_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Récupère une conversation appartenant à l'utilisateur courant"""
    async with database.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM conversations WHERE id = $1 AND user_id = $2",
            conversation_id, current_user['id']
        )
        if not row:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return Conversation(**dict(row))


@app.patch("/api/conversations/{conversation_id}", response_model=Conversation)
async def update_conversation(
    conversation_id: UUID,
    request: ConversationUpdate,
    current_user: dict = Depends(get_current_user)
):
    """
    Met à jour une conversation appartenant à l'utilisateur courant

    Le champ reranking_enabled permet de contrôler le reranking par conversation :
    - None (null) : Utilise la variable d'environnement RERANKER_ENABLED
    - True : Active le reranking pour cette conversation
    - False : Désactive le reranking pour cette conversation
    """
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

    # Support explicite pour reranking_enabled (y compris None pour reset)
    if "reranking_enabled" in request.model_dump(exclude_unset=True):
        updates.append(f"reranking_enabled = ${param_count}")
        values.append(request.reranking_enabled)
        param_count += 1

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    values.extend([conversation_id, current_user['id']])
    query = f"""
        UPDATE conversations
        SET {', '.join(updates)}
        WHERE id = ${param_count} AND user_id = ${param_count + 1}
        RETURNING *
    """

    async with database.db_pool.acquire() as conn:
        row = await conn.fetchrow(query, *values)
        if not row:
            raise HTTPException(status_code=404, detail="Conversation not found")

        logger.info(f"📝 Conversation {conversation_id} updated by user {current_user['username']}")
        return Conversation(**dict(row))


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Supprime une conversation appartenant à l'utilisateur courant"""
    async with database.db_pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM conversations WHERE id = $1 AND user_id = $2",
            conversation_id, current_user['id']
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
    offset: int = 0,
    current_user: dict = Depends(get_current_user)
):
    """Récupère les messages d'une conversation appartenant à l'utilisateur"""
    async with database.db_pool.acquire() as conn:
        # Vérifier que la conversation appartient à l'utilisateur
        conversation = await conn.fetchrow(
            "SELECT id FROM conversations WHERE id = $1 AND user_id = $2",
            conversation_id, current_user['id']
        )
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

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


async def generate_conversation_title(user_message: str) -> str:
    """
    Génère un titre court et descriptif pour une conversation basé sur le premier message.

    Args:
        user_message: Le premier message de l'utilisateur

    Returns:
        Un titre court (max 50 caractères) ou fallback sur les premiers mots
    """
    try:
        from .utils.generic_llm_provider import get_generic_llm_model
        from pydantic_ai.messages import ModelRequest, UserPromptPart

        # Prompt optimisé pour génération rapide
        prompt = f"""Génère un titre court et descriptif (maximum 50 caractères) pour une conversation basée sur cette question.
Le titre doit être en français, sans guillemets, et capturer l'essence de la question.

Question : {user_message}

Titre :"""

        logger.info("🎯 Génération du titre de conversation avec LLM")
        model = get_generic_llm_model()

        # Appel simple sans agent (plus rapide) avec timeout court
        response, _ = await asyncio.wait_for(
            model.request([ModelRequest(parts=[UserPromptPart(content=prompt)])]),
            timeout=10.0
        )

        # Extraire le texte de la réponse
        title = ""
        for part in response.parts:
            if hasattr(part, 'content'):
                title += part.content

        title = title.strip()

        # Nettoyer et limiter
        title = title.replace('"', '').replace("'", '').replace('\n', ' ').strip()
        if len(title) > 50:
            title = title[:47] + "..."

        result = title if title else user_message[:50]
        logger.info(f"✅ Titre généré : {result}")
        return result

    except asyncio.TimeoutError:
        logger.warning("⏱️ Timeout génération titre, fallback sur message")
        return user_message[:50] + ("..." if len(user_message) > 50 else "")
    except Exception as e:
        logger.warning(f"⚠️ Échec génération titre, fallback sur message: {e}")
        # Fallback : premiers mots du message
        return user_message[:50] + ("..." if len(user_message) > 50 else "")


@app.post("/api/chat", response_model=ChatResponse)
@limiter.limit("20/minute")  # Max 20 messages per minute
async def send_message(
    request: Request,
    chat_request: ChatRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Envoie un message et obtient une réponse du RAG agent

    Cette route:
    1. Vérifie que la conversation appartient à l'utilisateur
    2. Crée le message utilisateur
    3. Récupère l'historique de la conversation
    4. Exécute le RAG agent avec le provider approprié
    5. Sauvegarde la réponse
    6. Retourne le tout
    """
    # Récupérer et vérifier la conversation
    async with database.db_pool.acquire() as conn:
        conversation = await conn.fetchrow(
            "SELECT * FROM conversations WHERE id = $1 AND user_id = $2",
            chat_request.conversation_id, current_user['id']
        )
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

    # Déterminer le provider à utiliser
    provider = chat_request.provider or conversation["provider"]
    use_tools = chat_request.use_tools if chat_request.use_tools is not None else conversation["use_tools"]
    reranking_enabled = chat_request.reranking_enabled if chat_request.reranking_enabled is not None else conversation.get("reranking_enabled")

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

    # Générer automatiquement le titre si c'est le premier message
    if conversation['title'] == 'Nouvelle conversation':
        async with database.db_pool.acquire() as conn:
            # Vérifier que c'est vraiment le premier message (hors message actuel)
            message_count = await conn.fetchval(
                "SELECT COUNT(*) FROM messages WHERE conversation_id = $1 AND id != $2",
                chat_request.conversation_id, user_message['id']
            )

            if message_count == 0:
                logger.info("🎯 Premier message détecté, génération automatique du titre")
                new_title = await generate_conversation_title(chat_request.message)

                # Mettre à jour le titre de la conversation
                await conn.execute(
                    "UPDATE conversations SET title = $1 WHERE id = $2",
                    new_title, chat_request.conversation_id
                )

                logger.info(f"✅ Titre de conversation mis à jour : '{new_title}'")

                # Mettre à jour l'objet conversation pour la réponse
                conversation = await conn.fetchrow(
                    "SELECT * FROM conversations WHERE id = $1",
                    chat_request.conversation_id
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
            use_tools=use_tools,
            conversation_id=chat_request.conversation_id,
            reranking_enabled=reranking_enabled
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

    # 🆕 DÉTECTER TOPIC SHIFT POUR SUGGESTION (optionnel, non-bloquant)
    topic_shift_suggestion = None
    try:
        from .conversation_context import detect_topic_shift

        conversation_context = assistant_response.get("conversation_context")

        # Détecter seulement s'il y a déjà au moins 2 échanges
        if conversation_context and len(conversation_context.get("conversation_flow", [])) >= 2:
            # Préparer le prochain message hypothétique (on ne sait pas encore ce que l'utilisateur va demander)
            # Cette détection sera plus utile si on l'implémente côté frontend au moment où l'utilisateur tape
            # Pour l'instant, on peut retourner le contexte actuel pour que le frontend puisse faire la détection
            topic_shift_suggestion = {
                "current_topic": conversation_context.get("current_topic"),
                "exchange_count": len(conversation_context.get("conversation_flow", [])),
                "message": "Le sujet de la conversation pourrait changer. Voulez-vous créer une nouvelle conversation ?"
            }
            logger.info(f"📊 Topic actuel: {conversation_context.get('current_topic')}")

    except Exception as e:
        logger.warning(f"⚠️ Erreur détection topic shift: {e}")

    # Retourner la réponse complète
    # Décoder les champs JSON depuis la base de données
    assistant_dict = dict(assistant_message)
    if assistant_dict.get('sources') and isinstance(assistant_dict['sources'], str):
        assistant_dict['sources'] = json.loads(assistant_dict['sources'])
    if assistant_dict.get('token_usage') and isinstance(assistant_dict['token_usage'], str):
        assistant_dict['token_usage'] = json.loads(assistant_dict['token_usage'])

    response_data = {
        "user_message": MessageResponse(**dict(user_message), rating=None),
        "assistant_message": MessageResponse(**assistant_dict, rating=None),
        "conversation": Conversation(**dict(conversation))
    }

    # Ajouter suggestion topic shift si détectée (optionnel, le frontend peut l'ignorer)
    if topic_shift_suggestion:
        response_data["topic_shift_suggestion"] = topic_shift_suggestion

    return ChatResponse(**response_data)


@app.post("/api/messages/{message_id}/regenerate", response_model=MessageResponse)
async def regenerate_message(
    message_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Régénère une réponse assistant pour une conversation de l'utilisateur"""
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

        # Récupérer et vérifier la conversation
        conversation = await conn.fetchrow(
            "SELECT * FROM conversations WHERE id = $1 AND user_id = $2",
            original["conversation_id"], current_user['id']
        )
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

    # Exécuter le RAG agent à nouveau
    try:
        assistant_response = await execute_rag_agent(
            message=user_msg["content"],
            history=[],  # TODO: Récupérer l'historique correct
            provider=conversation["provider"],
            use_tools=conversation["use_tools"],
            conversation_id=original["conversation_id"]
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
async def rate_message(
    message_id: UUID,
    request: RatingCreate,
    current_user: dict = Depends(get_current_user)
):
    """Note un message d'une conversation de l'utilisateur"""
    async with database.db_pool.acquire() as conn:
        # Vérifier que le message existe et appartient à une conversation de l'utilisateur
        message = await conn.fetchrow(
            """
            SELECT m.id
            FROM messages m
            JOIN conversations c ON m.conversation_id = c.id
            WHERE m.id = $1 AND c.user_id = $2
            """,
            message_id, current_user['id']
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
    request: ExportRequest,
    current_user: dict = Depends(get_current_user)
):
    """Exporte une conversation de l'utilisateur en Markdown ou PDF"""
    # Récupérer et vérifier la conversation
    async with database.db_pool.acquire() as conn:
        conversation = await conn.fetchrow(
            "SELECT * FROM conversations WHERE id = $1 AND user_id = $2",
            conversation_id, current_user['id']
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


async def rerank_results(query: str, results: List[dict]) -> List[dict]:
    """
    Rerank les résultats de recherche vectorielle pour améliorer la pertinence.

    Args:
        query: La question de l'utilisateur
        results: Liste des résultats de la recherche vectorielle

    Returns:
        Liste des résultats reranked (triés par pertinence)
    """
    reranker_url = os.getenv("RERANKER_API_URL", "http://reranker:8002")

    try:
        # Préparer les documents pour le reranking
        documents = []
        for row in results:
            documents.append({
                "chunk_id": str(row["chunk_id"]),
                "document_id": str(row["document_id"]),
                "document_title": row["document_title"],
                "document_source": row["document_source"],
                "chunk_index": row["chunk_index"],
                "content": row["content"],
                "similarity": float(row["similarity"])
            })

        # Appeler le service de reranking
        return_k = int(os.getenv("RERANKER_RETURN_K", "5"))
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{reranker_url}/rerank",
                json={
                    "query": query,
                    "documents": documents,
                    "top_k": return_k
                },
                timeout=60.0
            )
            response.raise_for_status()
            reranked_data = response.json()

        logger.info(f"✅ Reranking effectué en {reranked_data['processing_time']:.3f}s, "
                   f"{reranked_data['count']} documents retournés")

        return reranked_data["documents"]

    except Exception as e:
        logger.warning(f"⚠️ Erreur lors du reranking (fallback vers vector search): {e}")
        # Fallback gracieux : retourner les résultats originaux
        return [
            {
                "chunk_id": str(row["chunk_id"]),
                "document_id": str(row["document_id"]),
                "document_title": row["document_title"],
                "document_source": row["document_source"],
                "chunk_index": row["chunk_index"],
                "content": row["content"],
                "similarity": float(row["similarity"])
            }
            for row in results[:int(os.getenv("RERANKER_RETURN_K", "5"))]
        ]


def _build_contextualized_response(
    document_title: str,
    main_content: str,
    adjacent_info: dict,
    images: list,
    use_adjacent_chunks: bool
) -> str:
    """
    Construit une réponse enrichie avec contexte adjacent et images.

    Args:
        document_title: Titre du document source
        main_content: Contenu principal du chunk
        adjacent_info: Dict avec prev_content, next_content, section_hierarchy, heading_context
        images: Liste des images associées
        use_adjacent_chunks: Si True, inclure prev/next chunks

    Returns:
        Réponse formatée pour le LLM avec contexte enrichi
    """
    parts = []

    # En-tête avec source et hiérarchie de section
    header = f"[Source: {document_title}]"

    # Ajouter hiérarchie de section si disponible
    section_hierarchy = adjacent_info.get("section_hierarchy")
    if section_hierarchy and isinstance(section_hierarchy, list) and len(section_hierarchy) > 0:
        section_path = " > ".join(section_hierarchy)
        header += f"\n[Section: {section_path}]"

    # Ajouter heading context si disponible
    heading_context = adjacent_info.get("heading_context")
    if heading_context:
        header += f"\n[Titre: {heading_context}]"

    parts.append(header)

    # Contexte précédent (si disponible et activé)
    if use_adjacent_chunks and adjacent_info.get("prev_content"):
        prev_preview = adjacent_info["prev_content"][:150]
        if len(adjacent_info["prev_content"]) > 150:
            prev_preview += "..."
        parts.append(f"\n📄 Contexte précédent:\n{prev_preview}\n")

    # Contenu principal (TOUJOURS inclus)
    parts.append(f"\n📌 Contenu principal:\n{main_content}\n")

    # Contexte suivant (si disponible et activé)
    if use_adjacent_chunks and adjacent_info.get("next_content"):
        next_preview = adjacent_info["next_content"][:150]
        if len(adjacent_info["next_content"]) > 150:
            next_preview += "..."
        parts.append(f"\n📄 Contexte suivant:\n{next_preview}\n")

    # Images associées
    if images:
        parts.append(f"\n📷 Images associées ({len(images)}):")
        for img in images:
            if img.get("description"):
                parts.append(f"  - {img['description']}")
            if img.get("ocr_text"):
                ocr_preview = img['ocr_text'][:100]
                if len(img.get("ocr_text", "")) > 100:
                    ocr_preview += "..."
                parts.append(f"    Texte: {ocr_preview}")

    return "\n".join(parts)


async def search_knowledge_base_tool(query: str, limit: int = 5) -> str:
    """
    Tool pour rechercher dans la base de connaissances avec enrichissement contextuel automatique.

    NOUVEAUTÉ (2025-01-24):
    - Enrichit automatiquement les queries courtes/vagues avec le contexte conversationnel
    - Récupère automatiquement les chunks adjacents (prev/next) pour contexte enrichi
    - Combine contexte séquentiel pour améliorer la pertinence des réponses

    Args:
        query: Question de recherche (peut être courte si contexte disponible)
        limit: Nombre maximum de résultats à retourner

    Returns:
        Résultats formatés pour le LLM avec sources, images, et contexte adjacent
    """
    global _current_request_sources, _current_conversation_id, _current_reranking_enabled
    logger.info(f"🔍 Tool search_knowledge_base_tool appelé avec query: {query}")
    try:
        # 🆕 ENRICHISSEMENT AUTOMATIQUE DE LA QUERY SI CONTEXTE DISPONIBLE
        enriched_query = query  # Par défaut, utiliser query originale
        if _current_conversation_id:
            try:
                from .conversation_context import (
                    build_conversation_context,
                    enrich_query_with_context
                )

                # Construire contexte conversationnel
                context = await build_conversation_context(
                    conversation_id=_current_conversation_id,
                    db_pool=database.db_pool,
                    limit=3  # Limité à 3 échanges pour performance
                )

                if context:
                    # Enrichir la query si nécessaire
                    enriched_query = await enrich_query_with_context(query, context)

                    if enriched_query != query:
                        logger.info(f"🔧 Query enrichie: '{query}' → '{enriched_query}'")

            except Exception as e:
                logger.warning(f"⚠️ Erreur enrichissement query: {e}, utilisation query originale")
                enriched_query = query
        # Déterminer si le reranking est activé (priorité: request > conversation > env var)
        reranker_enabled = os.getenv("RERANKER_ENABLED", "false").lower() == "true"

        # Priorité 1: Valeur passée explicitement dans la requête via variable globale
        if _current_reranking_enabled is not None:
            reranker_enabled = _current_reranking_enabled
            logger.info(f"🎚️ Préférence requête: reranking={reranker_enabled}")
        # Priorité 2: Préférence de la conversation
        elif _current_conversation_id:
            async with database.db_pool.acquire() as conn:
                conv = await conn.fetchrow(
                    "SELECT reranking_enabled FROM conversations WHERE id = $1",
                    _current_conversation_id
                )
                if conv and conv['reranking_enabled'] is not None:
                    # Préférence explicite de la conversation (True ou False)
                    reranker_enabled = conv['reranking_enabled']
                    logger.info(f"🎚️ Préférence conversation {_current_conversation_id}: reranking={reranker_enabled}")
                else:
                    # NULL ou conversation non trouvée: utiliser la variable d'environnement
                    logger.info(f"🌐 Préférence globale (env): reranking={reranker_enabled}")
        else:
            # Priorité 3: Variable d'environnement
            logger.info(f"🌐 Préférence globale (env): reranking={reranker_enabled}")

        # Ajuster la limite de recherche selon le mode
        if reranker_enabled:
            search_limit = int(os.getenv("RERANKER_TOP_K", "20"))
            logger.info(f"🔄 Reranking activé: recherche de {search_limit} candidats")
        else:
            search_limit = limit
            logger.info(f"📊 Reranking désactivé: recherche vectorielle directe (top-{limit})")

        # Générer l'embedding via le service (utilise query enrichie)
        embeddings_url = os.getenv("EMBEDDINGS_API_URL", "http://ragfab-embeddings:8001")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{embeddings_url}/embed",
                json={"text": enriched_query},  # 🆕 Utilise query enrichie
                timeout=30.0
            )
            response.raise_for_status()
            query_embedding = response.json()["embedding"]

        embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"

        # 🆕 RECHERCHE HIÉRARCHIQUE SI PARENT-CHILD ACTIVÉ
        # Déterminer si on utilise la recherche hiérarchique (search enfants → return parents)
        use_hierarchical = os.getenv("USE_PARENT_CHILD_CHUNKS", "false").lower() == "true"

        # Rechercher dans la BD avec fonction match_chunks (supporte mode hiérarchique)
        async with database.db_pool.acquire() as conn:
            if use_hierarchical:
                logger.info("🔍 Recherche hiérarchique: search dans enfants, contexte des parents")
                results = await conn.fetch(
                    """
                    SELECT * FROM match_chunks(
                        $1::vector,
                        $2,
                        0.0,
                        true  -- use_hierarchical=true
                    )
                    """,
                    embedding_str,
                    search_limit
                )
            else:
                logger.info("📊 Recherche standard: tous les chunks")
                results = await conn.fetch(
                    """
                    SELECT * FROM match_chunks(
                        $1::vector,
                        $2,
                        0.0,
                        false  -- use_hierarchical=false
                    )
                    """,
                    embedding_str,
                    search_limit
                )

            # Renommer les colonnes pour compatibilité avec le reste du code
            results = [
                {
                    "chunk_id": row["id"],
                    "content": row["content"],
                    "chunk_index": 0,  # Not used in current flow
                    "metadata": row["metadata"],
                    "document_id": row["document_id"],
                    "document_title": row["document_title"],
                    "document_source": row["document_source"],
                    "similarity": row["similarity"]
                }
                for row in results
            ]

        if not results:
            _current_request_sources = []
            return "Aucune information pertinente trouvée dans la base de connaissances."

        # 🆕 RÉCUPÉRER LES CHUNKS ADJACENTS POUR CONTEXTE ENRICHI
        # Vérifier si la fonctionnalité est activée
        use_adjacent_chunks = os.getenv("USE_ADJACENT_CHUNKS", "true").lower() == "true"
        chunk_adjacent_map = {}  # Map chunk_id -> {prev_content, next_content}

        if use_adjacent_chunks:
            chunk_ids_for_adjacent = [row["chunk_id"] for row in results]
            async with database.db_pool.acquire() as conn:
                adjacent_results = await conn.fetch(
                    """
                    SELECT
                        c.id as chunk_id,
                        prev_c.content as prev_content,
                        next_c.content as next_content,
                        c.section_hierarchy,
                        c.heading_context
                    FROM chunks c
                    LEFT JOIN chunks prev_c ON c.prev_chunk_id = prev_c.id
                    LEFT JOIN chunks next_c ON c.next_chunk_id = next_c.id
                    WHERE c.id = ANY($1::uuid[])
                    """,
                    chunk_ids_for_adjacent
                )

                for adj_row in adjacent_results:
                    chunk_adjacent_map[str(adj_row["chunk_id"])] = {
                        "prev_content": adj_row["prev_content"],
                        "next_content": adj_row["next_content"],
                        "section_hierarchy": adj_row["section_hierarchy"],
                        "heading_context": adj_row["heading_context"]
                    }

                logger.info(f"📚 Chunks adjacents récupérés pour {len(chunk_adjacent_map)} résultats")

        # Récupérer les images pour tous les chunks trouvés
        chunk_ids = [str(row["chunk_id"]) for row in results]
        chunk_images_map = {}  # Map chunk_id -> list of images

        if chunk_ids:
            async with database.db_pool.acquire() as conn:
                image_rows = await conn.fetch(
                    """
                    SELECT
                        chunk_id, id as image_id, page_number, position,
                        description, ocr_text, image_base64
                    FROM document_images
                    WHERE chunk_id = ANY($1::uuid[])
                    ORDER BY page_number, (position->>'y')::float
                    """,
                    chunk_ids
                )

                for img_row in image_rows:
                    chunk_id = str(img_row["chunk_id"])
                    if chunk_id not in chunk_images_map:
                        chunk_images_map[chunk_id] = []

                    chunk_images_map[chunk_id].append({
                        "id": str(img_row["image_id"]),
                        "page_number": img_row["page_number"],
                        "position": json.loads(img_row["position"]) if img_row["position"] else {},
                        "description": img_row["description"],
                        "ocr_text": img_row["ocr_text"],
                        "image_base64": img_row["image_base64"]
                    })

        # Si reranking activé, appliquer le reranking
        if reranker_enabled:
            logger.info(f"🎯 Application du reranking sur {len(results)} candidats")
            reranked_docs = await rerank_results(enriched_query, results)  # 🆕 Utilise query enrichie

            # Stocker les sources avec métadonnées + images pour le frontend
            sources = []
            response_parts = []
            for doc in reranked_docs:
                chunk_id = doc["chunk_id"]
                images = chunk_images_map.get(chunk_id, [])

                # Check if this is a synthetic image chunk
                metadata = doc.get("metadata", {}) or {}
                is_image_chunk = metadata.get("is_image_chunk", False) if isinstance(metadata, dict) else False

                sources.append({
                    "chunk_id": chunk_id,
                    "document_id": doc["document_id"],
                    "document_title": doc["document_title"],
                    "document_source": doc["document_source"],
                    "chunk_index": doc["chunk_index"],
                    "content": doc["content"][:200] + "..." if len(doc["content"]) > 200 else doc["content"],
                    "similarity": doc["similarity"],
                    "images": images,  # Include associated images
                    "is_image_chunk": is_image_chunk  # Flag to identify synthetic image chunks
                })

                # 🆕 Build response with adjacent chunks context
                adjacent_info = chunk_adjacent_map.get(chunk_id, {})
                response_part = _build_contextualized_response(
                    doc['document_title'],
                    doc['content'],
                    adjacent_info,
                    images,
                    use_adjacent_chunks
                )

                response_parts.append(response_part)
        else:
            # Mode normal sans reranking
            sources = []
            response_parts = []
            for row in results:
                chunk_id = str(row["chunk_id"])
                images = chunk_images_map.get(chunk_id, [])

                # Check if this is a synthetic image chunk
                metadata = row.get("metadata", {}) or {}
                is_image_chunk = metadata.get("is_image_chunk", False) if isinstance(metadata, dict) else False

                sources.append({
                    "chunk_id": chunk_id,
                    "document_id": str(row["document_id"]),
                    "document_title": row["document_title"],
                    "document_source": row["document_source"],
                    "chunk_index": row["chunk_index"],
                    "content": row["content"][:200] + "..." if len(row["content"]) > 200 else row["content"],
                    "similarity": float(row["similarity"]),
                    "images": images,  # Include associated images
                    "is_image_chunk": is_image_chunk  # Flag to identify synthetic image chunks
                })

                # 🆕 Build response with adjacent chunks context
                adjacent_info = chunk_adjacent_map.get(chunk_id, {})
                response_part = _build_contextualized_response(
                    row['document_title'],
                    row['content'],
                    adjacent_info,
                    images,
                    use_adjacent_chunks
                )

                response_parts.append(response_part)

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
    # On se concentre sur les vrais pronoms de référence, pas les articles génériques
    question_lower = current_question.lower()
    words = question_lower.split()

    # Références fortes qui indiquent presque toujours un contexte
    strong_references = ["celle", "celui", "celles", "ceux", "celle-ci", "celui-ci"]

    # Références moyennes qui dépendent du contexte
    medium_references = ["ça", "cela", "ce", "cette", "ces"]

    # Pronoms qui sont des références si en début de question
    pronouns_at_start = ["il", "elle", "ils", "elles", "y", "en"]

    has_strong_reference = any(ref in words for ref in strong_references)
    has_medium_reference = any(ref in words for ref in medium_references)
    has_pronoun_at_start = len(words) > 0 and words[0] in pronouns_at_start

    # Questions typiques qui commencent par une référence
    starts_with_reference = question_lower.startswith(("et celle", "et celui", "et ça", "et ce", "et cette"))

    has_reference = has_strong_reference or starts_with_reference or (has_medium_reference and len(words) < 8) or has_pronoun_at_start

    if not has_reference:
        logger.info(f"🔄 Pas de reformulation nécessaire (pas de référence contextuelle détectée)")
        return current_question

    logger.info(f"🔄 Reformulation nécessaire (référence contextuelle détectée: '{current_question}')")

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
        # Appel API LLM générique pour la reformulation
        from app.utils.generic_llm_provider import get_generic_llm_model

        model = get_generic_llm_model()
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


def build_tool_system_prompt_with_json() -> str:
    """
    Construit un system prompt renforcé incluant la définition JSON explicite des tools.
    Cette double approche (API tool_choice + JSON dans le prompt) maximise la fiabilité
    du function calling en donnant au LLM une compréhension claire de ce qui est attendu.
    """
    tool_definition = {
        "type": "function",
        "function": {
            "name": "search_knowledge_base_tool",
            "description": (
                "Recherche sémantique dans la base de connaissances documentaire pour trouver les informations "
                "pertinentes qui permettront de répondre à la question de l'utilisateur. Cet outil effectue une "
                "recherche vectorielle parmi tous les documents ingérés (PDF, DOCX, MD, TXT, HTML) et retourne "
                "les passages les plus pertinents avec leurs métadonnées (titre du document, source, page). "
                "Utilise obligatoirement cet outil dès qu'une question porte sur des informations contenues dans "
                "des documents (politique interne, rapport, contrat, documentation technique, etc.). "
                "Le système applique automatiquement un reranking pour améliorer la pertinence des résultats si activé, "
                "et enrichit les résultats avec les descriptions d'images extraites par VLM."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "La question ou requête de recherche à utiliser pour trouver les informations pertinentes "
                            "dans la base de connaissances. Doit être une question claire et précise, idéalement "
                            "reformulée pour être autonome (sans dépendre du contexte conversationnel). "
                            "Exemples : 'Quelle est la politique de télétravail ?' ou "
                            "'Quels sont les effets secondaires du médicament XYZ ?'"
                        )
                    },
                    "limit": {
                        "type": "integer",
                        "description": (
                            "Nombre maximum de passages à retourner (par défaut: 5). Si le reranking est activé, "
                            "ce paramètre est automatiquement ajusté (20 candidats recherchés, 5 finaux retournés après reranking)."
                        ),
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        }
    }

    prompt = f"""Tu es un assistant qui répond UNIQUEMENT en utilisant une base de connaissances documentaire.

OUTIL DISPONIBLE - DÉFINITION COMPLÈTE :
{json.dumps([tool_definition], indent=2, ensure_ascii=False)}

EXEMPLE D'UTILISATION CORRECTE :
Question utilisateur: "Quelle est la politique de télétravail ?"
→ ÉTAPE 1 - APPEL OBLIGATOIRE: search_knowledge_base_tool(query="Quelle est la politique de télétravail ?")
→ ÉTAPE 2 - RÉCEPTION: [Résultats de la base de connaissances avec sources]
→ ÉTAPE 3 - RÉPONSE: [Synthèse basée UNIQUEMENT sur les résultats de l'outil]

RÈGLES ABSOLUES - AUCUNE EXCEPTION :
1. Pour CHAQUE question de l'utilisateur, tu DOIS OBLIGATOIREMENT appeler l'outil 'search_knowledge_base_tool' AVANT de répondre
2. Tu ne peux répondre QU'avec les informations retournées par l'outil - JAMAIS avec tes connaissances générales
3. Si l'outil ne retourne aucune information pertinente, tu dois dire : "Je n'ai pas trouvé cette information dans la base de connaissances"
4. Ne cite PAS les sources dans ta réponse (pas de [Source: ...]) car elles sont affichées séparément
5. Même si tu penses connaître la réponse, tu DOIS d'abord chercher dans la base de connaissances

COMPORTEMENTS INTERDITS :
❌ Répondre sans avoir appelé l'outil de recherche
❌ Utiliser tes connaissances générales ou pré-entraînées
❌ Inventer ou supposer des informations
❌ Répondre de manière générique
❌ Ajouter [Source: ...] dans la réponse
❌ Utiliser une autre langue que le français

LANGUE DE RÉPONSE - RÈGLE STRICTE :
🇫🇷 Tu DOIS répondre UNIQUEMENT et EXCLUSIVEMENT en français.
🚫 NE PAS utiliser d'autres langues (anglais, chinois, espagnol, etc.)
🚫 Si tu ne peux pas répondre en français, dis "Je ne peux pas répondre à cette question"
✅ Chaque mot, chaque phrase, chaque explication doit être en français

Réponds en français de manière concise en te basant UNIQUEMENT sur les résultats de recherche."""

    return prompt


async def execute_rag_agent(
    message: str,
    history: List[dict],
    provider: str,
    use_tools: bool,
    conversation_id: Optional[UUID] = None,
    reranking_enabled: Optional[bool] = None
) -> dict:
    """
    Exécute le RAG agent avec contexte conversationnel intelligent.

    NOUVEAUTÉ (2025-01-24): Contexte conversationnel injecté dans le system prompt
    au lieu de l'historique complet. Permet de maintenir la cohérence conversationnelle
    tout en forçant le function calling à chaque tour.

    Mode tools activé (use_tools=True):
        - Construit contexte conversationnel structuré depuis la DB
        - Utilise le provider générique avec function calling
        - System prompt enrichi avec contexte + JSON explicite des tools
        - Historique vide pour forcer l'appel du tool (mais contexte dans le prompt!)

    Mode tools désactivé (use_tools=False):
        - Injection manuelle du contexte dans le prompt
        - Pas de function calling
    """
    try:
        from pydantic_ai import Agent, RunContext
        from .utils.generic_llm_provider import get_generic_llm_model
        from .conversation_context import (
            build_conversation_context,
            create_contextual_system_prompt,
            enrich_query_with_context
        )

        global _current_request_sources, _current_conversation_id, _current_reranking_enabled

        # Initialiser le contexte pour cette requête
        _current_request_sources = []
        _current_conversation_id = conversation_id
        _current_reranking_enabled = reranking_enabled
        sources = []

        # 🆕 CONSTRUIRE LE CONTEXTE CONVERSATIONNEL DEPUIS LA DB
        conversation_context = None
        if conversation_id:
            logger.info(f"📚 Construction du contexte conversationnel (conv_id={conversation_id})")
            conversation_context = await build_conversation_context(
                conversation_id=conversation_id,
                db_pool=database.db_pool,
                limit=5  # 5 derniers échanges
            )

            if conversation_context:
                logger.info(
                    f"✅ Contexte construit: topic='{conversation_context['current_topic']}', "
                    f"{len(conversation_context['conversation_flow'])} échanges"
                )
            else:
                logger.info(f"📭 Première question de la conversation")

        # Déterminer si on utilise les tools (LLM_USE_TOOLS ou MISTRAL_USE_TOOLS)
        llm_use_tools = os.getenv("LLM_USE_TOOLS", "").lower() == "true"
        mistral_use_tools = os.getenv("RAG_PROVIDER", "mistral") == "mistral" and use_tools
        use_function_calling = llm_use_tools or mistral_use_tools

        if use_function_calling:
            # Mode function calling avec system prompt enrichi
            logger.info(f"🔧 Création agent LLM générique avec function calling")

            model = get_generic_llm_model()

            # 🆕 CRÉER SYSTEM PROMPT CONTEXTUEL (base + contexte conversationnel)
            base_prompt = build_tool_system_prompt_with_json()
            system_prompt = await create_contextual_system_prompt(
                context=conversation_context,
                base_prompt=base_prompt
            )

            logger.info(f"📋 System prompt contextuel généré ({len(system_prompt)} chars)")
            agent = Agent(model, system_prompt=system_prompt, tools=[search_knowledge_base_tool])
            logger.info(f"✅ Agent créé avec {len(agent._function_tools)} tools")
        else:
            # Mode injection manuelle (pas de function calling)
            logger.info(f"🔍 Mode injection manuelle: recherche avant appel LLM")

            # 🆕 ENRICHIR LA QUERY AVEC LE CONTEXTE SI NÉCESSAIRE
            enriched_message = await enrich_query_with_context(message, conversation_context)

            search_results = await search_knowledge_base_tool(enriched_message, limit=5)
            sources = _current_request_sources.copy()
            logger.info(f"📚 {len(sources)} sources récupérées (injection manuelle)")

            system_prompt = f"""Tu es un assistant intelligent.

CONTEXTE DE LA BASE DE CONNAISSANCES:
{search_results}

INSTRUCTIONS:
- Utilise UNIQUEMENT les informations du contexte ci-dessus pour répondre
- Si l'information n'est pas dans le contexte, dis-le clairement
- Réponds en français de manière concise et précise

LANGUE DE RÉPONSE - RÈGLE STRICTE :
🇫🇷 Tu DOIS répondre UNIQUEMENT et EXCLUSIVEMENT en français.
🚫 NE PAS utiliser d'autres langues (anglais, chinois, espagnol, etc.)
🚫 Si tu ne peux pas répondre en français, dis "Je ne peux pas répondre à cette question"
✅ Chaque mot, chaque phrase, chaque explication doit être en français"""

            model = get_generic_llm_model()
            agent = Agent(model, system_prompt=system_prompt)

        # Exécution selon le mode
        if use_function_calling:
            # 🆕 UTILISER ANCIEN SYSTÈME DE REFORMULATION SEULEMENT COMME FALLBACK
            # Le contexte conversationnel dans le system prompt est maintenant la méthode principale
            reformulated_message = await reformulate_question_with_context(message, history)

            # Envoyer la question reformulée SANS historique
            # (Le contexte est déjà dans le system prompt!)
            logger.info(f"🎯 Function calling: question envoyée avec contexte dans system prompt")
            result = await agent.run(reformulated_message, message_history=[])

            # Récupérer les sources depuis la variable globale (le tool les a sauvegardées)
            sources = _current_request_sources.copy()
            logger.info(f"📚 Sources récupérées du tool: {len(sources)} sources")
        else:
            # Mode injection manuelle: on peut injecter un résumé du contexte conversationnel
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
            # Les sources ont déjà été récupérées lors de la recherche manuelle

        # Déterminer le nom du modèle pour le retour
        model_name = os.getenv("LLM_MODEL_NAME") or os.getenv("MISTRAL_MODEL_NAME", "generic-llm")

        return {
            "content": result.data,
            "sources": sources,
            "model_name": model_name,
            "token_usage": None,
            # 🆕 RETOURNER AUSSI LE CONTEXTE POUR DÉTECTION TOPIC SHIFT (optionnel)
            "conversation_context": conversation_context
        }

    except Exception as e:
        logger.error(f"Erreur RAG agent: {e}", exc_info=True)
        return {
            "content": f"Erreur: {str(e)}",
            "sources": [],
            "model_name": provider,
            "token_usage": None,
            "conversation_context": None
        }

