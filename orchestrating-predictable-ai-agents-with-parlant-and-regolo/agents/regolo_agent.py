"""Regolo chat client used by the orchestrator."""

from __future__ import annotations

from typing import Any

import requests


class RegoloAgent:
    """Thin wrapper around Regolo's OpenAI-compatible chat endpoint."""

    def __init__(self, api_key: str, base_url: str, model: str, temperature: float = 0.2) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=payload,
            timeout=45,
        )
        response.raise_for_status()

        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
