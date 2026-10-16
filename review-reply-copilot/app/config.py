"""Settings read from the environment (and a local .env file)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    regolo_api_key: str
    regolo_base_url: str
    regolo_admin_url: str
    chat_model: str
    decision_model: str
    reasoning_effort: str
    db_path: Path
    brands_dir: Path
    data_dir: Path
    host: str
    port: int


def get_settings() -> Settings:
    return Settings(
        regolo_api_key=os.getenv("REGOLO_API_KEY", ""),
        regolo_base_url=os.getenv("REGOLO_BASE_URL", "https://api.regolo.ai/v1").rstrip("/"),
        regolo_admin_url=os.getenv("REGOLO_ADMIN_URL", "https://api.regolo.ai").rstrip("/"),
        chat_model=os.getenv("REGOLO_CHAT_MODEL", "qwen3.8-27b"),
        decision_model=os.getenv("REGOLO_DECISION_MODEL", "clef-flash"),
        reasoning_effort=os.getenv("REGOLO_REASONING_EFFORT", "none"),
        db_path=Path(os.getenv("DB_PATH", ROOT / "data" / "app.db")),
        brands_dir=ROOT / "brands",
        data_dir=ROOT / "data",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8100")),
    )
