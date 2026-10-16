#!/usr/bin/env python3
"""
Reproducible retrieval & MRL compression benchmark:
- Local Apple M1 Ultra (64GB RAM) via Ollama:
  - embeddinggemma-2:270m-bf16-text (Google EmbeddingGemma 2 text tower, 270M, 768d)
  - embeddinggemma:latest (Google EmbeddingGemma 1 baseline, 308M, 768d)
  - qwen3-embedding:0.6b (Alibaba Qwen3-Embedding-0.6B, 595M, 1024d)
- Regolo Sovereign EU API (https://api.regolo.ai/v1):
  - Qwen3-Embedding-8B (4096d native + MRL pass-through)
  - Qwen3-Reranker-4B (two-stage cross-encoder reranking on /v1/rerank)
"""
from __future__ import annotations

import json
import math
import os
import ssl
import statistics
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
CORPUS_PATH = BASE_DIR / "corpus.json"
RESULTS_PATH = BASE_DIR / "results" / "benchmark_results.json"

OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
REGOLO_URL = os.environ.get("REGOLO_BASE_URL", "https://api.regolo.ai/v1")


def load_regolo_key() -> str:
    if os.environ.get("REGOLO_API_KEY"):
        return os.environ["REGOLO_API_KEY"].strip()
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.strip().startswith(("REGOLO_API_KEY=", "regolo_api_key=")):
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                if val and val != "replace_me":
                    return val
    raise RuntimeError("Set REGOLO_API_KEY in your environment or in .env (see .env.example)")


def format_query(model: str, query: str, domain: str) -> str:
    m = model.lower()
    if "embeddinggemma" in m:
        if domain == "code":
            return f"task: code retrieval | query: {query}"
        return f"task: search result | query: {query}"
    if "qwen3-embedding" in m:
        if domain == "code":
            task = "Given a natural language description of code, retrieve the matching code implementation"
        elif domain == "multilingual":
            task = "Given a multilingual search query in Italian or English, retrieve relevant compliance or technical passages that answer the query"
        else:
            task = "Given a technical search query, retrieve relevant documentation passages that answer the query"
        return f"Instruct: {task}\nQuery:{query}"
    return query


def format_document(model: str, title: str, text: str) -> str:
    m = model.lower()
    if "embeddinggemma" in m:
        return f"title: {title} | text: {text}"
    return f"{title}\n{text}"


def mrl_truncate_and_normalize(vec: list[float], dim: int) -> list[float]:
    sliced = vec[:dim]
    norm = math.sqrt(sum(x * x for x in sliced))
    if norm < 1e-12:
        return sliced
    return [x / norm for x in sliced]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def dcg_at_k(ranked_doc_ids: list[str], qrels: dict[str, int], k: int) -> float:
    score = 0.0
    for idx, doc_id in enumerate(ranked_doc_ids[:k], start=1):
        rel = qrels.get(doc_id, 0)
        if rel > 0:
            score += (2**rel - 1) / math.log2(idx + 1)
    return score


def ndcg_at_k(ranked_doc_ids: list[str], qrels: dict[str, int], k: int = 10) -> float:
    actual = dcg_at_k(ranked_doc_ids, qrels, k)
    ideal_Order = [doc_id for doc_id, _ in sorted(qrels.items(), key=lambda x: x[1], reverse=True)]
    ideal = dcg_at_k(ideal_Order, qrels, k)
    return actual / ideal if ideal > 0 else 0.0


def recall_at_k(ranked_doc_ids: list[str], qrels: dict[str, int], k: int = 5) -> float:
    relevant = {doc_id for doc_id, rel in qrels.items() if rel > 0}
    if not relevant:
        return 0.0
    hits = sum(1 for doc_id in ranked_doc_ids[:k] if doc_id in relevant)
    return hits / len(relevant)


def mrr_at_k(ranked_doc_ids: list[str], qrels: dict[str, int], k: int = 10) -> float:
    relevant = {doc_id for doc_id, rel in qrels.items() if rel > 0}
    for idx, doc_id in enumerate(ranked_doc_ids[:k], start=1):
        if doc_id in relevant:
            return 1.0 / idx
    return 0.0


def _http_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: float = 60.0) -> dict[str, Any]:
    cafile = "/etc/ssl/cert.pem" if Path("/etc/ssl/cert.pem").exists() else None
    try:
        ctx = ssl.create_default_context(cafile=cafile)
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", **headers},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        if "CERTIFICATE_VERIFY_FAILED" not in str(exc):
            raise
        ctx = ssl._create_unverified_context()
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", **headers},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return json.loads(resp.read().decode("utf-8"))


