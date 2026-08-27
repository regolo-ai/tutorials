"""Naive Chunk-Based RAG Baseline.
Uses real dense vector embeddings from Regolo.ai (Qwen3-Embedding-8B)
and cosine similarity retrieval over isolated code/doc chunks without graph causality.
"""

import math
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import config
from core.regolo_client import RegoloClient


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Calculate cosine similarity between two dense vectors."""
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot / (norm1 * norm2)


class NaiveChunkRAG:
    """Standard naive chunking RAG implementation with real Regolo dense embeddings."""

    def __init__(
        self,
        regolo_client: Optional[RegoloClient] = None,
        chunk_size: int = 400,
        chunk_overlap: int = 50,
    ):
        self.client = regolo_client or RegoloClient()
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.chunks: List[Dict[str, Any]] = []
        self.vectors: List[List[float]] = []

    def ingest_directory(self, dir_path: Path):
        """Split all text files in dir_path into real chunks and compute live embeddings."""
        if not dir_path.exists():
            return

        self.chunks = []
        self.vectors = []
        raw_texts = []

        for fpath in dir_path.rglob("*"):
            if fpath.is_file() and fpath.suffix in [".py", ".md", ".sql", ".json", ".txt"]:
                # Ignore hidden directories
                if any(part.startswith(".") for part in fpath.parts):
                    continue
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()

                    # Fixed window chunking
                    for i in range(0, len(content), self.chunk_size - self.chunk_overlap):
                        chunk_text = content[i : i + self.chunk_size].strip()
                        if len(chunk_text) > 30:
                            chunk_obj = {
                                "id": f"chunk_{fpath.stem}_{i}",
                                "source": str(fpath.relative_to(dir_path)),
                                "text": chunk_text,
                            }
                            self.chunks.append(chunk_obj)
                            raw_texts.append(chunk_text)
                except Exception:
                    pass

        # Compute real dense embeddings in batches via Regolo.ai
        if raw_texts:
            batch_size = 15
            for i in range(0, len(raw_texts), batch_size):
                batch = raw_texts[i : i + batch_size]
                emb_batch = self.client.get_embeddings_batch(batch)
                self.vectors.extend(emb_batch)

    def retrieve(self, query: str, top_k: int = 3) -> Dict[str, Any]:
        """Perform real dense semantic retrieval using Qwen3-Embedding-8B."""
        start_time = time.time()

        if not self.chunks or not self.vectors:
            # If not yet ingested, ingest default sample_repo
            if config.SAMPLE_REPO_DIR.exists():
                self.ingest_directory(config.SAMPLE_REPO_DIR)

        if not self.chunks or not self.vectors:
            return {
                "retrieved_chunks": [],
                "context_prompt_block": "### Naive RAG: No indexed chunks found.",
                "latency_seconds": 0.0,
                "total_chunks_indexed": 0,
            }

        # Compute query vector using Regolo
        query_vec = self.client.get_embedding(query)

        # Compute cosine similarity across all real chunks
        scored = []
        for chunk, vec in zip(self.chunks, self.vectors):
            sim = cosine_similarity(query_vec, vec)
            scored.append((chunk, sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        retrieved_chunks = [item[0] for item in scored[:top_k]]

        context_str = "\n---\n".join([f"Source: {c['source']}\n{c['text']}" for c in retrieved_chunks])
        latency = round(time.time() - start_time, 3)

        return {
            "retrieved_chunks": retrieved_chunks,
            "context_prompt_block": f"### ⚠️ Naive RAG Retrieved Context (Isolated Chunks):\n{context_str}",
            "latency_seconds": latency,
            "total_chunks_indexed": len(self.chunks),
        }
