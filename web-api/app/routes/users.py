"""
Routes de gestion des utilisateurs (réservées aux admins)
"""
from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional
from uuid import UUID
import logging

from ..auth import get_current_admin_user, get_password_hash
from .. import database
from ..models import UserCreate, UserUpdate, UserResponse, UserListResponse, PasswordReset

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/users", tags=["User Management"])


@router.get("", response_model=List[UserListResponse])
async def list_users(
    limit: int = 100,
    offset: int = 0,
    is_active: Optional[bool] = None,
    is_admin: Optional[bool] = None,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Liste tous les utilisateurs avec filtrage optionnel

    Args:
        limit: Nombre maximum de résultats
        offset: Offset pour la pagination
        is_active: Filtrer par statut actif
        is_admin: Filtrer par rôle admin
        current_user: Utilisateur admin courant (dépendance)

    Returns:
        Liste des utilisateurs
    """
    # Construction de la requête avec filtres optionnels
    conditions = []
    params = []
    param_count = 1

    if is_active is not None:
        conditions.append(f"is_active = ${param_count}")
        params.append(is_active)
        param_count += 1

    if is_admin is not None:
        conditions.append(f"is_admin = ${param_count}")
        params.append(is_admin)
        param_count += 1

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    query = f"""
        SELECT id, username, email, first_name, last_name, is_active, is_admin, created_at, last_login
        FROM users
        {where_clause}
        ORDER BY created_at DESC
        LIMIT ${param_count} OFFSET ${param_count + 1}
    """
    params.extend([limit, offset])

    async with database.db_pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
        users = [UserListResponse(**dict(row)) for row in rows]

    logger.info(f"📋 Liste utilisateurs récupérée ({len(users)} résultats) par {current_user.get('username')}")
    return users


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Crée un nouvel utilisateur

    Args:
        user_data: Données du nouvel utilisateur
        current_user: Utilisateur admin courant (dépendance)

    Returns:
        Utilisateur créé

    Raises:
        HTTPException: Si le username existe déjà
    """
    # Vérifier si le username existe déjà
    async with database.db_pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT id FROM users WHERE username = $1",
            user_data.username
        )

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Le nom d'utilisateur '{user_data.username}' existe déjà"
            )

        # Hacher le mot de passe
        hashed_password = get_password_hash(user_data.password)

        # Créer l'utilisateur avec must_change_password=True par défaut
        user = await conn.fetchrow(
            """
            INSERT INTO users (username, email, first_name, last_name, hashed_password, is_active, is_admin, must_change_password)
            VALUES ($1, $2, $3, $4, $5, $6, $7, true)
            RETURNING id, username, email, first_name, last_name, is_active, is_admin, created_at, last_login
            """,
            user_data.username,
            user_data.email,
            user_data.first_name,
            user_data.last_name,
            hashed_password,
            user_data.is_active,
            user_data.is_admin
        )

    logger.info(f"✅ Utilisateur créé: {user['username']} (admin: {user['is_admin']}) par {current_user.get('username')}")
    return UserResponse(**dict(user))


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Récupère les détails d'un utilisateur

    Args:
        user_id: ID de l'utilisateur
        current_user: Utilisateur admin courant (dépendance)

    Returns:
        Détails de l'utilisateur

    Raises:
        HTTPException: Si l'utilisateur n'existe pas
    """
    async with database.db_pool.acquire() as conn:
        user = await conn.fetchrow(
            """
            SELECT id, username, email, first_name, last_name, is_active, is_admin, created_at, last_login
            FROM users
            WHERE id = $1
            """,
            user_id
        )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Utilisateur {user_id} non trouvé"
            )

    return UserResponse(**dict(user))


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    user_data: UserUpdate,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Met à jour un utilisateur

    Args:
        user_id: ID de l'utilisateur
        user_data: Données à mettre à jour
        current_user: Utilisateur admin courant (dépendance)

    Returns:
        Utilisateur mis à jour

    Raises:
        HTTPException: Si l'utilisateur n'existe pas
    """
    # Construction de la requête de mise à jour dynamique
    updates = []
    values = []
    param_count = 1

    if user_data.email is not None:
        updates.append(f"email = ${param_count}")
        values.append(user_data.email)
        param_count += 1

    if user_data.first_name is not None:
        updates.append(f"first_name = ${param_count}")
        values.append(user_data.first_name)
        param_count += 1

    if user_data.last_name is not None:
        updates.append(f"last_name = ${param_count}")
        values.append(user_data.last_name)
        param_count += 1

    if user_data.is_active is not None:
        updates.append(f"is_active = ${param_count}")
        values.append(user_data.is_active)
        param_count += 1

    if user_data.is_admin is not None:
        updates.append(f"is_admin = ${param_count}")
        values.append(user_data.is_admin)
        param_count += 1

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucune donnée à mettre à jour"
        )

    values.append(user_id)
    query = f"""
        UPDATE users
        SET {', '.join(updates)}
        WHERE id = ${param_count}
        RETURNING id, username, email, first_name, last_name, is_active, is_admin, created_at, last_login
    """

    async with database.db_pool.acquire() as conn:
        user = await conn.fetchrow(query, *values)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Utilisateur {user_id} non trouvé"
            )

    logger.info(f"✏️ Utilisateur modifié: {user['username']} par {current_user.get('username')}")
    return UserResponse(**dict(user))


@router.delete("/{user_id}")
async def delete_user(
    user_id: UUID,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Supprime un utilisateur

    Args:
        user_id: ID de l'utilisateur
        current_user: Utilisateur admin courant (dépendance)

    Returns:
        Message de confirmation

    Raises:
        HTTPException: Si tentative de suppression de soi-même ou utilisateur non trouvé
    """
    # Protection: ne pas se supprimer soi-même
    if str(user_id) == str(current_user.get('id')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vous ne pouvez pas supprimer votre propre compte"
        )

    async with database.db_pool.acquire() as conn:
        # Récupérer le username avant suppression (pour les logs)
        user = await conn.fetchrow(
            "SELECT username FROM users WHERE id = $1",
            user_id
        )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Utilisateur {user_id} non trouvé"
            )

        # Supprimer l'utilisateur
        await conn.execute("DELETE FROM users WHERE id = $1", user_id)

    logger.warning(f"🗑️ Utilisateur supprimé: {user['username']} par {current_user.get('username')}")
    return {"message": f"Utilisateur {user['username']} supprimé avec succès"}


@router.post("/{user_id}/reset-password")
async def reset_user_password(
    user_id: UUID,
    password_data: PasswordReset,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Réinitialise le mot de passe d'un utilisateur

    Args:
        user_id: ID de l'utilisateur
        password_data: Nouveau mot de passe
        current_user: Utilisateur admin courant (dépendance)

    Returns:
        Message de confirmation

    Raises:
        HTTPException: Si l'utilisateur n'existe pas
    """
    # Hacher le nouveau mot de passe
    hashed_password = get_password_hash(password_data.new_password)

    async with database.db_pool.acquire() as conn:
        # Mettre à jour le mot de passe
        result = await conn.fetchrow(
            """
            UPDATE users
            SET hashed_password = $1
            WHERE id = $2
            RETURNING username
            """,
            hashed_password,
            user_id
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Utilisateur {user_id} non trouvé"
            )

    logger.info(f"🔑 Mot de passe réinitialisé pour: {result['username']} par {current_user.get('username')}")
    return {"message": f"Mot de passe réinitialisé pour {result['username']}"}
