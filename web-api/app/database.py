"""
Gestion de la connexion à la base de données PostgreSQL
"""
import asyncpg
import logging
import socket
from typing import Optional
from .config import settings

logger = logging.getLogger(__name__)

# Pool de connexions global
db_pool: Optional[asyncpg.Pool] = None


async def initialize_database():
    """
    Initialise le pool de connexions à la base de données
    Force IPv4 pour éviter les problèmes de résolution DNS IPv6
    """
    global db_pool

    try:
        # Logs de debug pour vérifier les valeurs
        logger.info(f"🔍 POSTGRES_HOST: {settings.POSTGRES_HOST}")
        logger.info(f"🔍 POSTGRES_PORT: {settings.POSTGRES_PORT}")
        logger.info(f"🔍 POSTGRES_USER: {settings.POSTGRES_USER}")
        logger.info(f"🔍 POSTGRES_PASSWORD: {'*' * len(settings.POSTGRES_PASSWORD)} (length: {len(settings.POSTGRES_PASSWORD)})")
        logger.info(f"🔍 POSTGRES_DB: {settings.POSTGRES_DB}")

        # Forcer IPv4 en utilisant les paramètres individuels
        db_pool = await asyncpg.create_pool(
            host=settings.POSTGRES_HOST,
            port=settings.POSTGRES_PORT,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            database=settings.POSTGRES_DB,
            min_size=2,
            max_size=10,
            command_timeout=60,
            server_settings={'jit': 'off'},  # Désactiver JIT pour compatibilité
        )
        logger.info("✅ Pool de connexions BD initialisé")
        return db_pool
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'initialisation de la BD: {e}")
        raise


async def close_database():
    """
    Ferme le pool de connexions
    """
    global db_pool

    if db_pool:
        await db_pool.close()
        logger.info("Pool de connexions BD fermé")
        db_pool = None


async def get_connection():
    """
    Retourne une connexion depuis le pool
    """
    if not db_pool:
        await initialize_database()
    return await db_pool.acquire()


async def release_connection(conn):
    """
    Libère une connexion vers le pool
    """
    if db_pool and conn:
        await db_pool.release(conn)
