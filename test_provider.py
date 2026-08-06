#!/usr/bin/env python3
"""Connectivity check for a single LLM provider.

Sends one short prompt through ``providers.interface.get_provider()`` and
prints the answer. Use this to confirm credentials and model access for a
vendor before switching the agent over to it.

    LLM_PROVIDER=anthropic python3 test_provider.py "What is 2+2?"

Each run costs one API call. Keep the prompts short.
"""

import os
import sys

from providers.interface import get_provider


def main() -> int:
    question = sys.argv[1] if len(sys.argv) > 1 else "What is 2+2?"
    name = os.environ.get("LLM_PROVIDER", "anthropic")

    try:
        provider = get_provider()
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"[{name}] {provider.call(question)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
