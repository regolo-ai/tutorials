"""Reproducible architecture diagramming benchmark: Uncompressed vs Local Topology Compression + Regolo Routing."""
import concurrent.futures
import json
import os
import ssl
import statistics
import time
import urllib.request
from pathlib import Path

from topology_extractor import inspect_repo_compression, select_diagram_route

HERE = Path(__file__).resolve().parent
CORPUS_PATH = HERE / "corpus.json"
RESULTS_PATH = HERE / "benchmark_results.json"


def generate_corpus() -> dict:
    yaml_comments = (
        "# Enterprise deployment descriptor v4.8 — ISO 27001 / DORA audit block\n"
        "# Logging and sidecar policies managed by platform-infra team\n"
        * 35
    )
    sql_comments = (
        "-- Sovereign database migration header: GDPR retention & PCI-DSS scope note\n"
        "-- Do not alter foreign key constraints without DBA sign-off\n"
        * 35
    )
    py_doc = (
        "Enterprise API Gateway & Settlement Router — compliance header.\n"
        "All outbound calls must propagate X-Trace-Id across Redis and PostgreSQL.\n"
        * 30
    )

    files = [
        {
            "path": "infra/docker-compose.yml",
            "content": yaml_comments
            + """
services:
  edge-gateway:
    image: regolo/edge-gateway:2.4
    ports: ["8443:8443"]
    depends_on: [auth-service, billing-worker, redis-cache]
    logging:
      driver: json-file
      max-size: "50m"
  auth-service:
    image: regolo/auth-service:1.9
    ports: ["9010:9010"]
    depends_on: [postgres-core, redis-cache]
  billing-worker:
    image: regolo/billing-worker:3.1
    ports: ["9020:9020"]
    depends_on: [postgres-core, kafka-bus]
  redis-cache:
    image: redis:7.2-alpine
    ports: ["6379:6379"]
  postgres-core:
    image: postgres:16-alpine
    ports: ["5432:5432"]
  kafka-bus:
    image: bitnami/kafka:3.7
    ports: ["9092:9092"]
""",
        },
        {
            "path": "db/schema.sql",
            "content": sql_comments
            + """
CREATE TABLE organizations (
    org_id VARCHAR(64) PRIMARY KEY,
    plan_tier VARCHAR(32) NOT NULL
);
CREATE TABLE api_keys (
    key_id VARCHAR(64) PRIMARY KEY,
    org_id VARCHAR(64) NOT NULL REFERENCES organizations(org_id),
    rate_limit_rpm INT NOT NULL DEFAULT 600
);
CREATE TABLE settlement_ledgers (
    tx_id VARCHAR(64) PRIMARY KEY,
    org_id VARCHAR(64) NOT NULL REFERENCES organizations(org_id),
    key_id VARCHAR(64) NOT NULL REFERENCES api_keys(key_id),
    amount_cents BIGINT NOT NULL
);
""",
        },
        {
            "path": "src/gateway_routes.py",
            "content": f'"""{py_doc}"""\n'
            + """
@app.post("/v1/inference/chat")
def route_chat(req):
    auth_client.verify_key("auth-service:9010")
    cache.check_rate("redis-cache:6379")
    return worker.dispatch("billing-worker:9020")

@app.post("/v1/billing/settle")
def settle_invoice(req):
    db.insert("postgres-core:5432", table="settlement_ledgers")
    bus.publish("kafka-bus:9092", topic="events.settled")
    return {"status": "settled"}
""",
        },
        {
            "path": "src/worker_consumers.py",
            "content": f'"""{py_doc}"""\n'
            + """
def consume_settlement_events():
    event = kafka.poll("kafka-bus:9092", topic="events.settled")
    postgres.write("postgres-core:5432", table="settlement_ledgers")
    redis.invalidate("redis-cache:6379", key="org:balance")
""",
        },
    ]

    questions = [
        {
            "id": "t1",
            "category": "topology",
            "question": "In infra/docker-compose.yml, which three services does edge-gateway depend on, and what external port does edge-gateway expose?",
            "required_terms": ["auth-service", "billing-worker", "redis-cache", "8443"],
        },
        {
            "id": "t2",
            "category": "topology",
            "question": "In infra/docker-compose.yml, which two backing stores does billing-worker depend on, and what port does kafka-bus expose?",
            "required_terms": ["postgres-core", "kafka-bus", "9092"],
        },
        {
            "id": "t3",
            "category": "schema",
            "question": "In db/schema.sql, which two tables does settlement_ledgers reference via foreign keys, and what is the primary key of settlement_ledgers?",
            "required_terms": ["organizations", "api_keys", "tx_id"],
        },
        {
            "id": "t4",
            "category": "schema",
            "question": "In src/gateway_routes.py, which Kafka topic and PostgreSQL table are written when /v1/billing/settle is called?",
            "required_terms": ["events.settled", "settlement_ledgers"],
        },
        {
            "id": "t5",
            "category": "svg_map",
            "question": "Generate a compact inline <svg viewBox='0 0 640 320'> architecture diagram snippet on a 4px grid containing <title>, <rect>, and <text> nodes for edge-gateway, billing-worker, postgres-core, and kafka-bus.",
            "required_terms": ["<svg", "edge-gateway", "billing-worker", "postgres-core", "kafka-bus"],
        },
        {
            "id": "t6",
            "category": "svg_map",
            "question": "Generate a compact inline <svg viewBox='0 0 640 320'> ER diagram snippet on a 4px grid containing <title>, <rect>, and <text> nodes for organizations, api_keys, and settlement_ledgers.",
            "required_terms": ["<svg", "organizations", "api_keys", "settlement_ledgers"],
        },
    ]

    corpus = {"files": files, "questions": questions}
    CORPUS_PATH.write_text(json.dumps(corpus, indent=2))
    return corpus


