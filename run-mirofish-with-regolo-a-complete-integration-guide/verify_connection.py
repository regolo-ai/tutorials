#!/usr/bin/env python3
"""
verify_connection.py
────────────────────
Quick smoke test for the regolo.ai ↔ MiroFish integration.

Run:
    python verify_connection.py

Expected output:
    ✓ API key loaded
    ✓ Chat completion succeeded
    Model reply: <short reply from the model>
    ✓ All checks passed — regolo.ai is ready for MiroFish
"""

import os
import sys
from pathlib import Path

# Load .env from this directory if present
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass  # dotenv optional; env vars may already be set

from openai import OpenAI, AuthenticationError, APIConnectionError


def main() -> None:
    api_key = os.environ.get("REGOLO_API_KEY")
    base_url = os.environ.get("REGOLO_BASE_URL", "https://api.regolo.ai/v1")
    model = os.environ.get("LLM_MODEL_NAME", "Llama-3.1-8B-Instruct")

    # ── 1. Key present ──────────────────────────────────────────────────────
    if not api_key or api_key == "your_regolo_api_key_here":
        print("✗ REGOLO_API_KEY not set. Copy .env.example to .env and fill in your key.")
        sys.exit(1)
    print("✓ API key loaded")

    client = OpenAI(api_key=api_key, base_url=base_url)

    # ── 2. Chat completion ──────────────────────────────────────────────────
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant. Reply in exactly one sentence.",
                },
                {
                    "role": "user",
                    "content": "Confirm the connection is working with a short message.",
                },
            ],
            max_tokens=64,
            temperature=0,
        )
    except AuthenticationError:
        print("✗ Authentication failed — check your REGOLO_API_KEY.")
        sys.exit(1)
    except APIConnectionError as exc:
        print(f"✗ Connection error: {exc}")
        sys.exit(1)

    reply = response.choices[0].message.content.strip()
    print("✓ Chat completion succeeded")
    print(f"  Model reply: {reply}")
    print(f"  Model used:  {response.model}")
    print(f"  Tokens used: {response.usage.total_tokens} total "
          f"(prompt={response.usage.prompt_tokens}, "
          f"completion={response.usage.completion_tokens})")

    # ── 3. Summary ──────────────────────────────────────────────────────────
    print("\n✓ All checks passed — regolo.ai is ready for MiroFish")


if __name__ == "__main__":
    main()
