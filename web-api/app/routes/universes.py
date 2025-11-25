"""
Routes pour la gestion des univers produits
"""
from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional
from uuid import UUID
import logging

from ..auth import get_current_admin_user, get_current_user
from .. import database
from ..models import (
    ProductUniverse, ProductUniverseCreate, ProductUniverseUpdate, ProductUniverseList,
    UserUniverseAccess, UserUniverseAccessList, UserUniverseAccessCreate,
    SetDefaultUniverseRequest, UserUniverseAccessSimple
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/universes", tags=["Universes"])


# ============================================================================
# Universe CRUD (Admin only)
# ============================================================================

@router.get("", response_model=ProductUniverseList)
async def list_universes(
    include_inactive: bool = False,
    current_user: dict = Depends(get_current_user)
):
    """
    Liste tous les univers produits.

    Par défaut, retourne uniquement les univers actifs.
    Les admins peuvent voir tous les univers avec include_inactive=true.
    """
    async with database.db_pool.acquire() as conn:
        if include_inactive and current_user.get("is_admin"):
            query = """
                SELECT id, name, slug, description, detection_keywords, color, is_active, created_at, updated_at
                FROM product_universes
                ORDER BY name
            """
            rows = await conn.fetch(query)
        else:
            query = """
                SELECT id, name, slug, description, detection_keywords, color, is_active, created_at, updated_at
                FROM product_universes
                WHERE is_active = true
                ORDER BY name
            """
            rows = await conn.fetch(query)

        universes = [ProductUniverse(**dict(row)) for row in rows]
        return ProductUniverseList(universes=universes, total=len(universes))


@router.get("/{universe_id}", response_model=ProductUniverse)
async def get_universe(
    universe_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Recupere un univers par son ID"""
    async with database.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, name, slug, description, detection_keywords, color, is_active, created_at, updated_at
            FROM product_universes
            WHERE id = $1
            """,
            universe_id
        )

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Univers {universe_id} non trouve"
            )

        return ProductUniverse(**dict(row))


@router.post("", response_model=ProductUniverse, status_code=status.HTTP_201_CREATED)
async def create_universe(
    universe_data: ProductUniverseCreate,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Cree un nouvel univers produit (admin uniquement).

    Le slug doit etre unique et en minuscules avec tirets.
    """
    async with database.db_pool.acquire() as conn:
        # Verifier si le slug existe deja
        existing = await conn.fetchrow(
            "SELECT id FROM product_universes WHERE slug = $1",
            universe_data.slug
        )

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Un univers avec le slug '{universe_data.slug}' existe deja"
            )

        # Creer l'univers
        row = await conn.fetchrow(
            """
            INSERT INTO product_universes (name, slug, description, detection_keywords, color, is_active)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id, name, slug, description, detection_keywords, color, is_active, created_at, updated_at
            """,
            universe_data.name,
            universe_data.slug,
            universe_data.description,
            universe_data.detection_keywords,
            universe_data.color,
            universe_data.is_active
        )

        logger.info(f"Univers cree: {universe_data.name} (slug: {universe_data.slug}) par {current_user['username']}")
        return ProductUniverse(**dict(row))


@router.patch("/{universe_id}", response_model=ProductUniverse)
async def update_universe(
    universe_id: UUID,
    universe_data: ProductUniverseUpdate,
    current_user: dict = Depends(get_current_admin_user)
):
    """Met a jour un univers produit (admin uniquement)"""
    updates = []
    values = []
    param_count = 1

    if universe_data.name is not None:
        updates.append(f"name = ${param_count}")
        values.append(universe_data.name)
        param_count += 1

    if universe_data.description is not None:
        updates.append(f"description = ${param_count}")
        values.append(universe_data.description)
        param_count += 1

    if universe_data.detection_keywords is not None:
        updates.append(f"detection_keywords = ${param_count}")
        values.append(universe_data.detection_keywords)
        param_count += 1

    if universe_data.color is not None:
        updates.append(f"color = ${param_count}")
        values.append(universe_data.color)
        param_count += 1

    if universe_data.is_active is not None:
        updates.append(f"is_active = ${param_count}")
        values.append(universe_data.is_active)
        param_count += 1

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucune donnee a mettre a jour"
        )

    values.append(universe_id)
    query = f"""
        UPDATE product_universes
        SET {', '.join(updates)}
        WHERE id = ${param_count}
        RETURNING id, name, slug, description, detection_keywords, color, is_active, created_at, updated_at
    """

    async with database.db_pool.acquire() as conn:
        row = await conn.fetchrow(query, *values)

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Univers {universe_id} non trouve"
            )

        logger.info(f"Univers {universe_id} mis a jour par {current_user['username']}")
        return ProductUniverse(**dict(row))


@router.delete("/{universe_id}")
async def delete_universe(
    universe_id: UUID,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Supprime un univers produit (admin uniquement).

    Attention: Les documents associes auront leur universe_id mis a NULL.
    """
    async with database.db_pool.acquire() as conn:
        # Verifier le nombre de documents associes
        doc_count = await conn.fetchval(
            "SELECT COUNT(*) FROM documents WHERE universe_id = $1",
            universe_id
        )

        if doc_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Impossible de supprimer: {doc_count} documents sont associes a cet univers. Reassignez-les d'abord."
            )

        result = await conn.execute(
            "DELETE FROM product_universes WHERE id = $1",
            universe_id
        )

        if result == "DELETE 0":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Univers {universe_id} non trouve"
            )

        logger.info(f"Univers {universe_id} supprime par {current_user['username']}")
        return {"message": f"Univers {universe_id} supprime"}


