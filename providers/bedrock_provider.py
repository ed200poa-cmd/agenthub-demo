"""AWS Bedrock connectivity check.

Calls a Claude model through Bedrock Runtime instead of the Anthropic API
directly. Same prompt in, same plain-text answer out, so it sits behind
the same interface as AnthropicDirectProvider.

This is the check-only path. The agent itself reaches Bedrock through
``chat_model.get_chat_model()`` (ChatBedrockConverse), not through here.

Requires:
  pip install boto3
  aws configure                 # credentials + region
  Bedrock console -> Model access -> request access to the Claude model

Bedrock model IDs are versioned and region-scoped, and newer Claude
models are served through cross-region inference profiles (the ``us.``
prefix). List what your account can actually reach with:

  aws bedrock list-inference-profiles --region us-east-1

then override BEDROCK_MODEL_ID if the default below is not available.
"""

from __future__ import annotations

import json
import os

import boto3

DEFAULT_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"


class BedrockProvider:
    def __init__(self, model_id: str | None = None, region: str | None = None):
        self.model_id = model_id or os.environ.get("BEDROCK_MODEL_ID", DEFAULT_MODEL_ID)
        self.client = boto3.client(
            "bedrock-runtime",
            region_name=region or os.environ.get("AWS_REGION", "us-east-1"),
        )

    def call(self, prompt: str, max_tokens: int = 500, temperature: float = 0.0) -> str:
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }

        response = self.client.invoke_model(
            modelId=self.model_id,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )

        payload = json.loads(response["body"].read())
        # Bedrock's Claude response shape mirrors the Anthropic Messages API:
        # {"content": [{"type": "text", "text": "..."}], ...}
        parts = [block["text"] for block in payload.get("content", []) if block.get("type") == "text"]
        return "".join(parts)
