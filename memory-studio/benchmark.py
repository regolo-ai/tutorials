"""Reproducible cross-agent memory benchmark: Cold Session Rescan vs ai-memory Wiki + Handoff + Regolo."""
import concurrent.futures
import json
import os
import ssl
import statistics
import time
import urllib.request
from pathlib import Path

from memory_engine import inspect_memory_handoff, select_memory_route

HERE = Path(__file__).resolve().parent
CORPUS_PATH = HERE / "corpus.json"
RESULTS_PATH = HERE / "benchmark_results.json"


def generate_corpus() -> dict:
    banner = (
        "Enterprise memory note: this service belongs to the sovereign EU checkout cluster.\n"
        "# AUDIT-BANNER: all changes must be recorded in the architecture decision log.\n"
        * 26
    )

    raw_session_transcript = (
        "[Turn 01 - Claude Code] Reading repository tree and running pytest...\n"
        "[Turn 02 - Claude Code] Grepping for JWT_LEEWAY_SECONDS and sqlite WAL pragma...\n"
        * 95
    ) + (
        "\n[Turn 91 - Claude Code Summary before rate-limit] "
        "We migrated session tokens in src/session_auth.py to Ed25519 (JWT_LEEWAY_SECONDS = 45, "
        "HEADER_NAME = 'X-Session-Assertion'). Failed approach: do NOT enable SQLite synchronous=OFF "
        "in src/wal_writer.py because crash tests corrupted index_page_42. Keep WAL_AUTOCHECKPOINT_PAGES = 1000 "
        "and BUSY_TIMEOUT_MS = 3500. Next task for OpenCode: update src/quota_enforcer.py so "
        "TEAM_DAILY_POOL_TOKENS = 200000000 and OVERAGE_MODE = 'throttle_to_brick_pro'."
    )

    handoff_brief = (
        "HANDOFF ID: hnd_2026_10_20_eu01 (from: claude-code -> to: opencode)\n"
        "- Completed: Ed25519 auth in src/session_auth.py (JWT_LEEWAY_SECONDS=45, HEADER_NAME='X-Session-Assertion').\n"
        "- Rejected approach: synchronous=OFF in src/wal_writer.py corrupted index_page_42; keep WAL_AUTOCHECKPOINT_PAGES=1000, BUSY_TIMEOUT_MS=3500.\n"
        "- Next step: in src/quota_enforcer.py verify TEAM_DAILY_POOL_TOKENS=200000000 and OVERAGE_MODE='throttle_to_brick_pro'."
    )

    files = [
        {
            "path": "src/session_auth.py",
            "content": f'"""{banner}"""\n'
            + """
SIGNING_ALGO = "Ed25519"
JWT_LEEWAY_SECONDS = 45
HEADER_NAME = "X-Session-Assertion"

def verify_assertion(token: str, pub_key: bytes) -> dict:
    return {"algo": SIGNING_ALGO, "leeway": JWT_LEEWAY_SECONDS}
""",
        },
        {
            "path": "src/wal_writer.py",
            "content": f'"""{banner}"""\n'
            + """
JOURNAL_MODE = "WAL"
SYNCHRONOUS_PRAGMA = "NORMAL"
WAL_AUTOCHECKPOINT_PAGES = 1000
BUSY_TIMEOUT_MS = 3500

def configure_sqlite_wal(conn):
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute(f"PRAGMA wal_autocheckpoint={WAL_AUTOCHECKPOINT_PAGES};")
""",
        },
        {
            "path": "src/quota_enforcer.py",
            "content": f'"""{banner}"""\n'
            + """
TEAM_DAILY_POOL_TOKENS = 200000000
OVERAGE_MODE = "throttle_to_brick_pro"
FALLBACK_MODEL = "brick-complexity-pro"

def check_daily_allowance(used_tokens: int) -> str:
    if used_tokens >= TEAM_DAILY_POOL_TOKENS:
        return OVERAGE_MODE
    return "allow_flagship"
""",
        },
        {
            "path": "src/vector_index.py",
            "content": f'"""{banner}"""\n'
            + """
EMBEDDING_MODEL = "Qwen3-Embedding-8B"
EMBEDDING_DIMENSIONS = 4096
HYBRID_RRF_K = 60
""",
        },
        {
            "path": "src/webhook_dispatcher.py",
            "content": f'"""{banner}"""\n'
            + """
MAX_CONCURRENT_WEBHOOKS = 32
WEBHOOK_RETRY_QUEUE = "q:webhook:retry"
""",
        },
    ]

    questions = [
        {
            "id": "m1",
            "category": "recall",
            "question": "According to the handoff and src/session_auth.py, what signing algorithm is used in SIGNING_ALGO and what is the value of JWT_LEEWAY_SECONDS?",
            "required_terms": ["ed25519", "45"],
        },
        {
            "id": "m2",
            "category": "recall",
            "question": "In src/wal_writer.py, what are the exact values of WAL_AUTOCHECKPOINT_PAGES and BUSY_TIMEOUT_MS?",
            "required_terms": ["1000", "3500"],
        },
        {
            "id": "m3",
            "category": "recall",
            "question": "In src/quota_enforcer.py, what is the exact string in OVERAGE_MODE and the integer value of TEAM_DAILY_POOL_TOKENS?",
            "required_terms": ["throttle_to_brick_pro", "200000000"],
        },
        {
            "id": "m4",
            "category": "recall",
            "question": "In src/vector_index.py, what model name is stored in EMBEDDING_MODEL and what is EMBEDDING_DIMENSIONS?",
            "required_terms": ["qwen3-embedding-8b", "4096"],
        },
        {
            "id": "m5",
            "category": "refactor",
            "question": "Why did the previous Claude Code session reject setting SQLite synchronous=OFF in src/wal_writer.py, and which pragma value in SYNCHRONOUS_PRAGMA must be kept alongside WAL_AUTOCHECKPOINT_PAGES=1000?",
            "required_terms": ["index_page_42", "normal", "1000"],
        },
        {
            "id": "m6",
            "category": "refactor",
            "question": "When used_tokens reaches TEAM_DAILY_POOL_TOKENS (200000000) in src/quota_enforcer.py, what string does check_daily_allowance return and which FALLBACK_MODEL handles requests?",
            "required_terms": ["throttle_to_brick_pro", "brick-complexity-pro"],
        },
    ]

    corpus = {
        "raw_session_transcript": raw_session_transcript,
        "handoff_brief": handoff_brief,
        "files": files,
        "questions": questions,
    }
    CORPUS_PATH.write_text(json.dumps(corpus, indent=2))
    return corpus


