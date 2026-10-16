"""Thin Regolo client with a meter for time, tokens and estimated cost.

Two kinds of call: ``decide`` sends typed multiple choice questions to Clef-Flash
(``/v1/systemone``), ``write`` asks a chat model for free text (``/v1/chat/completions``).
Costs are estimates from the tokens reported by the API and the Regolo catalog rates.
"""
from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, field

import requests

from app.config import Settings, get_settings


class RegoloError(RuntimeError):
    pass


@dataclass
class Meter:
    """Accumulates usage per kind of call ("decide" or "write")."""

    lock: threading.Lock = field(default_factory=threading.Lock)
    totals: dict = field(default_factory=lambda: {
        "decide": {"calls": 0, "seconds": 0.0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "unpriced_calls": 0},
        "write": {"calls": 0, "seconds": 0.0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "unpriced_calls": 0},
    })

    def record(self, kind: str, seconds: float, input_tokens: int, output_tokens: int, cost: float | None) -> None:
        with self.lock:
            t = self.totals[kind]
            t["calls"] += 1
            t["seconds"] += seconds
            t["input_tokens"] += input_tokens
            t["output_tokens"] += output_tokens
            if cost is None:
                t["unpriced_calls"] += 1
            else:
                t["cost_usd"] += cost

    def snapshot(self) -> dict:
        with self.lock:
            return {k: dict(v) for k, v in self.totals.items()}


class RegoloClient:
    def __init__(self, settings: Settings | None = None, meter: Meter | None = None) -> None:
        self.settings = settings or get_settings()
        self.meter = meter or Meter()
        self.session = requests.Session()
        self._prices: dict[str, tuple[float, float]] | None = None

    @property
    def headers(self) -> dict[str, str]:
        if not self.settings.regolo_api_key or self.settings.regolo_api_key == "replace_me":
            raise RegoloError("REGOLO_API_KEY is not set. Copy .env.example to .env and add your key.")
        return {"Authorization": f"Bearer {self.settings.regolo_api_key}", "Content-Type": "application/json"}

    # -- prices ------------------------------------------------------------
    def prices(self) -> dict[str, tuple[float, float]]:
        """Catalog rates per token as (input, output). Empty when the catalog is unavailable."""
        if self._prices is None:
            try:
                response = self.session.get(f"{self.settings.regolo_admin_url}/model_group/info", headers=self.headers, timeout=30)
                response.raise_for_status()
                self._prices = {
                    row["model_group"]: (float(row.get("input_cost_per_token") or 0), float(row.get("output_cost_per_token") or 0))
                    for row in response.json().get("data", [])
                    if row.get("input_cost_per_token") is not None
                }
            except (requests.RequestException, ValueError, KeyError):
                self._prices = {}
        return self._prices

    def _cost(self, model: str, input_tokens: int, output_tokens: int) -> float | None:
        rate = self.prices().get(model)
        if rate is None:
            return None
        return input_tokens * rate[0] + output_tokens * rate[1]

    # -- Clef-Flash --------------------------------------------------------
    def decide(self, sentences: list[dict], questions: dict) -> dict:
        """One request with up to 64 typed questions. Returns {question_id: answer}."""
        if not questions or len(questions) > 64:
            raise RegoloError("Clef-Flash takes 1 to 64 questions per request.")
        model = self.settings.decision_model
        started = time.monotonic()
        response = self.session.post(
            f"{self.settings.regolo_base_url}/systemone",
            headers=self.headers,
            json={"model": model, "state": {"sentences": sentences}, "questions": questions},
            timeout=120,
        )
        seconds = time.monotonic() - started
        response.raise_for_status()
        payload = response.json()
        answers = payload.get("answers")
        if not isinstance(answers, dict) or set(answers) != set(questions):
            raise RegoloError("Incomplete answer from Clef-Flash.")
        usage = payload.get("usage") or {}
        tin = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
        tout = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
        self.meter.record("decide", seconds, tin, tout, self._cost(model, tin, tout))
        return answers

    # -- chat model --------------------------------------------------------
    def _chat_body(self, model: str, messages: list[dict], temperature: float, max_tokens: int) -> dict:
        body = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        effort = self.settings.reasoning_effort
        if effort and effort != "default":
            # "none" turns reasoning off: a 3 sentence reply takes about 1 second instead of 5 to 70.
            body["reasoning_effort"] = effort
        return body

    def write(self, messages: list[dict], temperature: float = 0.3, max_tokens: int = 1400) -> str:
        """Asks the chat model for text. A reasoning model can spend the whole budget thinking and return
        nothing, so an empty answer cut off by the token limit is retried once with twice the budget."""
        model = self.settings.chat_model
        text, finish = "", ""
        for budget in (max_tokens, max_tokens * 2):
            started = time.monotonic()
            response = self.session.post(
                f"{self.settings.regolo_base_url}/chat/completions",
                headers=self.headers,
                json=self._chat_body(model, messages, temperature, budget),
                timeout=180,
            )
            seconds = time.monotonic() - started
            response.raise_for_status()
            payload = response.json()
            usage = payload.get("usage") or {}
            tin, tout = int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)
            self.meter.record("write", seconds, tin, tout, self._cost(model, tin, tout))
            choice = payload["choices"][0]
            text = strip_reasoning((choice["message"].get("content") or "").strip())
            finish = choice.get("finish_reason") or ""
            if text or finish != "length":
                break
        return text


def strip_reasoning(text: str) -> str:
    """Removes <think>...</think> blocks some reasoning models put in the content."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S | re.I)
    text = re.sub(r"^.*?</think>", "", text, flags=re.S | re.I) if "</think>" in text.lower() else text
    return text.strip()
