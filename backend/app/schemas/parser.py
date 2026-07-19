"""API schemas for the resume parsing endpoints."""

from pydantic import BaseModel, Field

from app.schemas.resume import CandidateProfile


class ResumeParseResponse(BaseModel):
    """Successful resume parse result."""

    filename: str = Field(..., description="Original uploaded filename")
    extracted_text: str = Field(..., description="Plain text extracted from the resume")
    parsed_profile: CandidateProfile = Field(
        ...,
        description="Structured candidate profile produced by the LLM parser",
    )


class ParserErrorResponse(BaseModel):
    """Structured error body returned by the parser API."""

    detail: str
    error_code: str


class ResumeParseItemResult(BaseModel):
    """Per-file outcome for a batch parse request."""

    filename: str
    success: bool
    result: ResumeParseResponse | None = None
    error: ParserErrorResponse | None = None


class ResumeBatchParseResponse(BaseModel):
    """Aggregate result for a multi-file resume parse request."""

    total: int
    succeeded: int
    failed: int
    results: list[ResumeParseItemResult]
