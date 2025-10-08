"""
Routes pour l'administration et l'upload de documents
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, status, Request
from fastapi.responses import JSONResponse
from typing import List
from uuid import UUID, uuid4
from datetime import datetime
import logging
import os
import shutil
from pathlib import Path

from ..auth import get_current_admin_user
from .. import database
from ..models import IngestionJob
from ..config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["Admin"])

# Rate limiter will be added when router is included in main.py


# Configuration des uploads
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls", ".md", ".txt", ".html", ".htm"}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB


def validate_file(file: UploadFile) -> tuple[bool, str]:
    """
    Validate uploaded file type and size.

    Args:
        file: Uploaded file

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check file extension
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        return False, f"Format de fichier non supporté: {file_ext}. Formats acceptés: {', '.join(ALLOWED_EXTENSIONS)}"

    # Note: We can't check size here without reading the file
    # Size validation will be done during streaming
    return True, ""


@router.post("/documents/upload")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Upload un document pour ingestion.

    Le fichier est sauvegardé dans /app/uploads/{job_id}/
    Un job d'ingestion est créé avec status='pending'
    Le worker traitera le fichier de manière asynchrone

    **Rate limit**: 10 uploads par heure
    """
    logger.info(f"📤 Upload document: {file.filename} by user {current_user.get('username')}")

    # Validate file
    is_valid, error_msg = validate_file(file)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    # Generate job ID
    job_id = uuid4()
    job_dir = Path(settings.UPLOAD_DIR) / str(job_id)

    try:
        # Create job directory
        job_dir.mkdir(parents=True, exist_ok=True)

        # Save uploaded file
        file_path = job_dir / file.filename
        total_size = 0

        with open(file_path, "wb") as buffer:
            while chunk := await file.read(8192):  # Read 8KB chunks
                total_size += len(chunk)

                # Check file size limit
                if total_size > MAX_FILE_SIZE:
                    # Cleanup
                    file_path.unlink(missing_ok=True)
                    job_dir.rmdir()
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Fichier trop volumineux. Limite: {MAX_FILE_SIZE // (1024*1024)} MB"
                    )

                buffer.write(chunk)

        logger.info(f"✅ File saved: {file_path} ({total_size} bytes)")

        # Create ingestion job in database
        async with database.db_pool.acquire() as conn:
            job = await conn.fetchrow("""
                INSERT INTO ingestion_jobs (id, filename, file_size, status, progress)
                VALUES ($1::uuid, $2, $3, 'pending', 0)
                RETURNING id, filename, file_size, status, progress, created_at
            """, str(job_id), file.filename, total_size)

        logger.info(f"📝 Ingestion job created: {job_id}")

        return {
            "job_id": str(job["id"]),
            "filename": job["filename"],
            "status": job["status"],
            "message": "Document uploadé avec succès. Le traitement va démarrer automatiquement."
        }

    except HTTPException:
        raise

    except Exception as e:
        # Cleanup on error
        if file_path.exists():
            file_path.unlink(missing_ok=True)
        if job_dir.exists():
            job_dir.rmdir()

        logger.error(f"❌ Upload error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'upload: {str(e)}"
        )


@router.get("/documents/jobs/{job_id}", response_model=IngestionJob)
async def get_ingestion_job(
    request: Request,
    job_id: UUID,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Récupère le statut d'un job d'ingestion.

    Utilisé par le frontend pour le polling et l'affichage de la progression.
    """
    async with database.db_pool.acquire() as conn:
        job = await conn.fetchrow("""
            SELECT id, filename, file_size, status, progress,
                   document_id, chunks_created, error_message,
                   created_at, started_at, completed_at
            FROM ingestion_jobs
            WHERE id = $1::uuid
        """, str(job_id))

        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} non trouvé"
            )

        return {
            "id": job["id"],
            "filename": job["filename"],
            "file_size": job["file_size"],
            "status": job["status"],
            "progress": job["progress"],
            "document_id": job["document_id"],
            "chunks_created": job["chunks_created"],
            "error_message": job["error_message"],
            "created_at": job["created_at"],
            "started_at": job["started_at"],
            "completed_at": job["completed_at"]
        }


@router.get("/documents/jobs", response_model=List[IngestionJob])
async def list_ingestion_jobs(
    request: Request,
    limit: int = 50,
    offset: int = 0,
    status_filter: str = None,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Liste tous les jobs d'ingestion avec filtrage optionnel par statut.

    Args:
        limit: Nombre maximum de résultats
        offset: Offset pour la pagination
        status_filter: Filtrer par statut (pending, processing, completed, failed)
    """
    async with database.db_pool.acquire() as conn:
        if status_filter:
            query = """
                SELECT id, filename, file_size, status, progress,
                       document_id, chunks_created, error_message,
                       created_at, started_at, completed_at
                FROM ingestion_jobs
                WHERE status = $1
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
            """
            rows = await conn.fetch(query, status_filter, limit, offset)
        else:
            query = """
                SELECT id, filename, file_size, status, progress,
                       document_id, chunks_created, error_message,
                       created_at, started_at, completed_at
                FROM ingestion_jobs
                ORDER BY created_at DESC
                LIMIT $1 OFFSET $2
            """
            rows = await conn.fetch(query, limit, offset)

        return [
            {
                "id": row["id"],
                "filename": row["filename"],
                "file_size": row["file_size"],
                "status": row["status"],
                "progress": row["progress"],
                "document_id": row["document_id"],
                "chunks_created": row["chunks_created"],
                "error_message": row["error_message"],
                "created_at": row["created_at"],
                "started_at": row["started_at"],
                "completed_at": row["completed_at"]
            }
            for row in rows
        ]


@router.delete("/documents/jobs/{job_id}")
async def delete_ingestion_job(
    request: Request,
    job_id: UUID,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Supprime un job d'ingestion.

    ⚠️ N'empêche pas le traitement si le job est déjà en cours.
    Utilisez uniquement pour nettoyer les jobs terminés ou échoués.
    """
    async with database.db_pool.acquire() as conn:
        # Check if job exists and get status
        job = await conn.fetchrow("""
            SELECT status FROM ingestion_jobs WHERE id = $1::uuid
        """, str(job_id))

        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} non trouvé"
            )

        if job["status"] == "processing":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Impossible de supprimer un job en cours de traitement"
            )

        # Delete job
        await conn.execute("""
            DELETE FROM ingestion_jobs WHERE id = $1::uuid
        """, str(job_id))

        # Cleanup uploaded file if still present
        job_dir = Path(settings.UPLOAD_DIR) / str(job_id)
        if job_dir.exists():
            try:
                shutil.rmtree(job_dir)
                logger.info(f"Cleaned up job directory: {job_dir}")
            except Exception as e:
                logger.warning(f"Could not cleanup job directory {job_dir}: {e}")

        return {"message": f"Job {job_id} supprimé"}
