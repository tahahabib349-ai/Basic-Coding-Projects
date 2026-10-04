"""Chooses which AI engine to use. Add new providers here."""

from __future__ import annotations

from ..config import find_api_key, settings
from ..errors import LLMError
from .base import LLMProvider
from .demo_provider import DemoProvider


def available_providers() -> list[str]:
    # Future: "openai", "anthropic" — implement a class in this package and add it here.
    return ["gemini", "demo"]


def get_provider(name: str | None = None, *, session_key: str | None = None,
                 model: str | None = None) -> LLMProvider:
    name = (name or settings.provider).lower()
    if name == "demo":
        return DemoProvider()
    if name == "gemini":
        from .gemini_provider import GeminiProvider

        key, _ = find_api_key(session_key)
        return GeminiProvider(api_key=key, model=model)
    raise LLMError(f"AI provider '{name}' is not supported yet.")
