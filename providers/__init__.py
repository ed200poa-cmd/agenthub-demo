"""LLM provider abstraction.

Two layers live here, and they serve different callers:

- ``chat_model.get_chat_model()`` returns a LangChain ``BaseChatModel``.
  This is the production path used by ``agent/agent.py``, because a
  tool-calling agent needs a chat model, not a plain text function.

- ``interface.get_provider()`` returns a minimal ``call(prompt) -> str``
  provider. This is a standalone connectivity check used by
  ``test_provider.py``; the agent does not go through it.

Both read the same ``LLM_PROVIDER`` environment variable, which defaults
to ``anthropic``.
"""

from .chat_model import get_chat_model
from .interface import get_provider

__all__ = ["get_chat_model", "get_provider"]
