"""Application service for resume upload → extract → LLM parse."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from fastapi import UploadFile

from app.parser.exceptions import (
    ExtractionError,
    LLMParsingError,
    UnsupportedFileTypeError,
    ValidationError,
)
from app.parser.llm.resume_parser import parse_resume_with_llm
from app.parser.pipeline import extract_resume_text
from app.schemas.parser import ResumeParseResponse
from app.schemas.resume import CandidateProfile
from app.utils.file_handler import cleanup_temp_file, save_temp_file

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = frozenset({".pdf", ".docx"})
_DEFAULT_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MiB


class ResumeParserService:
    """Orchestrates temp persistence, extraction, and LLM parsing."""

    def __init__(self, *, max_upload_bytes: int = _DEFAULT_MAX_UPLOAD_BYTES) -> None:
        self._max_upload_bytes = max_upload_bytes

    async def parse_upload(self, upload: UploadFile) -> ResumeParseResponse:
        """Parse an uploaded resume file into structured profile data.

        Always attempts to clean up the temporary file, even on failure.

        Raises:
            UnsupportedFileTypeError: Unsupported extension.
            ValueError: Empty upload or empty extracted text.
            ExtractionError: Text extraction failure.
            LLMParsingError: LLM provider / JSON failures.
            ValidationError: Parsed payload failed schema validation.
        """
        filename = (upload.filename or "").strip() or "upload"
        self._assert_supported_filename(filename)

        temp_path: Path | None = None
        try:
            temp_path = await save_temp_file(upload)
            file_size = temp_path.stat().st_size
            if file_size > self._max_upload_bytes:
                raise ValueError(
                    f"Uploaded file exceeds maximum size of "
                    f"{self._max_upload_bytes // (1024 * 1024)} MiB"
                )

            logger.info(
                "Parsing resume upload filename=%s size_bytes=%d temp=%s",
                filename,
                file_size,
                temp_path,
            )

            file_bytes = await asyncio.to_thread(temp_path.read_bytes)
            extracted_text = await asyncio.to_thread(
                extract_resume_text,
                file_bytes,
                filename,
            )
            if not extracted_text or not extracted_text.strip():
                raise ExtractionError(
                    "No usable text could be extracted from the resume"
                )

            profile: CandidateProfile = await asyncio.to_thread(
                parse_resume_with_llm,
                extracted_text,
            )

            logger.info(
                "Resume parse complete filename=%s chars=%d skills=%d experience=%d",
                filename,
                len(extracted_text),
                len(profile.skills),
                len(profile.experience),
            )

            return ResumeParseResponse(
                filename=filename,
                extracted_text=extracted_text,
                parsed_profile=profile,
            )
        finally:
            if temp_path is not None:
                await cleanup_temp_file(temp_path)

    @staticmethod
    def _assert_supported_filename(filename: str) -> None:
        extension = Path(filename).suffix.lower()
        if extension not in _SUPPORTED_EXTENSIONS:
            supported = ", ".join(sorted(_SUPPORTED_EXTENSIONS))
            raise UnsupportedFileTypeError(
                f"Unsupported file type '{extension or '(none)'}'. "
                f"Supported types: {supported}"
            )
