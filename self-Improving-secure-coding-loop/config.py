"""Configuration module for Closed-Loop Secure Coding Agent.
Connects to Regolo.ai OpenAI-Compatible API with Brick Semantic Routing (brick-complexity-pro).
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
REGOLO_MODEL = os.getenv("REGOLO_MODEL", "qwen3-coder-next")

# Meta-Router Model (Brick Semantic Routing & Complexity Evaluation)
MODEL_BRICK_ROUTER = os.getenv("MODEL_BRICK_ROUTER", "brick-complexity-pro")

# Per-Stage Model Routing (Configurable via .env)
# Supported models available on Regolo.ai:
# - brick-complexity-pro  (Semantic meta-router, complexity scoring 1.0-10.0, tier routing)
# - gpt-oss-20b           (Fast & economic classification, triage, graph extraction - 0.28s)
# - qwen3.5-122b          (Deep reasoning, architecture planning, complex verify - requires max_tokens >= 800)
# - qwen3-coder-next      (Code generation, AST & security scanning specialist - 0.18s)
# - gpt-oss-120b          (Balanced reasoning & code synthesis)
# - Llama-3.3-70B-Instruct (Fast instruction following)
MODEL_OPEN_SWE_CLASSIFY = os.getenv("MODEL_OPEN_SWE_CLASSIFY", "gpt-oss-20b")
MODEL_OPEN_SWE_PLAN = os.getenv("MODEL_OPEN_SWE_PLAN", "qwen3.5-122b")
MODEL_OPEN_SWE_EXECUTE = os.getenv("MODEL_OPEN_SWE_EXECUTE", "qwen3-coder-next")
MODEL_DEEPSEC_SCAN = os.getenv("MODEL_DEEPSEC_SCAN", "qwen3-coder-next")
MODEL_DEEPSEC_REVALIDATE = os.getenv("MODEL_DEEPSEC_REVALIDATE", "qwen3.5-122b")
MODEL_COGNEE_EXTRACT = os.getenv("MODEL_COGNEE_EXTRACT", "gpt-oss-20b")

# Dynamic Routing & Budget Governance Constraints
TOTAL_PIPELINE_TOKEN_BUDGET = int(os.getenv("TOTAL_PIPELINE_TOKEN_BUDGET", "25000"))
BUDGET_WARNING_THRESHOLD = float(os.getenv("BUDGET_WARNING_THRESHOLD", "0.75"))
ENABLE_SEMANTIC_ROUTING = os.getenv("ENABLE_SEMANTIC_ROUTING", "true").lower() == "true"
ENABLE_DYNAMIC_ESCALATION = os.getenv("ENABLE_DYNAMIC_ESCALATION", "true").lower() == "true"
ESCALATION_COMPLEXITY_THRESHOLD = float(os.getenv("ESCALATION_COMPLEXITY_THRESHOLD", "7.0"))

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
        "timeout": int(os.getenv("TIMEOUT_CLASSIFY", "60")),
        "description": "Issue triage & intent classification",
    },
    "plan": {
        "model": MODEL_OPEN_SWE_PLAN,
        # qwen3.5-122b requires max_tokens >= 800 for reasoning
        "max_tokens": int(os.getenv("MAX_TOKENS_PLAN", "1500")),
        "temperature": float(os.getenv("TEMP_PLAN", "0.2")),
        "timeout": int(os.getenv("TIMEOUT_PLAN", "120")),
        "description": "SWE Architecture & Remediation Planning",
    },
    "implement": {
        "model": MODEL_OPEN_SWE_EXECUTE,
        "max_tokens": int(os.getenv("MAX_TOKENS_IMPLEMENT", "2500")),
        "temperature": float(os.getenv("TEMP_IMPLEMENT", "0.2")),
        "timeout": int(os.getenv("TIMEOUT_IMPLEMENT", "180")),
        "description": "Code Generation & Patch Implementation",
    },
    "deepsec_scan": {
        "model": MODEL_DEEPSEC_SCAN,
        "max_tokens": int(os.getenv("MAX_TOKENS_DEEPSEC_SCAN", "1500")),
        "temperature": float(os.getenv("TEMP_DEEPSEC_SCAN", "0.1")),
        "timeout": int(os.getenv("TIMEOUT_DEEPSEC_SCAN", "90")),
        "description": "Security Harness SAST & AST Finding Analysis",
    },
    "deepsec_revalidate": {
        "model": MODEL_DEEPSEC_REVALIDATE,
        # qwen3.5-122b requires max_tokens >= 800 for reasoning
        "max_tokens": int(os.getenv("MAX_TOKENS_DEEPSEC_REVALIDATE", "1200")),
        "temperature": float(os.getenv("TEMP_DEEPSEC_REVALIDATE", "0.1")),
        "timeout": int(os.getenv("TIMEOUT_DEEPSEC_REVALIDATE", "120")),
        "description": "Patch Revalidation & Regression Gate",
    },
    "cognee_extract": {
        "model": MODEL_COGNEE_EXTRACT,
        "max_tokens": int(os.getenv("MAX_TOKENS_COGNEE_EXTRACT", "1024")),
        "temperature": float(os.getenv("TEMP_COGNEE_EXTRACT", "0.1")),
        "timeout": int(os.getenv("TIMEOUT_COGNEE_EXTRACT", "60")),
        "description": "Engineering Memory & Knowledge Graph Extraction",
    },
}

# Sub-agent profiles for Brick Semantic Router
SUBAGENT_PROFILES = {
    "classify": {
        "role_name": "Governance & Triage",
        "description": "Issue triage, risk assessment, and policy governance",
        "preferred_model": MODEL_OPEN_SWE_CLASSIFY,
        "fallback_model": "gpt-oss-20b",
        "escalation_model": "gpt-oss-120b",
        "token_limit": 1024,
        "timeout_sec": int(os.getenv("TIMEOUT_CLASSIFY", "60")),
        "escalation_threshold": 8.5,
        "criticality": "MEDIUM",
        "allowed_tools": ["triage_classifier", "policy_evaluator"],
    },
    "plan": {
        "role_name": "Open SWE Planner",
        "description": "Deep architecture planning and remediation strategy",
        "preferred_model": MODEL_OPEN_SWE_PLAN,
        "fallback_model": "qwen3-coder-next",
        "escalation_model": "qwen3.5-122b",
        "token_limit": 1500,
        "timeout_sec": int(os.getenv("TIMEOUT_PLAN", "120")),
        "escalation_threshold": ESCALATION_COMPLEXITY_THRESHOLD,
        "criticality": "HIGH",
        "allowed_tools": ["cognee_query", "ast_inspect"],
    },
    "implement": {
        "role_name": "Open SWE Executor",
        "description": "Defensive code refactoring and patch execution",
        "preferred_model": MODEL_OPEN_SWE_EXECUTE,
        "fallback_model": "gpt-oss-120b",
        "escalation_model": "qwen3-coder-next",
        "token_limit": 2500,
        "timeout_sec": int(os.getenv("TIMEOUT_IMPLEMENT", "180")),
        "escalation_threshold": ESCALATION_COMPLEXITY_THRESHOLD,
        "criticality": "CRITICAL",
        "allowed_tools": ["sandbox_write", "pytest_runner"],
    },
    "deepsec_scan": {
        "role_name": "Deepsec Security Scanner",
        "description": "SAST AST static analysis and semantic vulnerability audit",
        "preferred_model": MODEL_DEEPSEC_SCAN,
        "fallback_model": "gpt-oss-20b",
        "escalation_model": "qwen3-coder-next",
        "token_limit": 1500,
        "timeout_sec": int(os.getenv("TIMEOUT_DEEPSEC_SCAN", "90")),
        "escalation_threshold": ESCALATION_COMPLEXITY_THRESHOLD,
        "criticality": "HIGH",
        "allowed_tools": ["ast_parser", "cwe_catalog"],
    },
    "deepsec_revalidate": {
        "role_name": "Deepsec Revalidation Gate",
        "description": "Zero-trust verification of patched code and sign-off",
        "preferred_model": MODEL_DEEPSEC_REVALIDATE,
        "fallback_model": "qwen3-coder-next",
        "escalation_model": "qwen3.5-122b",
        "token_limit": 1200,
        "timeout_sec": int(os.getenv("TIMEOUT_DEEPSEC_REVALIDATE", "120")),
        "escalation_threshold": ESCALATION_COMPLEXITY_THRESHOLD,
        "criticality": "CRITICAL",
        "allowed_tools": ["regression_scanner", "evidence_signer"],
    },
    "cognee_extract": {
        "role_name": "Cognee Memory Engine",
        "description": "Knowledge graph entity extraction and memory synthesis",
        "preferred_model": MODEL_COGNEE_EXTRACT,
        "fallback_model": "gpt-oss-20b",
        "escalation_model": "gpt-oss-120b",
        "token_limit": 1024,
        "timeout_sec": int(os.getenv("TIMEOUT_COGNEE_EXTRACT", "60")),
        "escalation_threshold": 8.5,
        "criticality": "LOW",
        "allowed_tools": ["graph_store", "qdrant_sync"],
    },
}

# Pricing estimation (USD per 1M tokens) on Regolo.ai vs Single Frontier Model Baseline
PRICING_ESTIMATION = {
    "brick-complexity-pro": {
        "prompt_cost_per_1m": 0.20,
        "completion_cost_per_1m": 0.50,
    },
    "gpt-oss-20b": {
        "prompt_cost_per_1m": 0.15,
        "completion_cost_per_1m": 0.30,
    },
    "gpt-oss-120b": {
        "prompt_cost_per_1m": 0.50,
        "completion_cost_per_1m": 1.50,
    },
    "glm5.2": {
        "prompt_cost_per_1m": 0.60,
        "completion_cost_per_1m": 1.80,
    },
    "GLM-5.2": {
        "prompt_cost_per_1m": 0.60,
        "completion_cost_per_1m": 1.80,
    },
    "Llama-3.3-70B-Instruct": {
        "prompt_cost_per_1m": 0.70,
        "completion_cost_per_1m": 2.00,
    },
    "qwen3.5-122b": {
        "prompt_cost_per_1m": 1.20,
        "completion_cost_per_1m": 3.50,
    },
    "qwen3-coder-next": {
        "prompt_cost_per_1m": 0.80,
        "completion_cost_per_1m": 2.20,
    },
    "single_frontier_baseline": {
        "prompt_cost_per_1m": 3.00,
        "completion_cost_per_1m": 15.00,
    },
}
