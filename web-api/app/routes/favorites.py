"""
Routes pour la gestion des favoris partagés.

Workflow:
1. User propose une conversation comme favori (POST /api/favorites)
2. Admin voit les favoris en attente (GET /api/favorites/admin/pending)
3. Admin valide/rejette avec édition optionnelle (POST /api/favorites/{id}/validate)
4. Users peuvent rechercher et copier les favoris publiés
"""
from fastapi import APIRouter, HTTPException, Depends, Query, status
from typing import List, Optional
from uuid import UUID
from datetime import datetime
import logging
import httpx
import os

from ..auth import get_current_admin_user, get_current_user
from .. import database
from ..models import (
    FavoriteCreate, FavoriteUpdate, FavoriteValidation,
    FavoriteResponse, FavoriteSearchResult, FavoriteListResponse,
    FavoriteSuggestionResponse, FavoriteCopyResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/favorites", tags=["Favorites"])

# Embeddings service URL
EMBEDDINGS_API_URL = os.getenv("EMBEDDINGS_API_URL", "http://ragfab-embeddings:8001")


# ============================================================================
# Helper Functions
# ============================================================================

async def generate_embedding(text: str) -> Optional[List[float]]:
    """Generate embedding using the external embeddings service."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{EMBEDDINGS_API_URL}/embed",
                json={"text": text},
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()
            return result.get("embedding")
    except Exception as e:
        logger.error(f"Failed to generate embedding: {e}")
    return None


def format_favorite_response(row: dict, include_admin_notes: bool = False) -> FavoriteResponse:
    """Convert a database row to FavoriteResponse."""
    # Parse sources if it's a JSON string
    sources = row.get("original_sources")
    if isinstance(sources, str):
        import json
        try:
            sources = json.loads(sources)
        except (json.JSONDecodeError, TypeError):
            sources = None

    return FavoriteResponse(
        id=row["id"],
        title=row.get("published_title") or row["original_question"][:100],
        question=row.get("published_question") or row["original_question"],
        response=row.get("published_response") or row["original_response"],
        sources=sources,
        status=row["status"],
        proposed_by_username=row.get("proposed_by_username"),
        validated_by_username=row.get("validated_by_username"),
        universe_id=row.get("universe_id"),
        universe_name=row.get("universe_name"),
        universe_slug=row.get("universe_slug"),
        universe_color=row.get("universe_color"),
        view_count=row.get("view_count", 0),
        copy_count=row.get("copy_count", 0),
        created_at=row["created_at"],
        validated_at=row.get("validated_at"),
        last_edited_at=row.get("last_edited_at"),
        rejection_reason=row.get("rejection_reason"),
        admin_notes=row.get("admin_notes") if include_admin_notes else None
    )


# ============================================================================
# User Endpoints
# ============================================================================

@router.post("", response_model=FavoriteResponse, status_code=status.HTTP_201_CREATED)
async def propose_favorite(
    data: FavoriteCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Propose une conversation comme favori partagé.

    Extrait la dernière paire Q&A de la conversation et crée un snapshot.
    Le favori sera en attente de validation par un admin.
    """
    async with database.db_pool.acquire() as conn:
        # Vérifier que la conversation appartient à l'utilisateur
        conv = await conn.fetchrow(
            """
            SELECT id, user_id, universe_id
            FROM conversations
            WHERE id = $1
            """,
            data.conversation_id
        )

        if not conv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation non trouvée"
            )

        if conv["user_id"] != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Vous ne pouvez proposer que vos propres conversations"
            )

        # Récupérer la dernière paire Q&A (user question + assistant response)
        messages = await conn.fetch(
            """
            SELECT role, content, sources
            FROM messages
            WHERE conversation_id = $1
            ORDER BY created_at DESC
            LIMIT 10
            """,
            data.conversation_id
        )

        if len(messages) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La conversation doit avoir au moins une paire question/réponse"
            )

        # Trouver la dernière paire user->assistant
        user_msg = None
        assistant_msg = None

        for msg in messages:
            if msg["role"] == "assistant" and assistant_msg is None:
                assistant_msg = msg
            elif msg["role"] == "user" and assistant_msg is not None and user_msg is None:
                user_msg = msg
                break

        if not user_msg or not assistant_msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Impossible de trouver une paire question/réponse valide"
            )

        # Générer l'embedding de la question
        embedding = await generate_embedding(user_msg["content"])

        # Créer le favori
        row = await conn.fetchrow(
            """
            INSERT INTO shared_favorites (
                original_question, original_response, original_sources,
                source_conversation_id, proposed_by, universe_id,
                question_embedding
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING *
            """,
            user_msg["content"],
            assistant_msg["content"],
            assistant_msg["sources"],
            data.conversation_id,
            current_user["id"],
            conv["universe_id"],
            embedding
        )

        # Récupérer les infos complètes
        result = await conn.fetchrow(
            """
            SELECT sf.*, u.username as proposed_by_username,
                   pu.name as universe_name, pu.slug as universe_slug, pu.color as universe_color
            FROM shared_favorites sf
            LEFT JOIN users u ON sf.proposed_by = u.id
            LEFT JOIN product_universes pu ON sf.universe_id = pu.id
            WHERE sf.id = $1
            """,
            row["id"]
        )

        logger.info(f"Favori proposé par {current_user['username']} depuis conversation {data.conversation_id}")
        return format_favorite_response(dict(result))


