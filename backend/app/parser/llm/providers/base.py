"""Abstract base for LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Contract every LLM provider must satisfy.

    Concrete implementations handle SDK setup, retries, timeouts, and
    response unwrapping internally so that callers only deal with plain
    strings.
    """

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Send a prompt pair and return the model's text response.

        Args:
            system_prompt: High-level instructions for the model.
            user_prompt:   The actual content to process.

        Returns:
            Raw text content from the model.

        Raises:
            LLMParsingError: When the provider cannot produce a response.
        """
