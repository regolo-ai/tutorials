"""
Hybrid Vector Store Module
Combines ChromaDB (dense) with BM25 (lexical) for better retrieval.
"""

import chromadb
from rank_bm25 import BM25Okapi
import pickle
import os
from typing import List, Dict
import numpy as np


class HybridStore:
    """
    Combines dense (ChromaDB) and lexical (BM25) retrieval.
    """

    def __init__(self, persist_path: str = "./rag_index"):
        """
        Initialize hybrid store.

        Args:
            persist_path: Directory for persistent storage
        """
        self.persist_path = persist_path
        os.makedirs(persist_path, exist_ok=True)

        self.client = chromadb.PersistentClient(path=persist_path)
        self.collection = self.client.get_or_create_collection(
            name="docs",
            metadata={"hnsw:space": "cosine"}
        )
        self.bm25 = None
        self.documents = []
        self.bm25_path = os.path.join(persist_path, "bm25_index.pkl")

    def index(self, chunks: List[Dict]):
        """
        Index chunks in both ChromaDB (dense) and BM25 (lexical).

        Args:
            chunks: List of chunk dicts with 'content', 'embedding', 'metadata'
        """
        if not chunks:
            raise ValueError("No chunks to index")

        print(f"Indexing {len(chunks)} chunks...")

        ids = [f"doc_{i}" for i in range(len(chunks))]
        contents = [c["content"] for c in chunks]
        embeddings = [c["embedding"].tolist() for c in chunks]
        metadatas = [c["metadata"] for c in chunks]

        # Add to ChromaDB (dense vector search)
        self.collection.add(
            embeddings=embeddings,
            documents=contents,
            metadatas=metadatas,
            ids=ids
        )

        print(f"  ✓ Indexed in ChromaDB (dense)")

        # Build BM25 index (lexical keyword search)
        self.documents = contents
        tokenized = [doc.lower().split() for doc in contents]
        self.bm25 = BM25Okapi(tokenized)

        # Save BM25 for persistence
        with open(self.bm25_path, "wb") as f:
            pickle.dump((self.bm25, self.documents), f)

        print(f"  ✓ Indexed in BM25 (lexical)")
        print(f"\n✓ Hybrid index built successfully")

    def load_bm25(self):
        """Load BM25 index from disk."""
        if not os.path.exists(self.bm25_path):
            raise FileNotFoundError(
                f"BM25 index not found at {self.bm25_path}. "
                "Run index() first."
            )

        with open(self.bm25_path, "rb") as f:
            self.bm25, self.documents = pickle.load(f)

        print(f"✓ Loaded BM25 index with {len(self.documents)} documents")

    def dense_search(self, query_embedding: np.ndarray, top_k: int = 10) -> List[str]:
        """
        Dense vector search using ChromaDB.

        Args:
            query_embedding: Query vector
            top_k: Number of results

        Returns:
            List of document texts
        """
        results = self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=top_k
        )
        return results["documents"][0] if results["documents"] else []

    def lexical_search(self, query: str, top_k: int = 10) -> List[str]:
        """
        Lexical BM25 search.

        Args:
            query: Query text
            top_k: Number of results

        Returns:
            List of document texts
        """
        if self.bm25 is None:
            self.load_bm25()

        tokenized_query = query.lower().split()
        bm25_scores = self.bm25.get_scores(tokenized_query)

        # Get top-K indices
        top_indices = np.argsort(bm25_scores)[-top_k:][::-1]

        return [self.documents[i] for i in top_indices]


if __name__ == "__main__":
    print("HybridStore test - run from main.py")
