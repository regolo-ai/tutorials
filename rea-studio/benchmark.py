"""Reproducible reverse engineering benchmark: Unfiltered REA Dumps vs REA Sieve + Regolo Routing."""
import concurrent.futures
import json
import os
import ssl
import statistics
import time
import urllib.request
from pathlib import Path

from rea_filter import inspect_rea_pipeline, select_rea_route

HERE = Path(__file__).resolve().parent
CORPUS_PATH = HERE / "corpus.json"
RESULTS_PATH = HERE / "benchmark_results.json"


def generate_corpus() -> dict:
    ipc_dump = {
        "bundle": "legacy-pos-desktop/app.asar",
        "ipc_channels": [
            {
                "channel": f"ui:renderer:repaint_widget_{i}",
                "scope": "renderer_ui",
                "file": f"dist/renderer/chunk_{i % 12}.js",
            }
            for i in range(160)
        ]
        + [
            {
                "channel": "ipc:sync:flush_offline_queue",
                "scope": "main_process",
                "handler": "flushOfflineQueueToWal",
                "max_batch_rows": 250,
                "ack_timeout_ms": 4800,
            },
            {
                "channel": "ipc:keystore:unseal_master_key",
                "scope": "preload_bridge",
                "handler": "unsealHardwareKey",
                "cipher": "AES-256-GCM",
                "header_tag": "X-POS-HSM- Seal",
            },
        ],
    }

    symbol_dump = {
        "binary": "bin/pos-sync-daemon-amd64",
        "symbols": [
            {
                "name": f"runtime.std.alloc_bucket_{i}",
                "module": "stdlib_runtime",
                "addr": f"0x0040{i:04x}",
            }
            for i in range(160)
        ]
        + [
            {
                "name": "crypto_keystore.DeriveOfflinePinKey",
                "module": "crypto_keystore",
                "kdf": "Argon2id",
                "memory_kib": 65536,
                "iterations": 4,
            },
            {
                "name": "wal_replicator.ReplicateWalFrame",
                "module": "wal_replicator",
                "sqlite_table": "offline_journal_frames",
                "conflict_policy": "LAST_WRITE_LWW_SEQ",
                "max_retry_backoff_ms": 7200,
            },
        ],
    }

    files = [
        {"path": "rea_dumps/electron_ipc_evidence.json", "content": json.dumps(ipc_dump, indent=2)},
        {"path": "rea_dumps/native_binary_symbols.json", "content": json.dumps(symbol_dump, indent=2)},
    ]

    questions = [
        {
            "id": "r1",
            "category": "triage",
            "question": "In rea_dumps/electron_ipc_evidence.json, what is the exact handler name for ipc:sync:flush_offline_queue and what is max_batch_rows?",
            "required_terms": ["flushofflinequeuetowal", "250"],
        },
        {
            "id": "r2",
            "category": "triage",
            "question": "In rea_dumps/electron_ipc_evidence.json, what cipher is used by ipc:keystore:unseal_master_key and what is ack_timeout_ms on ipc:sync:flush_offline_queue?",
            "required_terms": ["aes-256-gcm", "4800"],
        },
        {
            "id": "r3",
            "category": "triage",
            "question": "In rea_dumps/native_binary_symbols.json, what KDF algorithm and memory_kib value does crypto_keystore.DeriveOfflinePinKey use?",
            "required_terms": ["argon2id", "65536"],
        },
        {
            "id": "r4",
            "category": "triage",
            "question": "In rea_dumps/native_binary_symbols.json, what sqlite_table and conflict_policy are used by wal_replicator.ReplicateWalFrame?",
            "required_terms": ["offline_journal_frames", "last_write_lww_seq"],
        },
        {
            "id": "r5",
            "category": "reconstruct",
            "question": "Trace the end-to-end offline sync path across both REA dumps: which Electron IPC channel triggers flushOfflineQueueToWal (with max_batch_rows=250), and which native daemon symbol writes to offline_journal_frames under LAST_WRITE_LWW_SEQ?",
            "required_terms": ["ipc:sync:flush_offline_queue", "flushofflinequeuetowal", "replicatewalframe", "offline_journal_frames"],
        },
        {
            "id": "r6",
            "category": "reconstruct",
            "question": "Compare ack_timeout_ms on ipc:sync:flush_offline_queue against max_retry_backoff_ms on wal_replicator.ReplicateWalFrame, and name the KDF and cipher used to unseal the offline key.",
            "required_terms": ["4800", "7200", "argon2id", "aes-256-gcm"],
        },
    ]

    corpus = {"files": files, "questions": questions}
    CORPUS_PATH.write_text(json.dumps(corpus, indent=2))
    return corpus


