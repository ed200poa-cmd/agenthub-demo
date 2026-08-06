"""Minimal provider interface used for connectivity checks.

This is deliberately narrower than the agent's real LLM path: it takes a
prompt string and returns a text answer, with no tools and no
conversation state. Its only job is to prove that credentials, region,
and model access work for a given vendor before wiring that vendor into
the agent through ``chat_model.get_chat_model()``.

Run it via ``test_provider.py`` at the repository root.
"""

from __future__ import annotations

import os
from typing import Protocol


class LLMProvider(Protocol):
    def call(self, prompt: str, max_tokens: int = 500, temperature: float = 0.0) -> str:
        ...


class AnthropicDirectProvider:
    """Baseline: calls the Anthropic API directly, the same vendor the
    agent uses by default."""

    def __init__(self, model: str | None = None):
        from anthropic import Anthropic

        self.client = Anthropic()
        self.model = model or os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")

    def call(self, prompt: str, max_tokens: int = 500, temperature: float = 0.0) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        parts = [block.text for block in response.content if block.type == "text"]
        return "".join(parts)


def get_provider() -> LLMProvider:
    """Selects a provider based on the LLM_PROVIDER environment variable.
    Defaults to the direct Anthropic API, which is what this project
    already runs today."""
    choice = os.environ.get("LLM_PROVIDER", "anthropic").lower()

    if choice == "anthropic":
        return AnthropicDirectProvider()

    raise ValueError(f"Unknown LLM_PROVIDER: {choice!r}. Use anthropic.")
