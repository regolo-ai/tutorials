"""Environment-backed configuration for the Qwen 3.5 122b tutorial."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str
    model: str
    reasoning_effort: str


def get_settings() -> Settings:
    api_key = os.getenv("REGOLO_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("REGOLO_API_KEY is not set. Put it in .env or export it.")

    return Settings(
        api_key=api_key,
        base_url=os.getenv("REGOLO_BASE_URL", "https://api.regolo.ai/v1").rstrip("/"),
        model=os.getenv("REGOLO_MODEL", "qwen3.5-122b"),
        reasoning_effort=os.getenv("REGOLO_REASONING_EFFORT", "medium"),
    )