@router.get("", response_model=FavoriteListResponse)
async def list_favorites(
    sort_by: str = Query("recent", regex="^(recent|popular)$"),
    universe_id: Optional[UUID] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """
    Liste les favoris publiés.

    - sort_by: "recent" (par date de validation) ou "popular" (par view_count)
    - universe_id: filtrer par univers
    """
    async with database.db_pool.acquire() as conn:
        # Construire la requête
        where_clauses = ["sf.status = 'published'"]
        params = []
        param_idx = 1

        if universe_id:
            where_clauses.append(f"sf.universe_id = ${param_idx}")
            params.append(universe_id)
            param_idx += 1

        where_sql = " AND ".join(where_clauses)
        order_sql = "sf.validated_at DESC" if sort_by == "recent" else "sf.view_count DESC"

        # Compter le total
        count_query = f"""
            SELECT COUNT(*) FROM shared_favorites sf
            WHERE {where_sql}
        """
        total = await conn.fetchval(count_query, *params)

        # Récupérer les favoris
        offset = (page - 1) * page_size
        query = f"""
            SELECT sf.*, u.username as proposed_by_username,
                   pu.name as universe_name, pu.slug as universe_slug, pu.color as universe_color
            FROM shared_favorites sf
            LEFT JOIN users u ON sf.proposed_by = u.id
            LEFT JOIN product_universes pu ON sf.universe_id = pu.id
            WHERE {where_sql}
            ORDER BY {order_sql}
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([page_size, offset])

        rows = await conn.fetch(query, *params)
        favorites = [format_favorite_response(dict(row)) for row in rows]

        total_pages = (total + page_size - 1) // page_size if total > 0 else 1

        return FavoriteListResponse(
            favorites=favorites,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )


@router.get("/search", response_model=List[FavoriteSearchResult])
async def search_favorites(
    q: str = Query(..., min_length=3),
    universe_id: Optional[UUID] = None,
    limit: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(get_current_user)
):
    """
    Recherche sémantique dans les favoris publiés.

    Utilise la similarité cosinus avec les embeddings.
    """
    # Générer l'embedding de la requête
    embedding = await generate_embedding(q)

    if not embedding:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la génération de l'embedding"
        )

    async with database.db_pool.acquire() as conn:
        # Utiliser la fonction match_favorites
        universe_ids = [universe_id] if universe_id else None

        rows = await conn.fetch(
            """
            SELECT * FROM match_favorites($1, $2, 0.0, $3)
            """,
            embedding,
            limit,
            universe_ids
        )

        # Enrichir avec les infos univers
        results = []
        for row in rows:
            universe_info = None
            if row["universe_id"]:
                universe_info = await conn.fetchrow(
                    "SELECT name, color FROM product_universes WHERE id = $1",
                    row["universe_id"]
                )

            results.append(FavoriteSearchResult(
                id=row["id"],
                title=row["title"],
                question=row["question"],
                response=row["response"],
                sources=row["sources"],
                similarity=row["similarity"],
                universe_id=row["universe_id"],
                universe_name=universe_info["name"] if universe_info else None,
                universe_color=universe_info["color"] if universe_info else None,
                view_count=row["view_count"],
                copy_count=row["copy_count"]
            ))

        return results


@router.get("/suggestions", response_model=FavoriteSuggestionResponse)
async def get_suggestions(
    q: str = Query(..., min_length=5),
    universe_ids: Optional[List[UUID]] = Query(None),
    threshold: float = Query(0.85, ge=0.5, le=1.0),
    limit: int = Query(3, ge=1, le=10),
    current_user: dict = Depends(get_current_user)
):
    """
    Vérifie si des favoris similaires existent (pré-RAG).

    Utilisé avant de lancer une recherche RAG pour proposer des solutions existantes.
    Seuil par défaut: 0.85 (très similaire).
    """
    # Générer l'embedding de la question
    embedding = await generate_embedding(q)

    if not embedding:
        return FavoriteSuggestionResponse(
            has_suggestions=False,
            suggestions=[],
            message=None
        )

    async with database.db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM match_favorites($1, $2, $3, $4)
            """,
            embedding,
            limit,
            threshold,
            universe_ids
        )

        if not rows:
            return FavoriteSuggestionResponse(
                has_suggestions=False,
                suggestions=[],
                message=None
            )

        # Enrichir avec les infos univers
        suggestions = []
        for row in rows:
            universe_info = None
            if row["universe_id"]:
                universe_info = await conn.fetchrow(
                    "SELECT name, color FROM product_universes WHERE id = $1",
                    row["universe_id"]
                )

            suggestions.append(FavoriteSearchResult(
                id=row["id"],
                title=row["title"],
                question=row["question"],
                response=row["response"],
                sources=row["sources"],
                similarity=row["similarity"],
                universe_id=row["universe_id"],
                universe_name=universe_info["name"] if universe_info else None,
                universe_color=universe_info["color"] if universe_info else None,
                view_count=row["view_count"],
                copy_count=row["copy_count"]
            ))

        return FavoriteSuggestionResponse(
            has_suggestions=True,
            suggestions=suggestions,
            message="Des solutions similaires existent. Voulez-vous les consulter ?"
        )


