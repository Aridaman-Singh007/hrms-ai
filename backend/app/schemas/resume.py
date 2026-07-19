"""Pydantic v2 schemas for structured resume data.

Designed for software-engineering hiring pipelines: skills carry an optional
category and experience estimate, projects track repo / live URLs, and the
top-level ``CandidateProfile`` aggregates every section an LLM parser is
expected to extract.
"""

from pydantic import BaseModel, EmailStr


class Skill(BaseModel):
    """A single technical or soft skill."""

    name: str
    category: str | None = None
    years_experience: float | None = None


class Experience(BaseModel):
    """One professional experience entry."""

    company: str
    role: str
    employment_type: str | None = None

    start_date: str | None = None
    end_date: str | None = None
    currently_working: bool | None = False

    duration_months: int | None = None

    location: str | None = None
    domain: str | None = None

    description: str | None = None

    technologies: list[str] = []


class Education(BaseModel):
    """One education entry."""

    degree: str
    specialization: str | None = None

    institution: str

    start_year: int | None = None
    end_year: int | None = None

    cgpa: float | None = None
    percentage: float | None = None
    grade: str | None = None


class Project(BaseModel):
    """A personal, academic, or open-source project."""

    title: str

    description: str | None = None

    technologies: list[str] = []

    role: str | None = None

    github_url: str | None = None
    live_url: str | None = None


class Certification(BaseModel):
    """A professional certification or credential."""

    name: str

    issuer: str | None = None

    issue_date: str | None = None


class CandidateProfile(BaseModel):
    """Top-level schema representing all structured data extracted from a resume."""

    full_name: str | None = None

    email: EmailStr | None = None

    phone: str | None = None

    linkedin_url: str | None = None

    github_url: str | None = None

    portfolio_url: str | None = None

    location: str | None = None

    total_experience_years: float | None = None

    summary: str | None = None

    skills: list[Skill] = []

    experience: list[Experience] = []

    education: list[Education] = []

    projects: list[Project] = []

    certifications: list[Certification] = []

    achievements: list[str] = []

    languages: list[str] = []
