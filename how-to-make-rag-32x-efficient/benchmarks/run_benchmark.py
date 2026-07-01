"""
Benchmark: Float32 exact search vs Binary Quantized search (+rerank).
Reproduces the methodology used to validate the CrewAI RAG pipeline.

Usage:
    python benchmarks/run_benchmark.py
"""
import time
import numpy as np
import faiss
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD

from src.quantization import binary_quantize, memory_footprint


def build_synthetic_corpus(n_docs=8000, seed=42):
    rng = np.random.default_rng(seed)
    topics = ["diabetes treatment", "climate change policy", "quantum computing algorithms",
              "vector databases", "supply chain logistics", "renewable energy storage",
              "cardiovascular disease", "large language models", "cybersecurity threats",
              "genomics research"]
    docs = []
    for i in range(n_docs):
        topic = topics[i % len(topics)]
        filler = " ".join(rng.choice(
            ["system", "method", "result", "patient", "model", "data", "process",
             "network", "analysis", "study", "performance", "risk", "outcome"], size=12))
        docs.append(f"{topic} {filler} document number {i}")
    return docs


def embed_corpus(docs, n_components=384, seed=42):
    tfidf = TfidfVectorizer(max_features=20000)
    X = tfidf.fit_transform(docs)
    svd = TruncatedSVD(n_components=n_components, random_state=seed)
    emb = svd.fit_transform(X).astype(np.float32)
    emb -= emb.mean(axis=0, keepdims=True)
    return emb


def run(n_docs=8000, n_queries=200, k=10, oversample_options=(50, 100, 200, 500, 1000)):
    docs = build_synthetic_corpus(n_docs)
    emb = embed_corpus(docs)
    d = emb.shape[1]

    emb_norm = emb / np.linalg.norm(emb, axis=1, keepdims=True)
    index_float = faiss.IndexFlatIP(d)
    index_float.add(emb_norm.astype(np.float32))

    binary_emb = binary_quantize(emb)
    index_binary = faiss.IndexBinaryFlat(d)
    index_binary.add(binary_emb)

    mem = memory_footprint(emb_norm, binary_emb)

    rng = np.random.default_rng(7)
    query_idx = rng.choice(n_docs, size=n_queries, replace=False)
    queries = emb_norm[query_idx].astype(np.float32)
    queries_bin = binary_quantize(emb[query_idx])

    t0 = time.time()
    _, I_f = index_float.search(queries, k)
    t_float = (time.time() - t0) / n_queries * 1000

    t0 = time.time()
    _, I_b = index_binary.search(queries_bin, k)
    t_binary = (time.time() - t0) / n_queries * 1000

    recall_no_rerank = np.mean([
        len(set(I_f[i]) & set(I_b[i])) / k for i in range(n_queries)
    ])

    rows = [
        {"method": "Float32 Flat (exact)", "memory_bytes": mem["float32_bytes"],
         "avg_latency_ms": t_float, "recall_at_10": 1.0},
        {"method": "Binary Quantized (no rerank)", "memory_bytes": mem["binary_bytes"],
         "avg_latency_ms": t_binary, "recall_at_10": recall_no_rerank},
    ]

    for osk in oversample_options:
        t0 = time.time()
        _, I_cand = index_binary.search(queries_bin, osk)
        recs = []
        for i in range(n_queries):
            cand_ids = I_cand[i]
            sims = emb_norm[cand_ids] @ queries[i]
            top_local = np.argsort(-sims)[:k]
            pred = set(cand_ids[top_local])
            recs.append(len(set(I_f[i]) & pred) / k)
        t_rerank = (time.time() - t0) / n_queries * 1000
        rows.append({
            "method": f"Binary + Rerank (oversample={osk})",
            "memory_bytes": mem["binary_bytes"],
            "avg_latency_ms": t_rerank,
            "recall_at_10": np.mean(recs),
        })

    df = pd.DataFrame(rows)
    df["memory_reduction_x"] = mem["float32_bytes"] / df["memory_bytes"]
    return df


if __name__ == "__main__":
    df = run()
    df.to_csv("benchmarks/benchmark_results.csv", index=False)
    print(df.to_string(index=False))