def grade_answer(answer: str, required_terms: list[str]) -> bool:
    low = answer.lower().replace(",", "").replace("_", "_")
    return all(term.lower() in low for term in required_terms)


def call_regolo(api_key: str, model: str, reasoning_effort: str, context: str, question: str) -> dict:
    t0 = time.perf_counter()
    payload = {
        "model": model,
        "reasoning_effort": reasoning_effort,
        "temperature": 0.0,
        "max_tokens": 900 if reasoning_effort == "high" else 220,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Answer the cross-agent handoff question using only the provided context. "
                    "Always include every requested constant name, string literal, and integer."
                ),
            },
            {"role": "user", "content": f"{context}\n\nQuestion: {question}"},
        ],
    }
    req = urllib.request.Request(
        "https://api.regolo.ai/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "authorization": f"Bearer {api_key}",
            "content-type": "application/json",
            "user-agent": "regolo-ai-memory-bench/1.0",
        },
        method="POST",
    )
    ssl_ctx = (
        ssl.create_default_context(cafile="/etc/ssl/cert.pem")
        if Path("/etc/ssl/cert.pem").exists()
        else ssl.create_default_context()
    )
    with urllib.request.urlopen(req, timeout=90, context=ssl_ctx) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    elapsed = time.perf_counter() - t0
    msg = data["choices"][0]["message"]
    content = (msg.get("content") or "") + " " + (msg.get("reasoning_content") or "")
    usage = data.get("usage", {})
    return {
        "content": content.strip(),
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
        "latency_s": round(elapsed, 3),
    }


