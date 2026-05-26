"""PDF resume text extraction using pdfplumber (primary) and PyMuPDF (fallback)."""

import io
import logging
import re

from app.parser.exceptions import ExtractionError

logger = logging.getLogger(__name__)


def _clean_text(raw: str) -> str:
    """Collapse redundant whitespace while preserving paragraph breaks."""
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[^\S\n]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_with_pdfplumber(stream: io.BytesIO) -> str:
    import pdfplumber

    pages: list[str] = []
    with pdfplumber.open(stream) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                pages.append(page_text)
    return "\n".join(pages)


def _extract_with_pymupdf(stream: io.BytesIO) -> str:
    import fitz  # PyMuPDF

    pages: list[str] = []
    with fitz.open(stream=stream, filetype="pdf") as doc:
        for page in doc:
            page_text = page.get_text()
            if page_text:
                pages.append(page_text)
    return "\n".join(pages)


def extract_text_from_pdf(file_content: bytes) -> str:
    """Extract and clean text from a PDF resume.

    Uses pdfplumber as the primary engine.  Falls back to PyMuPDF when
    pdfplumber yields no usable text or raises an error.

    Raises:
        ExtractionError: When both engines fail to extract text.
    """
    if not file_content:
        raise ExtractionError("Received empty PDF payload")

    text = ""

    try:
        text = _extract_with_pdfplumber(io.BytesIO(file_content))
        if text.strip():
            logger.info("PDF text extracted via pdfplumber (%d chars)", len(text))
    except Exception as exc:
        logger.warning("pdfplumber extraction failed: %s", exc)
        text = ""

    if not text.strip():
        try:
            text = _extract_with_pymupdf(io.BytesIO(file_content))
            if text.strip():
                logger.info("PDF text extracted via PyMuPDF fallback (%d chars)", len(text))
        except Exception as exc:
            logger.warning("PyMuPDF fallback extraction failed: %s", exc)
            text = ""

    if not text.strip():
        raise ExtractionError(
            "Both pdfplumber and PyMuPDF failed to extract text from the PDF"
        )

    return _clean_text(text)


class PdfExtractor:
    """Adapter that satisfies the ``DocumentExtractor`` protocol using PDF extraction."""

    def extract(self, file_content: bytes) -> str:
        return extract_text_from_pdf(file_content)
