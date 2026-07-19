"""OCR fallback for scanned / image-only resume PDFs.

Primary path is local PaddleOCR (cheap). Expensive Bedrock vision OCR is
kept only as a fallback when local OCR fails.
"""

from __future__ import annotations

import io
import logging
from functools import lru_cache

from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import get_settings
from app.parser.exceptions import ExtractionError

logger = logging.getLogger(__name__)

_MIN_USEFUL_CHARS = 40
_RENDER_SCALE = 2.0  # Higher DPI improves OCR accuracy on resumes

_AUTO_PROVIDER_ORDER = ("paddleocr", "tesseract", "bedrock", "textract")
_SUPPORTED_PROVIDERS = frozenset(_AUTO_PROVIDER_ORDER)


def needs_ocr(text: str) -> bool:
    """Return True when extracted text is empty or too sparse to be useful."""
    if not text or not text.strip():
        return True
    alnum = sum(1 for ch in text if ch.isalnum())
    return alnum < _MIN_USEFUL_CHARS


def _render_pdf_pages(file_content: bytes) -> list[bytes]:
    """Render each PDF page to PNG bytes for OCR."""
    import fitz  # PyMuPDF

    images: list[bytes] = []
    matrix = fitz.Matrix(_RENDER_SCALE, _RENDER_SCALE)

    with fitz.open(stream=file_content, filetype="pdf") as doc:
        if len(doc) == 0:
            raise ExtractionError("PDF has no pages for OCR")

        for index, page in enumerate(doc):
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            png_bytes = pixmap.tobytes("png")
            images.append(png_bytes)
            logger.debug(
                "Rendered PDF page %d for OCR (%d bytes PNG)",
                index + 1,
                len(png_bytes),
            )

    return images


def _png_to_numpy(image_bytes: bytes):
    """Decode PNG bytes into an RGB numpy array."""
    import numpy as np
    from PIL import Image

    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    return np.array(image)


@lru_cache(maxsize=1)
def _get_paddle_ocr():
    """Return a cached PaddleOCR engine instance."""
    try:
        from paddleocr import PaddleOCR
    except ImportError as exc:
        raise ExtractionError(
            "PaddleOCR is not installed. Run: pip install paddlepaddle paddleocr"
        ) from exc

    # Compatible with PaddleOCR 2.x and 3.x constructor kwargs.
    try:
        engine = PaddleOCR(
            lang="en",
            use_angle_cls=True,
            show_log=False,
        )
    except TypeError:
        engine = PaddleOCR(lang="en")

    logger.info("PaddleOCR engine initialised (lang=en)")
    return engine


def _extract_lines_from_paddle_result(result: object) -> list[str]:
    """Normalize PaddleOCR 2.x / 3.x result shapes into plain text lines."""
    lines: list[str] = []

    if result is None:
        return lines

    # PaddleOCR 3.x predict() often returns list[dict]-like objects.
    if isinstance(result, list) and result and isinstance(result[0], dict):
        for item in result:
            texts = item.get("rec_texts") or item.get("texts") or []
            for text in texts:
                cleaned = str(text).strip()
                if cleaned:
                    lines.append(cleaned)
        if lines:
            return lines

    # PaddleOCR 2.x: result = [ [ [box, (text, conf)], ... ] ] per image
    pages = result if isinstance(result, list) else [result]
    for page in pages:
        if not page:
            continue
        if isinstance(page, dict):
            texts = page.get("rec_texts") or page.get("texts") or []
            for text in texts:
                cleaned = str(text).strip()
                if cleaned:
                    lines.append(cleaned)
            continue

        for entry in page:
            if not entry or len(entry) < 2:
                continue
            text_info = entry[1]
            if isinstance(text_info, (list, tuple)) and text_info:
                cleaned = str(text_info[0]).strip()
            else:
                cleaned = str(text_info).strip()
            if cleaned:
                lines.append(cleaned)

    return lines


