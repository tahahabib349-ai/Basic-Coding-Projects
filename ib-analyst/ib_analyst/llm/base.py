"""The provider-neutral "socket" every AI engine plugs into.

The rest of the application only talks to `LLMProvider`. To add OpenAI or
Anthropic later, write one new class implementing `generate_json` and
`test_connection`, and register it in `factory.py`. Nothing else changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class LLMResult:
    data: dict
    provider: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    raw_text: str = ""
    notes: list[str] = field(default_factory=list)


class LLMProvider(ABC):
    name: str = "base"
    model: str = ""
    is_demo: bool = False

    @abstractmethod
    def generate_json(self, *, system: str, prompt: str, schema: dict,
                      task: dict | None = None) -> LLMResult:
        """Send instructions + material, receive a JSON object matching `schema`.

        `task` carries optional metadata (e.g. the section list) that a provider
        may use or ignore.
        """

    @abstractmethod
    def test_connection(self) -> str:
        """Make a tiny request. Return a short success message or raise LLMError."""
