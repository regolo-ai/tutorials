"""Minimal OpenAI-compatible client for Regolo chat completion and streaming."""

from __future__ import annotations

import json
from typing import Any, Iterable

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
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def chat_completion(self, messages: list[dict[str, str]], model: str | None = None) -> str:
        payload: dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "reasoning_effort": self.reasoning_effort,
        }
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=self._headers,
            json=payload,
            timeout=45,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()

    def stream_chat_completion(self, messages: list[dict[str, str]], model: str | None = None) -> Iterable[str]:
        payload: dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "reasoning_effort": self.reasoning_effort,
            "stream": True,
        }
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=self._headers,
            json=payload,
            stream=True,
            timeout=90,
        )
        response.raise_for_status()

        for raw in response.iter_lines(decode_unicode=True):
            if not raw:
                continue
            if not raw.startswith("data:"):
                continue

            chunk = raw.replace("data:", "", 1).strip()
            if chunk == "[DONE]":
                break

            try:
                payload_obj = json.loads(chunk)
            except json.JSONDecodeError:
                continue

            delta = payload_obj.get("choices", [{}])[0].get("delta", {})
            content = delta.get("content")
            if content:
                yield content
