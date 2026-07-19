"""LLM provider implementations."""

from app.parser.llm.providers.base import LLMProvider

__all__ = ["LLMProvider", "BedrockProvider"]


def __getattr__(name: str):
    if name == "BedrockProvider":
        from app.parser.llm.providers.bedrock import BedrockProvider

        return BedrockProvider
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
