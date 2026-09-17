import os
import time
from typing import Optional

try:
    import requests
except ImportError:
    requests = None

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from .config import (
    REGOLO_API_KEY,
    REGOLO_BASE_URL,
    REGOLO_TIMEOUT,
    REGOLO_MODEL,
    REGOLO_MAX_TOKENS,
    REGOLO_THINKING_EFFORT,
)

class RegoloAPIError(Exception):
    pass

class RegoloClient:
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        if OpenAI is None or requests is None:
            raise RegoloAPIError("Required client dependencies missing. Run 'regolo doctor' to set up the environment.")

        self.api_key = api_key or REGOLO_API_KEY
        self.base_url = base_url or REGOLO_BASE_URL

        if not self.api_key:
            raise RegoloAPIError("REGOLO_API_KEY not configured. Create .env from .env.example.")
        if not self.base_url.startswith("https://"):
            raise RegoloAPIError("REGOLO_BASE_URL must use HTTPS.")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=REGOLO_TIMEOUT,
        )

    def check_connection(self) -> dict:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            res = requests.get(
                f"{self.base_url}/models",
                headers=headers,
                timeout=REGOLO_TIMEOUT,
            )
            if res.status_code == 200:
                data = res.json()
                models = [m.get("id") for m in data.get("data", []) if m.get("id")]
                return {
                    "status": "connected",
                    "endpoint": self.base_url,
                    "models": models,
                }
            return {
                "status": "error",
                "http_status": res.status_code,
                "message": res.text,
            }
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def complete(self, messages, model=None, temperature=None, max_tokens=None, thinking_effort=None, tools=None, tool_choice=None):
        kwargs = {
            "model": model or REGOLO_MODEL,
            "messages": messages,
            "temperature": temperature,
            "timeout": REGOLO_TIMEOUT,
            "max_tokens": max_tokens or REGOLO_MAX_TOKENS,
        }
        effort = thinking_effort or REGOLO_THINKING_EFFORT
        if effort and str(effort).lower() != "none":
            kwargs["reasoning_effort"] = str(effort).lower()

        if tools is not None:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice or "auto"
        return self.client.chat.completions.create(**kwargs)

    def stream(self, messages, model=None, temperature=None, max_tokens=None):
        return self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
