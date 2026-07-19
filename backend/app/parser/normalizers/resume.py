"""Deterministic post-LLM normalization for parsed resume data.

Runs after schema validation to enrich fields that should be computed by code
rather than inferred by the LLM: experience durations, total experience, and
known certification issuers. All logic is deterministic — no hallucination.
"""

from __future__ import annotations

import logging
import re
from datetime import date

from app.schemas.resume import CandidateProfile

logger = logging.getLogger(__name__)

_MONTHS: dict[str, int] = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

_PRESENT_TOKENS = frozenset(
    {"present", "current", "currently", "now", "till date", "ongoing", "to date"}
)

# Deterministic issuer map for well-known certifications.
_CERTIFICATION_ISSUERS: dict[str, str] = {
    "aws developer associate": "Amazon Web Services",
    "aws certified developer associate": "Amazon Web Services",
    "aws solutions architect": "Amazon Web Services",
    "aws certified solutions architect": "Amazon Web Services",
    "aws cloud practitioner": "Amazon Web Services",
    "azure fundamentals": "Microsoft",
    "azure developer associate": "Microsoft",
    "google cloud associate": "Google Cloud",
    "professional cloud architect": "Google Cloud",
    "machine learning specialization": "Stanford Online / DeepLearning.AI",
    "deep learning specialization": "DeepLearning.AI",
    "ckad": "The Linux Foundation",
    "cka": "The Linux Foundation",
}


class ResumeNormalizer:
    """Enriches a validated ``CandidateProfile`` with computed fields."""

    def normalize(self, profile: CandidateProfile) -> CandidateProfile:
        """Return a normalized copy of *profile* with computed enrichments."""
        data = profile.model_dump()

        for exp in data.get("experience", []):
            self._normalize_experience_dict(exp)

        for cert in data.get("certifications", []):
            self._fill_certification_issuer(cert)

        if data.get("total_experience_years") is None:
            data["total_experience_years"] = self._compute_total_experience_years(
                data.get("experience", [])
            )

        return CandidateProfile.model_validate(data)

    def _normalize_experience_dict(self, exp: dict) -> None:
        """Normalize dates and compute duration for one experience entry."""
        end_raw = exp.get("end_date")
        is_present = _is_present(end_raw)

        if is_present:
            exp["end_date"] = "Present"
            if exp.get("currently_working") is None:
                exp["currently_working"] = True

        if exp.get("duration_months") is None:
            months = _compute_duration_months(
                exp.get("start_date"), exp.get("end_date")
            )
            if months is not None:
                exp["duration_months"] = months
                logger.debug(
                    "Computed duration_months=%d for %s @ %s",
                    months,
                    exp.get("role"),
                    exp.get("company"),
                )

    def _fill_certification_issuer(self, cert: dict) -> None:
        """Fill a known issuer when the LLM left it null."""
        if cert.get("issuer"):
            return

        name = cert.get("name")
        if not name:
            return

        issuer = _lookup_certification_issuer(name)
        if issuer:
            cert["issuer"] = issuer
            logger.debug("Filled issuer '%s' for certification '%s'", issuer, name)

    def _compute_total_experience_years(self, experiences: list[dict]) -> float | None:
        """Sum experience durations into total years (excludes internships is caller's job)."""
        total_months = 0
        found = False

        for exp in experiences:
            months = exp.get("duration_months")
            if isinstance(months, int) and months > 0:
                total_months += months
                found = True

        if not found:
            return None

        return round(total_months / 12, 1)


def _is_present(value: object) -> bool:
    """Return True when a date value denotes ongoing/current."""
    if not isinstance(value, str):
        return False
    return value.strip().lower() in _PRESENT_TOKENS


def _parse_month_year(value: object) -> date | None:
    """Parse a human-readable date into a ``date`` (day defaults to 1).

    Supports formats like ``"August 2025"``, ``"Aug 2025"``, ``"2025"``,
    ``"08/2025"``, ``"2025-08"``. Returns None when unparseable.
    """
    if not isinstance(value, str):
        return None

    text = value.strip().lower()
    if not text or text in _PRESENT_TOKENS:
        return None

    # Month name + year, e.g. "august 2025" / "aug 2025"
    match = re.search(r"([a-z]+)\.?\s+(\d{4})", text)
    if match and match.group(1) in _MONTHS:
        return date(int(match.group(2)), _MONTHS[match.group(1)], 1)

    # Numeric month/year, e.g. "08/2025" or "8-2025"
    match = re.search(r"\b(\d{1,2})[/\-](\d{4})\b", text)
    if match:
        month = int(match.group(1))
        if 1 <= month <= 12:
            return date(int(match.group(2)), month, 1)

    # Year-month, e.g. "2025-08"
    match = re.search(r"\b(\d{4})[/\-](\d{1,2})\b", text)
    if match:
        month = int(match.group(2))
        if 1 <= month <= 12:
            return date(int(match.group(1)), month, 1)

    # Bare year, e.g. "2025"
    match = re.search(r"\b(\d{4})\b", text)
    if match:
        return date(int(match.group(1)), 1, 1)

    return None


def _compute_duration_months(start: object, end: object) -> int | None:
    """Compute inclusive month span between two human-readable dates.

    ``end`` may be a present token, in which case today's date is used.
    """
    start_date = _parse_month_year(start)
    if start_date is None:
        return None

    if _is_present(end):
        end_date = date.today()
    else:
        end_date = _parse_month_year(end)

    if end_date is None:
        return None

    if end_date < start_date:
        logger.warning("End date %s precedes start date %s; skipping duration", end_date, start_date)
        return None

    months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month) + 1
    return months


def _lookup_certification_issuer(name: str) -> str | None:
    """Return a known issuer for a certification name via normalized matching."""
    normalized = re.sub(r"[^a-z0-9 ]", "", name.strip().lower())
    normalized = re.sub(r"\s+", " ", normalized)

    if normalized in _CERTIFICATION_ISSUERS:
        return _CERTIFICATION_ISSUERS[normalized]

    for key, issuer in _CERTIFICATION_ISSUERS.items():
        if key in normalized:
            return issuer

    return None
