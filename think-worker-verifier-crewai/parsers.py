"""parsers.py — Parsing robusto del JSON dagli output LLM."""
from __future__ import annotations
import json, re
from typing import Type, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

def extract_json_block(text: str) -> str:
    for pattern in [
        r"```json\s*(\{.*?\})\s*```",
        r"```\s*(\{.*?\})\s*```",
        r"(\{.*\})",
    ]:
        m = re.search(pattern, text, re.S)
        if m:
            return m.group(1)
    raise ValueError(f"Nessun JSON trovato nell'output:\n{text[:500]}")

def parse_model(text: str, model_type: Type[T]) -> T:
    data = json.loads(extract_json_block(text))
    return model_type.model_validate(data)
