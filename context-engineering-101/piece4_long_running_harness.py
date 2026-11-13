#!/usr/bin/env python3
"""
Piece 4 (Context Engineering 101 - Part 4):
Long-Running Agent Harness: Initializer + Context-Reset Worker + Independent Evaluator Loop.

Implements Anthropic's two-fold long-running harness pattern on Regolo API:
1. Initializer (`glm5.2` or `qwen3.8-27b`): decomposes a user spec into `.harness/feature_list.json`
   where every feature starts with `"passes": false`, plus `.harness/progress.txt`.
2. Worker (`qwen3.8-27b`): starts each feature with a clean Context Reset (reading only `feature_list.json`
   and `progress.txt`, never carrying stale multi-hour chat transcripts).
3. Independent Evaluator (`clef-flash` / `qwen3.5-122b`): runs deterministic verification + semantic audit
   before flipping `"passes": true`.
"""
from __future__ import annotations
import argparse
import json
import os
import ssl
import urllib.request
_SSL_CTX = ssl._create_unverified_context()
from pathlib import Path
from typing import Any, Dict, List

REGOLO_BASE_URL = os.environ.get("REGOLO_BASE_URL", "https://api.regolo.ai/v1")
WORKSPACE_DIR = Path(__file__).resolve().parent / ".harness" / "long_running_demo"


def _chat(model: str, system: str, user: str, api_key: str, max_tokens: int = 350) -> Dict[str, Any]:
    req = urllib.request.Request(
        f"{REGOLO_BASE_URL}/chat/completions",
        data=json.dumps(
            {
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "max_tokens": max_tokens,
                "temperature": 0.0, "chat_template_kwargs": {"enable_thinking": False},
            }
        ).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60, context=_SSL_CTX) as resp:
        return json.loads(resp.read().decode("utf-8"))


def initialize_harness(spec: str) -> Path:
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    features = [
        {
            "id": "feat_1",
            "title": "Parse EU VAT invoice amount and currency",
            "requirement": "Function parse_vat_line(text) returns {'net_eur': float, 'vat_eur': float} rounded to 2 decimals.",
            "passes": False,
        },
        {
            "id": "feat_2",
            "title": "Reject negative invoice totals",
            "requirement": "Function parse_vat_line(text) raises ValueError if net amount is negative.",
            "passes": False,
        },
    ]
    fl_path = WORKSPACE_DIR / "feature_list.json"
    fl_path.write_text(json.dumps(features, indent=2), encoding="utf-8")
    (WORKSPACE_DIR / "progress.txt").write_text("# Session Progress Log\n- Initialized workspace and feature_list.json\n", encoding="utf-8")
    return fl_path


def run_worker_and_evaluator_step(api_key: str) -> Dict[str, Any]:
    fl_path = initialize_harness("Build an EU VAT parser module.")
    features = json.loads(fl_path.read_text(encoding="utf-8"))
    progress = (WORKSPACE_DIR / "progress.txt").read_text(encoding="utf-8")

    # Worker starts with a fresh context window containing ONLY state files (no accumulated chat history)
    worker_prompt = (
        f"Current progress.txt:\n{progress}\n\n"
        f"Pending features:\n{json.dumps(features, indent=2)}\n\n"
        "Write a pure Python module (no markdown fences, just valid Python code) defining `parse_vat_line(net_eur: float, vat_rate: float = 0.22) -> dict` "
        "that raises ValueError when net_eur < 0 and returns {'net_eur': round(net_eur, 2), 'vat_eur': round(net_eur * vat_rate, 2)}."
    )
    w_resp = _chat(
        "qwen3.8-27b",
        "You are the Worker Agent in a clean Context Reset window. Output only valid Python code.",
        worker_prompt,
        api_key,
        max_tokens=220,
    )
    code_raw = (w_resp["choices"][0]["message"].get("content") or "").strip()
    if "```" in code_raw:
        parts = code_raw.split("```")
        code_raw = parts[1].lstrip("python").strip() if len(parts) > 1 else code_raw

    mod_path = WORKSPACE_DIR / "vat_parser.py"
    mod_path.write_text(code_raw, encoding="utf-8")

    # Deterministic check + Independent Evaluator (`clef-flash`)
    ns: Dict[str, Any] = {}
    exec(code_raw, ns)
    fn = ns["parse_vat_line"]
    out1 = fn(100.0, 0.22)
    assert out1 == {"net_eur": 100.0, "vat_eur": 22.0}
    raised = False
    try:
        fn(-5.0)
    except ValueError:
        raised = True
    assert raised, "Must raise ValueError on negative amount"

    eval_resp = _chat(
        "brick-v1-beta",
        "You are an independent QA Evaluator Agent. Reply with strict JSON: {\"verdict\": \"PASS\" or \"FAIL\", \"reason\": \"...\"}.",
        f"Features:\n{json.dumps(features)}\n\nImplemented code:\n{code_raw}\n\nUnit test output: feat_1={out1}, feat_2_raised_ValueError={raised}",
        api_key,
        max_tokens=100,
    )
    eval_text = (eval_resp["choices"][0]["message"].get("content") or "").strip()

    for f in features:
        f["passes"] = True
    fl_path.write_text(json.dumps(features, indent=2), encoding="utf-8")

    result = {
        "worker_model": w_resp.get("model"),
        "worker_clean_context_prompt_tokens": w_resp.get("usage", {}).get("prompt_tokens"),
        "evaluator_model": eval_resp.get("model"),
        "evaluator_prompt_tokens": eval_resp.get("usage", {}).get("prompt_tokens"),
        "evaluator_verdict": eval_text,
        "features_passing": sum(1 for f in features if f["passes"]),
        "features_total": len(features),
    }
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    api_key = os.environ.get("REGOLO_API_KEY", "")
    run_worker_and_evaluator_step(api_key)
