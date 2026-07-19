"""LLM-based structured job description parsing."""

from __future__ import annotations

import logging
import re
from typing import Any

from pydantic import ValidationError as PydanticValidationError

from app.parser.exceptions import LLMParsingError, ValidationError
from app.parser.llm.client import generate_completion
from app.parser.llm.jd_prompts import (
    JD_PARSER_SYSTEM_PROMPT,
    build_job_description_prompt,
)
from app.parser.llm.utils import safe_json_loads
from app.parser.normalizers.skills import normalize_skill
from app.parser.normalizers.taxonomy import get_skill_category
from app.schemas.job_description import JobDescription

logger = logging.getLogger(__name__)

_ALLOWED_TOP_LEVEL_KEYS = frozenset(JobDescription.model_fields.keys())

_SKILL_LIST_FIELDS = frozenset({"required_skills", "preferred_skills"})
_STRING_LIST_FIELDS = frozenset(
    {
        "responsibilities",
        "technologies",
        "mandatory_qualifications",
        "optional_qualifications",
        "benefits",
    }
)

_SKILL_KEYS = frozenset({"name", "category", "min_years"})
_EDUCATION_KEYS = frozenset({"degree", "specialization", "mandatory"})
_CERTIFICATION_KEYS = frozenset({"name", "mandatory"})
_EXPERIENCE_KEYS = frozenset({"min_years", "max_years", "description"})

_WORK_MODE_ALIASES: dict[str, str] = {
    "remote": "remote",
    "fully remote": "remote",
    "work from home": "remote",
    "wfh": "remote",
    "hybrid": "hybrid",
    "onsite": "onsite",
    "on-site": "onsite",
    "on site": "onsite",
    "in office": "onsite",
    "in-office": "onsite",
    "office": "onsite",
}


def parse_job_description(text: str) -> JobDescription:
    """Parse raw job description text into a validated ``JobDescription``.

    Args:
        text: Plain-text job description content.

    Returns:
        Validated and skill-normalized job description.

    Raises:
        LLMParsingError: When the LLM call or JSON parsing fails.
        ValidationError: When the payload cannot be validated against the schema.
        ValueError: When ``text`` is empty.
    """
    if not text or not text.strip():
        raise ValueError("text must not be empty")

    logger.info("Starting LLM job description parse (%d chars of input)", len(text))

    try:
        user_prompt = build_job_description_prompt(text)
        raw_response = generate_completion(JD_PARSER_SYSTEM_PROMPT, user_prompt)
    except LLMParsingError:
        raise
    except Exception as exc:
        logger.exception("LLM completion failed during job description parse")
        raise LLMParsingError(f"LLM job description parse failed: {exc}") from exc

    logger.debug("LLM raw response received (%d chars)", len(raw_response))

    payload = _parse_llm_json(raw_response)
    sanitized = _sanitize_payload(payload)
    normalized = _normalize_skills_in_payload(sanitized)

    jd = _validate_job_description(normalized)

    logger.info(
        "Job description parsed successfully (required_skills=%d, preferred_skills=%d, responsibilities=%d)",
        len(jd.required_skills),
        len(jd.preferred_skills),
        len(jd.responsibilities),
    )
    return jd


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
    """Whitelist fields, coerce shapes, and drop invalid nested entries."""
    removed_keys = set(data.keys()) - _ALLOWED_TOP_LEVEL_KEYS
    if removed_keys:
        logger.warning("Removing unknown top-level fields: %s", sorted(removed_keys))

    sanitized: dict[str, Any] = {}

    for key in _ALLOWED_TOP_LEVEL_KEYS:
        value = data.get(key)

        if key in _SKILL_LIST_FIELDS:
            sanitized[key] = _sanitize_skill_list(value, key)
        elif key in _STRING_LIST_FIELDS:
            sanitized[key] = _sanitize_string_list(value, key)
        elif key == "experience":
            sanitized[key] = _sanitize_experience(value)
        elif key == "education":
            sanitized[key] = _sanitize_education_list(value)
        elif key == "certifications":
            sanitized[key] = _sanitize_certification_list(value)
        elif key == "work_mode":
            sanitized[key] = _sanitize_work_mode(value)
        else:
            sanitized[key] = _null_if_blank(value)

    return sanitized


def _sanitize_skill_list(value: Any, field_name: str) -> list[dict[str, Any]]:
    """Coerce a skill requirement list to the expected shape."""
    if value is None:
        return []
    if not isinstance(value, list):
        logger.warning(
            "Field '%s' is not a list (%s); using []", field_name, type(value).__name__
        )
        return []

    result: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        # Tolerate bare strings ("Python") as skill entries.
        if isinstance(item, str):
            item = {"name": item}
        if not isinstance(item, dict):
            logger.warning(
                "Skipping non-object entry in '%s' at index %d", field_name, index
            )
            continue

        name = _null_if_blank(item.get("name"))
        if not name:
            logger.warning(
                "Skipping '%s' entry at index %d missing name", field_name, index
            )
            continue

        result.append(
            {
                "name": str(name).strip(),
                "category": _null_if_blank(item.get("category")),
                "min_years": _coerce_optional_float(item.get("min_years")),
            }
        )

    return result


