"""Resume text extraction modules."""

from app.parser.extractors.base import DocumentExtractor
from app.parser.extractors.docx import DocxExtractor, extract_text_from_docx
from app.parser.extractors.pdf import PdfExtractor, extract_text_from_pdf

__all__ = [
    "DocumentExtractor",
    "DocxExtractor",
    "PdfExtractor",
    "extract_text_from_docx",
    "extract_text_from_pdf",
    "needs_ocr",
    "ocr_pdf_to_text",
]


def __getattr__(name: str):
    if name in {"needs_ocr", "ocr_pdf_to_text"}:
        from app.parser.extractors import ocr as ocr_module

        return getattr(ocr_module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
