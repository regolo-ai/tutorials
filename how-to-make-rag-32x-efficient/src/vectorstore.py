"""
FAISS-backed binary vector store for the CrewAI RAG pipeline.
Wraps a binary FAISS index (Hamming distance) plus a float32
oversample/rerank stage for accuracy recovery.
"""
import faiss
import numpy as np
from .quantization import binary_quantize


class BinaryVectorStore:
    def __init__(self, dim: int, oversample_k: int = 200):
        self.dim = dim
        self.oversample_k = oversample_k
        self.index_binary = faiss.IndexBinaryFlat(dim)
        self.float_vectors = None  # kept only for rerank, could be memory-mapped
        self.documents = []

    def add(self, float_vectors: np.ndarray, documents: list[str]):
        norm = float_vectors / np.linalg.norm(float_vectors, axis=1, keepdims=True)
        self.float_vectors = norm.astype(np.float32) if self.float_vectors is None else \
            np.vstack([self.float_vectors, norm.astype(np.float32)])
        binary_vecs = binary_quantize(float_vectors)
        self.index_binary.add(binary_vecs)
        self.documents.extend(documents)

    def search(self, query_float: np.ndarray, k: int = 5, rerank: bool = True):
        query_norm = query_float / np.linalg.norm(query_float)
        query_bin = binary_quantize(query_float.reshape(1, -1))

        if not rerank:
            _, idx = self.index_binary.search(query_bin, k)
            idx = idx[0]
        else:
            _, cand_idx = self.index_binary.search(query_bin, self.oversample_k)
            cand_idx = cand_idx[0]
            cand_vecs = self.float_vectors[cand_idx]
            sims = cand_vecs @ query_norm
            order = np.argsort(-sims)[:k]
            idx = cand_idx[order]

        return [self.documents[i] for i in idx], idx