# ============================================================================
# User Universe Access Management (Admin only)
# ============================================================================

@router.get("/users/{user_id}/access", response_model=UserUniverseAccessList)
async def get_user_universe_access(
    user_id: UUID,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Liste les acces univers d'un utilisateur (admin uniquement).
    """
    async with database.db_pool.acquire() as conn:
        # Verifier que l'utilisateur existe
        user = await conn.fetchrow(
            "SELECT id, username FROM users WHERE id = $1",
            user_id
        )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Utilisateur {user_id} non trouve"
            )

        # Recuperer les acces via la vue
        rows = await conn.fetch(
            """
            SELECT
                access_id as id,
                user_id,
                universe_id,
                universe_name,
                universe_slug,
                universe_color,
                is_default,
                granted_at,
                granted_by,
                granted_by_username
            FROM user_universes_view
            WHERE user_id = $1
            ORDER BY is_default DESC, universe_name
            """,
            user_id
        )

        accesses = [UserUniverseAccess(**dict(row)) for row in rows]

        return UserUniverseAccessList(
            user_id=user_id,
            username=user["username"],
            accesses=accesses,
            total=len(accesses)
        )


@router.post("/users/{user_id}/access", response_model=UserUniverseAccess, status_code=status.HTTP_201_CREATED)
async def grant_universe_access(
    user_id: UUID,
    access_data: UserUniverseAccessCreate,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Accorde l'acces a un univers pour un utilisateur (admin uniquement).
    """
    async with database.db_pool.acquire() as conn:
        # Verifier que l'utilisateur existe
        user = await conn.fetchrow(
            "SELECT id FROM users WHERE id = $1",
            user_id
        )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Utilisateur {user_id} non trouve"
            )

        # Verifier que l'univers existe
        universe = await conn.fetchrow(
            "SELECT id FROM product_universes WHERE id = $1 AND is_active = true",
            access_data.universe_id
        )

        if not universe:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Univers {access_data.universe_id} non trouve ou inactif"
            )

        try:
            # Creer l'acces
            await conn.execute(
                """
                INSERT INTO user_universe_access (user_id, universe_id, is_default, granted_by)
                VALUES ($1, $2, $3, $4)
                """,
                user_id,
                access_data.universe_id,
                access_data.is_default,
                current_user["id"]
            )
        except Exception as e:
            if "unique" in str(e).lower():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="L'utilisateur a deja acces a cet univers"
                )
            raise

        # Recuperer l'acces cree via la vue
        row = await conn.fetchrow(
            """
            SELECT
                access_id as id,
                user_id,
                universe_id,
                universe_name,
                universe_slug,
                universe_color,
                is_default,
                granted_at,
                granted_by,
                granted_by_username
            FROM user_universes_view
            WHERE user_id = $1 AND universe_id = $2
            """,
            user_id,
            access_data.universe_id
        )

        logger.info(f"Acces univers {access_data.universe_id} accorde a {user_id} par {current_user['username']}")
        return UserUniverseAccess(**dict(row))


