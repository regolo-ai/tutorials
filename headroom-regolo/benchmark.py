"""Reproducible codebase comprehension benchmark: Uncompressed vs Context-Mode + Headroom + Regolo."""
import concurrent.futures
import json
import os
import ssl
import statistics
import time
import urllib.request
from pathlib import Path

from compressor import (
    build_compressed_prompt,
    build_uncompressed_prompt,
    inspect_three_layers,
    select_route_and_effort,
)

HERE = Path(__file__).resolve().parent
CORPUS_PATH = HERE / "corpus.json"
RESULTS_PATH = HERE / "benchmark_results.json"


def generate_corpus() -> dict:
    """Create a realistic multi-file payment & webhook codebase + SRE JSON logs + 12 graded questions."""
    padding_doc = (
        "Enterprise compliance note: all payment mutations must be logged to the audit stream.\n"
        "This module is part of the sovereign billing service v4.2.\n"
        * 18
    )

    files = [
        {
            "path": "src/config.py",
            "content": f'"""{padding_doc}"""\n'
            + '''
WEBHOOK_TOLERANCE_SECONDS = 180
MAX_RETRY_ATTEMPTS = 5
RETRY_BACKOFF_BASE_MS = 450
REDIS_LOCK_TTL_MS = 1200
DEFAULT_CURRENCY = "EUR"
SIGNATURE_HEADER = "X-Regolo-Signature-256"

def get_retry_delay_ms(attempt: int) -> int:
    """Calculate exponential backoff in milliseconds for webhook delivery."""
    return RETRY_BACKOFF_BASE_MS * (2 ** attempt)
''',
        },
        {
            "path": "src/auth.py",
            "content": f'"""{padding_doc}"""\n'
            + '''
import hmac
import hashlib
import time
from src.config import WEBHOOK_TOLERANCE_SECONDS, SIGNATURE_HEADER

def verify_webhook_signature(payload: bytes, header_val: str, secret: str, now_ts: int) -> bool:
    """Verify HMAC-SHA256 webhook signature and enforce timestamp tolerance window."""
    if not header_val or "," not in header_val:
        return False
    parts = dict(item.split("=", 1) for item in header_val.split(","))
    ts_str = parts.get("t", "0")
    sig_hex = parts.get("v1", "")
    ts_val = int(ts_str)
    if abs(now_ts - ts_val) > WEBHOOK_TOLERANCE_SECONDS:
        return False
    signed_payload = f"{ts_val}.".encode() + payload
    expected = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig_hex)
''',
        },
        {
            "path": "src/idempotency.py",
            "content": f'"""{padding_doc}"""\n'
            + '''
from src.config import REDIS_LOCK_TTL_MS

class IdempotencyStore:
    """Manage webhook event deduplication and distributed lock acquisition."""

    def __init__(self, db_conn, redis_client):
        self.db = db_conn
        self.redis = redis_client

    def acquire_event_lock(self, event_id: str) -> bool:
        """Acquire a non-blocking distributed lock for event_id."""
        lock_key = f"lock:webhook:{event_id}"
        return bool(self.redis.set(lock_key, "1", nx=True, px=REDIS_LOCK_TTL_MS))

    def has_processed(self, event_id: str) -> bool:
        """Check SQLite processed_events table BEFORE lock acquisition."""
        row = self.db.execute(
            "SELECT status FROM processed_events WHERE event_id = ?", (event_id,)
        ).fetchone()
        return row is not None and row[0] == "completed"

    def mark_completed(self, event_id: str) -> None:
        """Record completed event_id in SQLite."""
        self.db.execute(
            "INSERT OR REPLACE INTO processed_events (event_id, status) VALUES (?, 'completed')",
            (event_id,),
        )
        self.db.commit()
''',
        },
        {
            "path": "src/webhooks.py",
            "content": f'"""{padding_doc}"""\n'
            + '''
from src.auth import verify_webhook_signature
from src.ledger import append_ledger_entry

def handle_invoice_paid_webhook(event: dict, store, ledger_db) -> dict:
    """Process invoice.paid webhook event and charge customer ledger.

    BUG NOTE: This handler checks store.has_processed(event_id) without calling
    store.acquire_event_lock(event_id) first, and external bank settlement takes 1800ms
    (longer than REDIS_LOCK_TTL_MS = 1200ms), allowing concurrent duplicate webhooks
    within 50ms to pass has_processed() simultaneously and double-charge the ledger.
    """
    event_id = event["id"]
    if store.has_processed(event_id):
        return {"status": "duplicate_ignored", "event_id": event_id}

    # Missing store.acquire_event_lock(event_id) before settlement!
    tx_id = append_ledger_entry(
        ledger_db,
        account_id=event["account_id"],
        amount_cents=event["amount_cents"],
        currency=event.get("currency", "EUR"),
    )
    store.mark_completed(event_id)
    return {"status": "charged", "tx_id": tx_id}
''',
        },
        {
            "path": "src/ledger.py",
            "content": f'"""{padding_doc}"""\n'
            + '''
LEDGER_TABLE = "account_ledger_entries"
MAX_OVERDRAFT_CENTS = 50000

def append_ledger_entry(db_conn, account_id: str, amount_cents: int, currency: str) -> str:
    """Insert an immutable debit or credit row into account_ledger_entries."""
    if amount_cents <= 0:
        raise ValueError("amount_cents must be strictly positive")
    tx_id = f"tx_{account_id}_{amount_cents}"
    db_conn.execute(
        f"INSERT INTO {LEDGER_TABLE} (tx_id, account_id, amount_cents, currency) VALUES (?, ?, ?, ?)",
        (tx_id, account_id, amount_cents, currency),
    )
    db_conn.commit()
    return tx_id
''',
        },
        {
            "path": "src/retry_worker.py",
            "content": f'"""{padding_doc}"""\n'
            + '''
from src.config import MAX_RETRY_ATTEMPTS, get_retry_delay_ms

DEAD_LETTER_QUEUE = "dlq:webhook:failed"

def schedule_or_dead_letter(redis_client, job: dict) -> str:
    """Route failed webhook job to retry queue or dead-letter queue after MAX_RETRY_ATTEMPTS."""
    attempts = int(job.get("attempts", 0)) + 1
    job["attempts"] = attempts
    if attempts > MAX_RETRY_ATTEMPTS:
        redis_client.lpush(DEAD_LETTER_QUEUE, str(job))
        return "dead_lettered"
    delay_ms = get_retry_delay_ms(attempts)
    redis_client.zadd("retry:webhook:zset", {str(job): delay_ms})
    return f"scheduled_in_{delay_ms}ms"
''',
        },
        {
            "path": "src/rate_limiter.py",
            "content": f'"""{padding_doc}"""\n'
            + '''
BURST_CAPACITY_TOKENS = 120
REFILL_RATE_PER_SECOND = 15

def check_token_bucket(bucket_state: dict, now_sec: float, cost: int = 1) -> bool:
    """Evaluate token-bucket rate limit with BURST_CAPACITY_TOKENS=120 and REFILL_RATE_PER_SECOND=15."""
    elapsed = max(0.0, now_sec - bucket_state.get("last_ts", now_sec))
    tokens = min(
        BURST_CAPACITY_TOKENS,
        bucket_state.get("tokens", BURST_CAPACITY_TOKENS) + elapsed * REFILL_RATE_PER_SECOND,
    )
    if tokens < cost:
        return False
    bucket_state["tokens"] = tokens - cost
    bucket_state["last_ts"] = now_sec
    return True
''',
        },
        {
            "path": "logs/sre_incident_dump.json",
            "content": json.dumps(
                {
                    "service": "billing-webhook-ingestor",
                    "environment": "eu-south-1",
                    "events": [
                        {
                            "ts": f"2026-10-19T10:00:{i % 60:02d}Z",
                            "level": "INFO",
                            "event": "healthcheck_ok",
                            "latency_ms": 2,
                            "worker": f"node-{i % 4}",
                        }
                        for i in range(180)
                    ]
                    + [
                        {
                            "ts": "2026-10-19T10:04:12Z",
                            "level": "WARN",
                            "event": "lock_ttl_exceeded",
                            "event_id": "evt_9941",
                            "settlement_ms": 1840,
                            "redis_lock_ttl_ms": 1200,
                        },
                        {
                            "ts": "2026-10-19T10:04:12Z",
                            "level": "FATAL",
                            "event": "duplicate_ledger_charge",
                            "error_code": "ERR_DOUBLE_DEBIT_77",
                            "event_id": "evt_9941",
                            "account_id": "acc_eu_882",
                            "amount_cents": 49000,
                        },
                    ],
                },
                indent=2,
            ),
        },
    ]

    questions = [
        {
            "id": "q1",
            "category": "lookup",
            "question": "In src/config.py, what is the exact value of WEBHOOK_TOLERANCE_SECONDS and the header name in SIGNATURE_HEADER?",
            "required_terms": ["180", "x-regolo-signature-256"],
        },
        {
            "id": "q2",
            "category": "lookup",
            "question": "In src/config.py, what are the values of MAX_RETRY_ATTEMPTS and RETRY_BACKOFF_BASE_MS?",
            "required_terms": ["5", "450"],
        },
        {
            "id": "q3",
            "category": "lookup",
            "question": "In src/retry_worker.py, what is the exact Redis key name stored in DEAD_LETTER_QUEUE?",
            "required_terms": ["dlq:webhook:failed"],
        },
        {
            "id": "q4",
            "category": "lookup",
            "question": "In src/rate_limiter.py, what are the exact values of BURST_CAPACITY_TOKENS and REFILL_RATE_PER_SECOND?",
            "required_terms": ["120", "15"],
        },
        {
            "id": "q5",
            "category": "lookup",
            "question": "In src/ledger.py, what is the exact SQLite table name in LEDGER_TABLE and the value of MAX_OVERDRAFT_CENTS?",
            "required_terms": ["account_ledger_entries", "50000"],
        },
        {
            "id": "q6",
            "category": "lookup",
            "question": "In logs/sre_incident_dump.json, what is the exact error_code and event_id on the FATAL log line?",
            "required_terms": ["err_double_debit_77", "evt_9941"],
        },
        {
            "id": "q7",
            "category": "diagnosis",
            "question": "Why does handle_invoice_paid_webhook in src/webhooks.py allow a duplicate charge when two identical webhooks arrive within 50ms? Name the missing method call on store and the Redis TTL constant.",
            "required_terms": ["acquire_event_lock", "1200"],
        },
        {
            "id": "q8",
            "category": "diagnosis",
            "question": "Compare the settlement duration in logs/sre_incident_dump.json (settlement_ms) against REDIS_LOCK_TTL_MS in src/config.py. What are the two numbers in milliseconds?",
            "required_terms": ["1840", "1200"],
        },
        {
            "id": "q9",
            "category": "diagnosis",
            "question": "How does verify_webhook_signature in src/auth.py construct signed_payload before computing the HMAC-SHA256 digest, and which function compares the digest?",
            "required_terms": ["compare_digest", "sha256"],
        },
        {
            "id": "q10",
            "category": "diagnosis",
            "question": "In src/retry_worker.py, if a job enters schedule_or_dead_letter with attempts=2, what delay in milliseconds is returned by get_retry_delay_ms(3)?",
            "required_terms": ["3600"],
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
        "max_tokens": 1400 if reasoning_effort == "high" else 260,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Answer every part of the codebase question using only the provided files. "
                    "Always include every requested constant string literal, identifier, and number."
                ),
            },
            {
                "role": "user",
                "content": f"{context}\n\nQuestion: {question}",
            },
        ],
    }
    req = urllib.request.Request(
        "https://api.regolo.ai/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "authorization": f"Bearer {api_key}",
            "content-type": "application/json",
            "user-agent": "regolo-codebase-bench/1.0",
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


def run_configuration(
    name: str,
    corpus: dict,
    api_key: str,
    use_compression: bool,
    use_regolo_routing: bool,
) -> dict:
    uncompressed_ctx = build_uncompressed_prompt(corpus)

    def process_q(q_item: dict) -> dict:
        trace = inspect_three_layers(corpus, q_item["question"], top_k=4)
        ctx = trace["compressed_prompt"] if use_compression else uncompressed_ctx
        model, effort = select_route_and_effort(q_item, use_regolo_routing)
        res = call_regolo(api_key, model, effort, ctx, q_item["question"])
        passed = grade_answer(res["content"], q_item["required_terms"])
        return {
            "id": q_item["id"],
            "category": q_item["category"],
            "raw_total_chars": trace["raw_total_chars"],
            "layer1_selected_files": trace["layer1_selected_paths"] if use_compression else [f["path"] for f in corpus["files"]],
            "layer1_skipped_files": trace["layer1_skipped_paths"] if use_compression else [],
            "layer1_chars": trace["layer1_chars"] if use_compression else trace["raw_total_chars"],
            "layer1_reduction_pct": trace["layer1_reduction_pct"] if use_compression else 0.0,
            "layer2_chars": trace["layer2_chars"] if use_compression else trace["raw_total_chars"],
            "layer2_step_reduction_pct": trace["layer2_step_reduction_pct"] if use_compression else 0.0,
            "layer2_char_reduction_pct": trace["layer2_reduction_pct"] if use_compression else 0.0,
            "headroom_actions": trace["headroom_actions"] if use_compression else [],
            "model": model,
            "reasoning_effort": effort,
            "passed": passed,
            "prompt_tokens": res["prompt_tokens"],
            "completion_tokens": res["completion_tokens"],
            "total_tokens": res["total_tokens"],
            "latency_s": res["latency_s"],
        }

    t_start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        items = list(pool.map(process_q, corpus["questions"]))
    wall_s = round(time.perf_counter() - t_start, 2)

    prompt_toks = sum(x["prompt_tokens"] for x in items)
    comp_toks = sum(x["completion_tokens"] for x in items)
    total_toks = sum(x["total_tokens"] for x in items)
    latencies = [x["latency_s"] for x in items]
    accuracy = round(100.0 * sum(1 for x in items if x["passed"]) / len(items), 1)

    # Cost projections per 1,000 sessions (each session = 10 codebase queries)
    # Verified against https://regolo.ai/pricing/ (Core Plan: €39/mo for 600M tokens = €0.065/1M;
    # 70% discount first 3 months: €11.70/mo = €0.0195/1M; all Core models Included).
    # 1. Origin Z.ai GLM-5.3 API ($1.40/1M in, $4.40/1M out)
    zai_cost_1k = (prompt_toks * 1000 / 1e6) * 1.40 + (comp_toks * 1000 / 1e6) * 4.40
    # 2. Private Workhorse API ($2.00/1M in, $10.00/1M out)
    priv_cost_1k = (prompt_toks * 1000 / 1e6) * 2.00 + (comp_toks * 1000 / 1e6) * 10.00
    # 3. Regolo Pay-As-You-Go (regolo.ai/pricing/: brick-complexity-pro €0.10/€0.40, qwen3.5-122b €1.00/€4.20)
    regolo_payg_1k_eur = sum(
        (x["prompt_tokens"] * 1000 / 1e6) * (0.10 if x["model"] == "brick-complexity-pro" else 1.00)
        + (x["completion_tokens"] * 1000 / 1e6) * (0.40 if x["model"] == "brick-complexity-pro" else 4.20)
        for x in items
    )
    # 4. Regolo Core Subscription Pool (€39/mo for 600M tokens = €0.065/1M; €11.70/mo promo = €0.0195/1M)
    regolo_cost_1k_eur = (total_toks * 1000 / 1e6) * 0.065
    regolo_promo_1k_eur = (total_toks * 1000 / 1e6) * 0.0195

    return {
        "name": name,
        "use_compression": use_compression,
        "use_regolo_routing": use_regolo_routing,
        "questions_count": len(items),
        "accuracy_pct": accuracy,
        "prompt_tokens": prompt_toks,
        "completion_tokens": comp_toks,
        "total_tokens": total_toks,
        "latency_p50_s": round(statistics.median(latencies), 2),
        "latency_p95_s": round(sorted(latencies)[int(0.95 * (len(latencies) - 1))], 2),
        "wall_time_s": wall_s,
        "cost_per_1000_sessions": {
            "zai_glm53_direct_usd": round(zai_cost_1k, 2),
            "private_workhorse_usd": round(priv_cost_1k, 2),
            "regolo_payg_eur": round(regolo_payg_1k_eur, 2),
            "regolo_core_standard_eur": round(regolo_cost_1k_eur, 2),
            "regolo_core_promo_3mo_eur": round(regolo_promo_1k_eur, 2),
        },
        "items": items,
    }


def main():
    api_key = os.environ.get("REGOLO_API_KEY")
    if not api_key:
        for env_candidate in (
            Path("/Users/alexgenovese/Desktop/bank anti fraud detection sub second with Clef/.env"),
            HERE.parent / "Reasoning Budgets and Model Routing/.env",
        ):
            if env_candidate.exists():
                for line in env_candidate.read_text().splitlines():
                    if line.startswith("REGOLO_API_KEY="):
                        api_key = line.split("=", 1)[1].strip()
                        break
            if api_key:
                break
    if not api_key:
        raise RuntimeError("Missing REGOLO_API_KEY")

    corpus = generate_corpus()
    configs = [
        ("A. Baseline (Uncompressed + Pinned Flagship)", False, False),
        ("B. Local Compression Only (Context-Mode + Headroom AST)", True, False),
        ("C. Regolo Brick Complexity Pro Only (Uncompressed)", False, True),
        ("D. Full Stack (Context-Mode + Headroom + Regolo Brick Pro)", True, True),
    ]

    results = []
    for label, comp, route in configs:
        print(f"Running {label}...", flush=True)
        r = run_configuration(label, corpus, api_key, comp, route)
        print(
            f"  -> Accuracy: {r['accuracy_pct']}% | Prompt: {r['prompt_tokens']} | "
            f"Completion: {r['completion_tokens']} | Total: {r['total_tokens']} | "
            f"p50: {r['latency_p50_s']}s | wall: {r['wall_time_s']}s | "
            f"Regolo Core/1k: €{r['cost_per_1000_sessions']['regolo_core_standard_eur']}",
            flush=True,
        )
        if comp and route:
            print("\n  === EXPLICIT 3-LAYER PIPELINE LOGS (Configuration D) ===", flush=True)
            for it in r["items"]:
                print(
                    f"  [{it['id']} · {it['category']}]\n"
                    f"    [Layer 1 · context-mode RRF] 8 repo files ({it['raw_total_chars']:,} chars) -> top 4 selected ({it['layer1_chars']} chars): {it['layer1_selected_files']}\n"
                    f"    [Layer 2 · headroom compress] {it['layer1_chars']} chars -> {it['layer2_chars']} chars (-{it['layer2_step_reduction_pct']}% in Layer 2 | -{it['layer2_char_reduction_pct']}% vs raw repo):",
                    flush=True,
                )
                for h in it["headroom_actions"]:
                    print(
                        f"      ├─ {h['path']} [{h['compressor']}]: {h['raw_chars']} -> {h['compressed_chars']} chars (-{h['reduction_pct']}%) · {h['detail']}",
                        flush=True,
                    )
                print(
                    f"    [Layer 3 · regolo routing]   model={it['model']} reasoning_effort={it['reasoning_effort']} -> "
                    f"in={it['prompt_tokens']} tok, out={it['completion_tokens']} tok, latency={it['latency_s']}s, pass={it['passed']}",
                    flush=True,
                )
        results.append(r)

    base = results[0]
    full = results[3]
    summary = {
        "date": "2026-10-20",
        "endpoint": "https://api.regolo.ai/v1/chat/completions",
        "questions_per_session": len(corpus["questions"]),
        "prompt_token_reduction_pct": round(
            100.0 * (1.0 - full["prompt_tokens"] / max(base["prompt_tokens"], 1)), 1
        ),
        "completion_token_reduction_pct": round(
            100.0 * (1.0 - full["completion_tokens"] / max(base["completion_tokens"], 1)), 1
        ),
        "total_token_reduction_pct": round(
            100.0 * (1.0 - full["total_tokens"] / max(base["total_tokens"], 1)), 1
        ),
        "speedup_p50_x": round(base["latency_p50_s"] / max(full["latency_p50_s"], 0.01), 1),
        "configurations": results,
    }
    RESULTS_PATH.write_text(json.dumps(summary, indent=2))
    print("\nSaved benchmark_results.json successfully.")


if __name__ == "__main__":
    main()
