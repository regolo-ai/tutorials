"""
Generation Module
Uses Llama-3.3-70B-Instruct on Regolo with strict prompting.
"""

import os
import requests
from typing import List

REGOLO_API_KEY = os.environ.get("REGOLO_API_KEY")
BASE_URL = os.environ.get("REGOLO_BASE_URL", "https://api.regolo.ai/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "Llama-3.3-70B-Instruct")


def rag_generate(
    query: str,
    retrieved_docs: List[str],
    temperature: float = 0.1,
    max_tokens: int = 500
) -> str:
    """
    Generate answer using Llama-3.3-70B-Instruct on Regolo.
    Uses strict prompt to reduce hallucination to <10%.

    Args:
        query: User question
        retrieved_docs: List of relevant document chunks
        temperature: Sampling temperature (low = factual)
        max_tokens: Maximum response length

    Returns:
        Generated answer text
    """
    if not REGOLO_API_KEY:
        raise RuntimeError(
            "REGOLO_API_KEY not set. "
            "Get your key from https://regolo.ai/dashboard"
        )

    if not retrieved_docs:
        return "No relevant context found to answer this question."

    # Format context with numbered references
    context = "\n\n".join([
        f"[{i+1}] {doc}"
        for i, doc in enumerate(retrieved_docs)
    ])

    # Strict prompt template to reduce hallucination
    prompt = f"""Use ONLY the following context to answer the question.
If the answer is not in the context, say "I don't know based on the provided context."
Do not make up information. Cite the reference number [X] when using information.

Context:
{context}

Question: {query}

Answer:"""

    response = requests.post(
        f"{BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {REGOLO_API_KEY}"},
        json={
            "model": LLM_MODEL,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a precise assistant that answers only based on provided context."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        },
        timeout=60
    )

    try:
        response.raise_for_status()
    except requests.HTTPError as e:
        print(f"Error generating answer: {e}")
        print(f"Response: {response.text}")
        raise

    data = response.json()
    answer = data["choices"][0]["message"]["content"]

    return answer


def rag_generate_with_metadata(
    query: str,
    retrieved_docs: List[str],
    **kwargs
) -> dict:
    """
    Generate answer and return metadata (tokens, cost estimate).

    Returns:
        Dict with 'answer', 'tokens', 'cost_usd'
    """
    answer = rag_generate(query, retrieved_docs, **kwargs)

    # Rough token count (1 token ≈ 4 chars)
    total_chars = len(query) + sum(len(d) for d in retrieved_docs) + len(answer)
    estimated_tokens = total_chars // 4

    # Llama-3.3-70B pricing on Regolo (example)
    # Input: $0.30 / 1M tokens, Output: $0.60 / 1M tokens
    input_tokens = (len(query) + sum(len(d) for d in retrieved_docs)) // 4
    output_tokens = len(answer) // 4

    cost_usd = (input_tokens * 0.30 / 1_000_000) + (output_tokens * 0.60 / 1_000_000)

    return {
        "answer": answer,
        "tokens": estimated_tokens,
        "cost_usd": cost_usd
    }


if __name__ == "__main__":
    # Test
    test_docs = [
        "RAG combines retrieval and generation for factual answers.",
        "Hybrid search uses both dense and lexical retrieval for better recall.",
        "gte-Qwen2 is the #1 open embedding model on MTEB benchmarks."
    ]

    answer = rag_generate("What is RAG?", test_docs)
    print(f"\nAnswer: {answer}\n")
