"""Prompt templates for LLM-based resume parsing.

Centralises all prompt strings so they can be versioned, tested, and tuned
independently of the LLM client.  Pair ``RESUME_PARSER_SYSTEM_PROMPT`` with
the user prompt returned by ``build_resume_parser_prompt()`` when calling
``generate_completion()``.
"""

from __future__ import annotations

import json

# ---------------------------------------------------------------------------
# Core output contract
# ---------------------------------------------------------------------------

_JSON_OUTPUT_RULES = """\
JSON OUTPUT RULES (mandatory):
- Return ONLY a single valid JSON object. No prose, no explanations.
- Do NOT wrap the response in markdown, code fences, or backticks.
- Do NOT include comments inside the JSON.
- Use double quotes for all keys and string values.
- Missing or unknown scalar fields MUST be null (not empty strings).
- Missing list fields MUST be [] (empty arrays), never null.
- Do not add keys beyond the schema below.
- Prioritize precision over completeness — omit uncertain data as null/[].
"""

_HALLUCINATION_RULES = """\
ANTI-HALLUCINATION RULES (mandatory):
- Extract ONLY information explicitly stated or clearly implied in the resume text.
- Do NOT infer, estimate, or generate data that is not supported by the text.
- Do NOT fabricate companies, roles, dates, skills, projects, or credentials.
- Do NOT calculate total_experience_years unless a clear total is stated; otherwise null.
- Do NOT merge or split roles unless the resume clearly does so.
- Preserve exact spelling and casing for company names, role titles, and institutions.
- If a field is ambiguous, use null rather than guessing.
"""

_GENERAL_RULES = """\
GENERAL EXTRACTION RULES:
- Preserve chronological ordering: most recent experience/education first when the resume lists them that way; otherwise follow source order.
- Dates must remain human-readable strings as written (e.g. "Jan 2022", "2020-2023", "Present"). Do not convert to ISO unless already in that form.
- URLs and emails must be copied exactly as they appear.
- Phone numbers: copy as written; do not reformat unless clearly standardised in the source.
- summary: only populate if an explicit summary/objective/profile section exists.
- achievements: bullet points or honours explicitly listed; do not invent.
- languages: spoken/human languages only; not programming languages.
"""

# ---------------------------------------------------------------------------
# Section-specific guidance
# ---------------------------------------------------------------------------

_SKILLS_RULES = """\
SKILLS:
- Extract technical and professional skills explicitly mentioned.
- Use canonical, industry-standard names where clearly identifiable (e.g. "React" not "reactjs", "Python" not "py").
- category: one of programming_language, frontend, backend, database, cloud, devops, ai_ml, data_engineering, testing, mobile, security, architecture — or null if unclear.
- years_experience: only if explicitly stated; otherwise null. Do not infer from tenure.
- Do not duplicate the same skill; merge aliases into one entry with the canonical name.
- Soft skills only if prominently listed as skills (not buried in prose).
"""

_EXPERIENCE_RULES = """\
EXPERIENCE:
- One object per distinct role/position at a company.
- company and role: exact text from the resume; do not normalise or expand abbreviations.
- employment_type: only if stated (e.g. "Internship", "Contract", "Full-time"); else null.
- start_date / end_date: human-readable strings from the resume; use "Present" if stated for current roles.
- currently_working: true only if the resume explicitly indicates current employment for that role; else false or null.
- duration_months: only if explicitly stated; do not compute from dates.
- technologies: tools, languages, frameworks explicitly tied to that role; do not infer from company domain.
- description: role summary/bullets condensed into one string if present; null if absent.
- Order entries from most recent to oldest when the resume structure allows it.
"""

_EDUCATION_RULES = """\
EDUCATION:
- degree and institution: exact text from the resume.
- specialization: field of study/major if stated; else null.
- start_year / end_year: integers only when explicit years are given; else null.
- cgpa: only if explicitly stated with a numeric value; else null.
- Order from most recent to oldest when discernible.
"""

_PROJECTS_RULES = """\
PROJECTS:
- Include personal, academic, and professional projects only when explicitly listed as projects.
- title: exact project name from the resume.
- technologies: stack/tools explicitly mentioned for that project.
- github_url / live_url: only if a URL is present in the resume; else null.
- Do not treat work experience entries as projects unless labelled as projects.
"""

_CERTIFICATIONS_RULES = """\
CERTIFICATIONS:
- name and issuer: exact text from the resume.
- issue_date: human-readable date string if present; else null.
- Do not include degrees under certifications.
"""

# ---------------------------------------------------------------------------
# JSON schema reference (matches app.schemas.resume.CandidateProfile)
# ---------------------------------------------------------------------------

_RESUME_JSON_SCHEMA: dict = {
    "full_name": None,
    "email": None,
    "phone": None,
    "linkedin_url": None,
    "github_url": None,
    "portfolio_url": None,
    "location": None,
    "total_experience_years": None,
    "summary": None,
    "skills": [
        {
            "name": "string",
            "category": None,
            "years_experience": None,
        }
    ],
    "experience": [
        {
            "company": "string",
            "role": "string",
            "employment_type": None,
            "start_date": None,
            "end_date": None,
            "currently_working": False,
            "duration_months": None,
            "location": None,
            "domain": None,
            "description": None,
            "technologies": [],
        }
    ],
    "education": [
        {
            "degree": "string",
            "specialization": None,
            "institution": "string",
            "start_year": None,
            "end_year": None,
            "cgpa": None,
        }
    ],
    "projects": [
        {
            "title": "string",
            "description": None,
            "technologies": [],
            "role": None,
            "github_url": None,
            "live_url": None,
        }
    ],
    "certifications": [
        {
            "name": "string",
            "issuer": None,
            "issue_date": None,
        }
    ],
    "achievements": [],
    "languages": [],
}

_SCHEMA_JSON = json.dumps(_RESUME_JSON_SCHEMA, indent=2)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

RESUME_PARSER_SYSTEM_PROMPT: str = "\n".join(
    [
        "You are a precision ATS resume parser for software-engineering hiring.",
        "Your task is to extract structured data from resume text into a strict JSON object.",
        "",
        _JSON_OUTPUT_RULES,
        _HALLUCINATION_RULES,
        _GENERAL_RULES,
        _SKILLS_RULES,
        _EXPERIENCE_RULES,
        _EDUCATION_RULES,
        _PROJECTS_RULES,
        _CERTIFICATIONS_RULES,
    ]
)

_USER_PROMPT_HEADER = """\
Parse the resume text below into a single JSON object matching this schema.
Replace placeholder types with actual extracted values; use null or [] for missing data.

SCHEMA (structure reference — return populated values, not type labels):
"""


def build_resume_parser_prompt(resume_text: str) -> str:
    """Build the user prompt for structured resume extraction.

    Args:
        resume_text: Plain-text resume content from the extraction pipeline.

    Returns:
        User prompt string to pass to ``generate_completion()`` alongside
        ``RESUME_PARSER_SYSTEM_PROMPT``.
    """
    cleaned = resume_text.strip()
    if not cleaned:
        raise ValueError("resume_text must not be empty")

    return "\n".join(
        [
            _USER_PROMPT_HEADER,
            _SCHEMA_JSON,
            "",
            "RESUME TEXT (extract only from this block):",
            "---BEGIN RESUME---",
            cleaned,
            "---END RESUME---",
            "",
            "Return the JSON object now. Output JSON only — no markdown.",
        ]
    )