@router.get("/{favorite_id}", response_model=FavoriteResponse)
async def get_favorite(
    favorite_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """
    Récupère le détail d'un favori publié.

    Incrémente le compteur de vues.
    """
    async with database.db_pool.acquire() as conn:
        # Incrémenter le compteur de vues
        await conn.execute(
            """
            UPDATE shared_favorites
            SET view_count = view_count + 1
            WHERE id = $1 AND status = 'published'
            """,
            favorite_id
        )

        row = await conn.fetchrow(
            """
            SELECT sf.*, u.username as proposed_by_username,
                   v.username as validated_by_username,
                   pu.name as universe_name, pu.slug as universe_slug, pu.color as universe_color
            FROM shared_favorites sf
            LEFT JOIN users u ON sf.proposed_by = u.id
            LEFT JOIN users v ON sf.validated_by = v.id
            LEFT JOIN product_universes pu ON sf.universe_id = pu.id
            WHERE sf.id = $1 AND sf.status = 'published'
            """,
            favorite_id
        )

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Favori non trouvé ou non publié"
            )

        return format_favorite_response(dict(row))


@router.post("/{favorite_id}/copy", response_model=FavoriteCopyResponse)
async def copy_favorite_to_conversation(
    favorite_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """
    Copie un favori vers une nouvelle conversation de l'utilisateur.

    Crée une nouvelle conversation avec la Q&A du favori.
    """
    async with database.db_pool.acquire() as conn:
        # Récupérer le favori
        fav = await conn.fetchrow(
            """
            SELECT * FROM shared_favorites
            WHERE id = $1 AND status = 'published'
            """,
            favorite_id
        )

        if not fav:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Favori non trouvé ou non publié"
            )

        # Créer la conversation
        question = fav["published_question"] or fav["original_question"]
        response = fav["published_response"] or fav["original_response"]
        title = (fav["published_title"] or question[:50]) + "..."

        conv = await conn.fetchrow(
            """
            INSERT INTO conversations (user_id, title, provider, use_tools, universe_id)
            VALUES ($1, $2, 'mistral', true, $3)
            RETURNING id
            """,
            current_user["id"],
            title,
            fav["universe_id"]
        )

        # Ajouter les messages
        await conn.execute(
            """
            INSERT INTO messages (conversation_id, role, content)
            VALUES ($1, 'user', $2)
            """,
            conv["id"],
            question
        )

        await conn.execute(
            """
            INSERT INTO messages (conversation_id, role, content, sources)
            VALUES ($1, 'assistant', $2, $3)
            """,
            conv["id"],
            response,
            fav["original_sources"]
        )

        # Mettre à jour message_count
        await conn.execute(
            "UPDATE conversations SET message_count = 2 WHERE id = $1",
            conv["id"]
        )

        # Incrémenter le compteur de copies
        await conn.execute(
            "UPDATE shared_favorites SET copy_count = copy_count + 1 WHERE id = $1",
            favorite_id
        )

        logger.info(f"Favori {favorite_id} copié par {current_user['username']} -> conversation {conv['id']}")

        return FavoriteCopyResponse(
            conversation_id=conv["id"],
            message="Favori copié avec succès"
        )


