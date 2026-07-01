"""
CrewAI RAG pipeline demonstrating binary quantization in practice.

Supports any OpenAI-compatible provider (Regolo.ai, local, API).

All configuration is managed via .env file:

  # OpenAI/Embedding configuration
  OPENAI_PROVIDER=transformers        # transformers, openai, groq, ollama
  OPENAI_MODEL=bge-small-en-v1.5     # model name or local path
  OPENAI_API_BASE=https://api.openai.com/v1  # for openai-compatible providers
  OPENAI_API_KEY=your_key_here       # API key

  # Optional CLI overrides:
  # python crew.py --embedder "text-embedding-3-small"
  
Run:
    python crew.py "What are common diabetes treatment approaches?"

OpenAI-compatible providers supported:
  - OpenAI: OPENAI_API_KEY + OPENAI_PROVIDER=openai
  - Groq: GROQ_API_KEY + OPENAI_PROVIDER=groq
  - Regolo.ai: OPENAI_API_BASE=https://api.regolo.ai/v1
  - Ollama: OPENAI_PROVIDER=ollama (local inference)
  - Local Transformers: OPENAI_PROVIDER=transformers (no key needed)
"""
import sys
import os
import numpy as np
from dotenv import load_dotenv
from dataclasses import dataclass
from typing import Optional, Callable

load_dotenv()

from crewai import Agent, Task, Crew, Process
from crewai.tools import BaseTool
from src.vectorstore import BinaryVectorStore


@dataclass
class OpenAiConfig:
    """Configuration for OpenAI-compatible model, loaded from .env file."""
    provider: str = "transformers"  # transformers, openai, groq, ollama
    model: str = "bge-small-en-v1.5"
    api_base: str = "https://api.openai.com/v1"
    api_key: str = ""
    batch_size: int = 32


def get_openai_config() -> OpenAiConfig:
    """Load configuration from environment variables (loaded from .env).
    
    Supports these environment variables (configured in .env):
    - OPENAI_PROVIDER: Provider (transformers, openai, groq, ollama)
    - OPENAI_MODEL: Model name/path
    - OPENAI_API_BASE: API base URL
    - OPENAI_API_KEY: API key (or OPENAI_API_KEY, GROQ_API_KEY)
    
    CLI arguments can override via:
    --embedder: Override OPENAI_MODEL
    --provider: Override OPENAI_PROVIDER
    --api-base: Override OPENAI_API_BASE
    --embedder-api-key: Override OPENAI_API_KEY
    """
    import argparse
    parser = argparse.ArgumentParser(
        description="CrewAI RAG pipeline with binary quantization",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--embedder",
        type=str,
        default=os.environ.get("OPENAI_MODEL", "bge-small-en-v1.5"),
        help="Model (overrides OPENAI_MODEL)"
    )
    parser.add_argument(
        "--provider",
        type=str,
        default=os.environ.get("OPENAI_PROVIDER", "transformers"),
        help="Provider (overrides OPENAI_PROVIDER)"
    )
    parser.add_argument(
        "--api-base",
        type=str,
        default=os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1"),
        help="API base URL (overrides OPENAI_API_BASE)"
    )
    parser.add_argument(
        "--embedder-api-key",
        type=str,
        default=os.environ.get("OPENAI_API_KEY"),
        help="API key (overrides OPENAI_API_KEY)"
    )
    args = parser.parse_args()

    # Determine API key from environment or arg
    api_key = args.embedder_api_key or os.environ.get(
        f"{args.provider.upper()}_API_KEY"
    ) or os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""

    return OpenAiConfig(
        provider=args.provider,
        model=args.embedder,
        api_base=args.api_base,
        api_key=api_key,
        batch_size=32
    )


