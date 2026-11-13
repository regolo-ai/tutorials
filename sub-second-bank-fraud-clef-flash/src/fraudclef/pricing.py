"""Regolo price for clef-flash, read from the live catalog (falls back to an env value)."""

from __future__ import annotations

import os
import time

import httpx

FALLBACK_USD_PER_M_INPUT = 0.15  # catalog value on 12 Oct 2026
_cache: dict[str, tuple[float, dict]] = {}


def model_price(model: str = "clef-flash", ttl_s: float = 3600) -> dict:
    """{"usd_per_input_token": float, "source": "regolo catalog" | "fallback"}"""
    hit = _cache.get(model)
    if hit and time.time() - hit[0] < ttl_s:
        return hit[1]
    price = {"usd_per_input_token": float(os.environ.get("REGOLO_USD_PER_M_INPUT", FALLBACK_USD_PER_M_INPUT)) / 1e6,
             "usd_per_output_token": 0.0, "source": "fallback"}
    key = os.environ.get("REGOLO_API_KEY")
    if key:
        try:
            r = httpx.get(f"{os.environ.get('REGOLO_BASE_URL', 'https://api.regolo.ai')}/model_group/info",
                          headers={"Authorization": f"Bearer {key}"}, timeout=5)
            r.raise_for_status()
            entry = next(e for e in r.json()["data"] if e.get("model_group") == model)
            price = {"usd_per_input_token": float(entry["input_cost_per_token"]),
                     "usd_per_output_token": float(entry.get("output_cost_per_token") or 0.0),
                     "source": "regolo catalog"}
        except Exception:
            pass
    _cache[model] = (time.time(), price)
    return price


def cost_usd(input_tokens: int | None, price: dict) -> float:
    return (input_tokens or 0) * price["usd_per_input_token"]