# ============================================================================
# Admin Endpoints
# ============================================================================

@router.get("/admin/pending", response_model=FavoriteListResponse)
async def list_pending_favorites(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Liste les favoris en attente de validation (admin uniquement).
    """
    async with database.db_pool.acquire() as conn:
        # Count total pending
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM shared_favorites WHERE status = 'pending'"
        )

        offset = (page - 1) * page_size
        rows = await conn.fetch(
            """
            SELECT sf.*, u.username as proposed_by_username,
                   pu.name as universe_name, pu.slug as universe_slug, pu.color as universe_color
            FROM shared_favorites sf
            LEFT JOIN users u ON sf.proposed_by = u.id
            LEFT JOIN product_universes pu ON sf.universe_id = pu.id
            WHERE sf.status = 'pending'
            ORDER BY sf.created_at DESC
            LIMIT $1 OFFSET $2
            """,
            page_size, offset
        )

        favorites = [format_favorite_response(dict(row), include_admin_notes=True) for row in rows]
        total_pages = (total + page_size - 1) // page_size if total > 0 else 1

        return FavoriteListResponse(
            favorites=favorites,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )


@router.get("/admin/{favorite_id}", response_model=FavoriteResponse)
async def get_favorite_admin(
    favorite_id: UUID,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Récupère un favori pour l'admin (tous statuts).
    """
    async with database.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT sf.*, u.username as proposed_by_username,
                   v.username as validated_by_username,
                   pu.name as universe_name, pu.slug as universe_slug, pu.color as universe_color
            FROM shared_favorites sf
            LEFT JOIN users u ON sf.proposed_by = u.id
            LEFT JOIN users v ON sf.validated_by = v.id
            LEFT JOIN product_universes pu ON sf.universe_id = pu.id
            WHERE sf.id = $1
            """,
            favorite_id
        )

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Favori non trouvé"
            )

        return format_favorite_response(dict(row), include_admin_notes=True)


@router.patch("/{favorite_id}", response_model=FavoriteResponse)
async def update_favorite(
    favorite_id: UUID,
    data: FavoriteUpdate,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Met à jour un favori (admin uniquement).

    Permet d'éditer le titre, la question et la réponse avant publication.
    """
    updates = []
    values = []
    param_idx = 1

    if data.published_title is not None:
        updates.append(f"published_title = ${param_idx}")
        values.append(data.published_title)
        param_idx += 1

    if data.published_question is not None:
        updates.append(f"published_question = ${param_idx}")
        values.append(data.published_question)
        param_idx += 1

    if data.published_response is not None:
        updates.append(f"published_response = ${param_idx}")
        values.append(data.published_response)
        param_idx += 1

    if data.admin_notes is not None:
        updates.append(f"admin_notes = ${param_idx}")
        values.append(data.admin_notes)
        param_idx += 1

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucune donnée à mettre à jour"
        )

    updates.append(f"last_edited_at = ${param_idx}")
    values.append(datetime.utcnow())
    param_idx += 1

    updates.append(f"last_edited_by = ${param_idx}")
    values.append(current_user["id"])
    param_idx += 1

    values.append(favorite_id)

    async with database.db_pool.acquire() as conn:
        query = f"""
            UPDATE shared_favorites
            SET {', '.join(updates)}
            WHERE id = ${param_idx}
            RETURNING *
        """

        row = await conn.fetchrow(query, *values)

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Favori non trouvé"
            )

        # Récupérer les infos complètes
        result = await conn.fetchrow(
            """
            SELECT sf.*, u.username as proposed_by_username,
                   v.username as validated_by_username,
                   pu.name as universe_name, pu.slug as universe_slug, pu.color as universe_color
            FROM shared_favorites sf
            LEFT JOIN users u ON sf.proposed_by = u.id
            LEFT JOIN users v ON sf.validated_by = v.id
            LEFT JOIN product_universes pu ON sf.universe_id = pu.id
            WHERE sf.id = $1
            """,
            favorite_id
        )

        logger.info(f"Favori {favorite_id} mis à jour par {current_user['username']}")
        return format_favorite_response(dict(result), include_admin_notes=True)


