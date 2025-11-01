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
            # PaddleOCR 3.x API: ocr() method returns list of pages
            # Each page is a list of lines: [([[bbox]], (text, confidence)), ...]
            logger.info("🔄 PaddleOCR: Running OCR...")
            ocr_output = self.ocr.ocr(image_np)
            logger.debug(f"OCR output type: {type(ocr_output)}")

            # Extract text lines and confidence scores
            texts = []
            confidences = []

            # Handle PaddleOCR 3.x output format
            # Format: List of pages, each page is a list of lines
            # Each line: ([[x1,y1], [x2,y2], [x3,y3], [x4,y4]], (text, confidence))

            if isinstance(ocr_output, list):
                # PaddleOCR 3.x returns list of pages
                logger.info(f"📊 List format detected: {len(ocr_output)} page(s)")

                for page_idx, page_result in enumerate(ocr_output):
                    if page_result is None:
                        logger.warning(f"⚠️ Page {page_idx} has no OCR results")
                        continue

                    if not isinstance(page_result, list):
                        logger.warning(f"⚠️ Page {page_idx} unexpected format: {type(page_result)}")
                        continue

                    logger.info(f"📄 Page {page_idx}: {len(page_result)} lines detected")

                    for line_idx, line in enumerate(page_result):
                        try:
                            # Each line is a tuple: (bbox, (text, confidence))
                            if not isinstance(line, (list, tuple)) or len(line) < 2:
                                logger.warning(f"⚠️ Line {line_idx} unexpected structure: {line}")
                                continue

                            bbox, text_info = line[0], line[1]

                            # text_info should be (text, confidence)
                            if isinstance(text_info, (list, tuple)) and len(text_info) >= 2:
                                text, confidence = text_info[0], text_info[1]

                                if text and isinstance(text, str) and len(text.strip()) > 0:
                                    texts.append(text.strip())
                                    confidences.append(float(confidence))
                                    logger.debug(f"✅ Page {page_idx}, Line {line_idx}: '{text[:50]}...' (conf: {confidence:.2f})")
                            else:
                                logger.warning(f"⚠️ Line {line_idx} text_info unexpected: {text_info}")

                        except Exception as e:
                            logger.warning(f"⚠️ Error parsing line {line_idx}: {e}")
                            continue

            # Fallback: try OCRResult object format (PaddleX or older PaddleOCR)
            elif hasattr(ocr_output, '__class__') and 'OCRResult' in str(type(ocr_output)):
                logger.info(f"📊 OCRResult object detected: {type(ocr_output)}")
                logger.debug(f"Available attributes: {[attr for attr in dir(ocr_output) if not attr.startswith('_')]}")

                # Try multiple attribute patterns for different PaddleX/PaddleOCR versions
                # Pattern 1: rec_texts, rec_scores (PaddleOCR 2.x style)
                if hasattr(ocr_output, 'rec_texts') and hasattr(ocr_output, 'rec_scores'):
                    rec_texts = ocr_output.rec_texts
                    rec_scores = ocr_output.rec_scores
                    logger.info(f"Using rec_texts/rec_scores attributes: {len(rec_texts)} lines")

                    for idx, (text, score) in enumerate(zip(rec_texts, rec_scores)):
                        if text and isinstance(text, str):
                            texts.append(text)
                            confidences.append(float(score))

                # Pattern 2: Try accessing as list-like with __getitem__ (PaddleX might use this)
                elif hasattr(ocr_output, '__iter__') and not isinstance(ocr_output, str):
                    logger.info("Trying to iterate OCRResult object")
                    try:
                        for page_result in ocr_output:
                            if page_result and hasattr(page_result, '__iter__'):
                                for line in page_result:
                                    if isinstance(line, (list, tuple)) and len(line) >= 2:
                                        bbox, text_info = line[0], line[1]
                                        if isinstance(text_info, (list, tuple)) and len(text_info) >= 2:
                                            text, confidence = text_info[0], text_info[1]
                                            if text and isinstance(text, str):
                                                texts.append(text.strip())
                                                confidences.append(float(confidence))
                    except Exception as e:
                        logger.warning(f"Failed to iterate OCRResult: {e}")

                # Pattern 3: Check for common PaddleX attributes
                elif hasattr(ocr_output, 'boxes') and hasattr(ocr_output, 'texts'):
                    logger.info("Using boxes/texts attributes (PaddleX format)")
                    ocr_texts = ocr_output.texts if hasattr(ocr_output, 'texts') else []
                    ocr_scores = ocr_output.scores if hasattr(ocr_output, 'scores') else [1.0] * len(ocr_texts)

                    for text, score in zip(ocr_texts, ocr_scores):
                        if text and isinstance(text, str):
                            texts.append(text)
                            confidences.append(float(score) if isinstance(score, (int, float)) else 1.0)

                else:
                    logger.warning(f"⚠️ OCRResult object has no recognized attributes")
                    logger.warning(f"Available: {[attr for attr in dir(ocr_output) if not attr.startswith('_')]}")

            else:
                logger.warning(f"⚠️ Unexpected OCR output format: {type(ocr_output)}")
                logger.warning(f"⚠️ Available attributes: {dir(ocr_output) if hasattr(ocr_output, '__dir__') else 'N/A'}")

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
