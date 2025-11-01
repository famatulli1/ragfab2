"""
PaddleOCR-VL client for local OCR and image analysis.

This module provides a wrapper around PaddleOCR 3.x for:
- Multilingual OCR (109 languages supported)
- Layout detection (tables, figures, text blocks)
- Fast local processing (no API calls needed)
- High accuracy for technical documents and screenshots

PaddleOCR-VL is optimized for documents with structured text (menus, buttons, code),
making it ideal for software screenshots and technical documentation.

Requires:
- paddleocr>=3.0.0
- paddlepaddle==3.2.0 (Python 3.11 compatible)
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
        "PaddleOCR not installed. Install with: "
        "pip install paddleocr>=3.0.0 paddlepaddle==3.2.0"
    )

load_dotenv()

logger = logging.getLogger(__name__)


class PaddleOCRVLClient:
    """
    Local PaddleOCR-VL client for image analysis (PaddleOCR 3.x API).

    Features:
    - Multilingual OCR (109 languages including French, English)
    - Layout detection and structure analysis
    - Local processing (no API calls, faster than VLM API)
    - Optimized for technical documents and screenshots
    - GPU auto-detection (no manual configuration needed)

    Configuration via environment variables:
    - PADDLEOCR_LANG: OCR language(s) (default: 'fr')

    Note: GPU acceleration is auto-detected by PaddlePaddle in version 3.x
    """

    def __init__(
        self,
        lang: Optional[str] = None
    ):
        """
        Initialize PaddleOCR 3.x client.

        Args:
            lang: OCR language ('fr', 'en', 'ch', etc.). Falls back to env PADDLEOCR_LANG

        Note: GPU acceleration is automatically detected by PaddlePaddle 3.x
        """
        if not PADDLEOCR_AVAILABLE:
            raise ImportError(
                "PaddleOCR not installed. Install with: "
                "pip install paddleocr>=3.0.0 paddlepaddle==3.2.0"
            )

        # Configuration from params or environment
        self.lang = lang or os.getenv("PADDLEOCR_LANG", "fr")

        # Initialize PaddleOCR 3.x (simplified API)
        logger.info(f"Initializing PaddleOCR 3.x: lang={self.lang} (GPU auto-detected)")

        try:
            # PaddleOCR 3.x simplified initialization
            # GPU is automatically detected, no need for use_gpu parameter
            self.ocr = PaddleOCR(lang=self.lang)
            logger.info("✅ PaddleOCR 3.x initialized successfully (local processing, GPU auto-detected)")
        except Exception as e:
            logger.error(f"Failed to initialize PaddleOCR 3.x: {e}")
            raise

    async def analyze_image(
        self,
        image_base64: str
    ) -> Tuple[str, str, Optional[float]]:
        """
        Analyze image with PaddleOCR 3.x.

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
            # PaddleOCR 3.x: use ocr() method (compatible with 2.x)
            result = self.ocr.ocr(image_np)

            # Extract text lines and confidence scores
            texts = []
            confidences = []

            # PaddleOCR 3.x result format: same as 2.x
            # result[0] is a list of detection results
            # Each result is [[box_coordinates], (text, confidence)]
            if result and result[0]:
                for line in result[0]:
                    try:
                        # line[0] = box coordinates [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                        # line[1] = (text, confidence) or [text, confidence]
                        text_data = line[1]

                        # Extract text and confidence (works for both tuple and list)
                        if isinstance(text_data, (list, tuple)) and len(text_data) >= 2:
                            text = str(text_data[0])
                            conf = float(text_data[1])
                            texts.append(text)
                            confidences.append(conf)
                        else:
                            logger.warning(f"Unexpected result format: {text_data}")
                    except (IndexError, TypeError, ValueError) as e:
                        logger.warning(f"Failed to parse line: {line}, error: {e}")
                        continue

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
                f"PaddleOCR 3.x extracted {len(texts)} text lines "
                f"(avg confidence: {avg_confidence:.2f})"
            )

            return description, ocr_text, avg_confidence

        except base64.binascii.Error as e:
            logger.error(f"Failed to decode base64 image: {e}")
            raise ValueError(f"Invalid base64 image data: {e}")

        except Exception as e:
            logger.error(f"PaddleOCR 3.x processing failed: {e}")
            raise RuntimeError(f"PaddleOCR 3.x analysis error: {e}")

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"PaddleOCRVLClient(lang={self.lang}, version=3.x, gpu=auto-detected)"
