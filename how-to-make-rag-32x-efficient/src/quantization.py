"""
Binary quantization utilities for CrewAI RAG pipeline.
Converts float32 embeddings into packed binary vectors (1 bit/dim),
delivering ~32x memory reduction vs float32 storage.
"""
import numpy as np


def binary_quantize(vectors: np.ndarray) -> np.ndarray:
    """Quantize float32 embeddings to packed binary vectors.

    Args:
        vectors: (N, D) float32 array of embeddings.

    Returns:
        (N, D/8) uint8 array of packed binary vectors.
    """
    bits = (vectors >= 0).astype(np.uint8)
    packed = np.packbits(bits, axis=1)
    return packed


def hamming_topk(query_bin: np.ndarray, corpus_bin: np.ndarray, k: int = 10):
    """Exact Hamming-distance top-k search over packed binary vectors."""
    xor = np.bitwise_xor(corpus_bin, query_bin)
    dist = np.unpackbits(xor, axis=1).sum(axis=1)
    top_idx = np.argsort(dist)[:k]
    return top_idx, dist[top_idx]


def memory_footprint(float_vectors: np.ndarray, binary_vectors: np.ndarray) -> dict:
    mem_float = float_vectors.astype(np.float32).nbytes
    mem_binary = binary_vectors.nbytes
    return {
        "float32_bytes": mem_float,
        "binary_bytes": mem_binary,
        "reduction_x": round(mem_float / mem_binary, 2),
    }
