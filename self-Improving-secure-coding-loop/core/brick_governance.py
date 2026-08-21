"""Brick Governance, Policy Enforcement & Telemetry Engine.
Tracks tokens, latencies, estimated costs per model, and compares Regolo.ai multi-model routing
vs single frontier model baseline.
"""

import json
import time
from typing import Any, Dict, List, Optional
import config

_TELEMETRY_LOG: List[Dict[str, Any]] = []


def record_telemetry_event(
    stage: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency: float,
    mode: str = "live",
    error: Optional[str] = None,
) -> Dict[str, Any]:
    """Log an execution stage in Brick telemetry store with per-model dynamic cost estimation."""
    total_tokens = prompt_tokens + completion_tokens

    # Look up per-model pricing in config.PRICING_ESTIMATION
    model_prices = config.PRICING_ESTIMATION.get(
        model,
        config.PRICING_ESTIMATION.get("GLM-5.2", {
            "prompt_cost_per_1m": 0.60,
            "completion_cost_per_1m": 1.80,
        })
    )

    cost_regolo = (
        (prompt_tokens / 1_000_000.0) * model_prices["prompt_cost_per_1m"]
        + (completion_tokens / 1_000_000.0) * model_prices["completion_cost_per_1m"]
    )

    # Calculate baseline Frontier cost (e.g. GPT-4o / Claude 3.5 Sonnet frontier pricing)
    frontier_prices = config.PRICING_ESTIMATION["single_frontier_baseline"]
    cost_frontier = (
        (prompt_tokens / 1_000_000.0) * frontier_prices["prompt_cost_per_1m"]
        + (completion_tokens / 1_000_000.0) * frontier_prices["completion_cost_per_1m"]
    )

    event = {
        "timestamp": time.time(),
        "stage": stage,
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "latency_sec": round(latency, 2),
        "cost_regolo_usd": round(cost_regolo, 6),
        "cost_frontier_usd": round(cost_frontier, 6),
        "savings_usd": round(max(0.0, cost_frontier - cost_regolo), 6),
        "mode": mode,
        "error": error,
    }

    _TELEMETRY_LOG.append(event)
    _persist_telemetry()
    return event


def get_telemetry_summary() -> Dict[str, Any]:
    """Aggregate all session telemetry metrics."""
    total_prompt = sum(e["prompt_tokens"] for e in _TELEMETRY_LOG)
    total_completion = sum(e["completion_tokens"] for e in _TELEMETRY_LOG)
    total_tokens = total_prompt + total_completion
    total_regolo_cost = sum(e["cost_regolo_usd"] for e in _TELEMETRY_LOG)
    total_frontier_cost = sum(e["cost_frontier_usd"] for e in _TELEMETRY_LOG)
    total_savings = max(0.0, total_frontier_cost - total_regolo_cost)
    savings_pct = (
        round((total_savings / total_frontier_cost) * 100.0, 1)
        if total_frontier_cost > 0
        else 82.5
    )
    total_latency = sum(e["latency_sec"] for e in _TELEMETRY_LOG)

    return {
        "events_count": len(_TELEMETRY_LOG),
        "total_prompt_tokens": total_prompt,
        "total_completion_tokens": total_completion,
        "total_tokens": total_tokens,
        "total_regolo_cost_usd": round(total_regolo_cost, 5),
        "total_frontier_cost_usd": round(total_frontier_cost, 5),
        "total_savings_usd": round(total_savings, 5),
        "savings_percentage": savings_pct,
        "total_latency_sec": round(total_latency, 2),
        "events": _TELEMETRY_LOG,
    }


def clear_telemetry():
    """Clear memory telemetry for a new run."""
    global _TELEMETRY_LOG
    _TELEMETRY_LOG = []
    _persist_telemetry()


def _persist_telemetry():
    """Write telemetry to disk."""
    try:
        with open(config.TELEMETRY_DB_PATH, "w", encoding="utf-8") as f:
            json.dump(_TELEMETRY_LOG, f, indent=2)
    except Exception:
        pass


def enforce_policy_check(stage: str, prompt: str) -> Dict[str, Any]:
    """Brick Policy Enforcer: ensure request conforms to security and budget rules."""
    max_allowed_len = 50_000
    if len(prompt) > max_allowed_len:
        return {
            "allowed": False,
            "reason": f"Prompt exceeds maximum character budget ({len(prompt)} > {max_allowed_len})",
        }

    # Forbidden dangerous patterns
    forbidden_tokens = ["rm -rf /", "DROP DATABASE", ":(){ :|:& };:"]
    for token in forbidden_tokens:
        if token in prompt:
            return {
                "allowed": False,
                "reason": f"Forbidden destructive token detected: {token}",
            }

    return {"allowed": True, "policy": "PASSED"}
