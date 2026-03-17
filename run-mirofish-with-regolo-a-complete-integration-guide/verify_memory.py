#!/usr/bin/env python3
"""
verify_memory.py
────────────────
End-to-end test for the Mem0 open-source memory layer using regolo.ai
as both the LLM reasoning backend and the embedding model.

No external account needed — Mem0 runs entirely locally.

Run:
    python verify_memory.py

Expected output:
    ✓ Mem0 initialized (LLM: ..., Embedder: ...)
    ✓ Memory stored  — id: <uuid>
    ✓ Memory retrieved: <content>
    ✓ Memory layer is ready for MiroFish
"""

import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

try:
    from mem0 import Memory
    from mem0.embeddings.openai import OpenAIEmbedding
except ImportError:
    print("✗ mem0ai not installed. Run: pip install mem0ai")
    sys.exit(1)


def _patch_mem0_embedder() -> None:
    """
    Mem0's OpenAI embedder always passes `dimensions=N` in the embeddings API
    call (hardcoded in mem0/embeddings/openai.py). regolo.ai's vLLM backend
    rejects the `dimensions` parameter for models that don't support matryoshka
    representation — even when the value equals the model's native size.

    This patch replaces the `embed()` method with an identical call that omits
    the `dimensions` parameter, making it fully compatible with regolo.ai.
    """
    def _embed_without_dimensions(self, text, memory_action=None):
        text = text.replace("\n", " ")
        return (
            self.client.embeddings.create(input=[text], model=self.config.model)
            .data[0]
            .embedding
        )

    OpenAIEmbedding.embed = _embed_without_dimensions


def build_mem0_config(api_key: str, base_url: str, llm_model: str, embed_model: str) -> dict:
    """
    Build a Mem0 config that routes BOTH LLM calls and embedding calls
    through regolo.ai's OpenAI-compatible API.

    Embedding dimensions (native, no matryoshka truncation):
      - gte-Qwen2          → 3584
      - Qwen3-Embedding-8B → 4096

    Important: do NOT pass `embedding_dims` inside the embedder config —
    that would send a `dimensions` parameter to the API and trigger a
    vLLM matryoshka error. Declare the dimension only in `vector_store`
    so Qdrant creates the collection with the correct size.
    """
    embed_dims = {
        "gte-Qwen2": 3584,
        "Qwen3-Embedding-8B": 4096,
    }
    dims = embed_dims.get(embed_model, 4096)

    return {
        "llm": {
            "provider": "openai",
            "config": {
                "model": llm_model,
                "openai_base_url": base_url,
                "api_key": api_key,
                "temperature": 0.1,
                "max_tokens": 2000,
            },
        },
        "embedder": {
            "provider": "openai",
            "config": {
                "model": embed_model,
                "openai_base_url": base_url,
                "api_key": api_key,
                # No `embedding_dims` here — would trigger matryoshka error on vLLM.
            },
        },
        # Qdrant in-memory — no server required; data lives in RAM for this test.
        # The `embedding_model_dims` tells Qdrant the native vector size.
        # For persistence across restarts, point to a local Qdrant instance:
        #   "vector_store": {
        #       "provider": "qdrant",
        #       "config": {"host": "localhost", "port": 6333,
        #                  "collection_name": "mirofish_agents",
        #                  "embedding_model_dims": dims}
        #   }
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "collection_name": "mirofish_agents",
                "embedding_model_dims": dims,
                "on_disk": False,
            },
        },
    }


def main() -> None:
    api_key     = os.environ.get("REGOLO_API_KEY", "")
    base_url    = os.environ.get("REGOLO_BASE_URL", "https://api.regolo.ai/v1")
    llm_model   = os.environ.get("MEM0_LLM_MODEL", "Llama-3.3-70B-Instruct")
    embed_model = os.environ.get("MEM0_EMBEDDER_MODEL", "Qwen3-Embedding-8B")

    if not api_key or api_key == "your_regolo_api_key_here":
        print("✗ REGOLO_API_KEY not set. Copy .env.example to .env and fill in your key.")
        sys.exit(1)

    # ── 1. Patch + Initialise Mem0 ─────────────────────────────────────────
    _patch_mem0_embedder()
    config = build_mem0_config(api_key, base_url, llm_model, embed_model)
    try:
        m = Memory.from_config(config)
    except Exception as exc:
        print(f"✗ Mem0 initialisation failed: {exc}")
        sys.exit(1)

    print(f"✓ Mem0 initialized (LLM: {llm_model}, Embedder: {embed_model})")

    # ── 2. Store a memory ───────────────────────────────────────────────────
    test_user = "mirofish_test_agent"
    test_msg  = [
        {"role": "user",      "content": "I am running a social simulation about climate policy."},
        {"role": "assistant", "content": "Understood. I will track all agents involved in the policy debate."},
    ]
    try:
        result = m.add(test_msg, user_id=test_user)
    except Exception as exc:
        print(f"✗ Memory storage failed: {exc}")
        sys.exit(1)

    # mem0 returns either a dict with 'results' list or a list directly
    stored = result.get("results", result) if isinstance(result, dict) else result
    mem_id = stored[0].get("id", "?") if stored else "?"
    print(f"✓ Memory stored  — id: {mem_id}")

    # ── 3. Retrieve the memory ──────────────────────────────────────────────
    try:
        hits = m.search("climate policy simulation", user_id=test_user)
    except Exception as exc:
        print(f"✗ Memory retrieval failed: {exc}")
        sys.exit(1)

    results = hits.get("results", hits) if isinstance(hits, dict) else hits
    if not results:
        print("✗ No memories returned on search — check your embedder config.")
        sys.exit(1)

    top = results[0].get("memory", str(results[0]))
    print(f"✓ Memory retrieved: {top}")

    # ── 4. Summary ──────────────────────────────────────────────────────────
    print("\n✓ Memory layer is ready for MiroFish")
    print("  All LLM + embedding calls routed through regolo.ai — no external memory service needed.")


if __name__ == "__main__":
    main()
