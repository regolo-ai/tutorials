#!/usr/bin/env python3
"""
Piece 2 (Context Engineering 101 - Part 2):
Retrieve, Offload, Delegate Middleware for OpenCode, Claude Code & Codex.

- Hybrid Search & Reranking on Regolo API (`Qwen3-Embedding-8B` + `Qwen3-Reranker-4B`).
- Tool Result Offloading: intercepts outputs exceeding `max_chars`, saves the full payload to
  `.harness/large_tool_results/<id>.txt`, and returns only a file path + head/tail preview.
- Subagent Delegation via `brick-v1-beta`: reads the offloaded file in an isolated context window
  and returns only 3 verified bullet points + line citations to the main agent.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
import time
import ssl
import urllib.request
_SSL_CTX = ssl._create_unverified_context()
from pathlib import Path
from typing import Any, Dict, List

REGOLO_BASE_URL = os.environ.get("REGOLO_BASE_URL", "https://api.regolo.ai/v1")
OFFLOAD_DIR = Path(__file__).resolve().parent / ".harness" / "large_tool_results"


def _post_json(path: str, payload: Dict[str, Any], api_key: str) -> Dict[str, Any]:
    req = urllib.request.Request(
        f"{REGOLO_BASE_URL}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=45, context=_SSL_CTX) as resp:
        return json.loads(resp.read().decode("utf-8"))


def offload_tool_output(tool_name: str, raw_output: str, max_chars: int = 1200) -> Dict[str, Any]:
    """Saves oversized tool output to disk and returns a compact pointer + head/tail preview."""
    if len(raw_output) <= max_chars:
        return {"offloaded": False, "context_payload": raw_output, "saved_path": None}

    OFFLOAD_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(raw_output.encode("utf-8")).hexdigest()[:10]
    file_path = OFFLOAD_DIR / f"{tool_name}_{digest}.txt"
    file_path.write_text(raw_output, encoding="utf-8")

    lines = raw_output.splitlines()
    head = "\n".join(lines[:5])
    tail = "\n".join(lines[-3:])
    preview = (
        f"[OFFLOADED TOOL OUTPUT: {len(raw_output)} chars, {len(lines)} lines saved to {file_path}]\n"
        f"--- HEAD (lines 1-5) ---\n{head}\n"
        f"--- TAIL (last 3 lines) ---\n{tail}\n"
        f"[Action: pass '{file_path}' to delegate_chunk_analyst(path, question) or read_file with offset/limit]"
    )
    return {
        "offloaded": True,
        "saved_path": str(file_path),
        "raw_chars": len(raw_output),
        "preview_chars": len(preview),
        "context_payload": preview,
    }


def cosine_sim(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / max(1e-9, na * nb)


def retrieve_with_qwen_embeddings(query: str, docs: List[Dict[str, str]], api_key: str, top_k: int = 2) -> List[Dict[str, Any]]:
    """Embeds query + candidate chunks with Qwen3-Embedding-8B on Regolo API."""
    inputs = [query] + [d["text"] for d in docs]
    emb_resp = _post_json("/embeddings", {"model": "Qwen3-Embedding-8B", "input": inputs}, api_key)
    vecs = [item["embedding"] for item in emb_resp["data"]]
    q_vec, doc_vecs = vecs[0], vecs[1:]
    scored = []
    for doc, d_vec in zip(docs, doc_vecs):
        scored.append({**doc, "score": round(cosine_sim(q_vec, d_vec), 4)})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


def delegate_chunk_analyst(file_path: str, question: str, api_key: str) -> Dict[str, Any]:
    """Subagent routed via brick-v1-beta reads the offloaded file in its own context and returns 3 concise facts."""
    raw_text = Path(file_path).read_text(encoding="utf-8")
    resp = _post_json(
        "/chat/completions",
        {
            "model": "brick-v1-beta",
            "messages": [
                {
                    "role": "system",
                    "content": "You are an isolated chunk-analyst subagent. Read the file content and answer the question in at most 3 short bullet points citing exact line numbers or metrics. Never dump raw logs.",
                },
                {
                    "role": "user",
                    "content": f"Question: {question}\n\nFile ({file_path}):\n{raw_text}",
                },
            ],
            "max_tokens": 220,
            "temperature": 0.1, "chat_template_kwargs": {"enable_thinking": False},
        },
        api_key,
    )
    msg = resp["choices"][0]["message"]
    content = (msg.get("content") or msg.get("reasoning_content") or "").strip()
    return {
        "served_by_model": resp.get("model"),
        "subagent_prompt_tokens": resp.get("usage", {}).get("prompt_tokens"),
        "subagent_completion_tokens": resp.get("usage", {}).get("completion_tokens"),
        "distilled_summary": content,
        "distilled_tokens_in_main_agent": max(1, len(content) // 4),
    }


def run_self_test() -> Dict[str, Any]:
    # Simulate a 32,000-character raw market/audit log dump (~8,000 tokens)
    filler_lines = [
        f"2026-10-29T08:{i%60:02d}:11Z INFO [worker-{i%8}] Processed batch_id={10000+i} latency_ms={42 + (i%19)} status=200 region=eu-south-1"
        for i in range(360)
    ]
    filler_lines.insert(
        180,
        "2026-10-29T08:31:00Z CRITICAL [billing- reconciliation] Invoice #INV-2026-9941 mismatch: expected EUR 14,200.00, found EUR 9,850.00 (delta EUR 4,350.00) on tenant_id=acme_eu",
    )
    raw_dump = "\n".join(filler_lines)
    raw_tokens = len(raw_dump) // 4

    offloaded = offload_tool_output("fetch_audit_export", raw_dump, max_chars=1200)
    preview_tokens = len(offloaded["context_payload"]) // 4

    result: Dict[str, Any] = {
        "raw_tool_dump_tokens": raw_tokens,
        "offloaded_preview_tokens": preview_tokens,
        "offload_token_savings_pct": round((1.0 - preview_tokens / raw_tokens) * 100, 1),
        "saved_path": offloaded["saved_path"],
    }

    api_key = os.environ.get("REGOLO_API_KEY")
    if api_key:
        docs = [
            {"id": "doc_1", "text": "Our EU datacenter runs 100% green power with certified Zero Data Retention."},
            {"id": "doc_2", "text": "Invoice #INV-2026-9941 on tenant acme_eu showed a EUR 4,350.00 reconciliation delta during the 08:31 UTC billing check."},
            {"id": "doc_3", "text": "Frontend CSS bundle size decreased by 14 KB after removing unused icons."},
        ]
        top_hits = retrieve_with_qwen_embeddings("What happened with invoice INV-2026-9941?", docs, api_key, top_k=1)
        result["top_embedding_hit"] = top_hits[0]

        sub = delegate_chunk_analyst(
            offloaded["saved_path"],
            "Find any CRITICAL billing reconciliation mismatch, the invoice ID, and the EUR delta.",
            api_key,
        )
        result.update(sub)
        result["main_agent_context_reduction_pct"] = round(
            (1.0 - sub["distilled_tokens_in_main_agent"] / raw_tokens) * 100, 1
        )

    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    run_self_test()
