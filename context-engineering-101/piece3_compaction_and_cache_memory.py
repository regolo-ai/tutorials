#!/usr/bin/env python3
"""
Piece 3 (Context Engineering 101 - Part 3):
Reversible Compaction + Prompt-Cache-Safe Memory Placement for OpenCode, Claude Code & Codex.

- Reversible Compaction: when conversation history exceeds `threshold_tokens`, saves the verbatim
  transcript to `.harness/conversation_history/<session_id>.md` and compacts older messages via
  `brick-v1-beta` while keeping the last N turns verbatim.
- Prompt-Cache-Safe Memory Placement (Weaviate Engram pattern): places static always-on memory
  (`AGENTS.md` / `UserProfile`) at the start of the conversation right after the system prompt
  (so the entire prefix + conversation history hits the LLM prompt cache), and injects dynamic
  per-turn search results at the very end after the user's message.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import ssl
import urllib.request
_SSL_CTX = ssl._create_unverified_context()
from pathlib import Path
from typing import Any, Dict, List

REGOLO_BASE_URL = os.environ.get("REGOLO_BASE_URL", "https://api.regolo.ai/v1")
HISTORY_DIR = Path(__file__).resolve().parent / ".harness" / "conversation_history"


def estimate_tokens_messages(messages: List[Dict[str, str]]) -> int:
    return sum(max(1, len(m.get("content", "")) // 4) for m in messages)


def build_naive_messages(
    system_prompt: str,
    always_on_memory: str,
    dynamic_search_memories: str,
    history: List[Dict[str, str]],
    user_message: str,
) -> List[Dict[str, str]]:
    """Anti-pattern: pasting dynamic search memories into the system prompt breaks prefix caching on every turn."""
    mutated_system = f"{system_prompt}\n\n[Always-on Memory]\n{always_on_memory}\n\n[Searched Memories]\n{dynamic_search_memories}"
    return [{"role": "system", "content": mutated_system}] + history + [{"role": "user", "content": user_message}]


def build_cache_safe_messages(
    system_prompt: str,
    always_on_memory: str,
    dynamic_search_memories: str,
    history: List[Dict[str, str]],
    user_message: str,
) -> List[Dict[str, str]]:
    """
    Cache-safe layout:
    1. System prompt + Always-on memory stay 100% static at the front.
    2. Conversation history follows unchanged (cached prefix grows cleanly).
    3. Current user message + dynamic per-turn search hits sit at the very end.
    """
    return (
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"[Standing Project Memory - Always On]\n{always_on_memory}"},
            {"role": "assistant", "content": "Understood. I will apply this standing project memory."},
        ]
        + history
        + [
            {
                "role": "user",
                "content": f"{user_message}\n\n<retrieved_turn_memory>\n{dynamic_search_memories}\n</retrieved_turn_memory>",
            }
        ]
    )


def shared_prefix_tokens(msgs_a: List[Dict[str, str]], msgs_b: List[Dict[str, str]]) -> int:
    """Computes how many leading tokens remain identical between Turn T and Turn T+1 (eligible for KV prefix cache)."""
    cached = 0
    for ma, mb in zip(msgs_a, msgs_b):
        if ma.get("role") == mb.get("role") and ma.get("content") == mb.get("content"):
            cached += max(1, len(ma.get("content", "")) // 4)
        else:
            break
    return cached


def reversible_compact(
    messages: List[Dict[str, str]],
    session_id: str,
    api_key: str,
    threshold_tokens: int = 800,
    keep_recent: int = 2,
) -> Dict[str, Any]:
    """Archives full history to disk and summarizes older turns via brick-v1-beta."""
    before_tokens = estimate_tokens_messages(messages)
    if before_tokens <= threshold_tokens or len(messages) <= keep_recent + 1:
        return {"compacted": False, "before_tokens": before_tokens, "after_tokens": before_tokens, "messages": messages}

    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    archive_path = HISTORY_DIR / f"{session_id}.md"
    older = messages[:-keep_recent]
    recent = messages[-keep_recent:]

    archive_text = "\n\n".join(f"### {m['role'].upper()}\n{m['content']}" for m in older)
    archive_path.write_text(archive_text, encoding="utf-8")

    req = urllib.request.Request(
        f"{REGOLO_BASE_URL}/chat/completions",
        data=json.dumps(
            {
                "model": "brick-v1-beta",
                "messages": [
                    {
                        "role": "system",
                        "content": "Summarize the earlier agent turns into a compact checkpoint: (1) completed actions, (2) key file paths/decisions, (3) open blockers. Max 120 words.",
                    },
                    {"role": "user", "content": archive_text},
                ],
                "max_tokens": 220,
                "temperature": 0.1, "chat_template_kwargs": {"enable_thinking": False},
            }
        ).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=45, context=_SSL_CTX) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    summary = (data["choices"][0]["message"].get("content") or data["choices"][0]["message"].get("reasoning_content") or "").strip()

    compacted_messages = [
        {
            "role": "system",
            "content": (
                f"[REVERSIBLE COMPACTION CHECKPOINT - Full transcript archived at {archive_path}]\n"
                f"{summary}\n"
                f"[If you need exact earlier lines, read {archive_path} with read_file]"
            ),
        }
    ] + recent
    after_tokens = estimate_tokens_messages(compacted_messages)
    return {
        "compacted": True,
        "served_by_model": data.get("model"),
        "archive_path": str(archive_path),
        "before_tokens": before_tokens,
        "after_tokens": after_tokens,
        "compaction_reduction_pct": round((1.0 - after_tokens / before_tokens) * 100, 1),
        "messages": compacted_messages,
    }


def run_self_test() -> Dict[str, Any]:
    sys_prompt = "You are a senior Python backend engineer working on our European payment gateway."
    always_on = "- Language: Python 3.12, FastAPI, Pydantic v2.\n- All external HTTP calls must set timeout=10s.\n- Never log raw IBAN or card numbers."
    history_t1 = [
        {"role": "user", "content": f"Step {i}: Audited module payment_router_{i}.py and verified idempotency keys across 12 endpoints with zero regressions." * 6}
        for i in range(1, 15)
    ]
    history_t2 = history_t1 + [
        {"role": "user", "content": "Check webhook signature middleware."},
        {"role": "assistant", "content": "Verified HMAC-SHA256 signature check in webhook_auth.py."},
    ]

    naive_t1 = build_naive_messages(sys_prompt, always_on, "Turn 14 memory: retry delay is 30s", history_t1, "Check webhook signature middleware.")
    naive_t2 = build_naive_messages(sys_prompt, always_on, "Turn 15 memory: HMAC secret rotation every 90d", history_t2, "Now verify rate limits.")

    safe_t1 = build_cache_safe_messages(sys_prompt, always_on, "Turn 14 memory: retry delay is 30s", history_t1, "Check webhook signature middleware.")
    safe_t2 = build_cache_safe_messages(sys_prompt, always_on, "Turn 15 memory: HMAC secret rotation every 90d", history_t2, "Now verify rate limits.")

    total_t2_tokens = estimate_tokens_messages(safe_t2)
    naive_cached = shared_prefix_tokens(naive_t1, naive_t2)
    safe_cached = shared_prefix_tokens(safe_t1, safe_t2)

    result: Dict[str, Any] = {
        "turn_15_total_tokens": total_t2_tokens,
        "naive_system_injection_cached_tokens": naive_cached,
        "naive_cache_hit_pct": round((naive_cached / total_t2_tokens) * 100, 1),
        "cache_safe_layout_cached_tokens": safe_cached,
        "cache_safe_hit_pct": round((safe_cached / total_t2_tokens) * 100, 1),
    }

    api_key = os.environ.get("REGOLO_API_KEY")
    if api_key:
        comp = reversible_compact(history_t2, "session_demo_01", api_key, threshold_tokens=500, keep_recent=2)
        result["compaction_served_by"] = comp.get("served_by_model")
        result["history_tokens_before_compaction"] = comp["before_tokens"]
        result["history_tokens_after_compaction"] = comp["after_tokens"]
        result["compaction_reduction_pct"] = comp.get("compaction_reduction_pct")
        result["archive_path"] = comp.get("archive_path")

    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    run_self_test()
