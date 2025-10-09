"""
Image extraction and processing module for RAGFab.

This module handles:
- Image detection and extraction from DoclingDocument
- VLM analysis (description + OCR) via remote API
- Image storage (filesystem + base64 encoding)
- Metadata preservation (position, page number, etc.)
"""

import os
import logging
import base64
import io
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass
from PIL import Image
import httpx
import fitz  # PyMuPDF

from docling_core.types.doc import DoclingDocument, PictureItem
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class ImageMetadata:
    """Metadata for an extracted image."""
    page_number: int
    position: Dict[str, float]  # {x, y, width, height}
    image_path: str  # Relative path
    image_base64: str  # Encoded for inline display
    image_format: str  # png, jpeg
    image_size_bytes: int
    description: Optional[str] = None
    ocr_text: Optional[str] = None
    confidence_score: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class VLMClient:
    """Client for remote VLM API (OpenAI-compatible)."""

    def __init__(
        self,
        api_url: str,
        api_key: Optional[str] = None,
        model_name: str = "SmolDocling-256M",
        timeout: float = 60.0,
        prompt: str = "Décris cette image en détail en français. Extrais tout le texte visible."
    ):
        """
        Initialize VLM client.

        Args:
            api_url: Base URL of VLM API (e.g., https://api.com/v1)
            api_key: Optional API key
            model_name: Model to use
            timeout: Request timeout in seconds
            prompt: Prompt for image analysis
        """
        self.api_url = api_url.rstrip('/')
        self.api_key = api_key
        self.model_name = model_name
        self.timeout = timeout
        self.prompt = prompt

        logger.info(f"VLM Client initialized: {api_url}, model={model_name}")

    async def analyze_image(self, image_base64: str) -> Tuple[str, Optional[float]]:
        """
        Analyze image with VLM to get description and OCR text.

        Args:
            image_base64: Base64 encoded image

        Returns:
            Tuple of (combined_text, confidence_score)
        """
        # Decode base64 to bytes for multipart upload
        image_bytes = base64.b64decode(image_base64)

        # Prepare multipart form data
        files = {
            "image": ("image.png", io.BytesIO(image_bytes), "image/png")
        }
        data = {
            "temperature": 0.1  # Low temperature for consistent extraction
        }

        # Optional API key header
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        # Retry logic for rate limiting
        max_retries = 3
        base_delay = 2.0  # seconds

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.api_url}/extract-and-describe",
                        files=files,
                        data=data,
                        headers=headers
                    )

                    # Handle rate limiting (429)
                    if response.status_code == 429:
                        if attempt < max_retries - 1:
                            delay = base_delay * (2 ** attempt)  # Exponential backoff
                            logger.warning(f"Rate limited (429), retrying in {delay}s (attempt {attempt + 1}/{max_retries})")
                            await asyncio.sleep(delay)
                            continue
                        else:
                            logger.error("Max retries reached for rate limiting")
                            raise httpx.HTTPStatusError(
                                f"Rate limit exceeded after {max_retries} attempts",
                                request=response.request,
                                response=response
                            )

                    response.raise_for_status()

                    result = response.json()

                    # Extract description and OCR text from FastAPI response
                    # Response format: {"description": "...", "extracted_text": "...", "confidence": 0.95}
                    description = result.get("description", "")
                    ocr_text = result.get("extracted_text", "")

                    # Combine description and OCR text
                    combined_parts = []
                    if description:
                        combined_parts.append(f"Description: {description}")
                    if ocr_text:
                        combined_parts.append(f"Texte extrait: {ocr_text}")

                    content = "\n".join(combined_parts) if combined_parts else "[No content extracted]"

                    # Extract confidence if available
                    confidence = result.get("confidence", None)

                    return content, confidence

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < max_retries - 1:
                    continue  # Already handled above
                logger.error(f"VLM HTTP error: {e.response.status_code} - {e.response.text if hasattr(e.response, 'text') else 'No details'}")
                raise  # Re-raise for other errors
            except httpx.TimeoutException:
                logger.error(f"VLM API timeout after {self.timeout}s")
                return "[VLM Timeout]", None
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"VLM request failed, retrying: {e}")
                    await asyncio.sleep(base_delay)
                    continue
                logger.error(f"VLM analysis failed after {max_retries} attempts: {e}")
                return "[VLM Failed]", None

        # Should not reach here
        return "[VLM Failed]", None