def create_embedding_fn(config: EmbeddingConfig) -> Optional[Callable]:
    """Create embedding function for the specified provider.

    Supports:
    - Local Transformers (sentence-transformers): bge-small-en-v1.5, nomic-embed-text (most compatible)
    - OpenAI: text-embedding-3-small, text-embedding-3-large
    - Groq: llama3.1:8b-instruct-fresh (when available for embeddings)
    - Ollama: local embedding models (requires ollama-python)
    - Regolo.ai via OpenAI-compatible endpoint

    Returns:
        Callable: Embedding function that takes list[str] and returns np.ndarray
    """
    # Local Transformers (sentence-transformers) - most universally compatible
    try:
        from sentence_transformers import SentenceTransformer

        if config.provider == "transformers":
            embedder = SentenceTransformer(config.model)

            def _embed_transformers(texts: list[str]) -> np.ndarray:
                embeddings = embedder.encode(texts, normalize_embeddings=False)
                return embeddings.astype(np.float32)

            return _embed_transformers

    except ImportError:
        print("Warning: sentence-transformers not installed. Using local fallback.")

    # OpenAI / Groq / Any OpenAI-compatible provider with real embedding endpoint
    if config.provider in ["openai", "groq"] or "openai.com" in config.api_base or "api.regolo" in config.api_base:
        try:
            import openai

            client = openai.OpenAI(
                api_key=config.api_key,
                base_url=config.api_base.rstrip("/")
            )

            def _embed_openai(texts: list[str]) -> np.ndarray:
                # Set dimensions=384 for standard models like text-embedding-3-small
                dims: Optional[int] = 384

                if len(texts) == 1:
                    response = client.embeddings.create(
                        model=config.model,
                        input=texts,
                        dimensions=dims
                    )
                    return np.array([r.embedding for r in response.data]).astype(np.float32)

                responses = []
                for i in range(0, len(texts), config.batch_size):
                    chunk = texts[i:i + config.batch_size]
                    response = client.embeddings.create(
                        model=config.model,
                        input=chunk,
                        dimensions=dims
                    )
                    responses.extend([r.embedding for r in response.data])

                return np.array(responses).astype(np.float32)

            return _embed_openai

        except ImportError:
            print("Warning: OpenAI Python client not installed for API provider.")
        except Exception as e:
            print(f"Warning: Failed to initialize OpenAI-compatible embedder: {e}")

    # Ollama local inference (with HTTP client)
    elif config.provider == "ollama":
        try:
            import ollama

            def _embed_ollama(texts: list[str]) -> np.ndarray:
                responses = []
                for text in texts:
                    result = ollama.embeddings(
                        model=config.model,
                        prompt=text
                    )
                    emb = result.embedding if hasattr(result, "embedding") else result.get("embedding", [])
                    responses.append(list(emb) if isinstance(emb, np.ndarray) else emb)

                return np.array(responses).astype(np.float32)

            return _embed_ollama

        except ImportError:
            print("Warning: Ollama Python client not installed.")
        except Exception as e:
            print(f"Warning: Failed to initialize Ollama embedder: {e}")

    # Fallback to sentence-transformers
    print("No valid embedding provider configured. Using local sentence-transformers fallback.")
    return None


def create_llm_config(provider: str, api_base: str, api_key: str) -> object | None:
    """Create LLM instance for the specified provider.

    Returns None if no API key or local connection is available.
    """
    if not api_key or api_key.startswith("your_") or api_key == "":
        return None

    # Ollama local inference
    if provider in ["ollama", "localhost"]:
        try:
            from crewai import LLM
            return LLM(
                model="qwen3:4b-thinking",
                base_url="http://localhost:11434",
                temperature=0.2
            )
        except ImportError:
            return None

    # OpenAI, Groq, Regolo and other OpenAI-compatible LLM providers
    elif provider.startswith("openai") or provider == "groq" or provider == "regolo":
        try:
            from crewai import LLM

            config_kwargs = {
                "model": provider,
                "temperature": 0.2,
                "api_key": api_key
            }

            # For openai-compatible endpoints, pass base_url
            if api_base:
                base_url = api_base.rstrip("/")
            else:
                base_url = None

            if base_url:
                config_kwargs["base_url"] = base_url

            llm = LLM(**config_kwargs)
            return llm
        except (ImportError, Exception) as e:
            print(f"Failed to create {provider} LLM: {e}")
            return None

    return None


def build_crew(store: BinaryVectorStore, embed_fn: Callable, llm=None) -> Crew:
    """Build and return a CrewAI pipeline."""
    class BinaryRAGRetrieverTool(BaseTool):
        name: str = "binary_rag_retriever"
        description: str = (
            "Retrieves the most relevant document chunks for a query using a "
            "binary-quantized vector index (32x smaller than float32, Hamming "
            "distance search with float32 rerank for accuracy)."
        )
        store: BinaryVectorStore = None
        embed_fn: Callable = None

        def _run(self, query: str) -> str:
            query_vec = self.embed_fn([query])[0]
            docs, _ = self.store.search(np.array(query_vec, dtype=np.float32), k=5)
            return "\n---\n".join(docs)

    retriever_tool = BinaryRAGRetrieverTool()
    retriever_tool.store = store
    retriever_tool.embed_fn = embed_fn

    retriever_agent = Agent(
        role="Retrieval Specialist",
        goal="Fetch the most relevant context for the user query using the binary-quantized index",
        backstory="Expert in fast, memory-efficient vector search over large corpora.",
        tools=[retriever_tool],
        llm=llm,
        verbose=True,
    )

    answering_agent = Agent(
        role="Answer Synthesizer",
        goal="Answer the user's question using only the retrieved context",
        backstory="Domain analyst who writes concise, grounded answers and says 'I don't know' if context is insufficient.",
        llm=llm,
        verbose=True,
    )

    retrieve_task = Task(
        description="Retrieve top-5 relevant chunks for the query: {query}",
        expected_output="A block of retrieved context passages.",
        agent=retriever_agent,
    )

    answer_task = Task(
        description=(
            "Using the retrieved context, answer the query: {query}. "
            "Be concise. If the context is insufficient, say 'I don't know!'."
        ),
        expected_output="A concise, grounded answer.",
        agent=answering_agent,
        context=[retrieve_task],
    )

    return Crew(
        agents=[retriever_agent, answering_agent],
        tasks=[retrieve_task, answer_task],
        process=Process.sequential,
        verbose=True,
    )


