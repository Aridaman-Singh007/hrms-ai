"""LLM-based structured resume parsing."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import EmailStr, TypeAdapter, ValidationError as PydanticValidationError

from app.parser.exceptions import LLMParsingError, ValidationError
from app.parser.llm.client import generate_completion
from app.parser.llm.prompts import (
    RESUME_PARSER_SYSTEM_PROMPT,
    build_resume_parser_prompt,
)
from app.parser.llm.utils import safe_json_loads
from app.parser.normalizers.skills import normalize_skill
from app.parser.normalizers.taxonomy import get_skill_category
from app.schemas.resume import CandidateProfile

logger = logging.getLogger(__name__)

_EMAIL_ADAPTER = TypeAdapter(EmailStr)
_ALLOWED_TOP_LEVEL_KEYS = frozenset(CandidateProfile.model_fields.keys())

_LIST_FIELDS = frozenset(
    {
        "skills",
        "experience",
        "education",
        "projects",
        "certifications",
        "achievements",
        "languages",
    }
)

_NESTED_LIST_FIELDS: dict[str, frozenset[str]] = {
    "skills": frozenset({"name", "category", "years_experience"}),
    "experience": frozenset(
        {
            "company",
            "role",
            "employment_type",
            "start_date",
            "end_date",
            "currently_working",
            "duration_months",
            "location",
            "domain",
            "description",
            "technologies",
        }
    ),
    "education": frozenset(
        {"degree", "specialization", "institution", "start_year", "end_year", "cgpa"}
    ),
    "projects": frozenset(
        {
            "title",
            "description",
            "technologies",
            "role",
            "github_url",
            "live_url",
        }
    ),
    "certifications": frozenset({"name", "issuer", "issue_date"}),
}

_REQUIRED_NESTED_FIELDS: dict[str, tuple[str, ...]] = {
    "skills": ("name",),
    "experience": ("company", "role"),
    "education": ("degree", "institution"),
    "projects": ("title",),
    "certifications": ("name",),
}

_STRING_LIST_FIELDS = frozenset({"achievements", "languages"})
_STRING_NESTED_LIST_FIELDS = frozenset({"technologies"})


def parse_resume_with_llm(resume_text: str) -> CandidateProfile:
    """Parse raw resume text into a validated ``CandidateProfile``.

    Args:
        resume_text: Plain-text resume from the extraction pipeline.

    Returns:
        Validated and skill-normalized candidate profile.

    Raises:
        LLMParsingError: When the LLM call or JSON parsing fails.
        ValidationError: When the payload cannot be validated against the schema.
        ValueError: When ``resume_text`` is empty.
    """
    if not resume_text or not resume_text.strip():
        raise ValueError("resume_text must not be empty")

    logger.info("Starting LLM resume parse (%d chars of input)", len(resume_text))

    try:
        user_prompt = build_resume_parser_prompt(resume_text)
        raw_response = generate_completion(RESUME_PARSER_SYSTEM_PROMPT, user_prompt)
    except LLMParsingError:
        raise
    except Exception as exc:
        logger.exception("LLM completion failed during resume parse")
        raise LLMParsingError(f"LLM resume parse failed: {exc}") from exc

    logger.debug("LLM raw response received (%d chars)", len(raw_response))

    payload = _parse_llm_json(raw_response)
    sanitized = _sanitize_payload(payload)
    normalized = _normalize_skills_in_payload(sanitized)

    profile = _validate_candidate_profile(normalized)

    logger.info(
        "Resume parsed successfully (skills=%d, experience=%d, education=%d)",
        len(profile.skills),
        len(profile.experience),
        len(profile.education),
    )
    return profile


def _parse_llm_json(raw_response: str) -> dict[str, Any]:
    """Parse and validate that the LLM response is a JSON object."""
    try:
        parsed = safe_json_loads(raw_response)
    except LLMParsingError:
        raise
    except Exception as exc:
        logger.error("Unexpected error parsing LLM JSON: %s", exc)
        raise LLMParsingError(f"Failed to parse LLM JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise LLMParsingError(
            f"Expected JSON object at root, got {type(parsed).__name__}"
        )

    return parsed


def _sanitize_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Whitelist fields, coerce list shapes, and drop invalid nested entries."""
    removed_keys = set(data.keys()) - _ALLOWED_TOP_LEVEL_KEYS
    if removed_keys:
        logger.warning("Removing unknown top-level fields: %s", sorted(removed_keys))

    sanitized: dict[str, Any] = {}

    for key in _ALLOWED_TOP_LEVEL_KEYS:
        value = data.get(key)

        if key in _LIST_FIELDS:
            sanitized[key] = _sanitize_list_field(key, value)
            continue

        if key == "email":
            sanitized[key] = _sanitize_email(value)
            continue

        sanitized[key] = _null_if_blank(value)

    return sanitized