class ImageProcessor:
    """Processor for extracting and analyzing images from documents."""

    def __init__(
        self,
        storage_path: str = "/app/uploads/images",
        max_size_mb: int = 10,
        image_quality: int = 85,
        output_format: str = "png",
        vlm_enabled: bool = False,
        vlm_client: Optional[VLMClient] = None
    ):
        """
        Initialize image processor.

        Args:
            storage_path: Base path for storing extracted images
            max_size_mb: Maximum image size in MB
            image_quality: JPEG quality (1-100)
            output_format: Output format (png, jpeg)
            vlm_enabled: Enable VLM analysis
            vlm_client: VLM client instance
        """
        self.storage_path = Path(storage_path)
        self.max_size_mb = max_size_mb
        self.image_quality = image_quality
        self.output_format = output_format.lower()
        self.vlm_enabled = vlm_enabled
        self.vlm_client = vlm_client

        # Create storage directory if needed
        self.storage_path.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"ImageProcessor initialized: "
            f"storage={storage_path}, "
            f"vlm_enabled={vlm_enabled}, "
            f"format={output_format}"
        )

    async def extract_images_from_document(
        self,
        docling_doc: DoclingDocument,
        job_id: str,
        pdf_path: Optional[str] = None
    ) -> List[ImageMetadata]:
        """
        Extract all images from a DoclingDocument.

        Args:
            docling_doc: Parsed document from Docling
            job_id: Unique job identifier for organizing images
            pdf_path: Optional path to original PDF for image extraction

        Returns:
            List of ImageMetadata objects
        """
        if not docling_doc:
            logger.warning("No DoclingDocument provided for image extraction")
            return []

        # Create job-specific directory
        job_dir = self.storage_path / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        extracted_images = []
        image_count = 0

        # DoclingDocument stores images in the 'pictures' list, not in pages
        if not hasattr(docling_doc, 'pictures'):
            logger.warning(f"DoclingDocument has no 'pictures' attribute. Type: {type(docling_doc)}")
            return []

        pictures = docling_doc.pictures
        if not pictures:
            logger.info("No pictures found in document")
            return []

        logger.info(f"Found {len(pictures)} pictures in document")

        # Process each PictureItem
        for idx, item in enumerate(pictures):
            if not isinstance(item, PictureItem):
                logger.warning(f"Item {idx} is not a PictureItem, skipping")
                continue

            # Extract page number from provenance if available
            page_num = 1  # Default
            if hasattr(item, 'prov') and item.prov:
                page_num = item.prov[0].page_no if item.prov else 1

            logger.debug(f"Processing picture {idx + 1}/{len(pictures)} from page {page_num}")

            try:
                image_metadata = await self._process_image(
                    picture_item=item,
                    page_number=page_num,
                    job_dir=job_dir,
                    image_index=image_count,
                    pdf_path=pdf_path
                )

                if image_metadata:
                    extracted_images.append(image_metadata)
                    image_count += 1

                # Add delay between images to avoid rate limiting
                if self.vlm_enabled and idx < len(pictures) - 1:  # Don't delay after last image
                    await asyncio.sleep(1.0)  # 1 second between VLM requests

            except Exception as e:
                logger.error(f"Failed to process image {idx + 1} from page {page_num}: {e}")
                continue

        logger.info(f"Extracted {len(extracted_images)} images from document (job: {job_id})")
        return extracted_images

    def _extract_image_from_pdf(
        self,
        pdf_path: str,
        page_number: int,
        picture_item: PictureItem
    ) -> Optional[Image.Image]:
        """
        Extract image from PDF using PyMuPDF at the coordinates specified by PictureItem.

        Args:
            pdf_path: Path to the PDF file
            page_number: Page number (1-indexed)
            picture_item: PictureItem with bbox coordinates

        Returns:
            PIL Image or None if extraction failed
        """
        try:
            # Open PDF
            doc = fitz.open(pdf_path)

            # Get page (PyMuPDF uses 0-indexed pages)
            page = doc[page_number - 1]

            # Get bbox from PictureItem provenance
            if not picture_item.prov or not picture_item.prov[0].bbox:
                logger.warning(f"No bbox in PictureItem for page {page_number}")
                return None

            bbox = picture_item.prov[0].bbox

            # Convert Docling bbox (BOTTOMLEFT origin) to PyMuPDF rect (TOPLEFT origin)
            # Docling: (l, t, r, b) from bottom-left
            # PyMuPDF: (x0, y0, x1, y1) from top-left
            page_height = page.rect.height
            rect = fitz.Rect(
                bbox.l,
                page_height - bbox.t,  # Convert from bottom-left to top-left
                bbox.r,
                page_height - bbox.b
            )

            # Extract image as pixmap
            pix = page.get_pixmap(clip=rect, dpi=150)

            # Convert pixmap to PIL Image
            img_data = pix.tobytes("png")
            pil_image = Image.open(io.BytesIO(img_data))

            doc.close()
            return pil_image

        except Exception as e:
            logger.error(f"Failed to extract image from PDF page {page_number}: {e}")
            return None

    async def _process_image(
        self,
        picture_item: PictureItem,
        page_number: int,
        job_dir: Path,
        image_index: int,
        pdf_path: Optional[str] = None
    ) -> Optional[ImageMetadata]:
        """
        Process a single image: save, encode, analyze.

        Args:
            picture_item: Docling PictureItem
            page_number: Page number in document
            job_dir: Directory for this job's images
            image_index: Index of this image
            pdf_path: Optional path to PDF for extracting images

        Returns:
            ImageMetadata or None if processing failed
        """
        # Generate filename
        image_filename = f"image_{image_index:03d}.{self.output_format}"
        image_path = job_dir / image_filename

        # Extract image data from PictureItem
        pil_image = None

        try:
            # Try Docling's embedded image data first
            if hasattr(picture_item, 'data') and picture_item.data:
                if isinstance(picture_item.data, bytes):
                    pil_image = Image.open(io.BytesIO(picture_item.data))
                else:
                    pil_image = picture_item.data
            elif hasattr(picture_item, 'image') and picture_item.image:
                pil_image = picture_item.image

            # If no embedded data, extract from PDF using bbox coordinates
            if not pil_image and pdf_path and os.path.exists(pdf_path):
                pil_image = self._extract_image_from_pdf(
                    pdf_path=pdf_path,
                    page_number=page_number,
                    picture_item=picture_item
                )

            if not pil_image:
                logger.warning(f"Failed to load image (page {page_number}, index {image_index})")
                return None

        except Exception as e:
            logger.error(f"Failed to extract image from PictureItem: {e}")
            return None

        # Check image size
        img_bytes = io.BytesIO()
        pil_image.save(img_bytes, format=self.output_format.upper(), quality=self.image_quality)
        img_bytes.seek(0)
        image_size_bytes = len(img_bytes.getvalue())

        # Skip if too large
        if image_size_bytes > self.max_size_mb * 1024 * 1024:
            logger.warning(
                f"Image too large ({image_size_bytes / 1024 / 1024:.2f}MB), "
                f"skipping (max: {self.max_size_mb}MB)"
            )
            return None

        # Save image to filesystem
        pil_image.save(image_path, format=self.output_format.upper(), quality=self.image_quality)
        logger.debug(f"Saved image: {image_path}")

        # Encode to base64 for inline display
        img_bytes.seek(0)
        image_base64 = base64.b64encode(img_bytes.getvalue()).decode('utf-8')

        # Get position from PictureItem bounding box
        bbox = picture_item.prov[0].bbox if picture_item.prov else None
        position = {
            "x": bbox.l if bbox else 0,
            "y": bbox.t if bbox else 0,
            "width": bbox.width if bbox else 0,
            "height": bbox.height if bbox else 0
        }

        # Analyze with VLM if enabled
        description = None
        ocr_text = None
        confidence = None

        if self.vlm_enabled and self.vlm_client:
            try:
                logger.debug(f"Analyzing image {image_index} with VLM...")
                combined_text, confidence = await self.vlm_client.analyze_image(image_base64)

                # Split description and OCR (simplified - VLM returns combined text)
                # In production, you might want to use structured output or parsing
                description = combined_text
                ocr_text = combined_text  # VLM output includes both description and text

                logger.info(f"VLM analysis complete for image {image_index}")

            except Exception as e:
                logger.error(f"VLM analysis failed for image {image_index}: {e}")

        # Create metadata object
        relative_path = f"images/{job_dir.name}/{image_filename}"

        return ImageMetadata(
            page_number=page_number,
            position=position,
            image_path=relative_path,
            image_base64=image_base64,
            image_format=self.output_format,
            image_size_bytes=image_size_bytes,
            description=description,
            ocr_text=ocr_text,
            confidence_score=confidence,
            metadata={
                "image_index": image_index,
                "original_width": pil_image.width,
                "original_height": pil_image.height
            }
        )


