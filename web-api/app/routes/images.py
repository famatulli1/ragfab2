"""
Routes pour la gestion des images extraites des documents.
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List
from uuid import UUID
import json

from ..database import get_db_connection
from ..models import ImageMetadata, ImageResponse
from ..auth import get_current_user

router = APIRouter()


@router.get("/chunks/{chunk_id}/images", response_model=List[ImageResponse])
async def get_chunk_images(
    chunk_id: UUID,
    current_user=Depends(get_current_user)
):
    """
    Get all images associated with a specific chunk.

    Args:
        chunk_id: UUID of the chunk

    Returns:
        List of images linked to this chunk
    """
    async with get_db_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT
                id, page_number, position, description, ocr_text,
                image_base64, confidence_score
            FROM document_images
            WHERE chunk_id = $1::uuid
            ORDER BY page_number, (position->>'y')::float
            """,
            str(chunk_id)
        )

        if not rows:
            return []

        images = []
        for row in rows:
            images.append(ImageResponse(
                id=row["id"],
                page_number=row["page_number"],
                position=json.loads(row["position"]),
                description=row["description"],
                ocr_text=row["ocr_text"],
                image_base64=row["image_base64"]
            ))

        return images


@router.get("/documents/{document_id}/images", response_model=List[ImageMetadata])
async def get_document_images(
    document_id: UUID,
    current_user=Depends(get_current_user)
):
    """
    Get all images from a specific document.

    Args:
        document_id: UUID of the document

    Returns:
        List of all images in this document
    """
    async with get_db_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT
                id, document_id, chunk_id, page_number, position,
                image_path, image_base64, image_format, image_size_bytes,
                description, ocr_text, confidence_score, metadata, created_at
            FROM document_images
            WHERE document_id = $1::uuid
            ORDER BY page_number, (position->>'y')::float
            """,
            str(document_id)
        )

        if not rows:
            return []

        images = []
        for row in rows:
            images.append(ImageMetadata(
                id=row["id"],
                document_id=row["document_id"],
                chunk_id=row["chunk_id"],
                page_number=row["page_number"],
                position=json.loads(row["position"]),
                image_path=row["image_path"],
                image_base64=row["image_base64"],
                image_format=row["image_format"],
                image_size_bytes=row["image_size_bytes"],
                description=row["description"],
                ocr_text=row["ocr_text"],
                confidence_score=row["confidence_score"],
                metadata=json.loads(row["metadata"]) if row["metadata"] else None,
                created_at=row["created_at"]
            ))

        return images


@router.get("/images/{image_id}", response_model=ImageMetadata)
async def get_image(
    image_id: UUID,
    current_user=Depends(get_current_user)
):
    """
    Get a specific image by ID.

    Args:
        image_id: UUID of the image

    Returns:
        Image metadata
    """
    async with get_db_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                id, document_id, chunk_id, page_number, position,
                image_path, image_base64, image_format, image_size_bytes,
                description, ocr_text, confidence_score, metadata, created_at
            FROM document_images
            WHERE id = $1::uuid
            """,
            str(image_id)
        )

        if not row:
            raise HTTPException(status_code=404, detail="Image not found")

        return ImageMetadata(
            id=row["id"],
            document_id=row["document_id"],
            chunk_id=row["chunk_id"],
            page_number=row["page_number"],
            position=json.loads(row["position"]),
            image_path=row["image_path"],
            image_base64=row["image_base64"],
            image_format=row["image_format"],
            image_size_bytes=row["image_size_bytes"],
            description=row["description"],
            ocr_text=row["ocr_text"],
            confidence_score=row["confidence_score"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else None,
            created_at=row["created_at"]
        )
