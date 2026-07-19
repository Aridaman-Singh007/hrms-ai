"""Prompt templates for LLM-based job description parsing.

Centralises JD prompt strings so they can be versioned, tested, and tuned
independently of the LLM client.  Pair ``JD_PARSER_SYSTEM_PROMPT`` with the
user prompt returned by ``build_job_description_prompt()`` when calling
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
- Extract ONLY information explicitly stated in the job description text.
- Do NOT infer company culture, benefits, salary, or seniority that is not written.
- Do NOT fabricate skills, technologies, qualifications, or certifications.
- Do NOT invent minimum years of experience; extract numbers only when stated.
- Preserve exact wording for responsibilities and qualifications (light trimming of bullets is fine; no rewriting).
- If a field is ambiguous, use null rather than guessing.
"""

_GENERAL_RULES = """\
GENERAL EXTRACTION RULES:
- job_title / company / department: exact text from the JD; null if absent.
- location: as written (e.g. "Bengaluru, India"); null if absent.
- work_mode: exactly one of "remote", "hybrid", "onsite" — only when the JD clearly states it (e.g. "work from home" -> remote, "3 days in office" -> hybrid); else null.
- employment_type: only if stated (e.g. "Full-time", "Contract", "Internship"); else null.
- seniority_level: only if stated or unambiguous from the title (e.g. "Senior", "Lead", "Entry-level"); else null.
- summary: a short role overview ONLY if the JD contains an explicit summary/about-the-role section; else null.
- domain: business/industry domain if stated (e.g. "fintech", "healthcare"); else null.
- salary_range: exact compensation text if present (e.g. "₹18-25 LPA"); else null.
- benefits: perks/benefits explicitly listed; else [].
"""

_SKILLS_RULES = """\
SKILLS (required vs preferred):
- required_skills: skills the JD marks as required, must-have, or lists under requirements.
- preferred_skills: skills marked nice-to-have, preferred, bonus, or "a plus".
- When the JD does not distinguish, treat listed skills as required.
- Never place the same skill in both lists; required wins.
- name: canonical industry-standard names (e.g. "React" not "reactjs", "PostgreSQL" not "postgres").
- category: one of programming_language, frontend, backend, database, cloud, devops, ai_ml, data_engineering, testing, devtools, mobile, security, architecture — or null if unclear.
- min_years: only when the JD ties a number of years to that specific skill (e.g. "3+ years of Python"); else null.
- technologies: a flat deduplicated list of ALL tools/frameworks/platforms mentioned anywhere in the JD (superset of skill names), using canonical names.
"""

_RESPONSIBILITIES_RULES = """\
RESPONSIBILITIES:
- One string per responsibility bullet/sentence, preserving original wording.
- Include only actual duties of the role, not company marketing text.
- Keep source order.
"""

_QUALIFICATIONS_RULES = """\
QUALIFICATIONS:
- mandatory_qualifications: entries under "requirements", "must have", "minimum qualifications".
- optional_qualifications: entries under "preferred", "nice to have", "bonus points".
- Preserve original wording per entry; keep source order.
- Skill-only bullets belong in required_skills/preferred_skills; broader statements (e.g. "Experience shipping production systems") belong here. A bullet may appear in both a skills list and qualifications when it mixes both.
"""

_EXPERIENCE_RULES = """\
EXPERIENCE:
- experience.min_years / max_years: numeric years extracted from statements like "3-5 years", "5+ years" (5+ -> min_years=5, max_years=null); else null.
- experience.description: the exact experience requirement sentence if present; else null.
- Do not derive years from seniority words alone (e.g. "senior" alone -> nulls).
"""

_EDUCATION_CERT_RULES = """\
EDUCATION:
- One entry per degree expectation (e.g. "Bachelor's in Computer Science").
- degree: exact degree text; specialization: field of study if stated; else null.
- mandatory: true when required, false when preferred/equivalent-experience-accepted; null when unclear.

CERTIFICATIONS:
- Only certifications explicitly named (e.g. "AWS Solutions Architect").
- mandatory: true when required, false when preferred; null when unclear.
"""

# ---------------------------------------------------------------------------
# JSON schema reference (matches app.schemas.job_description.JobDescription)
# ---------------------------------------------------------------------------

_JD_JSON_SCHEMA: dict = {
    "job_title": None,
    "company": None,
    "department": None,
    "location": None,
    "work_mode": None,
    "employment_type": None,
    "seniority_level": None,
    "summary": None,
    "domain": None,
    "responsibilities": [],
    "required_skills": [
        {
            "name": "string",
            "category": None,
            "min_years": None,
        }
    ],
    "preferred_skills": [
        {
            "name": "string",
            "category": None,
            "min_years": None,
        }
    ],
    "technologies": [],
    "experience": {
        "min_years": None,
        "max_years": None,
        "description": None,
    },
    "mandatory_qualifications": [],
    "optional_qualifications": [],
    "education": [
        {
            "degree": "string",
            "specialization": None,
            "mandatory": None,
        }
    ],
    "certifications": [
        {
            "name": "string",
            "mandatory": None,
        }
    ],
    "salary_range": None,
    "benefits": [],
}

_SCHEMA_JSON = json.dumps(_JD_JSON_SCHEMA, indent=2)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

JD_PARSER_SYSTEM_PROMPT: str = "\n".join(
    [
        "You are a precision ATS job description parser for software-engineering hiring.",
        "Your task is to extract structured data from job description text into a strict JSON object.",
        "",
        _JSON_OUTPUT_RULES,
        _HALLUCINATION_RULES,
        _GENERAL_RULES,
        _SKILLS_RULES,
        _RESPONSIBILITIES_RULES,
        _QUALIFICATIONS_RULES,
        _EXPERIENCE_RULES,
        _EDUCATION_CERT_RULES,
    ]
)

_USER_PROMPT_HEADER = """\
Parse the job description text below into a single JSON object matching this schema.
Replace placeholder types with actual extracted values; use null or [] for missing data.

SCHEMA (structure reference — return populated values, not type labels):
"""


def build_job_description_prompt(job_description_text: str) -> str:
    """Build the user prompt for structured job description extraction.

    Args:
        job_description_text: Plain-text JD content.

    Returns:
        User prompt string to pass to ``generate_completion()`` alongside
        ``JD_PARSER_SYSTEM_PROMPT``.

    Raises:
        ValueError: When the text is empty.
    """
    cleaned = job_description_text.strip()
    if not cleaned:
        raise ValueError("job_description_text must not be empty")

    return "\n".join(
        [
            _USER_PROMPT_HEADER,
            _SCHEMA_JSON,
            "",
            "JOB DESCRIPTION TEXT (extract only from this block):",
            "---BEGIN JOB DESCRIPTION---",
            cleaned,
            "---END JOB DESCRIPTION---",
            "",
            "Return the JSON object now. Output JSON only — no markdown.",
        ]
    )
