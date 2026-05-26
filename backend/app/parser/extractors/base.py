"""Contracts for resume text extraction."""

from typing import Protocol


class DocumentExtractor(Protocol):
    """Interface for extracting raw text from uploaded resume files."""

    def extract(self, file_content: bytes) -> str:
        """Return plain text extracted from a document payload."""
        raise NotImplementedError

