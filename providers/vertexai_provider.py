"""Google Vertex AI connectivity check.

Calls a Gemini model through Vertex AI, behind the same
``call(prompt) -> str`` interface as AnthropicDirectProvider and
BedrockProvider.

This is the check-only path. The agent itself reaches Vertex AI through
``chat_model.get_chat_model()`` (ChatGoogleGenerativeAI in Vertex mode),
not through here.

Requires:
  pip install google-genai
  gcloud auth application-default login
  gcloud services enable aiplatform.googleapis.com
  export GCP_PROJECT_ID=<project>
"""

from __future__ import annotations

import os

from google import genai
from google.genai import types

DEFAULT_MODEL_ID = "gemini-3.6-flash"


class VertexAIProvider:
    def __init__(
        self,
        project_id: str | None = None,
        location: str | None = None,
        model_id: str | None = None,
    ):
        self.project_id = project_id or os.environ["GCP_PROJECT_ID"]
        self.location = location or os.environ.get("GCP_LOCATION", "global")
        self.model_id = model_id or os.environ.get("VERTEX_MODEL_ID", DEFAULT_MODEL_ID)

        self.client = genai.Client(
            vertexai=True,
            project=self.project_id,
            location=self.location,
        )

    def call(self, prompt: str, max_tokens: int = 500, temperature: float = 0.0) -> str:
        response = self.client.models.generate_content(
            model=self.model_id,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
            ),
        )
        return response.text