@router.delete("/users/{user_id}/access/{universe_id}")
async def revoke_universe_access(
    user_id: UUID,
    universe_id: UUID,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Revoque l'acces a un univers pour un utilisateur (admin uniquement).
    """
    async with database.db_pool.acquire() as conn:
        result = await conn.execute(
            """
            DELETE FROM user_universe_access
            WHERE user_id = $1 AND universe_id = $2
            """,
            user_id,
            universe_id
        )

        if result == "DELETE 0":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Acces non trouve"
            )

        logger.info(f"Acces univers {universe_id} revoque pour {user_id} par {current_user['username']}")
        return {"message": "Acces revoque"}


@router.post("/users/{user_id}/access/{universe_id}/set-default")
async def set_user_default_universe(
    user_id: UUID,
    universe_id: UUID,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Definit l'univers par defaut d'un utilisateur (admin uniquement).

    Le trigger en base s'assure qu'un seul univers est par defaut.
    """
    async with database.db_pool.acquire() as conn:
        # Verifier que l'acces existe
        access = await conn.fetchrow(
            """
            SELECT id FROM user_universe_access
            WHERE user_id = $1 AND universe_id = $2
            """,
            user_id,
            universe_id
        )

        if not access:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="L'utilisateur n'a pas acces a cet univers"
            )

        # Mettre a jour (le trigger gere le reset des autres)
        await conn.execute(
            """
            UPDATE user_universe_access
            SET is_default = true
            WHERE user_id = $1 AND universe_id = $2
            """,
            user_id,
            universe_id
        )

        logger.info(f"Univers {universe_id} defini comme defaut pour {user_id} par {current_user['username']}")
        return {"message": "Univers par defaut mis a jour"}


# ============================================================================
# Current User Universe Access
# ============================================================================

@router.get("/me/access", response_model=List[UserUniverseAccessSimple])
async def get_my_universe_access(
    current_user: dict = Depends(get_current_user)
):
    """
    Liste les univers auxquels l'utilisateur courant a acces.
    """
    async with database.db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                uua.universe_id,
                pu.name as universe_name,
                pu.slug as universe_slug,
                pu.color as universe_color,
                uua.is_default
            FROM user_universe_access uua
            JOIN product_universes pu ON uua.universe_id = pu.id
            WHERE uua.user_id = $1 AND pu.is_active = true
            ORDER BY uua.is_default DESC, pu.name
            """,
            current_user["id"]
        )

        return [UserUniverseAccessSimple(**dict(row)) for row in rows]


@router.post("/me/set-default", response_model=UserUniverseAccessSimple)
async def set_my_default_universe(
    request: SetDefaultUniverseRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Definit l'univers par defaut de l'utilisateur courant.

    L'utilisateur doit avoir acces a cet univers.
    """
    async with database.db_pool.acquire() as conn:
        # Verifier que l'utilisateur a acces a cet univers
        access = await conn.fetchrow(
            """
            SELECT id FROM user_universe_access
            WHERE user_id = $1 AND universe_id = $2
            """,
            current_user["id"],
            request.universe_id
        )

        if not access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Vous n'avez pas acces a cet univers"
            )

        # Mettre a jour (le trigger gere le reset des autres)
        await conn.execute(
            """
            UPDATE user_universe_access
            SET is_default = true
            WHERE user_id = $1 AND universe_id = $2
            """,
            current_user["id"],
            request.universe_id
        )

        # Recuperer l'acces mis a jour
        row = await conn.fetchrow(
            """
            SELECT
                uua.universe_id,
                pu.name as universe_name,
                pu.slug as universe_slug,
                pu.color as universe_color,
                uua.is_default
            FROM user_universe_access uua
            JOIN product_universes pu ON uua.universe_id = pu.id
            WHERE uua.user_id = $1 AND uua.universe_id = $2
            """,
            current_user["id"],
            request.universe_id
        )

        logger.info(f"Univers {request.universe_id} defini comme defaut par {current_user['username']}")
        return UserUniverseAccessSimple(**dict(row))


