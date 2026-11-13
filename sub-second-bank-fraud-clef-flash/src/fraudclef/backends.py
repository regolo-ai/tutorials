"""Decision backends speaking the SystemOne protocol (`POST /v1/systemone`)."""

from __future__ import annotations

import asyncio
import math
import os
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Protocol

import httpx


class BackendError(Exception):
    pass


@dataclass
class ModelResult:
    answers: dict[str, dict[str, Any]]
    input_tokens: int | None
    backend: str
    model: str


class DecisionBackend(Protocol):
    name: str
    model: str

    async def decide(self, state: dict, questions: dict, timeout_s: float) -> ModelResult: ...

    async def aclose(self) -> None: ...


class SystemOneBackend:
    """HTTP client for the SystemOne protocol, as served by Regolo."""

    def __init__(self, name: str, base_url: str, model: str, api_key: str | None = None):
        self.name, self.model = name, model
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers=headers,
            limits=httpx.Limits(max_keepalive_connections=32, max_connections=64, keepalive_expiry=60),
        )

    async def decide(self, state: dict, questions: dict, timeout_s: float) -> ModelResult:
        deadline = time.perf_counter() + timeout_s
        payload = {"model": self.model, "state": state, "questions": questions}
        for attempt in (1, 2):
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                raise BackendError(f"{self.name}: time budget exhausted")
            try:
                resp = await self._client.post("/v1/systemone", json=payload, timeout=remaining)
                break
            except httpx.ConnectError as e:
                # One retry, only for connection errors and only within the budget.
                if attempt == 2:
                    raise BackendError(f"{self.name}: connection failed: {e}") from e
            except httpx.TimeoutException as e:
                raise BackendError(f"{self.name}: timeout after {timeout_s * 1000:.0f} ms") from e
            except httpx.HTTPError as e:
                raise BackendError(f"{self.name}: {type(e).__name__}: {e}") from e
        if resp.status_code != 200:
            # Never echo request headers (API key); the body of an error is safe to show.
            raise BackendError(f"{self.name}: HTTP {resp.status_code}: {resp.text[:300]}")
        body = resp.json()
        answers = body.get("answers")
        if not isinstance(answers, dict) or set(answers) != set(questions):
            raise BackendError(f"{self.name}: malformed answers: {str(body)[:300]}")
        for qid, a in answers.items():
            _validate_answer(qid, a)
        return ModelResult(answers, (body.get("usage") or {}).get("input_tokens"), self.name, body.get("model", self.model))

    async def aclose(self) -> None:
        await self._client.aclose()


def _validate_answer(qid: str, a: dict) -> None:
    t = a.get("type")
    vals = []
    if t == "noul":
        vals = [a.get("noul")]
    elif t in ("choice", "score"):
        vals = list((a.get("probabilities") or {}).values())
    if not vals or any(not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 or v > 1 for v in vals):
        raise BackendError(f"answer '{qid}' has invalid probabilities: {a}")


def regolo_backend(model: str = "clef-flash") -> SystemOneBackend:
    key = os.environ.get("REGOLO_API_KEY")
    if not key:
        raise BackendError("REGOLO_API_KEY is not set (copy .env.example to .env)")
    return SystemOneBackend("regolo", os.environ.get("REGOLO_BASE_URL", "https://api.regolo.ai"), model, key)


