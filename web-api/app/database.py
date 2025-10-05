"""
Gestion de la connexion à la base de données PostgreSQL
"""
import asyncpg
import logging
from typing import Optional
from .config import settings

logger = logging.getLogger(__name__)

# Pool de connexions global
db_pool: Optional[asyncpg.Pool] = None


async def initialize_database():
    """
    Initialise le pool de connexions à la base de données
    """
    global db_pool

    try:
        db_pool = await asyncpg.create_pool(
            settings.DATABASE_URL,
            min_size=2,
            max_size=10,
            command_timeout=60,
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
