"""
Routes for document operations including PDF annotation and viewing.
"""

import os
import json
import tempfile
import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Query
from fastapi.responses import FileResponse
import fitz  # PyMuPDF

from .. import database
from .auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/documents/{document_id}/annotated-pdf")
async def get_annotated_pdf(
    document_id: str,
    background_tasks: BackgroundTasks,
    chunk_ids: Optional[str] = Query(None, description="Comma-separated list of chunk IDs to highlight"),
    current_user: dict = Depends(get_current_user)
):
    """
    Generate an annotated PDF with source chunks highlighted.

    This endpoint:
    1. Retrieves the original PDF document
    2. Fetches chunk bounding boxes from database
    3. Highlights specified chunks (or all chunks if none specified)
    4. Returns the annotated PDF for download

    Args:
        document_id: UUID of the document
        chunk_ids: Optional comma-separated list of chunk UUIDs to highlight
        current_user: Authenticated user (injected by dependency)

    Returns:
        FileResponse with annotated PDF

    Raises:
        HTTPException 404: Document or PDF source not found
        HTTPException 400: Invalid chunk IDs or missing bounding boxes
    """
    try:
        logger.info(f"📄 Annotated PDF request: document_id={document_id}, chunk_ids={chunk_ids}")

        # 1. Retrieve document from database
        async with database.db_pool.acquire() as conn:
            document = await conn.fetchrow(
                "SELECT * FROM documents WHERE id = $1",
                UUID(document_id)
            )

            if not document:
                logger.error(f"❌ Document not found: {document_id}")
                raise HTTPException(status_code=404, detail="Document not found")

            logger.info(f"✅ Document found: {document['title']}, source={document['source']}")

            # 2. Retrieve chunks with bounding boxes
            if chunk_ids:
                # Parse chunk IDs from comma-separated string
                try:
                    chunk_uuid_list = [UUID(cid.strip()) for cid in chunk_ids.split(",")]
                    logger.info(f"🔍 Searching for {len(chunk_uuid_list)} specific chunks")
                except ValueError as e:
                    logger.error(f"❌ Invalid chunk ID format: {e}")
                    raise HTTPException(status_code=400, detail=f"Invalid chunk ID format: {e}")

                # Use helper function to get chunks for annotation
                try:
                    chunks = await conn.fetch(
                        """
                        SELECT * FROM get_chunks_for_annotation(
                            $1::uuid,
                            $2::uuid[]
                        )
                        """,
                        UUID(document_id),
                        chunk_uuid_list
                    )
                except Exception as e:
                    logger.error(f"❌ Database function error (migration 11 not applied?): {e}")
                    raise HTTPException(
                        status_code=500,
                        detail="Database error: get_chunks_for_annotation function not found. Please apply migration 11."
                    )
            else:
                # Get all chunks with bbox for this document
                try:
                    chunks = await conn.fetch(
                        """
                        SELECT * FROM get_chunks_for_annotation(
                            $1::uuid,
                            NULL::uuid[]
                        )
                        """,
                        UUID(document_id)
                    )
                except Exception as e:
                    logger.error(f"❌ Database function error (migration 11 not applied?): {e}")
                    raise HTTPException(
                        status_code=500,
                        detail="Database error: get_chunks_for_annotation function not found. Please apply migration 11."
                    )

            logger.info(f"📊 Retrieved {len(chunks)} chunks with bbox data")

        # 3. Locate the original PDF file (même si pas de bbox, on retourne le PDF original)
        logger.info(f"🔍 Will return {'annotated' if chunks else 'original'} PDF")

        # Locate PDF file
        # Assuming PDFs are stored in /app/uploads directory
        # Format: /app/uploads/jobs/{job_id}/{filename}.pdf
        # For backward compatibility, also check direct path in document.source
        uploads_dir = os.getenv("UPLOADS_DIR", "/app/uploads")

        # Try multiple path strategies
        potential_paths = [
            os.path.join(uploads_dir, document['source']),  # Direct source path (if source contains full path)
            os.path.join(uploads_dir, "jobs", document['source']),  # Jobs subdirectory (old format)
        ]

        logger.info(f"🔍 Searching for PDF: {document['source']}")

        pdf_path = None
        for path in potential_paths:
            if os.path.exists(path):
                pdf_path = path
                logger.info(f"✅ Found PDF at: {pdf_path}")
                break

        # If not found by direct paths, search recursively in jobs subdirectories
        if not pdf_path:
            logger.info(f"🔍 PDF not found in direct paths, searching recursively in {uploads_dir}/jobs/")
            jobs_dir = os.path.join(uploads_dir, "jobs")

            if os.path.exists(jobs_dir):
                # Extract filename from source (in case it contains subdirectories)
                filename = os.path.basename(document['source'])
                logger.info(f"   Looking for filename: {filename}")

                # Walk through all subdirectories
                for root, dirs, files in os.walk(jobs_dir):
                    if filename in files:
                        pdf_path = os.path.join(root, filename)
                        logger.info(f"✅ Found PDF via recursive search at: {pdf_path}")
                        break

        if not pdf_path:
            logger.error(f"❌ PDF source file not found for document {document_id}")
            logger.error(f"   Searched in: {potential_paths}")
            logger.error(f"   Also searched recursively in: {uploads_dir}/jobs/")
            logger.error(f"   Document source: {document['source']}")
            raise HTTPException(
                status_code=404,
                detail=f"PDF source file not found for document {document_id}. Source: {document['source']}"
            )

        # 4. Open and annotate the PDF
        try:
            doc = fitz.open(pdf_path)
            logger.info(f"📖 Opened PDF successfully: {len(doc)} pages")
        except Exception as e:
            logger.error(f"❌ Failed to open PDF: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to open PDF: {str(e)}"
            )

        # 5. Add highlights for each chunk
        annotations_added = 0
        logger.info(f"🎨 Starting annotation of {len(chunks)} chunks")

        for chunk in chunks:
            if not chunk['bbox']:
                logger.debug(f"Chunk {chunk['chunk_id']} has no bbox, skipping")
                continue

            try:
                # Parse bbox JSON
                bbox = json.loads(chunk['bbox']) if isinstance(chunk['bbox'], str) else chunk['bbox']
                page_num = chunk['page_number']

                # Validate page number
                if page_num < 1 or page_num > len(doc):
                    logger.warning(f"Invalid page number {page_num} for chunk {chunk['chunk_id']}")
                    continue

                # Get page (PyMuPDF uses 0-indexed pages)
                page = doc[page_num - 1]
                page_height = page.rect.height

                # Convert Docling bbox (bottom-left origin) to PyMuPDF rect (top-left origin)
                # Docling: (l, t, r, b) from bottom-left
                # PyMuPDF: (x0, y0, x1, y1) from top-left
                rect = fitz.Rect(
                    bbox['l'],
                    page_height - bbox['t'],  # Convert Y coordinate
                    bbox['r'],
                    page_height - bbox['b']   # Convert Y coordinate
                )

                # Add yellow highlight annotation
                highlight = page.add_highlight_annot(rect)
                highlight.set_colors(stroke=[1, 1, 0])  # RGB: Yellow
                highlight.set_opacity(0.5)  # Semi-transparent
                highlight.update()

                annotations_added += 1
                logger.debug(f"Added highlight for chunk {chunk['chunk_id']} on page {page_num}")

            except Exception as e:
                logger.error(f"Failed to annotate chunk {chunk['chunk_id']}: {e}")
                continue

        logger.info(f"✅ Added {annotations_added} highlights to PDF {document['title']}")

        # 6. Save annotated PDF to temporary file
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                doc.save(tmp.name, garbage=4, deflate=True)  # Optimize output
                tmp_path = tmp.name
                logger.info(f"💾 Saved annotated PDF to temp file: {tmp_path}")

            doc.close()
        except Exception as e:
            logger.error(f"❌ Failed to save PDF: {e}")
            doc.close()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save annotated PDF: {str(e)}"
            )

        # 7. Schedule cleanup of temporary file after response is sent
        background_tasks.add_task(os.unlink, tmp_path)

        # 8. Return annotated PDF
        filename = f"{document['title']}_annotated.pdf"
        # Sanitize filename (remove special characters)
        filename = "".join(c for c in filename if c.isalnum() or c in (' ', '.', '_', '-')).rstrip()

        logger.info(f"📤 Returning annotated PDF: {filename}")

        return FileResponse(
            tmp_path,
            media_type="application/pdf",
            filename=filename,
            headers={
                "Content-Disposition": f'inline; filename="{filename}"'
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating annotated PDF: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate annotated PDF: {str(e)}")


@router.get("/api/documents/{document_id}/debug")
async def debug_document_files(
    document_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Debug endpoint to check if PDF file exists and where.
    """
    try:
        async with database.db_pool.acquire() as conn:
            document = await conn.fetchrow(
                "SELECT * FROM documents WHERE id = $1",
                UUID(document_id)
            )

            if not document:
                raise HTTPException(status_code=404, detail="Document not found")

        uploads_dir = os.getenv("UPLOADS_DIR", "/app/uploads")

        # Check all potential paths
        checks = {
            "document_source": document['source'],
            "uploads_dir": uploads_dir,
            "direct_path": os.path.join(uploads_dir, document['source']),
            "jobs_path": os.path.join(uploads_dir, "jobs", document['source']),
        }

        # Check if paths exist
        results = {
            "direct_path_exists": os.path.exists(checks["direct_path"]),
            "jobs_path_exists": os.path.exists(checks["jobs_path"]),
        }

        # List all files in uploads dir
        all_files = []
        if os.path.exists(uploads_dir):
            for root, dirs, files in os.walk(uploads_dir):
                for file in files:
                    if file.endswith('.pdf'):
                        full_path = os.path.join(root, file)
                        all_files.append({
                            "filename": file,
                            "path": full_path,
                            "matches": file == os.path.basename(document['source'])
                        })

        return {
            "document_id": document_id,
            "document_title": document['title'],
            **checks,
            **results,
            "all_pdf_files": all_files[:20]  # Limit to 20 files
        }

    except Exception as e:
        logger.error(f"Debug error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/documents/{document_id}/chunks-bbox")
async def get_document_chunks_bbox(
    document_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Retrieve all chunks with bounding boxes for a document.

    Useful for:
    - Frontend PDF.js overlay implementation (alternative to backend annotation)
    - Debugging bbox extraction
    - API clients needing chunk position metadata

    Args:
        document_id: UUID of the document
        current_user: Authenticated user

    Returns:
        List of chunks with bbox metadata
    """
    try:
        async with database.db_pool.acquire() as conn:
            chunks = await conn.fetch(
                """
                SELECT
                    c.id,
                    c.chunk_index,
                    c.bbox,
                    (c.metadata->>'page_number')::integer as page_number,
                    c.content
                FROM chunks c
                WHERE c.document_id = $1::uuid
                AND c.bbox IS NOT NULL
                ORDER BY c.chunk_index
                """,
                UUID(document_id)
            )

        return {
            "document_id": document_id,
            "chunks_with_bbox": [
                {
                    "id": str(chunk['id']),
                    "chunk_index": chunk['chunk_index'],
                    "page_number": chunk['page_number'],
                    "bbox": json.loads(chunk['bbox']) if isinstance(chunk['bbox'], str) else chunk['bbox'],
                    "content_preview": chunk['content'][:200] + "..." if len(chunk['content']) > 200 else chunk['content']
                }
                for chunk in chunks
            ]
        }

    except Exception as e:
        logger.error(f"Error fetching chunks bbox: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
