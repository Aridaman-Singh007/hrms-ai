"""AWS Bedrock LLM provider using the Converse API."""

from __future__ import annotations

import logging
from functools import lru_cache

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import get_settings
from app.parser.exceptions import LLMParsingError
from app.parser.llm.providers.base import LLMProvider

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_MAX_TOKENS = 8192


class _BedrockThrottledError(Exception):
    """Internal marker for retryable Bedrock throttling."""


@lru_cache(maxsize=1)
def _get_bedrock_client():
    """Return a configured Bedrock Runtime client (singleton)."""
    settings = get_settings()
    if not settings.aws_access_key_id or not settings.aws_secret_access_key:
        raise LLMParsingError(
            "AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY must be set for Bedrock"
        )

    client = boto3.client(
        "bedrock-runtime",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )
    logger.info(
        "Bedrock client initialised (region=%s, model=%s)",
        settings.aws_region,
        settings.bedrock_model_id,
    )
    return client


class BedrockProvider(LLMProvider):
    """Bedrock-backed LLM provider with retries and timeouts."""

    def __init__(self) -> None:
        settings = get_settings()
        self._client = _get_bedrock_client()
        self._model = settings.bedrock_model_id

    @retry(
        retry=retry_if_exception_type(_BedrockThrottledError),
        stop=stop_after_attempt(_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _call_api(self, system_prompt: str, user_prompt: str) -> str:
        """Low-level Converse API call wrapped with tenacity retry logic."""
        try:
            response = self._client.converse(
                modelId=self._model,
                system=[{"text": system_prompt}],
                messages=[
                    {
                        "role": "user",
                        "content": [{"text": user_prompt}],
                    }
                ],
                inferenceConfig={
                    "temperature": 0.0,
                    "maxTokens": _MAX_TOKENS,
                },
            )
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code in {
                "ThrottlingException",
                "TooManyRequestsException",
                "ServiceUnavailableException",
                "ModelTimeoutException",
            }:
                raise _BedrockThrottledError(str(exc)) from exc
            raise

        content = (
            response.get("output", {})
            .get("message", {})
            .get("content", [])
        )
        text_parts = [
            block.get("text", "").strip()
            for block in content
            if isinstance(block, dict) and block.get("text")
        ]
        text = "\n".join(part for part in text_parts if part).strip()

        if not text:
            raise LLMParsingError("Bedrock returned an empty response")

        return text

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Send a prompt pair to Bedrock and return the model's text response.

        Raises:
            LLMParsingError: On API failures, empty responses, or exhausted
                retries.
        """
        try:
            return self._call_api(system_prompt, user_prompt)
        except LLMParsingError:
            raise
        except _BedrockThrottledError as exc:
            logger.error("Bedrock throttled after retries: %s", exc)
            raise LLMParsingError(f"Bedrock rate limit exceeded: {exc}") from exc
        except ClientError as exc:
            error = exc.response.get("Error", {})
            code = error.get("Code", "ClientError")
            message = error.get("Message", str(exc))
            logger.error("Bedrock API error (%s): %s", code, message)
            raise LLMParsingError(f"Bedrock API error ({code}): {message}") from exc
        except BotoCoreError as exc:
            logger.error("Bedrock connection error: %s", exc)
            raise LLMParsingError(f"Bedrock connection error: {exc}") from exc
        except Exception as exc:
            logger.exception("Unexpected error during Bedrock call")
            raise LLMParsingError(f"Unexpected Bedrock failure: {exc}") from exc
