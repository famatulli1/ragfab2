"""
Configuration de l'application FastAPI
"""
import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Configuration de l'application"""

    # Base de données
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://raguser:ragpass@postgres:5432/ragdb"
    )

    # JWT
    JWT_SECRET: str = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 60 * 24 * 7  # 7 jours

    # Admin credentials (pour création initiale)
    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "admin")

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",  # Vite dev server
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    # Uploads
    UPLOAD_DIR: str = "/app/uploads"
    MAX_UPLOAD_SIZE: int = 500 * 1024 * 1024  # 500 MB (augmenté pour gros documents)

    # RAG Agent paths (montés depuis le container rag-app)
    RAG_APP_PATH: str = "/rag-app"

    # Embeddings server
    EMBEDDINGS_API_URL: str = os.getenv("EMBEDDINGS_API_URL", "http://embeddings:8001")

    # Mistral API
    MISTRAL_API_KEY: str = os.getenv("MISTRAL_API_KEY", "")
    MISTRAL_MODEL_NAME: str = os.getenv("MISTRAL_MODEL_NAME", "mistral-small-latest")

    # Chocolatine API (vLLM)
    CHOCOLATINE_API_URL: str = os.getenv("CHOCOLATINE_API_URL", "https://apigpt.mynumih.fr")
    CHOCOLATINE_MODEL_NAME: str = os.getenv(
        "CHOCOLATINE_MODEL_NAME",
        "jpacifico/Chocolatine-2-14B-Instruct-v2.0.3"
    )

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
