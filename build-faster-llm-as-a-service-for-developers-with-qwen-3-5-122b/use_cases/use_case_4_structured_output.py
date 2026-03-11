"""Use case 4: extract structured data from unstructured text."""

from __future__ import annotations

import json
from typing import Any

from regolo_client import RegoloClient


def clean_json_block(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```json"):
        text = text[len("```json") :]
    if text.startswith("```"):
        text = text[len("```") :]
    if text.endswith("```"):
        text = text[: -len("```")]
    return text.strip()


def extract_job_posting(client: RegoloClient, raw_text: str) -> dict[str, Any]:
    prompt = f"""Extract information from this job posting and return ONLY valid JSON with these fields:
- title (string)
- company (string)
- location (string)
- remote (boolean)
- skills (array of strings)
- experience_years (integer or null)
- salary_range (string or null)

Job posting:
{raw_text}

Return only the JSON object, no markdown, no explanation."""

    content = client.chat_completion(messages=[{"role": "user", "content": prompt}])

    try:
        return json.loads(clean_json_block(content))
    except json.JSONDecodeError:
        return {"error": "Failed to parse JSON", "raw": content}