def embed_ollama(model: str, inputs: list[str] | str) -> tuple[list[list[float]], float]:
    t0 = time.perf_counter()
    res = _http_json(f"{OLLAMA_URL}/api/embed", {"model": model, "input": inputs}, {})
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    return res["embeddings"], elapsed_ms


def embed_regolo(
    api_key: str, model: str, inputs: list[str] | str, dimensions: int | None = None
) -> tuple[list[list[float]], float]:
    payload: dict[str, Any] = {"model": model, "input": inputs}
    if dimensions is not None:
        payload["dimensions"] = dimensions
    t0 = time.perf_counter()
    res = _http_json(
        f"{REGOLO_URL}/embeddings",
        payload,
        {"Authorization": f"Bearer {api_key}"},
        timeout=90.0,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    items = sorted(res["data"], key=lambda x: x["index"])
    return [item["embedding"] for item in items], elapsed_ms


def rerank_regolo(
    api_key: str,
    query: str,
    candidate_docs: list[dict[str, str]],
    top_n: int = 10,
    use_chat_template: bool = True,
) -> tuple[list[str], float]:
    task = "Given a web search query, retrieve relevant passages that answer the query"
    if use_chat_template:
        formatted_query = (
            '<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the Instruct provided. '
            'Note that the answer can only be "yes" or "no".<|im_end|>\n'
            f"<|im_start|>user\n<Instruct>: {task}\n<Query>: {query}\n"
        )
        formatted_docs = [
            f"<Document>: {d['title']}\n{d['text']}<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
            for d in candidate_docs
        ]
    else:
        formatted_query = f"<Instruct>: {task}\n<Query>: {query}"
        formatted_docs = [f"<Document>: {d['title']}\n{d['text']}" for d in candidate_docs]
    payload = {
        "model": "Qwen3-Reranker-4B",
        "query": formatted_query,
        "documents": formatted_docs,
        "top_n": top_n,
    }
    t0 = time.perf_counter()
    res = _http_json(
        f"{REGOLO_URL}/rerank",
        payload,
        {"Authorization": f"Bearer {api_key}"},
        timeout=60.0,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    ranked_indices = [item["index"] for item in res.get("results", [])]
    return [candidate_docs[i]["id"] for i in ranked_indices], elapsed_ms


def get_ollama_ps() -> list[dict[str, str]]:
    out = subprocess.check_output(["/opt/homebrew/bin/ollama", "ps"], text=True)
    lines = [line.strip() for line in out.strip().splitlines() if line.strip()]
    if len(lines) <= 1:
        return []
    records = []
    for line in lines[1:]:
        parts = line.split()
        records.append({"raw": line, "name": parts[0], "id": parts[1], "size": f"{parts[2]} {parts[3]}"})
    return records


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return s[int(k)]
    return s[f] * (c - k) + s[c] * (k - f)


def evaluate_rankings(
    queries: list[dict[str, Any]],
    doc_ids: list[str],
    doc_vecs: list[list[float]],
    query_vecs: list[list[float]],
    target_dim: int,
) -> dict[str, Any]:
    trunc_docs = [mrl_truncate_and_normalize(v, target_dim) for v in doc_vecs]
    trunc_queries = [mrl_truncate_and_normalize(v, target_dim) for v in query_vecs]

    per_domain: dict[str, list[dict[str, float]]] = {"code": [], "multilingual": [], "tech_docs": []}
    all_metrics: list[dict[str, float]] = []
    top_candidates_by_query: dict[str, list[str]] = {}

    for q_obj, q_vec in zip(queries, trunc_queries):
        scored = [(doc_id, cosine_similarity(q_vec, d_vec)) for doc_id, d_vec in zip(doc_ids, trunc_docs)]
        scored.sort(key=lambda x: x[1], reverse=True)
        ranked_ids = [doc_id for doc_id, _ in scored]
        top_candidates_by_query[q_obj["id"]] = ranked_ids

        m = {
            "ndcg@10": ndcg_at_k(ranked_ids, q_obj["qrels"], 10),
            "recall@5": recall_at_k(ranked_ids, q_obj["qrels"], 5),
            "mrr@10": mrr_at_k(ranked_ids, q_obj["qrels"], 10),
        }
        per_domain[q_obj["domain"]].append(m)
        all_metrics.append(m)

    def summarize(items: list[dict[str, float]]) -> dict[str, float]:
        return {
            "ndcg@10": round(statistics.mean(x["ndcg@10"] for x in items) * 100, 2),
            "recall@5": round(statistics.mean(x["recall@5"] for x in items) * 100, 2),
            "mrr@10": round(statistics.mean(x["mrr@10"] for x in items) * 100, 2),
        }

    return {
        "overall": summarize(all_metrics),
        "by_domain": {dom: summarize(vals) for dom, vals in per_domain.items()},
        "top_candidates": top_candidates_by_query,
    }


def run_benchmark() -> dict[str, Any]:
    api_key = load_regolo_key()
    corpus_data = json.loads(CORPUS_PATH.read_text())
    documents: list[dict[str, str]] = corpus_data["documents"]
    queries: list[dict[str, Any]] = corpus_data["queries"]
    doc_ids = [d["id"] for d in documents]
    doc_by_id = {d["id"]: d for d in documents}

    models_config = [
        {
            "id": "embeddinggemma-2:270m-bf16-text",
            "label": "EmbeddingGemma 2 (270M Text BF16)",
            "provider": "local_ollama",
            "native_dim": 768,
            "mrl_dims": [768, 512, 256, 128],
        },
        {
            "id": "embeddinggemma:latest",
            "label": "EmbeddingGemma 1 (308M Baseline)",
            "provider": "local_ollama",
            "native_dim": 768,
            "mrl_dims": [768, 512, 256, 128],
        },
        {
            "id": "qwen3-embedding:0.6b",
            "label": "Qwen3-Embedding-0.6B (Local)",
            "provider": "local_ollama",
            "native_dim": 1024,
            "mrl_dims": [1024, 768, 512, 256, 128],
        },
        {
            "id": "Qwen3-Embedding-8B",
            "label": "Qwen3-Embedding-8B (Regolo API)",
            "provider": "regolo_api",
            "native_dim": 4096,
            "mrl_dims": [4096, 1024, 768, 512, 256, 128],
        },
    ]

    results: dict[str, Any] = {
        "metadata": {
            "date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "local_hardware": "Apple M1 Ultra (64 GB unified memory, macOS arm64)",
            "ollama_version": "0.40.4",
            "regolo_endpoint": REGOLO_URL,
            "num_documents": len(documents),
            "num_queries": len(queries),
        },
        "models": {},
        "api_native_mrl_verification": {},
        "two_stage_reranking": {},
    }

    raw_embeddings_store: dict[str, dict[str, Any]] = {}

    for cfg in models_config:
        mid = cfg["id"]
        print(f"=== Benchmarking {cfg['label']} ({mid}) ===")
        formatted_docs = [format_document(mid, d["title"], d["text"]) for d in documents]
        formatted_queries = [format_query(mid, q["query"], q["domain"]) for q in queries]

        # Warm-up
        if cfg["provider"] == "local_ollama":
            embed_ollama(mid, "warmup query")
            ps_info = get_ollama_ps()
        else:
            embed_regolo(api_key, mid, "warmup query")
            ps_info = []

        # Batch index all 60 documents
        t_idx0 = time.perf_counter()
        if cfg["provider"] == "local_ollama":
            doc_vecs, idx_ms = embed_ollama(mid, formatted_docs)
        else:
            doc_vecs, idx_ms = embed_regolo(api_key, mid, formatted_docs)
        idx_total_ms = (time.perf_counter() - t_idx0) * 1000.0

        # Sequential single-query latency (30 queries)
        query_vecs: list[list[float]] = []
        query_latencies_ms: list[float] = []
        for fq in formatted_queries:
            if cfg["provider"] == "local_ollama":
                qv, q_ms = embed_ollama(mid, fq)
            else:
                qv, q_ms = embed_regolo(api_key, mid, fq)
            query_vecs.append(qv[0])
            query_latencies_ms.append(q_ms)

        # Also test unprefixed (raw) queries to quantify asymmetric prompt mismatch penalty!
        raw_query_vecs: list[list[float]] = []
        if cfg["provider"] == "local_ollama":
            raw_query_vecs, _ = embed_ollama(mid, [q["query"] for q in queries])
        else:
            raw_query_vecs, _ = embed_regolo(api_key, mid, [q["query"] for q in queries])

        mrl_results = {}
        for dim in cfg["mrl_dims"]:
            eval_out = evaluate_rankings(queries, doc_ids, doc_vecs, query_vecs, dim)
            mrl_results[str(dim)] = {
                "overall": eval_out["overall"],
                "by_domain": eval_out["by_domain"],
                "ram_10m_vectors_float32_gb": round((10_000_000 * dim * 4) / (1024**3), 2),
                "ram_10m_vectors_int8_gb": round((10_000_000 * dim * 1) / (1024**3), 2),
            }

        unprefixed_eval = evaluate_rankings(queries, doc_ids, doc_vecs, raw_query_vecs, cfg["native_dim"])
        native_eval = evaluate_rankings(queries, doc_ids, doc_vecs, query_vecs, cfg["native_dim"])

        raw_embeddings_store[mid] = {
            "top_candidates": native_eval["top_candidates"],
        }

        results["models"][mid] = {
            "label": cfg["label"],
            "provider": cfg["provider"],
            "native_dim": len(doc_vecs[0]),
            "ollama_ps": ps_info,
            "indexing_60_docs_ms": round(idx_total_ms, 1),
            "docs_per_sec": round(len(documents) / (idx_total_ms / 1000.0), 1),
            "query_latency_ms": {
                "p50": round(percentile(query_latencies_ms, 0.50), 2),
                "p95": round(percentile(query_latencies_ms, 0.95), 2),
                "mean": round(statistics.mean(query_latencies_ms), 2),
            },
            "native_metrics": native_eval["overall"],
            "native_by_domain": native_eval["by_domain"],
            "unprefixed_query_metrics": unprefixed_eval["overall"],
            "unprefixed_query_by_domain": unprefixed_eval["by_domain"],
            "mrl_curve": mrl_results,
        }

    # Verify Regolo API server-side `dimensions` pass-through on Qwen3-Embedding-8B (e.g. dimensions=512 and 256)
    print("=== Verifying Regolo API native dimensions parameter (512d & 256d) ===")
    for api_dim in [512, 256]:
        formatted_docs_8b = [format_document("Qwen3-Embedding-8B", d["title"], d["text"]) for d in documents]
        formatted_queries_8b = [format_query("Qwen3-Embedding-8B", q["query"], q["domain"]) for q in queries]
        d_vecs_api, _ = embed_regolo(api_key, "Qwen3-Embedding-8B", formatted_docs_8b, dimensions=api_dim)
        q_vecs_api, _ = embed_regolo(api_key, "Qwen3-Embedding-8B", formatted_queries_8b, dimensions=api_dim)
        eval_api_dim = evaluate_rankings(queries, doc_ids, d_vecs_api, q_vecs_api, api_dim)
        results["api_native_mrl_verification"][str(api_dim)] = {
            "returned_dim": len(d_vecs_api[0]),
            "overall": eval_api_dim["overall"],
            "by_domain": eval_api_dim["by_domain"],
        }

    # Experiment 3: Two-Stage Retrieval (First-stage Top-15 -> Qwen3-Reranker-4B on Regolo API)
    print("=== Running Two-Stage Retrieval with Qwen3-Reranker-4B on Regolo API ===")
    for first_stage_id in ["embeddinggemma-2:270m-bf16-text", "qwen3-embedding:0.6b", "Qwen3-Embedding-8B"]:
        top_map = raw_embeddings_store[first_stage_id]["top_candidates"]
        rerank_latencies: list[float] = []
        per_domain_rr: dict[str, list[dict[str, float]]] = {"code": [], "multilingual": [], "tech_docs": []}
        all_rr: list[dict[str, float]] = []

        for q_obj in queries:
            cand_ids = top_map[q_obj["id"]][:15]
            cand_docs = [doc_by_id[cid] for cid in cand_ids]
            reranked_ids, rr_ms = rerank_regolo(api_key, q_obj["query"], cand_docs, top_n=10, use_chat_template=True)
            rerank_latencies.append(rr_ms)
            m = {
                "ndcg@10": ndcg_at_k(reranked_ids, q_obj["qrels"], 10),
                "recall@5": recall_at_k(reranked_ids, q_obj["qrels"], 5),
                "mrr@10": mrr_at_k(reranked_ids, q_obj["qrels"], 10),
            }
            per_domain_rr[q_obj["domain"]].append(m)
            all_rr.append(m)

        def sum_rr(items: list[dict[str, float]]) -> dict[str, float]:
            return {
                "ndcg@10": round(statistics.mean(x["ndcg@10"] for x in items) * 100, 2),
                "recall@5": round(statistics.mean(x["recall@5"] for x in items) * 100, 2),
                "mrr@10": round(statistics.mean(x["mrr@10"] for x in items) * 100, 2),
            }

        results["two_stage_reranking"][first_stage_id] = {
            "first_stage_model": first_stage_id,
            "reranker_model": "Qwen3-Reranker-4B",
            "candidates_reranked": 15,
            "rerank_latency_ms": {
                "p50": round(percentile(rerank_latencies, 0.50), 2),
                "p95": round(percentile(rerank_latencies, 0.95), 2),
                "mean": round(statistics.mean(rerank_latencies), 2),
            },
            "overall": sum_rr(all_rr),
            "by_domain": {dom: sum_rr(vals) for dom, vals in per_domain_rr.items()},
        }

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(results, indent=2))
    print(f"Saved complete benchmark results to {RESULTS_PATH}")
    return results


if __name__ == "__main__":
    run_benchmark()
