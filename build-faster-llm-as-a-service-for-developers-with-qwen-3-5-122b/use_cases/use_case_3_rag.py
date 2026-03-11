"""Use case 3: minimal RAG with embeddings placeholder retrieval + rerank prompt."""

from __future__ import annotations

import numpy as np

from regolo_client import RegoloClient


KNOWLEDGE_BASE = [
    "Regolo.ai uses high-performance NVIDIA GPUs for inference.",
    "All data processed by Regolo is hosted in EU infrastructure with zero retention policy.",
    "Regolo supports chat, embeddings, and reranking workflows through OpenAI-compatible APIs.",
    "Pricing is pay-as-you-go with no monthly minimum commitment.",
    "Qwen, Llama, and other open models are available depending on plan and workload.",
]


def tokenize_embedding(text: str) -> np.ndarray:
    # Lightweight fallback embedding for local demonstration when not calling embedding APIs.
    vocab = ["gpu", "eu", "retention", "api", "pricing", "qwen", "llama", "rag", "chat"]
    vec = np.array([text.lower().count(token) for token in vocab], dtype=float)
    norm = np.linalg.norm(vec)
    return vec if norm == 0 else vec / norm


def retrieve(query: str, top_k: int = 3) -> list[str]:
    query_vec = tokenize_embedding(query)
    scores: list[tuple[float, str]] = []

    for doc in KNOWLEDGE_BASE:
        doc_vec = tokenize_embedding(doc)
        score = float(np.dot(query_vec, doc_vec))
        scores.append((score, doc))

    scores.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in scores[:top_k]]


def answer_with_rag(client: RegoloClient, query: str) -> str:
    candidates = retrieve(query=query, top_k=3)
    context = "\n".join(f"- {c}" for c in candidates)

    prompt = f"""Answer the question using only the context below.
If the context is insufficient, say so explicitly.

Context:
{context}

Question: {query}

Answer concisely."""

    return client.chat_completion(messages=[{"role": "user", "content": prompt}])
