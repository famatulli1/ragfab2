"""
Worker permanent pour traiter les jobs d'ingestion de documents.
Poll la table ingestion_jobs et traite les documents uploadés via l'interface admin.
"""

import os
import sys
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import asyncpg
from dotenv import load_dotenv

# Ajouter le path du rag-app pour importer les modules d'ingestion
sys.path.insert(0, "/app/rag-app")

from ingestion.ingest import DocumentIngestionPipeline
from utils.models import IngestionConfig

# Load environment variables
load_dotenv()

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class IngestionWorker:
    """Worker qui traite les jobs d'ingestion en permanence."""

    def __init__(
        self,
        poll_interval: int = 3,
        timeout_minutes: int = 30,
        uploads_dir: str = "/app/uploads"
    ):
        """
        Initialize ingestion worker.

        Args:
            poll_interval: Interval in seconds between job polls
            timeout_minutes: Max time before considering a job stuck
            uploads_dir: Directory where uploaded files are stored
        """
        self.poll_interval = poll_interval
        self.timeout_minutes = timeout_minutes
        self.uploads_dir = Path(uploads_dir)

        # Database connection pool
        self.db_pool: Optional[asyncpg.Pool] = None

        # Ingestion pipeline (initialized later)
        self.pipeline: Optional[DocumentIngestionPipeline] = None

        # Worker state
        self.running = False
        self.current_job_id: Optional[str] = None

    async def initialize(self):
        """Initialize database connection and ingestion pipeline."""
        logger.info("Initializing ingestion worker...")

        # Initialize database connection pool
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL environment variable not set")

        self.db_pool = await asyncpg.create_pool(
            database_url,
            min_size=2,
            max_size=5,
            command_timeout=60
        )

        logger.info("Database connection pool initialized")

        # Initialize ingestion pipeline with default config
        config = IngestionConfig(
            chunk_size=int(os.getenv("CHUNK_SIZE", "1500")),
            chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "200")),
            use_semantic_chunking=os.getenv("USE_SEMANTIC_CHUNKING", "true").lower() == "true"
        )

        self.pipeline = DocumentIngestionPipeline(
            config=config,
            documents_folder=str(self.uploads_dir),
            clean_before_ingest=False  # Never clean on worker
        )

        await self.pipeline.initialize()
        logger.info("Ingestion pipeline initialized")

        logger.info("✅ Worker initialization complete")

    async def close(self):
        """Close database connections and cleanup."""
        logger.info("Shutting down worker...")

        if self.pipeline:
            await self.pipeline.close()

        if self.db_pool:
            await self.db_pool.close()

        logger.info("Worker shutdown complete")

    async def get_next_pending_job(self) -> Optional[dict]:
        """
        Get the next pending job from the database.

        Returns:
            Job dict or None if no pending jobs
        """
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT id, filename, file_size, created_at
                FROM ingestion_jobs
                WHERE status = 'pending'
                ORDER BY created_at ASC
                LIMIT 1
            """)

            if row:
                return dict(row)
            return None

    async def reset_stuck_jobs(self):
        """
        Reset jobs that have been processing for too long.
        This handles worker crashes or unexpected interruptions.
        """
        timeout_threshold = datetime.now() - timedelta(minutes=self.timeout_minutes)

        async with self.db_pool.acquire() as conn:
            result = await conn.execute("""
                UPDATE ingestion_jobs
                SET status = 'pending',
                    error_message = 'Job timed out - worker may have crashed',
                    started_at = NULL
                WHERE status = 'processing'
                  AND started_at < $1
            """, timeout_threshold)

            if result != "UPDATE 0":
                count = int(result.split()[-1])
                logger.warning(f"Reset {count} stuck jobs that exceeded {self.timeout_minutes} min timeout")

    async def claim_job(self, job_id: str) -> bool:
        """
        Claim a job by setting it to processing status.

        Args:
            job_id: Job ID to claim

        Returns:
            True if job was successfully claimed
        """
        async with self.db_pool.acquire() as conn:
            result = await conn.execute("""
                UPDATE ingestion_jobs
                SET status = 'processing',
                    started_at = NOW()
                WHERE id = $1::uuid
                  AND status = 'pending'
            """, job_id)

            return result == "UPDATE 1"

    async def update_job_progress(self, job_id: str, progress: int):
        """Update job progress percentage."""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE ingestion_jobs
                SET progress = $1
                WHERE id = $2::uuid
            """, progress, job_id)

    async def complete_job(
        self,
        job_id: str,
        document_id: str,
        chunks_created: int
    ):
        """Mark job as completed."""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE ingestion_jobs
                SET status = 'completed',
                    progress = 100,
                    document_id = $1::uuid,
                    chunks_created = $2,
                    completed_at = NOW()
                WHERE id = $3::uuid
            """, document_id, chunks_created, job_id)

        logger.info(f"✅ Job {job_id} completed: {chunks_created} chunks created")

    async def fail_job(self, job_id: str, error_message: str):
        """Mark job as failed."""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE ingestion_jobs
                SET status = 'failed',
                    error_message = $1,
                    completed_at = NOW()
                WHERE id = $2::uuid
            """, error_message, job_id)

        logger.error(f"❌ Job {job_id} failed: {error_message}")

    async def process_job(self, job: dict):
        """
        Process a single ingestion job.

        Args:
            job: Job dict with id, filename, file_size
        """
        job_id = str(job["id"])
        filename = job["filename"]

        logger.info(f"📄 Processing job {job_id}: {filename}")

        # Claim the job
        claimed = await self.claim_job(job_id)
        if not claimed:
            logger.warning(f"Could not claim job {job_id} - may have been claimed by another worker")
            return

        self.current_job_id = job_id

        try:
            # Find the uploaded file
            job_dir = self.uploads_dir / job_id
            if not job_dir.exists():
                raise FileNotFoundError(f"Job directory not found: {job_dir}")

            # Find the uploaded file (should be only one file in the directory)
            files = list(job_dir.glob("*"))
            if not files:
                raise FileNotFoundError(f"No file found in job directory: {job_dir}")

            file_path = files[0]
            logger.info(f"Found file: {file_path}")

            # Update progress: 10% (file located)
            await self.update_job_progress(job_id, 10)

            # Read and process document
            logger.info("Reading document...")
            document_content, docling_doc = self.pipeline._read_document(str(file_path))

            # Update progress: 30% (file read)
            await self.update_job_progress(job_id, 30)

            # Extract metadata
            document_title = self.pipeline._extract_title(document_content, str(file_path))
            document_source = filename
            document_metadata = self.pipeline._extract_document_metadata(document_content, str(file_path))

            logger.info(f"Document title: {document_title}")

            # Update progress: 40% (metadata extracted)
            await self.update_job_progress(job_id, 40)

            # Chunk the document
            logger.info("Chunking document...")
            chunks = await self.pipeline.chunker.chunk_document(
                content=document_content,
                title=document_title,
                source=document_source,
                metadata=document_metadata,
                docling_doc=docling_doc
            )

            if not chunks:
                raise ValueError("No chunks created from document")

            logger.info(f"Created {len(chunks)} chunks")

            # Update progress: 60% (chunking complete)
            await self.update_job_progress(job_id, 60)

            # Generate embeddings
            logger.info("Generating embeddings...")
            embedded_chunks = await self.pipeline.embedder.embed_chunks(chunks)

            # Update progress: 80% (embeddings generated)
            await self.update_job_progress(job_id, 80)

            # Save to PostgreSQL
            logger.info("Saving to database...")
            document_id = await self.pipeline._save_to_postgres(
                document_title,
                document_source,
                document_content,
                embedded_chunks,
                document_metadata
            )

            logger.info(f"Saved document with ID: {document_id}")

            # Update progress: 90% (saved to DB)
            await self.update_job_progress(job_id, 90)

            # Complete the job
            await self.complete_job(job_id, document_id, len(chunks))

            # Cleanup uploaded file
            try:
                file_path.unlink()
                job_dir.rmdir()
                logger.info(f"Cleaned up uploaded file: {file_path}")
            except Exception as e:
                logger.warning(f"Could not cleanup file {file_path}: {e}")

        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            logger.error(f"Error processing job {job_id}: {error_msg}", exc_info=True)
            await self.fail_job(job_id, error_msg)

        finally:
            self.current_job_id = None

    async def run(self):
        """Main worker loop - polls for jobs and processes them."""
        logger.info(f"🚀 Worker started (polling every {self.poll_interval}s)")
        self.running = True

        # Reset any stuck jobs on startup
        await self.reset_stuck_jobs()

        while self.running:
            try:
                # Get next pending job
                job = await self.get_next_pending_job()

                if job:
                    await self.process_job(job)
                else:
                    # No jobs available, wait before polling again
                    await asyncio.sleep(self.poll_interval)

            except asyncio.CancelledError:
                logger.info("Worker received cancellation signal")
                break

            except Exception as e:
                logger.error(f"Unexpected error in worker loop: {e}", exc_info=True)
                await asyncio.sleep(self.poll_interval)

        logger.info("Worker stopped")

    def stop(self):
        """Stop the worker gracefully."""
        logger.info("Stopping worker...")
        self.running = False


async def main():
    """Main entry point for the worker."""
    # Configuration from environment
    poll_interval = int(os.getenv("WORKER_POLL_INTERVAL", "3"))
    timeout_minutes = int(os.getenv("WORKER_TIMEOUT_MINUTES", "30"))
    uploads_dir = os.getenv("UPLOADS_DIR", "/app/uploads")

    # Create worker
    worker = IngestionWorker(
        poll_interval=poll_interval,
        timeout_minutes=timeout_minutes,
        uploads_dir=uploads_dir
    )

    try:
        # Initialize
        await worker.initialize()

        # Run worker loop
        await worker.run()

    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise

    finally:
        # Cleanup
        await worker.close()


if __name__ == "__main__":
    asyncio.run(main())
