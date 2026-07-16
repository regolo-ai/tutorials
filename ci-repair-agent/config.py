"""
Model configuration for OpenAI-compatible providers.

Works with:
- OpenAI (default)
- Any OpenAI-compatible endpoint (vLLM, LM Studio, Ollama with OpenAI shim,
  Together, Groq, Fireworks, local proxies, etc.) by setting OPENAI_BASE_URL.
"""

from __future__ import annotations

import os
from langchain_openai import ChatOpenAI


def get_chat_model() -> ChatOpenAI:
    """
    Build a ChatOpenAI-compatible client from environment variables.

    Required:
        OPENAI_API_KEY      - API key for the target provider.

    Optional:
        OPENAI_BASE_URL     - Custom base URL for OpenAI-compatible providers.
                               Leave unset to use the official OpenAI API.
        OPENAI_MODEL         - Model name/id exposed by the provider.
                               Defaults to "gpt-4o-mini".
        OPENAI_TEMPERATURE   - Sampling temperature. Defaults to "0".
    """
    # Load all variables from .env file into os.environ if they are not already set
    env_file = ".env"
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip()
                    if val.startswith(('"', "'")) and val.endswith(('"', "'")):
                        val = val[1:-1]
                    if key not in os.environ:
                        os.environ[key] = val

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Export it before running the agent."
        )

    base_url = os.environ.get("OPENAI_BASE_URL")  # e.g. https://api.together.xyz/v1
    model_name = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    temperature = float(os.environ.get("OPENAI_TEMPERATURE", "0"))

    kwargs = {
        "model": model_name,
        "api_key": api_key,
        "temperature": temperature,
    }

    if base_url:
        kwargs["base_url"] = base_url

    return ChatOpenAI(**kwargs)
