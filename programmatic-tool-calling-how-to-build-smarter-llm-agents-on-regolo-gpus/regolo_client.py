"""OpenAI-compatible Regolo client for chat and tool calling."""

from __future__ import annotations

import json
from typing import Any

import requests


class RegoloClient:
    def __init__(self, api_key: str, base_url: str, model: str, reasoning_effort: str = "medium") -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.reasoning_effort = reasoning_effort

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def chat_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] = "auto",
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "reasoning_effort": self.reasoning_effort,
        }
        if tools is not None:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice

        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=self._headers,
            data=json.dumps(payload),
            timeout=60,
        )
        response.raise_for_status()
        return response.json()