def _sanitize_list_field(field_name: str, value: Any) -> list[Any]:
    """Coerce a list field to the expected shape."""
    if value is None:
        return []

    if not isinstance(value, list):
        logger.warning("Field '%s' is not a list (%s); using []", field_name, type(value).__name__)
        return []

    if field_name in _STRING_LIST_FIELDS:
        return _sanitize_string_list(value, field_name)

    allowed_keys = _NESTED_LIST_FIELDS.get(field_name, frozenset())
    required = _REQUIRED_NESTED_FIELDS.get(field_name, ())
    result: list[Any] = []

    for index, item in enumerate(value):
        if not isinstance(item, dict):
            logger.warning(
                "Skipping non-object entry in '%s' at index %d", field_name, index
            )
            continue

        cleaned = _sanitize_nested_object(item, allowed_keys, field_name)

        if not _has_required_fields(cleaned, required):
            logger.warning(
                "Skipping '%s' entry at index %d missing required fields %s",
                field_name,
                index,
                required,
            )
            continue

        result.append(cleaned)

    return result


def _sanitize_nested_object(
    item: dict[str, Any],
    allowed_keys: frozenset[str],
    parent_field: str,
) -> dict[str, Any]:
    """Keep only allowed keys on a nested object."""
    removed = set(item.keys()) - allowed_keys
    if removed:
        logger.debug(
            "Removing unknown keys from '%s' entry: %s", parent_field, sorted(removed)
        )

    cleaned: dict[str, Any] = {}
    for key in allowed_keys:
        value = item.get(key)
        if key in _STRING_NESTED_LIST_FIELDS:
            cleaned[key] = _sanitize_string_list(value, f"{parent_field}.{key}")
        else:
            cleaned[key] = _null_if_blank(value)

    return cleaned


def _sanitize_string_list(value: Any, field_name: str) -> list[str]:
    """Coerce values to a list of non-empty strings."""
    if value is None:
        return []

    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []

    if not isinstance(value, list):
        logger.warning("Field '%s' is not a string list; using []", field_name)
        return []

    result: list[str] = []
    for index, entry in enumerate(value):
        if entry is None:
            continue
        text = str(entry).strip()
        if text:
            result.append(text)

    return result


def _has_required_fields(item: dict[str, Any], required: tuple[str, ...]) -> bool:
    """Return True when all required fields are non-empty."""
    for field in required:
        value = item.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            return False
    return True


def _null_if_blank(value: Any) -> Any:
    """Convert blank strings to None."""
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _sanitize_email(value: Any) -> str | None:
    """Return a valid email string or None if the LLM value is invalid."""
    value = _null_if_blank(value)
    if value is None:
        return None

    try:
        return str(_EMAIL_ADAPTER.validate_python(value))
    except PydanticValidationError:
        logger.warning("Invalid email from LLM; setting to null: %r", value)
        return None


def _normalize_skills_in_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize skill names and categories using the taxonomy."""
    skills_raw = data.get("skills")
    if not isinstance(skills_raw, list):
        return data

    data["skills"] = _normalize_skill_entries(skills_raw)

    for exp in data.get("experience") or []:
        if isinstance(exp, dict) and isinstance(exp.get("technologies"), list):
            exp["technologies"] = _normalize_technology_list(exp["technologies"])

    for project in data.get("projects") or []:
        if isinstance(project, dict) and isinstance(project.get("technologies"), list):
            project["technologies"] = _normalize_technology_list(
                project["technologies"]
            )

    return data


def _normalize_skill_entries(skills: list[Any]) -> list[dict[str, Any]]:
    """Deduplicate and canonicalize skill entries; preserve source order."""
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []

    for entry in skills:
        if not isinstance(entry, dict):
            continue

        raw_name = entry.get("name")
        if not raw_name or not str(raw_name).strip():
            continue

        raw_name = str(raw_name).strip()
        canonical = normalize_skill(raw_name) or raw_name
        dedupe_key = canonical.lower()

        if dedupe_key in seen:
            logger.debug("Skipping duplicate skill '%s'", canonical)
            continue

        seen.add(dedupe_key)

        category = entry.get("category")
        if not category:
            category = get_skill_category(canonical)

        normalized.append(
            {
                "name": canonical,
                "category": _null_if_blank(category),
                "years_experience": entry.get("years_experience"),
            }
        )

    logger.debug("Normalized %d skills to %d canonical entries", len(skills), len(normalized))
    return normalized


def _normalize_technology_list(technologies: list[Any]) -> list[str]:
    """Normalize technology strings where taxonomy matches exist."""
    seen: set[str] = set()
    result: list[str] = []

    for tech in technologies:
        if tech is None:
            continue
        text = str(tech).strip()
        if not text:
            continue

        canonical = normalize_skill(text) or text
        key = canonical.lower()
        if key in seen:
            continue

        seen.add(key)
        result.append(canonical)

    return result


def _validate_candidate_profile(data: dict[str, Any]) -> CandidateProfile:
    """Validate sanitized data against ``CandidateProfile``."""
    try:
        return CandidateProfile.model_validate(data)
    except PydanticValidationError as exc:
        logger.error("CandidateProfile validation failed: %s", exc)
        raise ValidationError(
            f"LLM resume output failed schema validation: {exc}"
        ) from exc
