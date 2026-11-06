"""The one model every agent uses: gpt-6-luna through the Portkey gateway.

The assignment allows ONLY gpt-6-luna. The name is a constant, not read from an env var,
so no other model can slip in through configuration.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

ROOT = Path(__file__).resolve().parent.parent
# PORTKEY_API_KEY lives in the AI COURSE folder's .env (one level above the project).
for env in (ROOT.parent / ".env", ROOT / ".env"):
    load_dotenv(env)

MODEL_NAME = "gpt-6-luna"
PORTKEY_URL = "https://api.portkey.ai/v1"

# Cap each model reply so one runaway answer can't burn the budget.
MODEL_SETTINGS = ModelSettings(max_tokens=4000)

_model: OpenAIResponsesModel | None = None


def get_model() -> OpenAIResponsesModel:
    """One shared model client for all five agents."""
    global _model
    if _model is None:
        key = os.getenv("PORTKEY_API_KEY")
        if not key:
            raise RuntimeError("PORTKEY_API_KEY is not set (put it in the AI COURSE/.env file).")
        client = AsyncOpenAI(
            base_url=PORTKEY_URL,
            api_key="portkey-gateway",  # unused; Portkey authenticates with the header below
            default_headers={"x-portkey-api-key": key},
        )
        _model = OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))
    assert _model.model_name == "gpt-6-luna", "Only gpt-6-luna is allowed in this homework."
    return _model
