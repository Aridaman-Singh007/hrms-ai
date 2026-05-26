"""DOCX resume text extraction using python-docx."""

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


def _extract_paragraphs(stream: io.BytesIO) -> str:
    from docx import Document
    from docx.opc.exceptions import PackageNotFoundError

    try:
        doc = Document(stream)
    except PackageNotFoundError:
        raise ExtractionError("File is not a valid DOCX package")

    sections: list[str] = []
    prev_style: str | None = None

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        style_name = para.style.name if para.style else ""
        is_heading = style_name.lower().startswith("heading")

        if is_heading and sections:
            sections.append("")

        if is_heading and prev_style and not prev_style.lower().startswith("heading"):
            sections.append("")

        sections.append(text)
        prev_style = style_name

    return "\n".join(sections)


def extract_text_from_docx(file_content: bytes) -> str:
    """Extract and clean text from a DOCX resume.

    Reads all paragraphs via python-docx and inserts blank lines before
    heading-style paragraphs to preserve section separation.

    Raises:
        ExtractionError: When the file cannot be read or yields no text.
    """
    if not file_content:
        raise ExtractionError("Received empty DOCX payload")

    try:
        raw = _extract_paragraphs(io.BytesIO(file_content))
    except ExtractionError:
        raise
    except Exception as exc:
        logger.warning("DOCX extraction failed: %s", exc)
        raise ExtractionError(f"Failed to extract text from DOCX: {exc}") from exc

    if not raw.strip():
        raise ExtractionError("DOCX file contained no extractable text")

    text = _clean_text(raw)
    logger.info("DOCX text extracted (%d chars)", len(text))
    return text


class DocxExtractor:
    """Adapter that satisfies the ``DocumentExtractor`` protocol using DOCX extraction."""

    def extract(self, file_content: bytes) -> str:
        return extract_text_from_docx(file_content)
