"""LangChain chat-model factory, selected by the LLM_PROVIDER env var.

``agent/agent.py`` builds a tool-calling agent with
``create_tool_calling_agent``, which requires a LangChain
``BaseChatModel``. Every provider below returns one, so the agent's
tool-calling logic is byte-identical across vendors: only the model
object changes.

Provider-specific packages are imported lazily inside each branch, so
the default ``anthropic`` path needs no extra dependencies. Install the
optional ones from ``providers/requirements-multicloud.txt`` when
switching providers.
"""

from __future__ import annotations

import os

from langchain_core.language_models.chat_models import BaseChatModel

DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"


def get_chat_model(temperature: float = 0.0, max_tokens: int = 2048) -> BaseChatModel:
    choice = os.environ.get("LLM_PROVIDER", "anthropic").lower()

    if choice == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=os.environ.get("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL),
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
            temperature=temperature,
            max_tokens=max_tokens,
        )

    raise ValueError(f"Unknown LLM_PROVIDER: {choice!r}. Use anthropic.")