@router.post("/{favorite_id}/validate", response_model=FavoriteResponse)
async def validate_favorite(
    favorite_id: UUID,
    data: FavoriteValidation,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Valide (publie) ou rejette un favori (admin uniquement).

    - action="publish": publie le favori, le rend visible à tous
    - action="reject": rejette le favori avec une raison optionnelle
    """
    async with database.db_pool.acquire() as conn:
        # Vérifier que le favori existe et est en pending
        fav = await conn.fetchrow(
            "SELECT id, status FROM shared_favorites WHERE id = $1",
            favorite_id
        )

        if not fav:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Favori non trouvé"
            )

        if fav["status"] != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Le favori n'est pas en attente (status actuel: {fav['status']})"
            )

        now = datetime.utcnow()

        if data.action == "publish":
            # Publier le favori
            update_fields = {
                "status": "published",
                "validated_by": current_user["id"],
                "validated_at": now
            }

            # Appliquer les éditions optionnelles
            if data.published_title:
                update_fields["published_title"] = data.published_title
            if data.published_question:
                update_fields["published_question"] = data.published_question
            if data.published_response:
                update_fields["published_response"] = data.published_response

            set_clauses = ", ".join(f"{k} = ${i+1}" for i, k in enumerate(update_fields.keys()))
            values = list(update_fields.values()) + [favorite_id]

            await conn.execute(
                f"""
                UPDATE shared_favorites
                SET {set_clauses}
                WHERE id = ${len(update_fields) + 1}
                """,
                *values
            )

            logger.info(f"Favori {favorite_id} publié par {current_user['username']}")

        else:  # reject
            await conn.execute(
                """
                UPDATE shared_favorites
                SET status = 'rejected',
                    validated_by = $1,
                    validated_at = $2,
                    rejection_reason = $3
                WHERE id = $4
                """,
                current_user["id"],
                now,
                data.rejection_reason,
                favorite_id
            )

            logger.info(f"Favori {favorite_id} rejeté par {current_user['username']}")

        # Retourner le favori mis à jour
        result = await conn.fetchrow(
            """
            SELECT sf.*, u.username as proposed_by_username,
                   v.username as validated_by_username,
                   pu.name as universe_name, pu.slug as universe_slug, pu.color as universe_color
            FROM shared_favorites sf
            LEFT JOIN users u ON sf.proposed_by = u.id
            LEFT JOIN users v ON sf.validated_by = v.id
            LEFT JOIN product_universes pu ON sf.universe_id = pu.id
            WHERE sf.id = $1
            """,
            favorite_id
        )

        return format_favorite_response(dict(result), include_admin_notes=True)


@router.delete("/{favorite_id}")
async def delete_favorite(
    favorite_id: UUID,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Supprime un favori (admin uniquement).
    """
    async with database.db_pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM shared_favorites WHERE id = $1",
            favorite_id
        )

        if result == "DELETE 0":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Favori non trouvé"
            )

        logger.info(f"Favori {favorite_id} supprimé par {current_user['username']}")
        return {"message": "Favori supprimé"}
