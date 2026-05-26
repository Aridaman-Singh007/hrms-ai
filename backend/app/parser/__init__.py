"""Resume parser package.

This package contains the parser pipeline and stage-specific modules used to
extract, parse, validate, and normalize resume data. API routes should depend on
the pipeline boundary instead of importing extractor or LLM implementation
details directly.
"""

from app.parser.pipeline import ResumeParserPipeline, extract_resume_text

__all__ = ["ResumeParserPipeline", "extract_resume_text"]

