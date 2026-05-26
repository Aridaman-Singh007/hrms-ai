"""Unified resume extraction pipeline.

Routes incoming files to the correct extractor based on file type and
provides a single entry-point for all upstream callers (API routes,
async workers, CLI tools, etc.).
"""

import logging
import mimetypes
from pathlib import PurePosixPath
from typing import Any

from app.parser.exceptions import ExtractionError, UnsupportedFileTypeError
from app.parser.extractors.docx import extract_text_from_docx
from app.parser.extractors.pdf import extract_text_from_pdf

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS: dict[str, str] = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

_MIME_TO_EXTRACTOR = {
    "application/pdf": extract_text_from_pdf,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": extract_text_from_docx,
}


def _resolve_mime_type(filename: str) -> str:
    """Determine MIME type from the filename extension.

    Falls back to ``mimetypes.guess_type`` when the extension is not in the
    explicit allow-list, but still rejects unknown types.
    """
    ext = PurePosixPath(filename).suffix.lower()

    if ext in _SUPPORTED_EXTENSIONS:
        return _SUPPORTED_EXTENSIONS[ext]

    guessed, _ = mimetypes.guess_type(filename)
    if guessed and guessed in _MIME_TO_EXTRACTOR:
        return guessed

    supported = ", ".join(sorted(_SUPPORTED_EXTENSIONS.keys()))
    raise UnsupportedFileTypeError(
        f"Unsupported file type '{ext or '(none)'}'. Supported types: {supported}"
    )


def extract_resume_text(file_content: bytes, filename: str) -> str:
    """Extract clean text from a resume file.

    1. Resolves the MIME type from *filename*.
    2. Routes to the matching extractor.
    3. Returns cleaned plain text.

    Args:
        file_content: Raw bytes of the uploaded resume file.
        filename:     Original filename (used for type detection only).

    Returns:
        Cleaned plain-text content of the resume.

    Raises:
        UnsupportedFileTypeError: When the file extension is not supported.
        ExtractionError:          When the matched extractor fails.
    """
    logger.info("Starting resume extraction for '%s' (%d bytes)", filename, len(file_content))

    mime = _resolve_mime_type(filename)
    extractor_fn = _MIME_TO_EXTRACTOR[mime]

    logger.debug("Resolved MIME '%s' → %s", mime, extractor_fn.__name__)

    text = extractor_fn(file_content)

    logger.info(
        "Extraction complete for '%s': %d chars extracted",
        filename,
        len(text),
    )
    return text


class ResumeParserPipeline:
    """Coordinates resume parsing stages.

    Currently handles extraction only.  Future stages (LLM parsing,
    validation, normalization) will be composed here via injected
    collaborators.
    """

    def parse(self, file_content: bytes, filename: str) -> dict[str, Any]:
        """Parse a resume file into structured data.

        For now, returns the extracted text.  Subsequent prompts will
        layer LLM parsing, validation, and normalization on top.
        """
        text = extract_resume_text(file_content, filename)
        return {"raw_text": text}