def grade_answer(answer: str, required_terms: list[str]) -> bool:
    low = answer.lower()
    return all(term.lower() in low for term in required_terms)


def call_regolo(api_key: str, model: str, reasoning_effort: str, context: str, question: str) -> dict:
    t0 = time.perf_counter()
    payload = {
        "model": model,
        "reasoning_effort": reasoning_effort,
        "temperature": 0.0,
        "max_tokens": 900 if reasoning_effort == "high" else 240,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Answer the architecture or SVG generation task using only the provided files. "
                    "Include every requested service name, port, table name, and SVG tag."
                ),
            },
            {"role": "user", "content": f"{context}\n\nTask: {question}"},
        ],
    }
    req = urllib.request.Request(
        "https://api.regolo.ai/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "authorization": f"Bearer {api_key}",
            "content-type": "application/json",
            "user-agent": "regolo-diagram-bench/1.0",
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


def run_config(name: str, corpus: dict, api_key: str, use_compression: bool, use_routing: bool) -> dict:
    uncompressed_ctx = "\n\n".join(f"=== FILE: {f['path']} ===\n{f['content']}" for f in corpus["files"])

    def process_item(q_item: dict) -> dict:
        trace = inspect_repo_compression(corpus["files"], q_item["category"])
        ctx = trace["compressed_prompt"] if use_compression else uncompressed_ctx
        model, effort = select_diagram_route(q_item, use_routing)
        res = call_regolo(api_key, model, effort, ctx, q_item["question"])
        passed = grade_answer(res["content"], q_item["required_terms"])
        return {
            "id": q_item["id"],
            "category": q_item["category"],
            "layer1_selected_files": trace["layer1_selected_paths"] if use_compression else [f["path"] for f in corpus["files"]],
            "layer1_chars": trace["layer1_chars"] if use_compression else trace["raw_total_chars"],
            "layer2_chars": trace["layer2_chars"] if use_compression else trace["raw_total_chars"],
            "layer2_step_reduction_pct": trace["layer2_step_reduction_pct"] if use_compression else 0.0,
            "layer2_char_reduction_pct": trace["layer2_reduction_pct"] if use_compression else 0.0,
            "actions": trace["actions"] if use_compression else [],
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
    env_file = HERE / ".env"  # optional: a .env next to this script (git-ignored), see .env.example
    if not api_key and env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("REGOLO_API_KEY="):
                api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    if not api_key:
        raise RuntimeError("Missing REGOLO_API_KEY: export it or put it in .env (see .env.example)")

    corpus = generate_corpus()
    configs = [
        ("A. Baseline (Uncompressed + Pinned qwen3.5-122b)", False, False),
        ("B. Local Topology Compression Only", True, False),
        ("C. Regolo Brick Complexity Pro Routing Only", False, True),
        ("D. Full Stack (Local Topology Compression + Regolo Brick Pro)", True, True),
    ]
    results = []
    for label, comp, route in configs:
        print(f"Running {label}...", flush=True)
        r = run_config(label, corpus, api_key, comp, route)
        print(
            f"  -> Accuracy: {r['accuracy_pct']}% | Prompt: {r['prompt_tokens']} | "
            f"Completion: {r['completion_tokens']} | Total: {r['total_tokens']} | "
            f"p50: {r['latency_p50_s']}s | Regolo PAYG/1k: €{r['cost_per_1000_sessions']['regolo_payg_eur']} | "
            f"Regolo Core/1k: €{r['cost_per_1000_sessions']['regolo_core_standard_eur']} (€{r['cost_per_1000_sessions']['regolo_core_promo_3mo_eur']} promo)",
            flush=True,
        )
        if comp and route:
            print("\n  === EXPLICIT 3-LAYER DIAGRAM PIPELINE LOGS (Configuration D) ===", flush=True)
            for it in r["items"]:
                print(
                    f"  [{it['id']} · {it['category']}]\n"
                    f"    [Layer 1 · file selector] 4 repo files -> {len(it['layer1_selected_files'])} selected ({it['layer1_chars']} chars): {it['layer1_selected_files']}\n"
                    f"    [Layer 2 · topology compressor] {it['layer1_chars']} chars -> {it['layer2_chars']} chars (-{it['layer2_step_reduction_pct']}% in Layer 2 | -{it['layer2_char_reduction_pct']}% vs raw repo):",
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