def _ocr_with_paddleocr(file_content: bytes) -> str:
    """Local OCR using PaddleOCR (primary, low-cost path)."""
    engine = _get_paddle_ocr()
    page_images = _render_pdf_pages(file_content)
    page_texts: list[str] = []

    for index, image_bytes in enumerate(page_images):
        image_array = _png_to_numpy(image_bytes)

        try:
            if hasattr(engine, "ocr"):
                raw = engine.ocr(image_array, cls=True)
            else:
                raw = engine.predict(image_array)
        except TypeError:
            # Some versions do not accept cls=
            if hasattr(engine, "ocr"):
                raw = engine.ocr(image_array)
            else:
                raw = engine.predict(image_array)

        lines = _extract_lines_from_paddle_result(raw)
        page_text = "\n".join(lines).strip()

        if page_text:
            page_texts.append(page_text)
            logger.info(
                "PaddleOCR page %d/%d extracted %d chars",
                index + 1,
                len(page_images),
                len(page_text),
            )
        else:
            logger.warning(
                "PaddleOCR page %d/%d returned no text",
                index + 1,
                len(page_images),
            )

    return "\n\n".join(page_texts)


@lru_cache(maxsize=1)
def _get_textract_client():
    """Return a configured Textract client (singleton)."""
    settings = get_settings()
    if not settings.aws_access_key_id or not settings.aws_secret_access_key:
        raise ExtractionError(
            "OCR via Textract requires AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY"
        )

    import boto3

    client = boto3.client(
        "textract",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )
    logger.info("Textract OCR client initialised (region=%s)", settings.aws_region)
    return client


def _ocr_image_with_textract(image_bytes: bytes) -> str:
    """Run Textract DetectDocumentText on a single PNG/JPEG image."""
    client = _get_textract_client()
    response = client.detect_document_text(Document={"Bytes": image_bytes})

    lines: list[str] = []
    for block in response.get("Blocks", []):
        if block.get("BlockType") == "LINE" and block.get("Text"):
            lines.append(block["Text"].strip())

    return "\n".join(line for line in lines if line)


def _ocr_with_textract(file_content: bytes) -> str:
    """OCR a PDF by rendering pages and calling Textract per page."""
    page_images = _render_pdf_pages(file_content)
    page_texts: list[str] = []

    for index, image_bytes in enumerate(page_images):
        try:
            page_text = _ocr_image_with_textract(image_bytes)
        except ClientError as exc:
            error = exc.response.get("Error", {})
            code = error.get("Code", "ClientError")
            message = error.get("Message", str(exc))
            raise ExtractionError(
                f"Textract OCR failed on page {index + 1} ({code}): {message}"
            ) from exc
        except BotoCoreError as exc:
            raise ExtractionError(
                f"Textract connection error on page {index + 1}: {exc}"
            ) from exc

        if page_text.strip():
            page_texts.append(page_text.strip())
            logger.info(
                "Textract OCR page %d/%d extracted %d chars",
                index + 1,
                len(page_images),
                len(page_text),
            )
        else:
            logger.warning(
                "Textract OCR page %d/%d returned no text",
                index + 1,
                len(page_images),
            )

    return "\n\n".join(page_texts)


_BEDROCK_OCR_PROMPT = (
    "Extract all readable text from this resume page exactly as written. "
    "Preserve natural line breaks and section order. "
    "Do not summarize, translate, or invent missing content. "
    "Return plain text only — no markdown fences."
)


