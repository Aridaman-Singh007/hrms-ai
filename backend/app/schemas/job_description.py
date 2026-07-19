"""Pydantic v2 schemas for structured job description data.

Designed for ATS processing of software-engineering job descriptions:
skills are split into required vs preferred, qualifications into mandatory
vs optional, and experience/education requirements are structured so a
future scoring engine can match them against ``CandidateProfile`` data.
"""

from pydantic import BaseModel


class SkillRequirement(BaseModel):
    """A single skill demanded (or preferred) by the job description."""

    name: str
    category: str | None = None
    min_years: float | None = None


class ExperienceRequirement(BaseModel):
    """Overall professional experience expectations."""

    min_years: float | None = None
    max_years: float | None = None
    description: str | None = None


class EducationRequirement(BaseModel):
    """One education expectation (degree / field)."""

    degree: str
    specialization: str | None = None
    mandatory: bool | None = None


class CertificationRequirement(BaseModel):
    """A certification named in the job description."""

    name: str
    mandatory: bool | None = None


class JobDescription(BaseModel):
    """Top-level schema representing all structured data extracted from a JD."""

    job_title: str | None = None
    company: str | None = None
    department: str | None = None

    location: str | None = None
    # remote | hybrid | onsite (null when the JD does not state it)
    work_mode: str | None = None
    employment_type: str | None = None
    seniority_level: str | None = None

    summary: str | None = None
    domain: str | None = None

    responsibilities: list[str] = []

    required_skills: list[SkillRequirement] = []
    preferred_skills: list[SkillRequirement] = []
    technologies: list[str] = []

    experience: ExperienceRequirement | None = None

    mandatory_qualifications: list[str] = []
    optional_qualifications: list[str] = []
    education: list[EducationRequirement] = []
    certifications: list[CertificationRequirement] = []

    salary_range: str | None = None
    benefits: list[str] = []