class FakeBackend:
    """Deterministic offline stand-in for tests and demos without a model. It reads the
    precomputed features from the state; it is NOT a fraud model."""

    name = "fake"

    def __init__(self, model: str = "fake-clef", fail: bool = False, delay_s: float = 0.0):
        self.model, self.fail, self.delay_s = model, fail, delay_s
        self.calls = 0

    async def decide(self, state: dict, questions: dict, timeout_s: float) -> ModelResult:
        self.calls += 1
        if self.delay_s:
            if self.delay_s > timeout_s:
                await asyncio.sleep(timeout_s)
                raise BackendError("fake: timeout")
            await asyncio.sleep(self.delay_s)
        if self.fail:
            raise BackendError("fake: simulated outage")
        f = state.get("features", {})
        signals = {
            "amount_anomalous": _sig(f.get("amount_zscore", 0) - 6),
            "geo_device_inconsistent": 0.9 if (f.get("new_country") or f.get("ip_geo_mismatch")) else 0.4 if f.get("new_device") else 0.05,
            "account_takeover": 0.95 if (f.get("new_device") and f.get("new_beneficiary") and f.get("profile_change_hours", 1e6) < 72) else 0.05,
        }
        level = sum(signals.values()) / len(signals)
        answers: dict[str, dict] = {}
        for qid, q in questions.items():
            if q["type"] == "noul":
                answers[qid] = {"type": "noul", "noul": signals.get(qid, level)}
            elif q["type"] == "choice":
                opts = list(q["criteria"])
                pick = opts[0] if level < 0.35 else next((o for o in opts if o in ("card_fraud", "account_takeover")), opts[-1])
                probs = {o: (0.9 if o == pick else 0.1 / (len(opts) - 1)) for o in opts}
                answers[qid] = {"type": "choice", "choice": pick, "confidence": 0.9, "probabilities": probs}
            else:
                n = len(q["criteria"])
                idx = min(int(level * n), n - 1)
                probs = {str(i): (0.85 if i == idx else 0.15 / (n - 1)) for i in range(n)}
                score = sum(i * p for i, p in enumerate(probs.values()))
                answers[qid] = {"type": "score", "score": score, "confidence": 0.85, "probabilities": probs}
        return ModelResult(answers, None, self.name, self.model)

    async def aclose(self) -> None:
        pass


def _sig(x: float) -> float:
    return 1 / (1 + math.exp(-x))


class CircuitBreaker:
    """Opens when the failure ratio over a sliding window exceeds a threshold; after
    `open_s` it lets traffic through again (half-open) and closes on success."""

    def __init__(self, failure_ratio: float, window_s: float, open_s: float, min_calls: int = 5):
        self.failure_ratio, self.window_s, self.open_s, self.min_calls = failure_ratio, window_s, open_s, min_calls
        self._events: deque[tuple[float, bool]] = deque()
        self._opened_at: float | None = None

    def allow(self) -> bool:
        if self._opened_at is None:
            return True
        if time.monotonic() - self._opened_at >= self.open_s:
            self._opened_at = None  # half-open: let the next call probe
            self._events.clear()
            return True
        return False

    def record(self, ok: bool) -> None:
        now = time.monotonic()
        self._events.append((now, ok))
        while self._events and now - self._events[0][0] > self.window_s:
            self._events.popleft()
        failures = sum(1 for _, good in self._events if not good)
        if len(self._events) >= self.min_calls and failures / len(self._events) >= self.failure_ratio:
            self._opened_at = now

    @property
    def is_open(self) -> bool:
        return self._opened_at is not None


class BackendRouter:
    """Guards the backend with a circuit breaker: while it is open, requests go straight to the
    policy's fail mode instead of waiting for a timeout (DORA: the bank keeps deciding when the
    ICT provider is down)."""

    def __init__(self, backend: DecisionBackend, breaker_cfg):
        self.backend = backend
        self.breaker = CircuitBreaker(breaker_cfg.failure_ratio, breaker_cfg.window_s, breaker_cfg.open_s, breaker_cfg.min_calls)

    async def decide(self, state: dict, questions: dict, timeout_s: float) -> ModelResult:
        if not self.breaker.allow():
            raise BackendError(f"{self.backend.name}: circuit open")
        try:
            result = await self.backend.decide(state, questions, timeout_s)
        except BackendError:
            self.breaker.record(False)
            raise
        self.breaker.record(True)
        return result

    async def aclose(self) -> None:
        await self.backend.aclose()


def make_backend(kind: str, model: str) -> DecisionBackend:
    if kind == "regolo":
        return regolo_backend(model)
    if kind == "fake":
        return FakeBackend()
    raise ValueError(f"unknown backend {kind!r}")
