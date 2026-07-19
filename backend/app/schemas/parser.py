"""API schemas for the resume parsing endpoint."""

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
