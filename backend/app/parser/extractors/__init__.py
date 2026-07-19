"""Resume text extraction modules."""

from app.parser.extractors.base import DocumentExtractor
from app.parser.extractors.docx import DocxExtractor, extract_text_from_docx
from app.parser.extractors.ocr import needs_ocr, ocr_pdf_to_text
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

