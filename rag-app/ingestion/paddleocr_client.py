"""
PaddleOCR-VL client for local OCR and image analysis.

This module provides a wrapper around PaddleOCR for:
- Multilingual OCR (109 languages supported)
- Layout detection (tables, figures, text blocks)
- Fast local processing (no API calls needed)
- High accuracy for technical documents and screenshots

PaddleOCR-VL is optimized for documents with structured text (menus, buttons, code),
making it ideal for software screenshots and technical documentation.
"""

import os
import logging
import base64
import io
from typing import Tuple, Optional
import numpy as np
from PIL import Image
from dotenv import load_dotenv

# PaddleOCR imports - handle import errors gracefully
try:
    from paddleocr import PaddleOCR
    PADDLEOCR_AVAILABLE = True
except ImportError:
    PADDLEOCR_AVAILABLE = False
    logging.warning(
        "PaddleOCR not installed. Install with: pip install paddleocr paddlepaddle"
    )

load_dotenv()

logger = logging.getLogger(__name__)


class PaddleOCRVLClient:
    """
    Local PaddleOCR-VL client for image analysis.

    Features:
    - Multilingual OCR (109 languages including French, English)
    - Layout detection and structure analysis
    - Local processing (no API calls, faster than VLM API)
    - Optimized for technical documents and screenshots

    Configuration via environment variables:
    - PADDLEOCR_USE_GPU: Enable GPU acceleration (default: false)
    - PADDLEOCR_LANG: OCR language(s), comma-separated (default: 'fr')
    - PADDLEOCR_SHOW_LOG: Show PaddleOCR logs (default: false)
    """

    def __init__(
        self,
        lang: Optional[str] = None,
        use_gpu: Optional[bool] = None,
        show_log: Optional[bool] = None
    ):
        """
        Initialize PaddleOCR-VL client.

        Args:
            lang: OCR language ('fr', 'en', 'ch', etc.). Falls back to env PADDLEOCR_LANG
            use_gpu: Use GPU acceleration. Falls back to env PADDLEOCR_USE_GPU
            show_log: Show PaddleOCR debug logs. Falls back to env PADDLEOCR_SHOW_LOG
        """
        if not PADDLEOCR_AVAILABLE:
            raise ImportError(
                "PaddleOCR not installed. Install with: "
                "pip install paddleocr paddlepaddle"
            )

        # Configuration from params or environment
        self.lang = lang or os.getenv("PADDLEOCR_LANG", "fr")
        self.use_gpu = (
            use_gpu
            if use_gpu is not None
            else os.getenv("PADDLEOCR_USE_GPU", "false").lower() == "true"
        )
        self.show_log = (
            show_log
            if show_log is not None
            else os.getenv("PADDLEOCR_SHOW_LOG", "false").lower() == "true"
        )

        # Initialize PaddleOCR
        # Note: PaddleOCR 2.7+ has a simplified API
        # - GPU auto-detected via PaddlePaddle backend (paddlepaddle vs paddlepaddle-gpu)
        # - Many parameters removed (use_gpu, show_log, max_text_length)
        logger.info(
            f"Initializing PaddleOCR-VL: lang={self.lang} "
            f"(GPU auto-detected by PaddlePaddle)"
        )

        try:
            # PaddleOCR 2.7+ minimal configuration
            # Only core parameters are supported
            self.ocr = PaddleOCR(
                use_angle_cls=True,  # Auto rotation for angled text
                lang=self.lang,  # Language model (e.g., 'fr', 'en')
            )

            # Log backend info
            backend = "GPU" if self.use_gpu else "CPU"
            logger.info(f"✅ PaddleOCR-VL initialized successfully (backend: {backend})")
        except Exception as e:
            logger.error(f"Failed to initialize PaddleOCR: {e}")
            raise

    async def analyze_image(
        self,
        image_base64: str
    ) -> Tuple[str, str, Optional[float]]:
        """
        Analyze image with PaddleOCR-VL.

        Performs OCR to extract text and generates a basic structural description.
        PaddleOCR excels at text extraction but provides simpler descriptions
        compared to VLM models like InternVL.

        Args:
            image_base64: Base64 encoded image

        Returns:
            Tuple of (description, ocr_text, confidence_score)
            - description: Basic structural description of the image
            - ocr_text: Extracted text from OCR
            - confidence_score: Average confidence of OCR results (0.0-1.0)

        Raises:
            ValueError: If image cannot be decoded
            RuntimeError: If PaddleOCR processing fails
        """
        try:
            # Decode base64 to image
            image_bytes = base64.b64decode(image_base64)
            image = Image.open(io.BytesIO(image_bytes))

            # Convert to numpy array for PaddleOCR
            image_np = np.array(image)

            # Run OCR (synchronous - PaddleOCR doesn't support async)
            result = self.ocr.ocr(image_np, cls=True)

            # Extract text lines and confidence scores
            texts = []
            confidences = []

            if result and result[0]:
                for line in result[0]:
                    # PaddleOCR result format: [[box], (text, confidence)]
                    text = line[1][0]
                    conf = line[1][1]
                    texts.append(text)
                    confidences.append(conf)

            # Combine extracted texts
            ocr_text = "\n".join(texts) if texts else ""

            # Calculate average confidence
            avg_confidence = (
                sum(confidences) / len(confidences)
                if confidences
                else 0.0
            )

            # Generate basic structural description
            # PaddleOCR focuses on OCR, not semantic description
            if texts:
                description = (
                    f"Document avec {len(texts)} ligne(s) de texte. "
                    f"Confiance moyenne: {avg_confidence:.1%}"
                )
            else:
                description = "Image sans texte détectable"

            logger.debug(
                f"PaddleOCR extracted {len(texts)} text lines "
                f"(avg confidence: {avg_confidence:.2f})"
            )

            return description, ocr_text, avg_confidence

        except base64.binascii.Error as e:
            logger.error(f"Failed to decode base64 image: {e}")
            raise ValueError(f"Invalid base64 image data: {e}")

        except Exception as e:
            logger.error(f"PaddleOCR processing failed: {e}")
            raise RuntimeError(f"PaddleOCR analysis error: {e}")

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"PaddleOCRVLClient(lang={self.lang}, "
            f"gpu={self.use_gpu}, show_log={self.show_log})"
        )
