"""Configuration module for Closed-Loop Secure Coding Agent.
Connects to Regolo.ai OpenAI-Compatible API with per-stage model routing.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent

# Load .env file
ENV_FILE = BASE_DIR / ".env"
if ENV_FILE.exists():
    load_dotenv(dotenv_path=ENV_FILE, override=True)
else:
    load_dotenv()

# Global Regolo API Configuration
REGOLO_API_KEY = os.getenv("REGOLO_API_KEY", "")
REGOLO_BASE_URL = os.getenv("REGOLO_BASE_URL", "https://api.regolo.ai/v1")
REGOLO_MODEL = os.getenv("REGOLO_MODEL", "GLM-5.2")

# Per-Stage Model Routing (Configurable via .env)
# Supported models available on Regolo.ai:
# - GLM-5.2               (Balanced reasoning, tool use, code generation)
# - qwen3.5-122b          (Deep reasoning, architecture planning, complex verify)
# - Llama-3.3-70B-Instruct (Fast execution, precise patch writing)
# - gpt-oss-20b           (Fast & economic classification, triage, graph extraction)
MODEL_OPEN_SWE_CLASSIFY = os.getenv("MODEL_OPEN_SWE_CLASSIFY", REGOLO_MODEL)
MODEL_OPEN_SWE_PLAN = os.getenv("MODEL_OPEN_SWE_PLAN", REGOLO_MODEL)
MODEL_OPEN_SWE_EXECUTE = os.getenv("MODEL_OPEN_SWE_EXECUTE", REGOLO_MODEL)
MODEL_DEEPSEC_SCAN = os.getenv("MODEL_DEEPSEC_SCAN", REGOLO_MODEL)
MODEL_DEEPSEC_REVALIDATE = os.getenv("MODEL_DEEPSEC_REVALIDATE", REGOLO_MODEL)
MODEL_COGNEE_EXTRACT = os.getenv("MODEL_COGNEE_EXTRACT", REGOLO_MODEL)

# Background Services Configuration (Qdrant & Cognee Docker Backends)
QDRANT_HOST = os.getenv("QDRANT_HOST", "127.0.0.1")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_URL = os.getenv("QDRANT_URL", f"http://{QDRANT_HOST}:{QDRANT_PORT}")
COGNEE_API_URL = os.getenv("COGNEE_API_URL", "http://127.0.0.1:8800")

# Memory & Storage paths
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True, parents=True)

COGNEE_DB_PATH = DATA_DIR / "cognee_graph.json"
TELEMETRY_DB_PATH = DATA_DIR / "telemetry.json"
SANDBOX_WORK_DIR = DATA_DIR / "sandboxes"
SANDBOX_WORK_DIR.mkdir(exist_ok=True, parents=True)

# Sample Repositories path
SAMPLE_REPOS_DIR = BASE_DIR / "sample_repos"

# Governance & Routing Configuration (Brick Policies)
STAGE_CONFIGS = {
    "classify": {
        "model": MODEL_OPEN_SWE_CLASSIFY,
        "max_tokens": int(os.getenv("MAX_TOKENS_CLASSIFY", "1024")),
        "temperature": float(os.getenv("TEMP_CLASSIFY", "0.1")),
        "description": "Issue triage & intent classification",
    },
    "plan": {
        "model": MODEL_OPEN_SWE_PLAN,
        "max_tokens": int(os.getenv("MAX_TOKENS_PLAN", "2048")),
        "temperature": float(os.getenv("TEMP_PLAN", "0.2")),
        "description": "SWE Architecture & Remediation Planning",
    },
    "implement": {
        "model": MODEL_OPEN_SWE_EXECUTE,
        "max_tokens": int(os.getenv("MAX_TOKENS_IMPLEMENT", "4096")),
        "temperature": float(os.getenv("TEMP_IMPLEMENT", "0.2")),
        "description": "Code Generation & Patch Implementation",
    },
    "deepsec_scan": {
        "model": MODEL_DEEPSEC_SCAN,
        "max_tokens": int(os.getenv("MAX_TOKENS_DEEPSEC_SCAN", "3072")),
        "temperature": float(os.getenv("TEMP_DEEPSEC_SCAN", "0.1")),
        "description": "Security Harness SAST & AST Finding Analysis",
    },
    "deepsec_revalidate": {
        "model": MODEL_DEEPSEC_REVALIDATE,
        "max_tokens": int(os.getenv("MAX_TOKENS_DEEPSEC_REVALIDATE", "2048")),
        "temperature": float(os.getenv("TEMP_DEEPSEC_REVALIDATE", "0.1")),
        "description": "Patch Revalidation & Regression Gate",
    },
    "cognee_extract": {
        "model": MODEL_COGNEE_EXTRACT,
        "max_tokens": int(os.getenv("MAX_TOKENS_COGNEE_EXTRACT", "2048")),
        "temperature": float(os.getenv("TEMP_COGNEE_EXTRACT", "0.1")),
        "description": "Engineering Memory & Knowledge Graph Extraction",
    },
}

# Pricing estimation (Regolo.ai vs Frontier Model comparison in USD per 1M tokens)
PRICING_ESTIMATION = {
    "regolo_glm52": {
        "prompt_cost_per_1m": 0.60,
        "completion_cost_per_1m": 1.80,
    },
    "single_frontier_baseline": {
        "prompt_cost_per_1m": 3.00,
        "completion_cost_per_1m": 15.00,
    },
}