def _sanitize_experience(value: Any) -> dict[str, Any] | None:
    """Coerce the experience requirement object."""
    if value is None:
        return None
    if not isinstance(value, dict):
        logger.warning(
            "Field 'experience' is not an object (%s); using null", type(value).__name__
        )
        return None

    cleaned = {
        "min_years": _coerce_optional_float(value.get("min_years")),
        "max_years": _coerce_optional_float(value.get("max_years")),
        "description": _null_if_blank(value.get("description")),
    }
    if all(v is None for v in cleaned.values()):
        return None
    return cleaned


def _sanitize_education_list(value: Any) -> list[dict[str, Any]]:
    """Coerce education requirement entries."""
    if value is None:
        return []
    if not isinstance(value, list):
        logger.warning("Field 'education' is not a list; using []")
        return []

    result: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if isinstance(item, str):
            item = {"degree": item}
        if not isinstance(item, dict):
            logger.warning("Skipping non-object education entry at index %d", index)
            continue

        degree = _null_if_blank(item.get("degree"))
        if not degree:
            logger.warning("Skipping education entry at index %d missing degree", index)
            continue

        result.append(
            {
                "degree": str(degree).strip(),
                "specialization": _null_if_blank(item.get("specialization")),
                "mandatory": _coerce_optional_bool(item.get("mandatory")),
            }
        )

    return result


def _sanitize_certification_list(value: Any) -> list[dict[str, Any]]:
    """Coerce certification requirement entries."""
    if value is None:
        return []
    if not isinstance(value, list):
        logger.warning("Field 'certifications' is not a list; using []")
        return []

    result: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if isinstance(item, str):
            item = {"name": item}
        if not isinstance(item, dict):
            logger.warning("Skipping non-object certification entry at index %d", index)
            continue

        name = _null_if_blank(item.get("name"))
        if not name:
            logger.warning(
                "Skipping certification entry at index %d missing name", index
            )
            continue

        result.append(
            {
                "name": str(name).strip(),
                "mandatory": _coerce_optional_bool(item.get("mandatory")),
            }
        )

    return result


def _sanitize_work_mode(value: Any) -> str | None:
    """Normalize work mode to remote | hybrid | onsite, else null."""
    value = _null_if_blank(value)
    if value is None:
        return None

    text = str(value).strip().lower()
    normalized = _WORK_MODE_ALIASES.get(text)
    if normalized is None:
        # Substring fallback for values like "Hybrid (3 days onsite)".
        for alias, mode in _WORK_MODE_ALIASES.items():
            if alias in text:
                normalized = mode
                break

    if normalized is None:
        logger.warning("Unrecognized work_mode %r; using null", value)
    return normalized


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
    for entry in value:
        if entry is None:
            continue
        text = str(entry).strip()
        if text:
            result.append(text)

    return result


def _null_if_blank(value: Any) -> Any:
    """Convert blank strings to None."""
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _coerce_optional_float(value: Any) -> float | None:
    """Coerce numeric LLM values into floats (handles "5+", "3 years")."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        match = re.search(r"\d+(?:\.\d+)?", text)
        if match:
            return float(match.group(0))
        logger.warning("Could not coerce float from %r; using null", value)
        return None
    return None


def _coerce_optional_bool(value: Any) -> bool | None:
    """Coerce LLM values into booleans, or None when unclear."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "yes", "required", "mandatory"}:
            return True
        if text in {"false", "no", "preferred", "optional"}:
            return False
    return None


def _normalize_skills_in_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Canonicalize skill names/categories and deduplicate across lists.

    Required skills win: a skill present in both lists is dropped from
    preferred.
    """
    required = _normalize_skill_entries(data.get("required_skills") or [])
    required_names = {entry["name"].lower() for entry in required}

    preferred = [
        entry
        for entry in _normalize_skill_entries(data.get("preferred_skills") or [])
        if entry["name"].lower() not in required_names
    ]

    data["required_skills"] = required
    data["preferred_skills"] = preferred

    # technologies is a deduplicated superset: LLM-listed tools + all skill names.
    technologies = data.get("technologies")
    combined = list(technologies) if isinstance(technologies, list) else []
    combined.extend(entry["name"] for entry in required + preferred)
    data["technologies"] = _normalize_technology_list(combined)

    return data


def _normalize_skill_entries(skills: list[Any]) -> list[dict[str, Any]]:
    """Deduplicate and canonicalize skill entries; preserve source order."""
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []

    for entry in skills:
        if not isinstance(entry, dict):
            continue

        raw_name = str(entry.get("name") or "").strip()
        if not raw_name:
            continue

        canonical = normalize_skill(raw_name) or raw_name
        dedupe_key = canonical.lower()
        if dedupe_key in seen:
            logger.debug("Skipping duplicate skill '%s'", canonical)
            continue
        seen.add(dedupe_key)

        category = entry.get("category") or get_skill_category(canonical)

        normalized.append(
            {
                "name": canonical,
                "category": _null_if_blank(category),
                "min_years": entry.get("min_years"),
            }
        )

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


def _validate_job_description(data: dict[str, Any]) -> JobDescription:
    """Validate sanitized data against ``JobDescription``."""
    try:
        return JobDescription.model_validate(data)
    except PydanticValidationError as exc:
        logger.error("JobDescription validation failed: %s", exc)
        raise ValidationError(
            f"LLM job description output failed schema validation: {exc}"
        ) from exc
