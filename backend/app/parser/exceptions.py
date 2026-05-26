"""Parser-specific exception hierarchy."""


class ParserError(Exception):
    """Base exception for all resume parser failures."""


class ExtractionError(ParserError):
    """Raised when resume text extraction fails."""


class LLMParsingError(ParserError):
    """Raised when structured resume parsing via an LLM fails."""


class ValidationError(ParserError):
    """Raised when parsed resume data does not satisfy parser validation rules."""


class NormalizationError(ParserError):
    """Raised when parsed resume data cannot be normalized."""


class UnsupportedFileTypeError(ParserError):
    """Raised when the uploaded file type is not supported by any extractor."""

