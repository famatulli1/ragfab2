"""
Routes pour l'administration et l'upload de documents
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, status, Request
from fastapi.responses import JSONResponse
from typing import List
from uuid import UUID, uuid4
from datetime import datetime
from pydantic import BaseModel
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
    ocr_engine: str = Form("rapidocr"),  # Nouveau: moteur OCR pour Docling
    vlm_engine: str = Form("paddleocr-vl"),  # Moteur VLM pour extraction images
    chunker_type: str = Form("hybrid"),  # Nouveau: stratégie de chunking
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Upload un document pour ingestion.

    Le fichier est sauvegardé dans /app/uploads/{job_id}/
    Un job d'ingestion est créé avec status='pending'
    Le worker traitera le fichier de manière asynchrone

    **Paramètres**:
    - file: Fichier à traiter
    - ocr_engine: Moteur OCR pour parsing Docling ('rapidocr', 'easyocr', 'tesseract')
    - vlm_engine: Moteur VLM pour extraction d'images ('paddleocr-vl', 'internvl', 'none')
    - chunker_type: Stratégie de découpage ('hybrid', 'parent_child')

    **Rate limit**: 10 uploads par heure
    """
    logger.info(
        f"📤 Upload document: {file.filename} by user {current_user.get('username')} "
        f"with OCR: {ocr_engine}, VLM: {vlm_engine}, Chunker: {chunker_type}"
    )

    # Validate OCR engine parameter
    allowed_ocr_engines = {"rapidocr", "easyocr", "tesseract"}
    if ocr_engine not in allowed_ocr_engines:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid OCR engine: {ocr_engine}. Allowed: {', '.join(allowed_ocr_engines)}"
        )

    # Validate VLM engine parameter
    allowed_vlm_engines = {"paddleocr-vl", "internvl", "none"}
    if vlm_engine not in allowed_vlm_engines:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid VLM engine: {vlm_engine}. Allowed: {', '.join(allowed_vlm_engines)}"
        )

    # Validate chunker type parameter
    allowed_chunker_types = {"hybrid", "parent_child"}
    if chunker_type not in allowed_chunker_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid chunker type: {chunker_type}. Allowed: {', '.join(allowed_chunker_types)}"
        )

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

        # Create ingestion job in database with OCR, VLM engine, and chunker type choices
        async with database.db_pool.acquire() as conn:
            job = await conn.fetchrow("""
                INSERT INTO ingestion_jobs (id, filename, file_size, status, progress, ocr_engine, vlm_engine, chunker_type)
                VALUES ($1::uuid, $2, $3, 'pending', 0, $4, $5, $6)
                RETURNING id, filename, file_size, status, progress, ocr_engine, vlm_engine, chunker_type, created_at
            """, str(job_id), file.filename, total_size, ocr_engine, vlm_engine, chunker_type)

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


class ReingestionRequest(BaseModel):
    ocr_engine: str = "rapidocr"
    vlm_engine: str = "paddleocr-vl"
    chunker_type: str = "hybrid"


