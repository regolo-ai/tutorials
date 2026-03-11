"""Configuration loader for Programmatic Tool Calling tutorial."""

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
        raise RuntimeError("REGOLO_API_KEY is not set. Configure .env or export it.")

    return Settings(
        api_key=api_key,
        base_url=os.getenv("REGOLO_BASE_URL", "https://api.regolo.ai/v1").rstrip("/"),
        model=os.getenv("REGOLO_MODEL", "Llama-3.3-70B-Instruct"),
        reasoning_effort=os.getenv("REGOLO_REASONING_EFFORT", "medium"),
    )
