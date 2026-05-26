"""Google Gemini LLM provider using the ``google-genai`` SDK."""

from __future__ import annotations

import logging
from functools import lru_cache

from google import genai
from google.genai import types
from google.api_core.exceptions import (
    GoogleAPIError,
    ResourceExhausted,
    ServiceUnavailable,
)
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from app.core.config import get_settings
from app.parser.exceptions import LLMParsingError
from app.parser.llm.providers.base import LLMProvider

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT_SECONDS = 120
_MAX_RETRIES = 3


@lru_cache(maxsize=1)
def _get_client() -> genai.Client:
    """Return a configured ``genai.Client`` singleton."""
    settings = get_settings()
    if not settings.gemini_api_key:
        raise LLMParsingError("GEMINI_API_KEY is not set in environment")
    client = genai.Client(api_key=settings.gemini_api_key)
    logger.info("Gemini client initialised (model=%s)", settings.gemini_model)
    return client


def get_gemini_model() -> str:
    """Return the configured Gemini model name."""
    return get_settings().gemini_model


class GeminiProvider(LLMProvider):
    """Gemini-backed LLM provider with retries and timeouts."""

    def __init__(self) -> None:
        self._client = _get_client()
        self._model = get_gemini_model()

    @retry(
        retry=retry_if_exception_type((ResourceExhausted, ServiceUnavailable)),
        stop=stop_after_attempt(_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _call_api(self, system_prompt: str, user_prompt: str) -> str:
        """Low-level API call wrapped with tenacity retry logic."""
        response = self._client.models.generate_content(
            model=self._model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.0,
            ),
        )

        if not response.text or not response.text.strip():
            raise LLMParsingError("Gemini returned an empty response")

        return response.text.strip()

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Send a prompt pair to Gemini and return the model's text response.

        Raises:
            LLMParsingError: On API failures, empty responses, or exhausted
                retries.
        """
        try:
            return self._call_api(system_prompt, user_prompt)
        except LLMParsingError:
            raise
        except ResourceExhausted as exc:
            logger.error("Gemini rate limit exceeded after retries: %s", exc)
            raise LLMParsingError(f"Gemini rate limit exceeded: {exc}") from exc
        except ServiceUnavailable as exc:
            logger.error("Gemini service unavailable after retries: %s", exc)
            raise LLMParsingError(f"Gemini service unavailable: {exc}") from exc
        except GoogleAPIError as exc:
            logger.error("Gemini API error: %s", exc)
            raise LLMParsingError(f"Gemini API error: {exc}") from exc
        except Exception as exc:
            logger.exception("Unexpected error during Gemini call")
            raise LLMParsingError(f"Unexpected Gemini failure: {exc}") from exc
