"""
src/utils.py
------------
Shared utility functions.
"""
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple


def now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def clean_llm_text(raw: str) -> str:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json|python)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


def safe_json_parse(raw: str) -> Tuple[Optional[dict], Optional[str]]:
    cleaned = clean_llm_text(raw)
    try:
        return json.loads(cleaned), None
    except json.JSONDecodeError as e:
        return None, f"JSON decode error at line {e.lineno}, col {e.colno}: {e.msg}"


def count_tokens_approx(text: str) -> int:
    return max(1, len(text) // 4)


def prompt_text(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or default


def prompt_float(label: str, default: float) -> float:
    while True:
        raw = input(f"{label} [{default}]: ").strip()
        if not raw:
            return default
        try:
            return float(raw)
        except ValueError:
            print("Please enter a valid number.")


def read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_file(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