def run_config(name: str, corpus: dict, api_key: str, use_memory: bool, use_routing: bool) -> dict:
    cold_ctx = (
        f"=== RAW TRANSCRIPT ===\n{corpus['raw_session_transcript']}\n\n"
        + "\n\n".join(f"=== FILE: {f['path']} ===\n{f['content']}" for f in corpus["files"])
    )

    def process_item(q_item: dict) -> dict:
        trace = inspect_memory_handoff(corpus, q_item["question"], top_k=2)
        ctx = trace["compressed_prompt"] if use_memory else cold_ctx
        model, effort = select_memory_route(q_item, use_routing)
        res = call_regolo(api_key, model, effort, ctx, q_item["question"])
        passed = grade_answer(res["content"], q_item["required_terms"])
        return {
            "id": q_item["id"],
            "category": q_item["category"],
            "layer1_selected_files": trace["layer1_selected_paths"] if use_memory else [f["path"] for f in corpus["files"]],
            "layer1_chars": trace["layer1_chars"] if use_memory else trace["raw_total_chars"],
            "layer2_chars": trace["layer2_chars"] if use_memory else trace["raw_total_chars"],
            "layer2_step_reduction_pct": trace["layer2_step_reduction_pct"] if use_memory else 0.0,
            "layer2_char_reduction_pct": trace["layer2_reduction_pct"] if use_memory else 0.0,
            "actions": trace["actions"] if use_memory else [],
            "model": model,
            "reasoning_effort": effort,
            "passed": passed,
            "prompt_tokens": res["prompt_tokens"],
            "completion_tokens": res["completion_tokens"],
            "total_tokens": res["total_tokens"],
            "latency_s": res["latency_s"],
        }

    t_start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        items = list(pool.map(process_item, corpus["questions"]))
    wall_s = round(time.perf_counter() - t_start, 2)

    prompt_toks = sum(x["prompt_tokens"] for x in items)
    comp_toks = sum(x["completion_tokens"] for x in items)
    total_toks = sum(x["total_tokens"] for x in items)
    latencies = [x["latency_s"] for x in items]
    accuracy = round(100.0 * sum(1 for x in items if x["passed"]) / len(items), 1)

    zai_cost_1k = (prompt_toks * 1000 / 1e6) * 1.40 + (comp_toks * 1000 / 1e6) * 4.40
    priv_cost_1k = (prompt_toks * 1000 / 1e6) * 2.00 + (comp_toks * 1000 / 1e6) * 10.00
    regolo_payg_1k_eur = sum(
        (x["prompt_tokens"] * 1000 / 1e6) * (0.10 if x["model"] == "brick-complexity-pro" else 1.00)
        + (x["completion_tokens"] * 1000 / 1e6) * (0.40 if x["model"] == "brick-complexity-pro" else 4.20)
        for x in items
    )
    regolo_core_1k_eur = (total_toks * 1000 / 1e6) * 0.065
    regolo_promo_1k_eur = (total_toks * 1000 / 1e6) * 0.0195

    return {
        "name": name,
        "accuracy_pct": accuracy,
        "prompt_tokens": prompt_toks,
        "completion_tokens": comp_toks,
        "total_tokens": total_toks,
        "latency_p50_s": round(statistics.median(latencies), 2),
        "wall_time_s": wall_s,
        "cost_per_1000_sessions": {
            "private_workhorse_usd": round(priv_cost_1k, 2),
            "zai_glm53_direct_usd": round(zai_cost_1k, 2),
            "regolo_payg_eur": round(regolo_payg_1k_eur, 2),
            "regolo_core_standard_eur": round(regolo_core_1k_eur, 2),
            "regolo_core_promo_3mo_eur": round(regolo_promo_1k_eur, 2),
        },
        "items": items,
    }


def main():
    api_key = os.environ.get("REGOLO_API_KEY")
    if not api_key:
        env_candidate = HERE / ".env"
        if env_candidate.exists():
            for line in env_candidate.read_text().splitlines():
                if line.startswith("REGOLO_API_KEY="):
                    api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not api_key:
        raise RuntimeError("Missing REGOLO_API_KEY")

    corpus = generate_corpus()
    configs = [
        ("A. Cold Session Baseline (Full Transcript + Raw Repo Rescan)", False, False),
        ("B. ai-memory Wiki + Claim-Once Handoff Only", True, False),
        ("C. Regolo Brick Complexity Pro Routing Only (Cold Context)", False, True),
        ("D. Full Stack (ai-memory Handoff + Wiki + Regolo Brick Pro)", True, True),
    ]
    results = []
    for label, mem, route in configs:
        print(f"Running {label}...", flush=True)
        r = run_config(label, corpus, api_key, mem, route)
        print(
            f"  -> Accuracy: {r['accuracy_pct']}% | Prompt: {r['prompt_tokens']} | "
            f"Completion: {r['completion_tokens']} | Total: {r['total_tokens']} | "
            f"p50: {r['latency_p50_s']}s | Regolo PAYG/1k: €{r['cost_per_1000_sessions']['regolo_payg_eur']} | "
            f"Regolo Core/1k: €{r['cost_per_1000_sessions']['regolo_core_standard_eur']} (€{r['cost_per_1000_sessions']['regolo_core_promo_3mo_eur']} promo)",
            flush=True,
        )
        if mem and route:
            print("\n  === EXPLICIT 3-LAYER AI-MEMORY PIPELINE LOGS (Configuration D) ===", flush=True)
            for it in r["items"]:
                print(
                    f"  [{it['id']} · {it['category']}]\n"
                    f"    [Layer 1 · FTS5 wiki index] 5 repo files + 90-turn log -> top 2 wiki pages: {it['layer1_selected_files']}\n"
                    f"    [Layer 2 · handoff & wiki consolidation] {it['layer1_chars']} chars -> {it['layer2_chars']} chars (-{it['layer2_char_reduction_pct']}% vs cold session):",
                    flush=True,
                )
                for act in it["actions"]:
                    print(
                        f"      ├─ {act['path']} [{act['compressor']}]: {act['raw_chars']} -> {act['compressed_chars']} chars (-{act['reduction_pct']}%) · {act['detail']}",
                        flush=True,
                    )
                print(
                    f"    [Layer 3 · regolo routing] model={it['model']} reasoning_effort={it['reasoning_effort']} -> "
                    f"in={it['prompt_tokens']} tok, out={it['completion_tokens']} tok, latency={it['latency_s']}s, pass={it['passed']}",
                    flush=True,
                )
        results.append(r)

    RESULTS_PATH.write_text(json.dumps({"date": "2026-10-20", "configurations": results}, indent=2))
    print("\nSaved benchmark_results.json successfully.")


if __name__ == "__main__":
    main()
