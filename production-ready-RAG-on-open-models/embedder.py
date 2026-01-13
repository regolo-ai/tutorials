"""
Embedding Module
Uses gte-Qwen2-7B-instruct on Regolo for SOTA open-source embeddings.
"""

import os
import requests
from typing import List, Dict
import numpy as np
import time

REGOLO_API_KEY = os.environ.get("REGOLO_API_KEY")
BASE_URL = os.environ.get("REGOLO_BASE_URL", "https://api.regolo.ai/v1")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "gte-Qwen2-7B-instruct")


def embed_with_gte_qwen2(
    texts: List[str],
    model: str = EMBEDDING_MODEL,
    batch_size: int = 32
) -> np.ndarray:
    """
    Generate embeddings using gte-Qwen2-7B-instruct on Regolo.
    Returns 3584-dimensional vectors (for 7B model).

    Args:
        texts: List of texts to embed
        model: Regolo embedding model name
        batch_size: Number of texts per API call

    Returns:
        NumPy array of shape (len(texts), embedding_dim)
    """
    if not REGOLO_API_KEY:
        raise RuntimeError(
            "REGOLO_API_KEY not set. "
            "Get your key from https://regolo.ai/dashboard"
        )

    all_embeddings = []

    # Process in batches to avoid rate limits
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]

        response = requests.post(
            f"{BASE_URL}/embeddings",
            headers={"Authorization": f"Bearer {REGOLO_API_KEY}"},
            json={
                "model": model,
                "input": batch
            },
            timeout=60
        )

        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            print(f"Error embedding batch {i//batch_size}: {e}")
            print(f"Response: {response.text}")
            raise

        data = response.json()
        batch_embeddings = [item["embedding"] for item in data["data"]]
        all_embeddings.extend(batch_embeddings)

        # Rate limiting: small delay between batches
        if i + batch_size < len(texts):
            time.sleep(0.1)

    return np.array(all_embeddings)


def embed_chunks(chunks: List[Dict]) -> List[Dict]:
    """
    Embed all chunks and attach vectors to metadata.

    Args:
        chunks: List of chunk dicts with 'content' key

    Returns:
        Same chunks with 'embedding' key added
    """
    texts = [chunk["content"] for chunk in chunks]

    print(f"Embedding {len(texts)} chunks with {EMBEDDING_MODEL}...")
    start = time.time()

    embeddings = embed_with_gte_qwen2(texts)

    elapsed = time.time() - start
    print(f"✓ Embedded {len(texts)} chunks in {elapsed:.2f}s")
    print(f"  Embedding dimension: {embeddings.shape[1]}")

    for i, chunk in enumerate(chunks):
        chunk["embedding"] = embeddings[i]

    return chunks


def embed_query(query: str, model: str = EMBEDDING_MODEL) -> np.ndarray:
    """
    Embed a single query string.

    Args:
        query: Query text
        model: Embedding model name

    Returns:
        1D NumPy array
    """
    embeddings = embed_with_gte_qwen2([query], model=model)
    return embeddings[0]


if __name__ == "__main__":
    # Test
    test_chunks = [
        {
            "content": "RAG combines retrieval and generation for factual answers.",
            "metadata": {"chunk_id": 0}
        },
        {
            "content": "gte-Qwen2 is the #1 open embedding model on MTEB benchmarks.",
            "metadata": {"chunk_id": 1}
        },
        {
            "content": "Hybrid search combines dense vector search with lexical BM25.",
            "metadata": {"chunk_id": 2}
        }
    ]

    embedded = embed_chunks(test_chunks)

    print(f"\n✓ Successfully embedded {len(embedded)} chunks")
    print(f"  First embedding shape: {embedded[0]['embedding'].shape}")
    print(f"  First 5 dimensions: {embedded[0]['embedding'][:5]}")
