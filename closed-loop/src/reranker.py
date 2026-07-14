"""
src/reranker.py
---------------
Qwen3-Reranker-4B second-stage reranking via Regolo API.

Takes top-k Qdrant candidates and reorders them by relevance
to the review query, returning top-n high-precision context items.

Falls back gracefully if the reranker endpoint is unavailable.
"""
import logging
import os
from typing import List, Optional, Tuple

from src.models import RetrievalResult

logger = logging.getLogger("closed_loop.reranker")


class Qwen3Reranker:
    """
    Wraps the Regolo rerank endpoint for Qwen3-Reranker-4B.
    Endpoint: POST /v1/rerank  (OpenAI-compatible cross-encoder interface)
    """

    def __init__(self, base_url: str, api_key: str, model: str = "Qwen/Qwen3-Reranker-4B"):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self._available = self._check_availability()

    def _check_availability(self) -> bool:
        """Quick connectivity check — fails silently."""
        try:
            import httpx
            r = httpx.get(f"{self.base_url}/models", headers={"Authorization": f"Bearer {self.api_key}"}, timeout=3)
            return r.status_code < 500
        except Exception:
            return False

    def rerank(
        self,
        query: str,
        candidates: List[RetrievalResult],
        top_n: int = 5,
    ) -> List[RetrievalResult]:
        """
        Rerank candidates using Qwen3-Reranker-4B.
        Returns top_n results sorted by descending relevance score.
        Falls back to original order if unavailable.
        """
        if not candidates:
            return []
        if not self._available:
            logger.warning("Reranker unavailable. Using Qdrant ranking order.")
            return candidates[:top_n]

        try:
            import httpx

            documents = [c.content for c in candidates]
            payload = {
                "model": self.model,
                "query": query,
                "documents": documents,
                "top_n": top_n,
            }
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            resp = httpx.post(
                f"{self.base_url}/rerank",
                json=payload,
                headers=headers,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            # Response: {"results": [{"index": int, "relevance_score": float}, ...]}
            ranked = sorted(
                data.get("results", []),
                key=lambda x: x.get("relevance_score", 0),
                reverse=True,
            )
            reranked = []
            for item in ranked[:top_n]:
                idx = item.get("index", 0)
                if 0 <= idx < len(candidates):
                    c = candidates[idx]
                    c.score = item.get("relevance_score", c.score)
                    reranked.append(c)
            logger.info("Reranked %d -> %d candidates", len(candidates), len(reranked))
            return reranked

        except Exception as exc:
            logger.warning("Reranker call failed (%s). Falling back to Qdrant order.", exc)
            return candidates[:top_n]
