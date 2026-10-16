"""Brand profiles: voice, facts, topics and guardrails for each client, as plain JSON files."""
from __future__ import annotations

import json
from functools import lru_cache

from app.config import get_settings


@lru_cache(maxsize=1)
def _all() -> dict[str, dict]:
    profiles = {}
    for path in sorted(get_settings().brands_dir.glob("*.json")):
        profile = json.loads(path.read_text())
        profiles[profile["id"]] = profile
    return profiles


def reload() -> None:
    _all.cache_clear()


def list_brands() -> list[dict]:
    return [{"id": b["id"], "name": b["name"], "type": b["type"], "topics": list(b["topics"])} for b in _all().values()]


def get_brand(brand_id: str) -> dict:
    try:
        return _all()[brand_id]
    except KeyError as error:
        raise KeyError(f"Unknown brand: {brand_id}") from error