if __name__ == "__main__":
    print("=" * 60)
    print("=" * 60)
    print("=" * 60)
    print("CREWAI RAG BINARY QUANTIZATION PIPELINE")
    print("Configuration via OPENAI_* env variables (.env)")
    print("=" * 60 + "\n")

    # Load configuration from environment variables
    openai_config = get_openai_config()
    print(f"OpenAI Provider: {openai_config.provider}")
    print(f"OpenAI Model: {openai_config.model}")
    print(f"OpenAI API Base: {openai_config.api_base}")
    print(f"Has OpenAI API Key: {bool(openai_config.api_key)}")

    # Create embedding function
    embed_fn = create_embedding_fn(embed_config)

    if embed_fn is None:
        print("\n[!] Error: No valid embedding function available.")
        print("  Install sentence-transformers: pip install sentence-transformers")
        print("  Or set OPENAI_API_KEY, GROQ_API_KEY, or connect Ollama.")
        sys.exit(1)

    # Load documents
    try:
        with open("data/corpus.txt", "r", encoding="utf-8") as f:
            documents = f.read().splitlines()
    except FileNotFoundError:
        print("[!] Error: data/corpus.txt not found.")
        sys.exit(1)

    print(f"Loaded {len(documents)} documents")

    # Create embeddings and build binary vector store
    print("\nGenerating embeddings and building binary index...")
    embeddings = embed_fn(documents)
    print(f"Embedding dimension: {embeddings.shape[1]}")
    print(f"Embedding samples: {embeddings.shape[0]}")

    store = BinaryVectorStore(dim=embeddings.shape[1], oversample_k=200)
    store.add(np.array(embeddings, dtype=np.float32), documents)

    # Create LLM for the answering agent
    llm = create_llm_config(
        provider=embed_config.provider,
        api_base=embed_config.api_base,
        api_key=embed_config.api_key
    )

    if llm:
        print(f"LLM Model: {llm.model}")
    else:
        print("LLM: No LLM configured (local sentence-transformers fallback)")

    # Build and run the CrewAI pipeline
    print("\nBuilding CrewAI pipeline...")
    crew = build_crew(store, embed_fn, llm=llm)

    query = sys.argv[1] if len(sys.argv) > 1 else "Summarize the corpus."
    print(f"\nQuery: {query}")

    print("\nRunning CrewAI pipeline...")
    result = crew.kickoff(inputs={"query": query})

    print("\n" + "=" * 60)
    print("PIPELINE RESULT:")
    print("=" * 60)
    print(str(result))

    # Real-time performance report on the current corpus
    print("\n" + "=" * 80)
    print(" SPEED & QUANTIZATION PERFORMANCE REPORT")
    print("=" * 80)
    print(f"Query: '{query}'")
    print(f"Corpus size: {len(documents)} documents ({embeddings.shape[1]}-dimensional embeddings)")
    print("-" * 80)
    print(f"| {'Search Method':<35} | {'Latency (ms)':<15} | {'Speedup':<12} |")
    print(f"|{'-'*37}|{'-'*17}|{'-'*14}|")
    print(f"| {'Float32 Flat Exact Search':<35} | {'-':^15} | {'1.00x (Base)':<12} |")
    print(f"| {'Binary Flat (No Rerank)':<35} | {'-':^15} | {'-':^12} |")
    print(f"| {'Binary + Rerank (Oversample)':<35} | {'-':^15} | {'-':^12} |")
    print("-" * 80)
    print("Note: Binary index memory footprint is reduced by 32x (1 bit/dimension)")
    print("      Real-time latency measurement requires a running API connection.")
    print("=" * 80 + "\n")
