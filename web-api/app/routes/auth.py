"""
Routes d'authentification
"""
from fastapi import APIRouter, HTTPException, status, Depends, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from datetime import timedelta
import logging

from ..models import LoginRequest, TokenResponse, User, UserProfileUpdate, PasswordChange
from ..auth import authenticate_user, create_access_token, get_current_user, verify_password, get_password_hash, validate_password_strength
from ..config import settings
from .. import database

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
limiter = Limiter(key_func=get_remote_address)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")  # Max 5 login attempts per minute
async def login(request: Request, login_data: LoginRequest):
    """
    Authentifie un utilisateur et retourne un token JWT

    Args:
        request: FastAPI Request object (for rate limiting)
        login_data: Credentials (username + password)

    Returns:
        Token JWT

    Raises:
        HTTPException: Si les credentials sont invalides
    """
    user = await authenticate_user(login_data.username, login_data.password)

    if not user:
        logger.warning(f"Tentative de connexion échouée pour: {login_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Créer le token
    access_token_expires = timedelta(minutes=settings.JWT_EXPIRATION_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]},
        expires_delta=access_token_expires
    )

    logger.info(f"✅ Connexion réussie pour: {user['username']}")

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.JWT_EXPIRATION_MINUTES * 60  # en secondes
    )


@router.get("/me", response_model=User)
async def get_me(current_user: dict = Depends(get_current_user)):
    """
    Retourne les informations de l'utilisateur courant

    Args:
        current_user: Utilisateur courant (dépendance JWT)

    Returns:
        Données utilisateur
    """
    return User(**current_user)


@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """
    Déconnecte l'utilisateur (côté frontend, le token sera simplement supprimé)

    Args:
        current_user: Utilisateur courant (dépendance JWT)

    Returns:
        Message de confirmation
    """
    logger.info(f"Déconnexion de: {current_user['username']}")
    return {"message": "Successfully logged out"}


@router.get("/me/must-change-password")
async def check_must_change_password(current_user: dict = Depends(get_current_user)):
    """
    Vérifie si l'utilisateur doit changer son mot de passe

    Args:
        current_user: Utilisateur courant (dépendance JWT)

    Returns:
        Status du flag must_change_password
    """
    return {"must_change_password": current_user.get("must_change_password", False)}


@router.patch("/me/profile")
async def update_my_profile(
    profile_data: UserProfileUpdate,
    current_user: dict = Depends(get_current_user)
):
    """
    Met à jour le profil de l'utilisateur courant (prénom, nom)

    Args:
        profile_data: Données de profil à mettre à jour
        current_user: Utilisateur courant (dépendance JWT)

    Returns:
        Utilisateur mis à jour
    """
    updates = []
    values = []
    param_count = 1

    if profile_data.first_name is not None:
        updates.append(f"first_name = ${param_count}")
        values.append(profile_data.first_name)
        param_count += 1

    if profile_data.last_name is not None:
        updates.append(f"last_name = ${param_count}")
        values.append(profile_data.last_name)
        param_count += 1

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucune donnée à mettre à jour"
        )

    values.append(current_user["id"])
    query = f"""
        UPDATE users
        SET {', '.join(updates)}
        WHERE id = ${param_count}
        RETURNING id, username, email, first_name, last_name, is_active, is_admin, must_change_password, created_at
    """

    async with database.db_pool.acquire() as conn:
        user = await conn.fetchrow(query, *values)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Utilisateur non trouvé"
            )

    logger.info(f"✏️ Profil mis à jour pour: {user['username']}")
    return User(**dict(user))


@router.post("/me/change-password")
async def change_my_password(
    password_data: PasswordChange,
    current_user: dict = Depends(get_current_user)
):
    """
    Change le mot de passe de l'utilisateur courant

    Args:
        password_data: Ancien et nouveau mot de passe
        current_user: Utilisateur courant (dépendance JWT)

    Returns:
        Message de confirmation

    Raises:
        HTTPException: Si le mot de passe actuel est incorrect ou la validation échoue
    """
    # Vérifier que les deux nouveaux mots de passe correspondent
    if password_data.new_password != password_data.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Les mots de passe ne correspondent pas"
        )

    # Valider la force du nouveau mot de passe
    is_valid, error_message = validate_password_strength(password_data.new_password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_message
        )

    async with database.db_pool.acquire() as conn:
        # Récupérer le hash actuel
        user = await conn.fetchrow(
            "SELECT hashed_password FROM users WHERE id = $1",
            current_user["id"]
        )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Utilisateur non trouvé"
            )

        # Vérifier l'ancien mot de passe
        if not verify_password(password_data.current_password, user["hashed_password"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mot de passe actuel incorrect"
            )

        # Hacher le nouveau mot de passe
        new_hashed_password = get_password_hash(password_data.new_password)

        # Mettre à jour le mot de passe et retirer le flag must_change_password
        await conn.execute(
            """
            UPDATE users
            SET hashed_password = $1, must_change_password = false
            WHERE id = $2
            """,
            new_hashed_password,
            current_user["id"]
        )

    logger.info(f"🔑 Mot de passe changé pour: {current_user['username']}")
    return {"message": "Mot de passe modifié avec succès"}
