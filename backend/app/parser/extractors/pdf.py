"""PDF resume text extraction using pdfplumber (primary) and PyMuPDF (fallback).

When both text extractors yield no usable text (typical for scanned /
image-only resumes), falls back to OCR via ``app.parser.extractors.ocr``.
"""

import io
import logging
import re

from app.parser.exceptions import ExtractionError
from app.parser.extractors.ocr import needs_ocr, ocr_pdf_to_text

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
            # Explicit tolerances help pdfplumber insert spaces between words
            # instead of merging them (a common cause of "gluedwords").
            page_text = page.extract_text(x_tolerance=1.5, y_tolerance=3)
            if page_text:
                pages.append(page_text)
    return "\n".join(pages)


def _merged_word_ratio(text: str) -> float:
    """Estimate how many tokens look like merged words (missing spaces).

    Returns the fraction of alphabetic tokens whose length is abnormally long
    (>= 20 chars). Higher means worse extraction quality.
    """
    tokens = re.findall(r"[A-Za-z]+", text)
    if not tokens:
        return 1.0
    long_tokens = sum(1 for token in tokens if len(token) >= 20)
    return long_tokens / len(tokens)


def _extract_with_pymupdf(stream: io.BytesIO) -> str:
    import fitz  # PyMuPDF

    pages: list[str] = []
    with fitz.open(stream=stream, filetype="pdf") as doc:
        for page in doc:
            page_text = page.get_text()
            if page_text:
                pages.append(page_text)
    return "\n".join(pages)


def _extract_hyperlinks(file_content: bytes) -> list[str]:
    """Collect embedded hyperlink URIs from PDF link annotations.

    Resume links (LinkedIn/GitHub/portfolio) are frequently stored as clickable
    link annotations whose visible text is an icon or label, so the raw text
    stream never contains the URL. Reading annotations recovers them.
    """
    try:
        import fitz  # PyMuPDF
    except Exception:
        return []

    urls: list[str] = []
    seen: set[str] = set()

    try:
        with fitz.open(stream=io.BytesIO(file_content), filetype="pdf") as doc:
            for page in doc:
                for link in page.get_links():
                    uri = link.get("uri")
                    if uri and uri not in seen and uri.lower().startswith(("http://", "https://")):
                        seen.add(uri)
                        urls.append(uri)
    except Exception as exc:
        logger.warning("Hyperlink extraction failed: %s", exc)
        return []

    if urls:
        logger.info("Extracted %d embedded hyperlink(s) from PDF", len(urls))

    return urls


_MERGED_WORD_THRESHOLD = 0.01


def extract_text_from_pdf(file_content: bytes) -> str:
    """Extract and clean text from a PDF resume.

    Uses pdfplumber as the primary engine. If its output shows signs of
    merged words (missing spaces), PyMuPDF is tried as well and the cleaner
    result is chosen. When both text extractors fail (scanned/image-only
    PDFs), falls back to OCR.

    Raises:
        ExtractionError: When text extraction and OCR both fail.
    """
    if not file_content:
        raise ExtractionError("Received empty PDF payload")

    plumber_text = ""
    try:
        plumber_text = _extract_with_pdfplumber(io.BytesIO(file_content))
    except Exception as exc:
        logger.warning("pdfplumber extraction failed: %s", exc)

    plumber_ok = bool(plumber_text.strip())
    plumber_score = _merged_word_ratio(plumber_text) if plumber_ok else 1.0

    chosen = ""
    used_ocr = False

    if plumber_ok and plumber_score <= _MERGED_WORD_THRESHOLD:
        chosen = plumber_text
        logger.info(
            "PDF text extracted via pdfplumber (%d chars, merged_ratio=%.4f)",
            len(plumber_text),
            plumber_score,
        )
    else:
        mupdf_text = ""
        try:
            mupdf_text = _extract_with_pymupdf(io.BytesIO(file_content))
        except Exception as exc:
            logger.warning("PyMuPDF extraction failed: %s", exc)

        mupdf_ok = bool(mupdf_text.strip())
        mupdf_score = _merged_word_ratio(mupdf_text) if mupdf_ok else 1.0

        if plumber_ok or mupdf_ok:
            if mupdf_ok and mupdf_score < plumber_score:
                chosen = mupdf_text
                logger.info(
                    "PDF text extracted via PyMuPDF (%d chars, merged_ratio=%.4f < pdfplumber %.4f)",
                    len(mupdf_text),
                    mupdf_score,
                    plumber_score,
                )
            else:
                chosen = plumber_text
                logger.info(
                    "PDF text extracted via pdfplumber (%d chars, merged_ratio=%.4f)",
                    len(plumber_text),
                    plumber_score,
                )

    if needs_ocr(chosen):
        logger.info(
            "Native PDF text missing or too sparse (%d chars); attempting OCR fallback",
            len(chosen.strip()) if chosen else 0,
        )
        try:
            chosen = ocr_pdf_to_text(file_content)
            used_ocr = True
        except ExtractionError:
            if not chosen.strip():
                raise
            logger.warning("OCR failed; continuing with sparse native text")

    if not chosen.strip():
        raise ExtractionError(
            "Failed to extract text from PDF via pdfplumber, PyMuPDF, and OCR"
        )

    cleaned = _clean_text(chosen)
    if used_ocr:
        logger.info("PDF text extracted via OCR (%d chars after cleaning)", len(cleaned))

    return _append_hyperlinks(cleaned, _extract_hyperlinks(file_content))


def _append_hyperlinks(text: str, urls: list[str]) -> str:
    """Append embedded URLs as a dedicated section for the LLM to categorize."""
    if not urls:
        return text

    # Skip URLs already present in the visible text to avoid noise.
    missing = [url for url in urls if url not in text]
    if not missing:
        return text

    links_block = "\n".join(missing)
    return f"{text}\n\nEMBEDDED LINKS:\n{links_block}"


class PdfExtractor:
    """Adapter that satisfies the ``DocumentExtractor`` protocol using PDF extraction."""

    def extract(self, file_content: bytes) -> str:
        return extract_text_from_pdf(file_content)