def _ocr_with_bedrock(file_content: bytes) -> str:
    """OCR via Bedrock multimodal Converse (expensive fallback)."""
    settings = get_settings()
    if not settings.aws_access_key_id or not settings.aws_secret_access_key:
        raise ExtractionError(
            "OCR via Bedrock requires AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY"
        )

    import boto3

    client = boto3.client(
        "bedrock-runtime",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )

    page_images = _render_pdf_pages(file_content)
    page_texts: list[str] = []

    for index, image_bytes in enumerate(page_images):
        try:
            response = client.converse(
                modelId=settings.bedrock_model_id,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "image": {
                                    "format": "png",
                                    "source": {"bytes": image_bytes},
                                }
                            },
                            {"text": _BEDROCK_OCR_PROMPT},
                        ],
                    }
                ],
                inferenceConfig={"temperature": 0.0, "maxTokens": 4096},
            )
        except ClientError as exc:
            error = exc.response.get("Error", {})
            code = error.get("Code", "ClientError")
            message = error.get("Message", str(exc))
            raise ExtractionError(
                f"Bedrock OCR failed on page {index + 1} ({code}): {message}"
            ) from exc
        except BotoCoreError as exc:
            raise ExtractionError(
                f"Bedrock OCR connection error on page {index + 1}: {exc}"
            ) from exc

        content = (
            response.get("output", {})
            .get("message", {})
            .get("content", [])
        )
        text_parts = [
            block.get("text", "").strip()
            for block in content
            if isinstance(block, dict) and block.get("text")
        ]
        page_text = "\n".join(part for part in text_parts if part).strip()

        if page_text:
            page_texts.append(page_text)
            logger.info(
                "Bedrock OCR page %d/%d extracted %d chars",
                index + 1,
                len(page_images),
                len(page_text),
            )
        else:
            logger.warning(
                "Bedrock OCR page %d/%d returned no text",
                index + 1,
                len(page_images),
            )

    return "\n\n".join(page_texts)


def _ocr_with_tesseract(file_content: bytes) -> str:
    """Optional local OCR fallback using pytesseract (if installed)."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise ExtractionError(
            "Local OCR fallback unavailable. Install pytesseract and Pillow, "
            "and ensure the Tesseract binary is on PATH."
        ) from exc

    page_images = _render_pdf_pages(file_content)
    page_texts: list[str] = []

    for index, image_bytes in enumerate(page_images):
        image = Image.open(io.BytesIO(image_bytes))
        page_text = pytesseract.image_to_string(image) or ""
        if page_text.strip():
            page_texts.append(page_text.strip())
            logger.info(
                "Tesseract OCR page %d/%d extracted %d chars",
                index + 1,
                len(page_images),
                len(page_text),
            )

    return "\n\n".join(page_texts)


def ocr_pdf_to_text(file_content: bytes) -> str:
    """Extract text from a scanned/image-only PDF via OCR.

    Provider selection (``OCR_PROVIDER``):
    - ``auto`` (default): PaddleOCR → Tesseract → Bedrock → Textract
    - ``paddleocr``: local PaddleOCR (preferred cheap path)
    - ``tesseract``: local pytesseract
    - ``bedrock``: Bedrock multimodal OCR (expensive fallback)
    - ``textract``: AWS Textract (optional / future; last in auto chain)

    Raises:
        ExtractionError: When OCR is disabled or all providers fail.
    """
    settings = get_settings()
    if not settings.ocr_enabled:
        raise ExtractionError("OCR is disabled (OCR_ENABLED=false)")

    if not file_content:
        raise ExtractionError("Received empty PDF payload for OCR")

    provider = (settings.ocr_provider or "auto").strip().lower()
    errors: list[str] = []

    if provider == "auto":
        providers = list(_AUTO_PROVIDER_ORDER)
    elif provider in _SUPPORTED_PROVIDERS:
        providers = [provider]
    else:
        supported = ", ".join(("auto", *_AUTO_PROVIDER_ORDER))
        raise ExtractionError(
            f"Unsupported OCR_PROVIDER '{settings.ocr_provider}'. "
            f"Use one of: {supported}."
        )

    dispatch = {
        "paddleocr": _ocr_with_paddleocr,
        "bedrock": _ocr_with_bedrock,
        "textract": _ocr_with_textract,
        "tesseract": _ocr_with_tesseract,
    }

    for name in providers:
        try:
            text = dispatch[name](file_content)
        except ExtractionError as exc:
            errors.append(f"{name}: {exc}")
            logger.warning("OCR provider '%s' failed: %s", name, exc)
            continue
        except Exception as exc:
            errors.append(f"{name}: {exc}")
            logger.warning("OCR provider '%s' unexpected failure: %s", name, exc)
            continue

        if text and text.strip():
            logger.info("OCR succeeded via %s (%d chars)", name, len(text))
            return text.strip()

        errors.append(f"{name}: empty OCR result")

    detail = "; ".join(errors) if errors else "no providers attempted"
    raise ExtractionError(
        "OCR failed for scanned/image-only PDF. "
        f"Details: {detail}"
    )