def create_image_processor() -> Optional[ImageProcessor]:
    """
    Factory function to create ImageProcessor from environment variables.

    Returns:
        ImageProcessor instance or None if VLM is disabled
    """
    vlm_enabled = os.getenv("VLM_ENABLED", "false").lower() == "true"

    if not vlm_enabled:
        logger.info("VLM disabled, image extraction will be skipped")
        return None

    # VLM configuration
    vlm_api_url = os.getenv("VLM_API_URL", "")
    vlm_api_key = os.getenv("VLM_API_KEY", "")
    vlm_model = os.getenv("VLM_MODEL_NAME", "SmolDocling-256M")
    vlm_timeout = float(os.getenv("VLM_TIMEOUT", "60.0"))
    vlm_prompt = os.getenv(
        "VLM_PROMPT",
        "Décris cette image en détail en français. Extrais tout le texte visible."
    )

    if not vlm_api_url:
        logger.warning("VLM_ENABLED=true but VLM_API_URL not set, disabling image extraction")
        return None

    # Create VLM client
    vlm_client = VLMClient(
        api_url=vlm_api_url,
        api_key=vlm_api_key if vlm_api_key else None,
        model_name=vlm_model,
        timeout=vlm_timeout,
        prompt=vlm_prompt
    )

    # Image processing configuration
    storage_path = os.getenv("IMAGE_STORAGE_PATH", "/app/uploads/images")
    max_size_mb = int(os.getenv("IMAGE_MAX_SIZE_MB", "10"))
    image_quality = int(os.getenv("IMAGE_QUALITY", "85"))
    output_format = os.getenv("IMAGE_OUTPUT_FORMAT", "png")

    return ImageProcessor(
        storage_path=storage_path,
        max_size_mb=max_size_mb,
        image_quality=image_quality,
        output_format=output_format,
        vlm_enabled=True,
        vlm_client=vlm_client
    )
