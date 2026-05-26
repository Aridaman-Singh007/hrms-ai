"""Utilities for sanitizing and parsing LLM JSON responses."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.parser.exceptions import LLMParsingError

logger = logging.getLogger(__name__)

_FENCE_PATTERN = re.compile(
    r"^```(?:json|JSON)?\s*\n?(.*?)\n?```\s*$",
    re.DOTALL,
)
_INLINE_FENCE_PATTERN = re.compile(
    r"```(?:json|JSON)?\s*\n?(.*?)\n?```",
    re.DOTALL,
)


def clean_llm_response(raw: str) -> str:
    """Normalize raw LLM text before JSON parsing.

    Steps:
    1. Strip leading/trailing whitespace and BOM.
    2. Remove markdown code fences when present.
    3. Extract the outermost JSON object if extra prose surrounds it.

    Args:
        raw: Unprocessed model output.

    Returns:
        Cleaned string expected to contain JSON.
    """
    if not raw or not raw.strip():
        logger.warning("Received empty LLM response for cleaning")
        return ""

    text = raw.strip().lstrip("\ufeff")

    fence_match = _FENCE_PATTERN.match(text)
    if fence_match:
        text = fence_match.group(1).strip()
        logger.debug("Stripped full-string markdown code fence")
    else:
        inline_match = _INLINE_FENCE_PATTERN.search(text)
        if inline_match:
            text = inline_match.group(1).strip()
            logger.debug("Stripped inline markdown code fence")

    if text.startswith("{") and not _is_balanced_json_object(text):
        extracted = _extract_json_object(text)
        if extracted != text:
            logger.debug("Extracted JSON object from surrounding text (%d chars)", len(extracted))
            text = extracted

    return text.strip()


def safe_json_loads(raw: str) -> Any:
    """Parse cleaned LLM output as JSON with graceful error handling.

    Args:
        raw: Raw or partially cleaned model output.

    Returns:
        Parsed JSON value (typically ``dict`` for resume payloads).

    Raises:
        LLMParsingError: When the response is empty or not valid JSON.
    """
    cleaned = clean_llm_response(raw)

    if not cleaned:
        logger.error("Cannot parse JSON from empty LLM response")
        raise LLMParsingError("LLM response was empty after cleaning")

    decode_error: json.JSONDecodeError | None = None

    try:
        parsed = json.loads(cleaned)
        logger.debug(
            "Parsed LLM JSON successfully (type=%s, size=%d chars)",
            type(parsed).__name__,
            len(cleaned),
        )
        return parsed
    except json.JSONDecodeError as exc:
        decode_error = exc
        logger.warning("Initial JSON parse failed: %s", exc)

    # Fallback: extract a JSON object substring and retry once
    extracted = _extract_json_object(cleaned)
    if extracted and extracted != cleaned:
        try:
            parsed = json.loads(extracted)
            logger.info("Parsed LLM JSON after extracting object substring")
            return parsed
        except json.JSONDecodeError as exc:
            logger.error("JSON parse failed after extraction: %s", exc)
            raise LLMParsingError(
                f"Invalid JSON in LLM response: {exc}"
            ) from exc

    assert decode_error is not None
    logger.error("JSON parse failed: %s", decode_error)
    raise LLMParsingError(
        f"Invalid JSON in LLM response: {decode_error}"
    ) from decode_error


def _is_balanced_json_object(text: str) -> bool:
    """Return True if *text* is a single balanced ``{...}`` object."""
    if not text.startswith("{"):
        return False
    return _extract_json_object(text) == text


def _extract_json_object(text: str) -> str:
    """Extract the first complete top-level JSON object from *text*."""
    start = text.find("{")
    if start == -1:
        return text

    depth = 0
    in_string = False
    escape = False

    for index in range(start, len(text)):
        char = text[index]

        if escape:
            escape = False
            continue

        if char == "\\" and in_string:
            escape = True
            continue

        if char == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]

    return text[start:]