@router.post("/documents/{document_id}/reingest")
async def reingest_document(
    request: Request,
    document_id: UUID,
    config: ReingestionRequest,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Réingère un document existant avec de nouveaux paramètres.

    Workflow:
    1. Récupère le job d'ingestion original
    2. Vérifie que le fichier existe encore
    3. Supprime l'ancien document (CASCADE sur chunks/images)
    4. Crée un nouveau job d'ingestion
    5. Copie le fichier dans le nouveau dossier job
    6. Le worker traitera le fichier automatiquement

    Retourne 404 si le fichier original n'existe plus.
    """
    logger.info(f"🔄 Reingest request for document {document_id} with ocr={config.ocr_engine}, vlm={config.vlm_engine}, chunker={config.chunker_type}")

    # Validate parameters
    allowed_ocr = {"rapidocr", "easyocr", "tesseract"}
    allowed_vlm = {"paddleocr-vl", "internvl", "none"}
    allowed_chunker = {"hybrid", "parent_child"}

    if config.ocr_engine not in allowed_ocr:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OCR engine invalide. Valeurs acceptées : {allowed_ocr}"
        )

    if config.vlm_engine not in allowed_vlm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"VLM engine invalide. Valeurs acceptées : {allowed_vlm}"
        )

    if config.chunker_type not in allowed_chunker:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chunker type invalide. Valeurs acceptées : {allowed_chunker}"
        )

    async with database.db_pool.acquire() as conn:
        # Get original document info
        document = await conn.fetchrow("""
            SELECT title, source FROM documents WHERE id = $1::uuid
        """, str(document_id))

        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document {document_id} non trouvé"
            )

        # Get original ingestion job (most recent)
        original_job = await conn.fetchrow("""
            SELECT id, filename
            FROM ingestion_jobs
            WHERE document_id = $1::uuid
            ORDER BY created_at DESC
            LIMIT 1
        """, str(document_id))

        if not original_job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job d'ingestion original non trouvé pour le document {document_id}"
            )

        # Check if original file still exists
        original_job_dir = Path(settings.UPLOAD_DIR) / str(original_job["id"])
        original_file_path = original_job_dir / original_job["filename"]

        if not original_file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Fichier original non trouvé dans {original_file_path}. Veuillez re-uploader le document manuellement."
            )

        logger.info(f"✅ Original file found: {original_file_path}")

        # Create new ingestion job
        new_job_id = uuid4()
        new_job_dir = Path(settings.UPLOAD_DIR) / str(new_job_id)
        new_job_dir.mkdir(parents=True, exist_ok=True)

        # Copy file to new job directory
        new_file_path = new_job_dir / original_job["filename"]
        try:
            shutil.copy2(original_file_path, new_file_path)
            logger.info(f"✅ File copied to: {new_file_path}")
        except Exception as e:
            # Cleanup on error
            if new_job_dir.exists():
                shutil.rmtree(new_job_dir)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erreur lors de la copie du fichier : {str(e)}"
            )

        # Create ingestion job in database
        await conn.execute("""
            INSERT INTO ingestion_jobs
            (id, filename, status, ocr_engine, vlm_engine, chunker_type)
            VALUES ($1, $2, 'pending', $3, $4, $5)
        """, str(new_job_id), original_job["filename"], config.ocr_engine, config.vlm_engine, config.chunker_type)

        logger.info(f"✅ New ingestion job created: {new_job_id}")

        # Delete ratings for messages that reference chunks from this document
        # (important pour analytics - sinon les anciens ratings polluent les stats)
        deleted_ratings = await conn.fetchval("""
            WITH document_chunks AS (
                SELECT id FROM chunks WHERE document_id = $1::uuid
            ),
            messages_to_clean AS (
                SELECT DISTINCT m.id
                FROM messages m
                CROSS JOIN LATERAL jsonb_array_elements(m.sources) AS source
                WHERE (source->>'chunk_id')::uuid IN (SELECT id FROM document_chunks)
            )
            DELETE FROM message_ratings
            WHERE message_id IN (SELECT id FROM messages_to_clean)
            RETURNING COUNT(*)
        """, str(document_id))

        logger.info(f"✅ Deleted {deleted_ratings or 0} ratings from messages referencing old document chunks")

        # Delete old document (CASCADE will delete chunks, images, etc.)
        await conn.execute("""
            DELETE FROM documents WHERE id = $1::uuid
        """, str(document_id))

        logger.info(f"✅ Old document deleted: {document_id}")

        return {
            "job_id": str(new_job_id),
            "message": f"Réingestion lancée pour '{document['title']}' avec OCR={config.ocr_engine}, VLM={config.vlm_engine}, Chunker={config.chunker_type}",
            "old_document_id": str(document_id),
            "new_job_id": str(new_job_id)
        }
