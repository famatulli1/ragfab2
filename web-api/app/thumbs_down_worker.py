"""
Worker asynchrone pour l'analyse automatique des thumbs down

Ce worker écoute les notifications PostgreSQL via pg_notify et déclenche
automatiquement l'analyse IA des nouveaux thumbs down.

Usage:
    python -m app.thumbs_down_worker
"""

import asyncio
import asyncpg
import json
import logging
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.thumbs_down_analyzer import ThumbsDownAnalyzer
from uuid import UUID

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ThumbsDownWorker:
    """Worker pour analyser automatiquement les thumbs down via pg_notify"""

    def __init__(self):
        self.database_url = os.getenv("DATABASE_URL")
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable not set")

        self.enabled = os.getenv("THUMBS_DOWN_AUTO_ANALYSIS", "true").lower() == "true"
        self.pool = None
        self.analyzer = None
        self.running = False

        logger.info(f"ThumbsDownWorker initialized (auto_analysis={self.enabled})")

    async def start(self):
        """Démarre le worker et commence à écouter les notifications"""
        if not self.enabled:
            logger.warning("Thumbs down auto-analysis is disabled. Worker will not start.")
            return

        try:
            # Créer pool de connexions
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=2,
                max_size=5
            )

            logger.info("✅ Database pool created successfully")

            # Initialiser analyzer
            self.analyzer = ThumbsDownAnalyzer(self.pool)

            # Démarrer l'écoute des notifications
            self.running = True
            await self._listen_for_notifications()

        except Exception as e:
            logger.error(f"❌ Error starting worker: {e}", exc_info=True)
            await self.stop()

    async def stop(self):
        """Arrête le worker proprement"""
        self.running = False

        if self.pool:
            await self.pool.close()
            logger.info("✅ Database pool closed")

    async def _listen_for_notifications(self):
        """Écoute en continu les notifications pg_notify"""
        conn = await self.pool.acquire()

        try:
            # S'abonner au canal 'thumbs_down_created'
            await conn.add_listener('thumbs_down_created', self._on_thumbs_down_created)
            logger.info("✅ Listening for 'thumbs_down_created' notifications...")

            # Boucle infinie pour maintenir la connexion
            while self.running:
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"❌ Error in notification listener: {e}", exc_info=True)

        finally:
            await conn.remove_listener('thumbs_down_created', self._on_thumbs_down_created)
            await self.pool.release(conn)

    async def _on_thumbs_down_created(self, connection, pid, channel, payload):
        """
        Callback appelé quand un nouveau thumbs down est créé

        Args:
            connection: Connexion PostgreSQL
            pid: Process ID du serveur PostgreSQL
            channel: Nom du canal (thumbs_down_created)
            payload: JSON avec les détails du thumbs down
        """
        try:
            # Parser le payload JSON
            data = json.loads(payload)
            rating_id = data.get('rating_id')

            if not rating_id:
                logger.warning(f"⚠️  Notification received without rating_id: {payload}")
                return

            logger.info(f"📬 New thumbs down notification received: rating_id={rating_id}")

            # Déclencher l'analyse en arrière-plan (non-bloquant)
            asyncio.create_task(self._analyze_thumbs_down(UUID(rating_id)))

        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON payload: {payload} - Error: {e}")
        except Exception as e:
            logger.error(f"❌ Error processing notification: {e}", exc_info=True)

    async def _analyze_thumbs_down(self, rating_id: UUID):
        """Analyse un thumbs down de manière asynchrone"""
        try:
            logger.info(f"🔄 Starting analysis for rating {rating_id}")

            result = await self.analyzer.analyze_thumbs_down(rating_id)

            if 'error' in result:
                logger.error(f"❌ Analysis failed for rating {rating_id}: {result['error']}")
            else:
                logger.info(
                    f"✅ Analysis completed for rating {rating_id}: "
                    f"classification={result['classification']}, "
                    f"confidence={result['confidence']:.2f}, "
                    f"needs_review={result['needs_review']}"
                )

        except Exception as e:
            logger.error(f"❌ Unexpected error analyzing rating {rating_id}: {e}", exc_info=True)


async def main():
    """Point d'entrée principal du worker"""
    worker = ThumbsDownWorker()

    try:
        logger.info("🚀 Starting Thumbs Down Analysis Worker...")
        await worker.start()

    except KeyboardInterrupt:
        logger.info("\n⏸️  Shutdown signal received, stopping worker...")
        await worker.stop()

    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        await worker.stop()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
