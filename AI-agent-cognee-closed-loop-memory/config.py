"""Configuration module for Regolo.ai + Cognee Long-Term Memory Suite.
Integrates European Sovereign AI inference with self-hosted Cognee memory layers.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Base project directory
BASE_DIR = Path(__file__).resolve().parent

# Load environment configuration
ENV_FILE = BASE_DIR / ".env"
if ENV_FILE.exists():
    load_dotenv(dotenv_path=ENV_FILE, override=True)
else:
    load_dotenv()

# Global Regolo.ai API Configuration
REGOLO_API_KEY = os.getenv("REGOLO_API_KEY", "").strip()
REGOLO_BASE_URL = os.getenv("REGOLO_BASE_URL", "https://api.regolo.ai/v1").rstrip("/")
REGOLO_DEFAULT_MODEL = os.getenv("REGOLO_DEFAULT_MODEL", "GLM-5.2")

# Brick Dynamic Meta-Router
MODEL_BRICK_ROUTER = os.getenv("MODEL_BRICK_ROUTER", "brick-complexity-pro")

# Specialized Stage Models on Regolo
MODEL_COGNEE_EXTRACT = os.getenv("MODEL_COGNEE_EXTRACT", "gpt-oss-20b")
MODEL_AGENT_CODER = os.getenv("MODEL_AGENT_CODER", "qwen3-coder-next")
MODEL_AGENT_REASONING = os.getenv("MODEL_AGENT_REASONING", "qwen3.5-122b")
MODEL_AGENT_CHAT = os.getenv("MODEL_AGENT_CHAT", "Llama-3.3-70B-Instruct")
MODEL_EMBEDDING = os.getenv("MODEL_EMBEDDING", "Qwen3-Embedding-8B")
MODEL_RERANKER = os.getenv("MODEL_RERANKER", "Qwen3-Reranker-4B")

# Postgres + pgvector Service Configuration
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "127.0.0.1")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_USER = os.getenv("POSTGRES_USER", "cognee")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "cognee_secret_pass")
POSTGRES_DB = os.getenv("POSTGRES_DB", "cognee_db")

# Cognee Backend API Configuration
COGNEE_API_HOST = os.getenv("COGNEE_API_HOST", "127.0.0.1")
COGNEE_API_PORT = int(os.getenv("COGNEE_API_PORT", "8800"))
COGNEE_API_URL = os.getenv("COGNEE_API_URL", f"http://{COGNEE_API_HOST}:{COGNEE_API_PORT}")

# Storage and Persisted Data Directories
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True, parents=True)

COGNEE_GRAPH_FILE = DATA_DIR / "cognee_knowledge_graph.json"
COGNEE_VECTOR_FILE = DATA_DIR / "cognee_vector_store.json"
COGNEE_MEMORY_LOG = DATA_DIR / "memory_session_log.json"
PLUGINS_CONFIG_DIR = BASE_DIR / "plugins"
PLUGINS_CONFIG_DIR.mkdir(exist_ok=True, parents=True)

# Sample SaaS Codebase path
SAMPLE_REPO_DIR = BASE_DIR / "sample_repo"

# Graph and Recall Parameters
MAX_GRAPH_HOPS = int(os.getenv("MAX_GRAPH_HOPS", "3"))
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.75"))

# Stage Specific Execution Configuration
STAGE_CONFIGS = {
    "extract": {
        "model": MODEL_COGNEE_EXTRACT,
        "max_tokens": 1200,
        "temperature": 0.1,
        "description": "Entity extraction, relation mapping & knowledge graph node generation",
    },
    "reasoning": {
        "model": MODEL_AGENT_REASONING,
        # qwen3.5-122b reasoning requires max_tokens >= 800
        "max_tokens": 1600,
        "temperature": 0.2,
        "description": "Deep architectural reasoning, policy compliance & multi-session causality",
    },
    "coder": {
        "model": MODEL_AGENT_CODER,
        "max_tokens": 2048,
        "temperature": 0.2,
        "description": "Precise code patch synthesis & pattern-aligned code generation",
    },
    "chat": {
        "model": MODEL_AGENT_CHAT,
        "max_tokens": 1024,
        "temperature": 0.3,
        "description": "Interactive developer query response & memory synthesis",
    },
}
