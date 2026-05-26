"""High-level LLM client facade.

Provides ``generate_completion`` as the single entry-point used by
the resume parser.  The concrete provider (currently Gemini) is an
implementation detail hidden behind this module.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from app.parser.llm.providers.base import LLMProvider
from app.parser.llm.providers.gemini import GeminiProvider

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_provider() -> LLMProvider:
    """Return the active LLM provider (singleton)."""
    return GeminiProvider()


def generate_completion(system_prompt: str, user_prompt: str) -> str:
    """Generate a text completion using the configured LLM provider.

    Args:
        system_prompt: High-level instructions for the model.
        user_prompt:   The actual content to process.

    Returns:
        Raw text content from the model.

    Raises:
        LLMParsingError: When the provider cannot produce a usable response.
    """
    provider = _get_provider()
    logger.debug(
        "Sending completion request (system_prompt=%d chars, user_prompt=%d chars)",
        len(system_prompt),
        len(user_prompt),
    )
    result = provider.generate(system_prompt, user_prompt)
    logger.info("LLM completion received (%d chars)", len(result))
    return result
