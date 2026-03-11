"""Centralized configuration for Parlant + Regolo orchestration demo."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Runtime settings loaded from environment variables."""

    regolo_api_key: str
    regolo_base_url: str = os.getenv("REGOLO_BASE_URL", "https://api.regolo.ai/v1")
    regolo_model: str = os.getenv("REGOLO_MODEL", "Llama-3.3-70B-Instruct")
    temperature: float = float(os.getenv("REGOLO_TEMPERATURE", "0.2"))


def get_settings() -> Settings:
    """Build settings and fail fast when required values are missing."""
    api_key = os.getenv("REGOLO_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("REGOLO_API_KEY is not set. Add it to .env or export it.")

    return Settings(regolo_api_key=api_key)
