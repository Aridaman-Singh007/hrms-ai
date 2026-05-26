"""LLM resume parser adapter."""

from __future__ import annotations

from typing import Any

from app.parser.llm.resume_parser import parse_resume_with_llm
from app.schemas.resume import CandidateProfile


class LLMResumeParser:
    """Converts extracted resume text into structured resume data."""

    def parse(self, resume_text: str) -> dict[str, Any]:
        """Return structured resume data parsed from raw resume text."""
        profile = parse_resume_with_llm(resume_text)
        return profile.model_dump(mode="json")

    def parse_profile(self, resume_text: str) -> CandidateProfile:
        """Return a validated ``CandidateProfile`` from raw resume text."""
        return parse_resume_with_llm(resume_text)