@router.get("/me/default")
async def get_my_default_universe(
    current_user: dict = Depends(get_current_user)
):
    """
    Retourne l'univers par defaut de l'utilisateur courant.
    """
    async with database.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                uua.universe_id,
                pu.name as universe_name,
                pu.slug as universe_slug,
                pu.color as universe_color,
                uua.is_default
            FROM user_universe_access uua
            JOIN product_universes pu ON uua.universe_id = pu.id
            WHERE uua.user_id = $1 AND uua.is_default = true AND pu.is_active = true
            LIMIT 1
            """,
            current_user["id"]
        )

        if not row:
            # Fallback: premier univers accessible
            row = await conn.fetchrow(
                """
                SELECT
                    uua.universe_id,
                    pu.name as universe_name,
                    pu.slug as universe_slug,
                    pu.color as universe_color,
                    uua.is_default
                FROM user_universe_access uua
                JOIN product_universes pu ON uua.universe_id = pu.id
                WHERE uua.user_id = $1 AND pu.is_active = true
                ORDER BY uua.granted_at
                LIMIT 1
                """,
                current_user["id"]
            )

        if not row:
            return {"default_universe": None}

        return {"default_universe": UserUniverseAccessSimple(**dict(row))}


# ============================================================================
# Document Universe Assignment
# ============================================================================

@router.get("/{universe_id}/documents/count")
async def get_universe_document_count(
    universe_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """
    Retourne le nombre de documents dans un univers.
    """
    async with database.db_pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM documents WHERE universe_id = $1",
            universe_id
        )

        return {"universe_id": str(universe_id), "document_count": count}


@router.post("/{universe_id}/documents/{document_id}/assign")
async def assign_document_to_universe(
    universe_id: UUID,
    document_id: UUID,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Assigne un document a un univers (admin uniquement).
    """
    async with database.db_pool.acquire() as conn:
        # Verifier que l'univers existe
        universe = await conn.fetchrow(
            "SELECT id, name FROM product_universes WHERE id = $1",
            universe_id
        )

        if not universe:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Univers {universe_id} non trouve"
            )

        # Mettre a jour le document
        result = await conn.execute(
            "UPDATE documents SET universe_id = $1 WHERE id = $2",
            universe_id,
            document_id
        )

        if result == "UPDATE 0":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document {document_id} non trouve"
            )

        logger.info(f"Document {document_id} assigne a l'univers {universe['name']} par {current_user['username']}")
        return {"message": f"Document assigne a l'univers {universe['name']}"}


@router.post("/documents/{document_id}/unassign")
async def unassign_document_from_universe(
    document_id: UUID,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Retire un document de son univers (admin uniquement).
    """
    async with database.db_pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE documents SET universe_id = NULL WHERE id = $1",
            document_id
        )

        if result == "UPDATE 0":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document {document_id} non trouve"
            )

        logger.info(f"Document {document_id} retire de son univers par {current_user['username']}")
        return {"message": "Document retire de son univers"}
