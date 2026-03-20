# pr_review_assistant.py
import os
import json
import subprocess
from pathlib import Path
import requests
from typing import Any, Dict, List


def load_local_env(env_path: Path) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_local_env(Path(__file__).with_name(".env"))

API_KEY = os.getenv("REGOLO_API_KEY")
if not API_KEY:
    raise RuntimeError("REGOLO_API_KEY non trovato: definire REGOLO_API_KEY nel file .env o nelle variabili di ambiente")

BASE_URL = os.getenv("REGOLO_BASE_URL", "https://api.regolo.ai")

ENGINEERING_CHECKLIST = """
Review this PR with focus on:
1. correctness
2. security and secrets exposure
3. performance and retry behavior
4. schema or API compatibility
5. observability and rollback safety
6. tests that should exist but are missing
Return markdown with these sections only:
- Summary
- Risks
- Suggested review comments
- Missing tests
- Rollout notes
"""

MODEL = os.getenv("REGOLO_CORE_MODEL", "qwen3.5-122b")

def get_git_diff() -> str:
    commands = [
        ["git", "diff", "--cached"],
        ["git", "diff", "HEAD~1", "HEAD"],
    ]
    for cmd in commands:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
    raise RuntimeError("No diff found. Stage changes or run inside a repo with recent commits.")

def review_diff(model: str, diff_text: str) -> Dict[str, Any]:
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a senior staff engineer reviewing a production pull request. "
                    "Be precise, avoid generic praise, and cite exact diff evidence."
                )
            },
            {
                "role": "user",
                "content": f"{ENGINEERING_CHECKLIST}\n\nDIFF:\n{diff_text[:120000]}"
            }
        ],
        "temperature": 0.1
    }

    r = requests.post(
        f"{BASE_URL}/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        },
        json=payload,
        timeout=180,
    )
    r.raise_for_status()
    return r.json()

def extract_content(resp: Dict[str, Any]) -> str:
    try:
        return resp["choices"][0]["message"]["content"]
    except Exception:
        return json.dumps(resp, indent=2)

def main():
    diff_text = get_git_diff()
    review = review_diff(MODEL, diff_text)

    print(f"# Regolo PR Review\n\nModel: `{MODEL}`\n")
    print(extract_content(review))

if __name__ == "__main__":
    main()
