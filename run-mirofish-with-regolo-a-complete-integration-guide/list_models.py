#!/usr/bin/env python3
"""
list_models.py
──────────────
List all LLM models available on your regolo.ai account,
annotated with recommended use cases for MiroFish simulations.

Run:
    python list_models.py
"""

import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

from openai import OpenAI, AuthenticationError


# Curated notes for models relevant to MiroFish workloads
MODEL_NOTES: dict[str, str] = {
    "Llama-3.1-8B-Instruct":  "⚡ Fast & cheap — ideal for dev/test runs (<40 rounds)",
    "Llama-3.3-70B-Instruct":  "✅ Balanced quality + speed — recommended for most simulations",
    "gpt-oss-20b":              "✅ Compact reasoning, good for structured JSON agent calls",
    "gpt-oss-120b":             "🔬 Maximum reasoning — use for final production simulations",
    "qwen3-8b":                 "⚡ Fast & multilingual — good for non-English seed documents",
    "qwen3.5-122b":             "🔬 Large MoE model — top-tier quality, higher token cost",
    "mistral-small3.2":         "✅ Strong instruction-following, multimodal capable",
    "qwen3-coder-next":         "🔧 Code-optimised — useful if seed docs contain technical specs",
    "gte-Qwen2":                "📐 Embedding model — for GraphRAG vector search in MiroFish",
    "Qwen3-Embedding-8B":       "📐 Embedding model — multilingual, 32k context",
    "Qwen3-Reranker-4B":        "📐 Reranker — improves retrieval quality in GraphRAG pipeline",
}

SKIP_FOR_SIMULATION = {"deepseek-ocr", "faster-whisper-large-v3", "Qwen-Image", "qwen3-vl-32b"}


def main() -> None:
    api_key = os.environ.get("REGOLO_API_KEY")
    base_url = os.environ.get("REGOLO_BASE_URL", "https://api.regolo.ai/v1")

    if not api_key or api_key == "your_regolo_api_key_here":
        print("✗ REGOLO_API_KEY not set. Copy .env.example to .env and fill in your key.")
        sys.exit(1)

    client = OpenAI(api_key=api_key, base_url=base_url)

    try:
        models = client.models.list()
    except AuthenticationError:
        print("✗ Authentication failed — check your REGOLO_API_KEY.")
        sys.exit(1)

    ids = sorted(m.id for m in models.data)

    print(f"{'MODEL':<32}  {'NOTES'}")
    print("─" * 80)
    for model_id in ids:
        if model_id in SKIP_FOR_SIMULATION:
            tag = "  (not used for text generation)"
        else:
            tag = f"  {MODEL_NOTES.get(model_id, '')}"
        print(f"{model_id:<32}{tag}")

    print(f"\n{len(ids)} models available on this account.")
    print("\nSet LLM_MODEL_NAME in .env to the model you want MiroFish to use.")


if __name__ == "__main__":
    main()
