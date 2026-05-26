"""Deterministic skill normalization for software-engineering resumes."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from app.parser.normalizers.taxonomy import SKILL_TAXONOMY, get_skill_category

logger = logging.getLogger(__name__)

_WHITESPACE_RE = re.compile(r"\s+")
_PUNCTUATION_RE = re.compile(r"[^\w\s+#.]")
_COMPACT_RE = re.compile(r"[^a-z0-9+#]")


@dataclass(frozen=True, slots=True)
class NormalizedSkill:
    """Structured result for a single normalized skill."""

    name: str
    in_taxonomy: bool
    category: str | None = None

    @property
    def is_known(self) -> bool:
        return self.in_taxonomy


# ---------------------------------------------------------------------------
# Lookup index (deterministic, built once at import)
# ---------------------------------------------------------------------------

_LOOKUP_INDEX: dict[str, str] = {}


def _normalize_key(skill: str) -> str:
    """Lowercase, collapse whitespace, strip surrounding punctuation."""
    text = skill.strip().lower()
    text = _PUNCTUATION_RE.sub("", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text


def _compact_key(skill: str) -> str:
    """Aggressive key: lowercase alphanumeric plus ``+`` and ``#`` only."""
    return _COMPACT_RE.sub("", skill.strip().lower())


def _register_alias(alias: str, canonical: str) -> None:
    """Register lookup variants for an alias string."""
    for key in {_normalize_key(alias), _compact_key(alias), alias.strip().lower()}:
        if key:
            _LOOKUP_INDEX.setdefault(key, canonical)


for _canonical, _meta in SKILL_TAXONOMY.items():
    _register_alias(_canonical, _canonical)
    for _alias in _meta.get("aliases", []):
        if isinstance(_alias, str):
            _register_alias(_alias, _canonical)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def normalize_skill(skill: str) -> str | None:
    """Return the canonical taxonomy name for *skill*, or ``None`` if unknown.

    Matching is case-insensitive and tolerates extra whitespace and punctuation.
    """
    if not skill or not skill.strip():
        return None

    for key in (
        _normalize_key(skill),
        _compact_key(skill),
        skill.strip().lower(),
    ):
        if key in _LOOKUP_INDEX:
            canonical = _LOOKUP_INDEX[key]
            logger.debug("Normalized skill %r -> %r", skill, canonical)
            return canonical

    return None


def normalize_skills(skills: list[str]) -> list[str]:
    """Normalize a list of skill strings with deduplication.

    Known skills are mapped to canonical taxonomy names. Unknown skills are
    preserved using cleaned original text (whitespace/punctuation stripped for
    matching only; returned name keeps readable form).

    Order from the input list is preserved.

    Args:
        skills: Raw skill strings from a resume or LLM output.

    Returns:
        Deduplicated list of normalized skill names.
    """
    results = normalize_skill_objects(skills)
    return [entry.name for entry in results]


def normalize_skill_objects(skills: list[str]) -> list[NormalizedSkill]:
    """Normalize skills into structured objects, separating known vs unknown.

    Args:
        skills: Raw skill strings.

    Returns:
        Deduplicated ``NormalizedSkill`` entries in source order.
    """
    seen: set[str] = set()
    normalized: list[NormalizedSkill] = []

    for raw in skills:
        if raw is None:
            continue

        cleaned = _clean_display_name(raw)
        if not cleaned:
            continue

        canonical = normalize_skill(cleaned)
        in_taxonomy = canonical is not None
        output_name = canonical if in_taxonomy else cleaned
        dedupe_key = output_name.lower()

        if dedupe_key in seen:
            logger.debug("Skipping duplicate skill %r", output_name)
            continue

        seen.add(dedupe_key)
        category = get_skill_category(output_name) if in_taxonomy else None

        normalized.append(
            NormalizedSkill(
                name=output_name,
                in_taxonomy=in_taxonomy,
                category=category,
            )
        )

        if in_taxonomy:
            logger.debug("Mapped skill %r -> %r (%s)", raw, output_name, category)
        else:
            logger.debug("Preserved unknown skill %r", output_name)

    logger.info(
        "Normalized %d raw skills -> %d (%d known, %d unknown)",
        len(skills),
        len(normalized),
        sum(1 for s in normalized if s.in_taxonomy),
        sum(1 for s in normalized if not s.in_taxonomy),
    )
    return normalized


def _clean_display_name(skill: str) -> str:
    """Return a readable cleaned skill label for unknown skills."""
    text = skill.strip()
    text = _WHITESPACE_RE.sub(" ", text)
    return text
