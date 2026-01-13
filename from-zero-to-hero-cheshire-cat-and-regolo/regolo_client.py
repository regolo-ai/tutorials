"""
Regolo.ai OpenAI-compatible API client
A minimal helper to call Regolo's /chat/completions endpoint
"""

import os
import requests
from typing import List, Dict, Optional


BASE_URL = "https://api.regolo.ai/v1"
API_KEY = os.environ.get("REGOLO_API_KEY")
MODEL = os.environ.get("REGOLO_MODEL", "Llama-3.3-70B-Instruct")


def regolo_chat(
    messages: List[Dict[str, str]], 
    temperature: float = 0.2,
    max_tokens: Optional[int] = None,
    model: Optional[str] = None
) -> str:
    """
    Call Regolo's OpenAI-compatible /chat/completions endpoint.

    Args:
        messages: List of message dicts with 'role' and 'content' keys
        temperature: Sampling temperature (0.0 to 2.0)
        max_tokens: Maximum tokens to generate (optional)
        model: Override default model (optional)

    Returns:
        String content of the first completion choice

    Raises:
        RuntimeError: If REGOLO_API_KEY is not set
        requests.HTTPError: If the API request fails
    """
    if not API_KEY:
        raise RuntimeError(
            "REGOLO_API_KEY environment variable is not set. "
            "Get your key from https://regolo.ai dashboard"
        )

    payload = {
        "model": model or MODEL,
        "temperature": temperature,
        "messages": messages,
    }

    if max_tokens:
        payload["max_tokens"] = max_tokens

    response = requests.post(
        f"{BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]


def regolo_stream_chat(
    messages: List[Dict[str, str]], 
    temperature: float = 0.2,
    model: Optional[str] = None
):
    """
    Call Regolo's streaming endpoint (if available).
    Yields text chunks as they arrive.
    """
    if not API_KEY:
        raise RuntimeError("REGOLO_API_KEY environment variable is not set")

    payload = {
        "model": model or MODEL,
        "temperature": temperature,
        "messages": messages,
        "stream": True,
    }

    response = requests.post(
        f"{BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json=payload,
        stream=True,
        timeout=30,
    )
    response.raise_for_status()

    for line in response.iter_lines():
        if line:
            yield line.decode('utf-8')


if __name__ == "__main__":
    # Quick smoke test
    result = regolo_chat(
        [
            {
                "role": "system",
                "content": "You are the brain of an enterprise support assistant built with Cheshire Cat.",
            },
            {
                "role": "user",
                "content": "Give me a concise status update about today's ticket queue.",
            },
        ]
    )
    print("\n=== Regolo Response ===")
    print(result)
    print("\n✓ Connection successful!")
