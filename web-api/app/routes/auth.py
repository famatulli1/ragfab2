"""
Routes d'authentification
"""
from fastapi import APIRouter, HTTPException, status, Depends, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from datetime import timedelta
import logging

from ..models import LoginRequest, TokenResponse, User
from ..auth import authenticate_user, create_access_token, get_current_user
from ..config import settings

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