def grade_answer(answer: str, required_terms: list[str]) -> bool:
    low = answer.lower().replace(",", "")
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
                    "Answer the reverse-engineering evidence question using only the provided REA JSON dumps. "
                    "Include every requested symbol name, IPC channel, cipher, table name, and integer."
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
            "user-agent": "regolo-rea-bench/1.0",
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


def run_config(name: str, corpus: dict, api_key: str, use_sieve: bool, use_routing: bool) -> dict:
    unfiltered_ctx = "\n\n".join(f"=== REA EVIDENCE: {f['path']} ===\n{f['content']}" for f in corpus["files"])

    def process_item(q_item: dict) -> dict:
        trace = inspect_rea_pipeline(corpus["files"], q_item["question"])
        ctx = trace["compressed_prompt"] if use_sieve else unfiltered_ctx
        model, effort = select_rea_route(q_item, use_routing)
        res = call_regolo(api_key, model, effort, ctx, q_item["question"])
        passed = grade_answer(res["content"], q_item["required_terms"])
        return {
            "id": q_item["id"],
            "category": q_item["category"],
            "layer1_selected_files": trace["layer1_selected_paths"] if use_sieve else [f["path"] for f in corpus["files"]],
            "layer1_chars": trace["layer1_chars"] if use_sieve else trace["raw_total_chars"],
            "layer2_chars": trace["layer2_chars"] if use_sieve else trace["raw_total_chars"],
            "layer2_step_reduction_pct": trace["layer2_step_reduction_pct"] if use_sieve else 0.0,
            "layer2_char_reduction_pct": trace["layer2_reduction_pct"] if use_sieve else 0.0,
            "actions": trace["actions"] if use_sieve else [],
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
        ("A. Baseline (Unfiltered REA Dumps + Pinned qwen3.5-122b)", False, False),
        ("B. Local REA IPC/Symbol Sieve Only", True, False),
        ("C. Regolo Brick Complexity Pro Routing Only", False, True),
        ("D. Full Stack (REA IPC/Symbol Sieve + Regolo Brick Pro)", True, True),
    ]
    results = []
    for label, sieve, route in configs:
        print(f"Running {label}...", flush=True)
        r = run_config(label, corpus, api_key, sieve, route)
        print(
            f"  -> Accuracy: {r['accuracy_pct']}% | Prompt: {r['prompt_tokens']} | "
            f"Completion: {r['completion_tokens']} | Total: {r['total_tokens']} | "
            f"p50: {r['latency_p50_s']}s | Regolo PAYG/1k: €{r['cost_per_1000_sessions']['regolo_payg_eur']} | "
            f"Regolo Core/1k: €{r['cost_per_1000_sessions']['regolo_core_standard_eur']} (€{r['cost_per_1000_sessions']['regolo_core_promo_3mo_eur']} promo)",
            flush=True,
        )
        if sieve and route:
            print("\n  === EXPLICIT 3-LAYER REA REVERSE-ENGINEERING LOGS (Configuration D) ===", flush=True)
            for it in r["items"]:
                print(
                    f"  [{it['id']} · {it['category']}]\n"
                    f"    [Layer 1 · REA dump selector] 2 raw dumps (37,854 chars) -> {it['layer1_selected_files']}\n"
                    f"    [Layer 2 · REA symbol/IPC sieve] {it['layer1_chars']} chars -> {it['layer2_chars']} chars (-{it['layer2_char_reduction_pct']}% vs raw dumps):",
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
