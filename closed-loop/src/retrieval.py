"""
src/retrieval.py
----------------
Qdrant-based semantic retrieval layer.

Collections:
  - code_chunks      : chunked source files
  - tech_docs        : ADRs, runbooks, style guides
  - review_memory    : past review outcomes and lessons

Payload schema follows ROADMAP.md recommendations.
"""
import hashlib
import logging
import time
from pathlib import Path
from typing import List, Optional

from src.models import RetrievalResult

logger = logging.getLogger("closed_loop.retrieval")

COLLECTION_CODE = "code_chunks"
COLLECTION_DOCS = "tech_docs"
COLLECTION_REVIEW = "review_memory"
VECTOR_SIZE = 1536  # text-embedding-ada-002 compatible

COLLECTIONS = [
    COLLECTION_CODE,
    COLLECTION_DOCS,
    COLLECTION_REVIEW,
]


def _chunk_text(text: str, chunk_size: int = 400, overlap: int = 80) -> List[str]:
    """Split text into overlapping chunks by character count."""
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


def _content_id(content: str, path: str, chunk_idx: int) -> str:
    h = hashlib.md5(f"{path}:{chunk_idx}:{content[:64]}".encode()).hexdigest()
    return h


class QdrantRetriever:
    """
    Wraps Qdrant for code/doc/review retrieval.
    Falls back gracefully if qdrant-client is not installed or Qdrant is unreachable.
    """

    def __init__(self, url: str, api_key: str = ""):
        self.url = url
        self.api_key = api_key
        self._client = None
        self._embedder = None
        self._available = False
        self._init_client()

    def _init_client(self) -> None:
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams, PayloadSchemaType

            kwargs = {"url": self.url, "timeout": 5}
            if self.api_key:
                kwargs["api_key"] = self.api_key

            self._client = QdrantClient(**kwargs)
            self._ensure_collections()
            self._available = True
            logger.info("Qdrant connected at %s", self.url)
        except ImportError:
            logger.warning("qdrant-client not installed. Retrieval layer disabled.")
        except Exception as exc:
            logger.warning("Qdrant unavailable (%s). Retrieval layer disabled.", exc)

    def _ensure_collections(self) -> None:
        from qdrant_client.models import Distance, VectorParams

        # Get actual embedding size from the model configured in environment
        try:
            test_vector = self._embed("test")
            actual_size = len(test_vector)
        except Exception as exc:
            logger.warning("Could not determine dynamic vector size: %s. Using default %d.", exc, VECTOR_SIZE)
            actual_size = VECTOR_SIZE

        existing_collections = self._client.get_collections().collections
        existing = {c.name for c in existing_collections}

        for name in COLLECTIONS:
            recreate = False
            if name in existing:
                try:
                    info = self._client.get_collection(collection_name=name)
                    vectors_config = info.config.params.vectors
                    if hasattr(vectors_config, "size"):
                        current_size = vectors_config.size
                    elif isinstance(vectors_config, dict) and "size" in vectors_config:
                        current_size = vectors_config["size"]
                    else:
                        current_size = getattr(vectors_config, "size", actual_size)

                    if current_size != actual_size:
                        logger.info("Collection %s has dimension %d, but embedding model uses %d. Recreating...", name, current_size, actual_size)
                        recreate = True
                except Exception as e:
                    logger.warning("Could not verify collection %s dimension: %s", name, e)

            if recreate:
                self._client.delete_collection(collection_name=name)

            if name not in existing or recreate:
                self._client.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(size=actual_size, distance=Distance.COSINE),
                )
                logger.info("Created Qdrant collection: %s with dimension %d", name, actual_size)

    def _get_embedder(self):
        """Lazy-load OpenAI embedder via environment."""
        if self._embedder is not None:
            return self._embedder
        import os
        from openai import OpenAI
        client = OpenAI(
            api_key=os.environ.get("REGOLO_API_KEY", ""),
            base_url=os.environ.get("BASE_URL", "https://api.regolo.ai/v1"),
        )
        self._embedder = client
        return self._embedder

    def _embed(self, text: str) -> List[float]:
        import os
        client = self._get_embedder()
        resp = client.embeddings.create(
            model=os.environ.get("RERANKER_MODEL", ""),
            input=text[:8000],
        )
        return resp.data[0].embedding

    def index_file(self, path: Path, repo_id: str = "", language: str = "python") -> int:
        """Chunk and index a source file into code_chunks collection."""
        if not self._available:
            return 0
        from qdrant_client.models import PointStruct

        content = path.read_text(encoding="utf-8", errors="ignore")
        chunks = _chunk_text(content)
        points = []
        for i, chunk in enumerate(chunks):
            try:
                vector = self._embed(chunk)
            except Exception as exc:
                logger.warning("Embedding failed for chunk %d: %s", i, exc)
                continue
            point_id = _content_id(chunk, str(path), i)
            points.append(PointStruct(
                id=abs(hash(point_id)) % (2**63),
                vector=vector,
                payload={
                    "repo_id": repo_id,
                    "path": str(path),
                    "language": language,
                    "chunk_idx": i,
                    "source_kind": "code",
                    "content": chunk,
                    "updated_at": time.time(),
                },
            ))
        if points:
            self._client.upsert(collection_name=COLLECTION_CODE, points=points)
        logger.info("Indexed %d chunks from %s", len(points), path)
        return len(points)

    def search(
        self,
        query: str,
        collection: str = COLLECTION_CODE,
        top_k: int = 10,
        filters: Optional[dict] = None,
    ) -> List[RetrievalResult]:
        """Vector search with optional payload filters."""
        if not self._available:
            return []
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            qdrant_filter = None
            if filters:
                conditions = [
                    FieldCondition(key=k, match=MatchValue(value=v))
                    for k, v in filters.items()
                ]
                qdrant_filter = Filter(must=conditions)

            vector = self._embed(query)
            if hasattr(self._client, "query_points"):
                response = self._client.query_points(
                    collection_name=collection,
                    query=vector,
                    limit=top_k,
                    query_filter=qdrant_filter,
                    with_payload=True,
                )
                hits = response.points
            else:
                hits = self._client.search(
                    collection_name=collection,
                    query_vector=vector,
                    limit=top_k,
                    query_filter=qdrant_filter,
                    with_payload=True,
                )
            results = []
            for hit in hits:
                payload = hit.payload or {}
                results.append(RetrievalResult(
                    id=str(hit.id),
                    score=hit.score,
                    payload=payload,
                    content=payload.get("content", ""),
                    source_kind=payload.get("source_kind", "code"),
                ))
            return results
        except Exception as exc:
            logger.warning("Qdrant search failed: %s", exc)
            return []

    def persist_review_outcome(
        self,
        target_path: str,
        status: str,
        iterations: int,
        reason: str,
        lessons: List[str],
    ) -> None:
        """Store a completed review outcome into review_memory collection."""
        if not self._available:
            return
        from qdrant_client.models import PointStruct

        summary = f"Review of {target_path}: {status} in {iterations} iterations. {reason}"
        if lessons:
            summary += " Lessons: " + "; ".join(lessons)
        try:
            vector = self._embed(summary)
            point_id = abs(hash(f"{target_path}:{time.time()}")) % (2**63)
            self._client.upsert(
                collection_name=COLLECTION_REVIEW,
                points=[PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "path": target_path,
                        "status": status,
                        "iterations": iterations,
                        "reason": reason,
                        "lessons": lessons,
                        "source_kind": "review",
                        "content": summary,
                        "updated_at": time.time(),
                    },
                )],
            )
            logger.info("Review outcome persisted to Qdrant review_memory")
        except Exception as exc:
            logger.warning("Failed to persist review outcome: %s", exc)
