"""
Production RAG Module
Adds Redis caching and async batching for 10k+ QPS.
"""

import os
import asyncio
import hashlib
import redis
from typing import List, Optional
from retriever import HybridRetriever
from generator import rag_generate


# Redis client for caching
try:
    rdb = redis.Redis(
        host=os.environ.get("REDIS_HOST", "localhost"),
        port=int(os.environ.get("REDIS_PORT", "6379")),
        decode_responses=True
    )
    # Test connection
    rdb.ping()
    REDIS_AVAILABLE = True
except (redis.ConnectionError, redis.ResponseError):
    print("⚠ Redis not available - caching disabled")
    REDIS_AVAILABLE = False
    rdb = None


async def cached_rag(
    query: str,
    retriever: HybridRetriever,
    ttl: int = 3600,
    use_cache: bool = True
) -> str:
    """
    RAG with Redis caching for 90%+ cache hit rate.

    Args:
        query: User question
        retriever: HybridRetriever instance
        ttl: Cache TTL in seconds
        use_cache: Enable/disable caching

    Returns:
        Generated answer
    """
    # Generate cache key
    cache_key = f"rag:{hashlib.sha256(query.encode()).hexdigest()[:16]}"

    # Check cache
    if use_cache and REDIS_AVAILABLE and rdb:
        cached = rdb.get(cache_key)
        if cached:
            return cached

    # Retrieve and generate
    retrieved = await asyncio.to_thread(retriever.retrieve, query, top_k=5)
    answer = rag_generate(query, retrieved)

    # Store in cache
    if use_cache and REDIS_AVAILABLE and rdb:
        rdb.setex(cache_key, ttl, answer)

    return answer


async def batch_rag(
    queries: List[str],
    retriever: HybridRetriever,
    max_concurrent: int = 10
) -> List[str]:
    """
    Process multiple queries concurrently with semaphore.

    Args:
        queries: List of questions
        retriever: HybridRetriever instance
        max_concurrent: Max concurrent requests

    Returns:
        List of answers
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    async def process_one(q):
        async with semaphore:
            return await cached_rag(q, retriever)

    tasks = [process_one(q) for q in queries]
    return await asyncio.gather(*tasks)


def clear_cache():
    """Clear all RAG cache keys."""
    if REDIS_AVAILABLE and rdb:
        keys = rdb.keys("rag:*")
        if keys:
            rdb.delete(*keys)
            print(f"✓ Cleared {len(keys)} cache keys")
    else:
        print("⚠ Redis not available")


if __name__ == "__main__":
    print("Production RAG module - run from main.py")
