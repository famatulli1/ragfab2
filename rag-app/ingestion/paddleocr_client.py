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
            logger.info("🔍 PaddleOCR: Starting image analysis...")

            # Decode base64 to image
            image_bytes = base64.b64decode(image_base64)
            image = Image.open(io.BytesIO(image_bytes))
            logger.debug(f"Image decoded: size={image.size}, mode={image.mode}")

            # Convert to numpy array for PaddleOCR
            image_np = np.array(image)
            logger.debug(f"Image converted to numpy: shape={image_np.shape}")

            # Run OCR (synchronous - PaddleOCR doesn't support async)
            # PaddleOCR 3.x API: ocr() method returns tuple (status, result)
            # status = 0 for success
            # result = list of detected text items
            logger.info("🔄 PaddleOCR: Running OCR...")
            ocr_output = self.ocr.ocr(image_np)
            logger.info(f"OCR output type: {type(ocr_output)}, content: {ocr_output}")

            # Extract text lines and confidence scores
            texts = []
            confidences = []

            # Handle PaddleOCR 3.x output format
            # Can be either:
            # 1. Tuple: (status_code, results) where status_code=0 for success
            # 2. List: [[...]] for direct results
            page_results = None

            if isinstance(ocr_output, tuple) and len(ocr_output) >= 2:
                # Format: (0, [[box, (text, conf)], ...])
                status_code = ocr_output[0]
                page_results = ocr_output[1]
                logger.info(f"📊 Tuple format detected: status={status_code}, results type={type(page_results)}")
            elif isinstance(ocr_output, list) and len(ocr_output) > 0:
                # Format: [[box, (text, conf)], ...]
                page_results = ocr_output[0] if ocr_output else None
                logger.info(f"📊 List format detected: results type={type(page_results)}")
            else:
                logger.warning(f"⚠️ Unexpected OCR output format: {type(ocr_output)}")

            # Debug: Log first few items to understand structure
            if page_results:
                if isinstance(page_results, (list, tuple)) and len(page_results) > 0:
                    logger.info(f"🔍 Page results count: {len(page_results)}")
                    logger.info(f"🔍 First result item type: {type(page_results[0])}")
                    logger.info(f"🔍 First result item: {page_results[0]}")
                    if len(page_results) > 1:
                        logger.info(f"🔍 Second result item: {page_results[1]}")
                else:
                    logger.warning(f"⚠️ Page results not indexable: type={type(page_results)}, value={page_results}")

                if page_results:
                    for idx, line in enumerate(page_results):
                        # Each line: [box_coords, (text, confidence)]
                        logger.debug(f"Processing line {idx}: type={type(line)}, content={line}")

                        if len(line) >= 2:
                            text_info = line[1]  # (text, confidence)
                            if isinstance(text_info, (tuple, list)) and len(text_info) >= 2:
                                text = text_info[0]
                                confidence = text_info[1]

                                if text:
                                    texts.append(str(text))
                                    confidences.append(float(confidence))
                                    logger.debug(f"✅ Line {idx}: '{text}' (confidence: {confidence:.2f})")
                            else:
                                logger.warning(f"❌ Line {idx}: Unexpected text_info format: {text_info} (type: {type(text_info)})")
                        else:
                            logger.warning(f"❌ Line {idx}: Unexpected line format (length={len(line)}): {line}")
                else:
                    logger.warning("⚠️ Page results is None or empty")
            else:
                logger.warning(f"⚠️ OCR result is empty or None: {result}")

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
                logger.info(f"✅ PaddleOCR extracted {len(texts)} text lines (avg confidence: {avg_confidence:.1%})")
            else:
                description = "Image sans texte détectable"
                logger.warning("❌ PaddleOCR found no text in image")

            logger.debug(
                f"PaddleOCR 3.x extracted {len(texts)} text lines "
                f"(avg confidence: {avg_confidence:.2f})"
            )

            return description, ocr_text, avg_confidence

        except base64.binascii.Error as e:
            logger.error(f"Failed to decode base64 image: {e}")
            raise ValueError(f"Invalid base64 image data: {e}")

        except Exception as e:
            logger.error(f"PaddleOCR 3.x processing failed: {e}", exc_info=True)
            raise RuntimeError(f"PaddleOCR 3.x analysis error: {e}")

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"PaddleOCRVLClient(lang={self.lang}, version=3.x, gpu=auto-detected)"
