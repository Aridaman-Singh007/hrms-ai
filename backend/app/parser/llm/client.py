"""High-level LLM client facade.

Provides ``generate_completion`` as the single entry-point used by
the resume parser.  The concrete provider is selected via ``LLM_PROVIDER``.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from app.core.config import get_settings
from app.parser.llm.providers.base import LLMProvider

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_provider() -> LLMProvider:
    """Return the active LLM provider (singleton) based on settings."""
    settings = get_settings()
    provider_name = settings.llm_provider.strip().lower()

    if provider_name == "bedrock":
        from app.parser.llm.providers.bedrock import BedrockProvider

        logger.info("Using Bedrock LLM provider (model=%s)", settings.bedrock_model_id)
        return BedrockProvider()

    if provider_name in {"gemini", ""}:
        from app.parser.llm.providers.gemini import GeminiProvider

        logger.info("Using Gemini LLM provider (model=%s)", settings.gemini_model)
        return GeminiProvider()

    raise ValueError(
        f"Unsupported LLM_PROVIDER '{settings.llm_provider}'. "
        "Use 'gemini' or 'bedrock'."
    )


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
