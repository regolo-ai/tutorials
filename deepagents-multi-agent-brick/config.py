"""Configuration module for Deep Agents with Brick Semantic Routing.
Connects to Regolo.ai OpenAI-Compatible API with multi-agent orchestration.
"""

import os
from pathlib import Path
from typing import Any, Dict, List
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
REGOLO_MODEL = os.getenv("REGOLO_MODEL", "gpt-oss-20b")

# Meta-Router Model on Regolo.ai
MODEL_BRICK_ROUTER = os.getenv("MODEL_BRICK_ROUTER", "brick-complexity-pro")

# Model name normalization: maps display names to actual Regolo.ai API identifiers
MODEL_NAME_MAP: Dict[str, str] = {
    "GLM-5.2": "gpt-oss-20b",
    "glm-5.2": "gpt-oss-20b",
    "GLM-5": "gpt-oss-20b",
    "Llama-3.3-70B-Instruct": "Llama-3.3-70B-Instruct",
    "llama-3.3-70b-instruct": "Llama-3.3-70B-Instruct",
    "llama-3.3-70b": "Llama-3.3-70B-Instruct",
    "qwen3.5-122b": "qwen3.5-122b",
    "Qwen3.5-122b": "qwen3.5-122b",
    "Qwen-3.5-122b": "qwen3.5-122b",
    "gpt-oss-20b": "gpt-oss-20b",
    "GPT-OSS-20B": "gpt-oss-20b",
}

# Set of valid model identifiers for validation
VALID_MODELS = frozenset(MODEL_NAME_MAP.values())


def normalize_model_name(model: str) -> str:
    """Normalize a model display name to its valid Regolo.ai API identifier."""
    if not model:
        return REGOLO_MODEL
    return MODEL_NAME_MAP.get(model, MODEL_NAME_MAP.get(model.lower(), model))


# Supported models verified on Regolo.ai:
# - gpt-oss-20b               (Ultra-fast & economical classification, triage, signature extraction)
# - qwen3.5-122b              (Deep reasoning, architecture planning, complex verify - reasoning model)
# - Llama-3.3-70B-Instruct    (Fast execution, precise coding, patch implementation)
# - brick-complexity-pro      (Semantic routing meta-model for Brick)

# Sub-Agent Model Assignments (Preferred & Fallback)
MODEL_PLANNER_PREFERRED = os.getenv("MODEL_PLANNER_PREFERRED", "qwen3.5-122b")
MODEL_PLANNER_FALLBACK = os.getenv("MODEL_PLANNER_FALLBACK", "gpt-oss-20b")

MODEL_RESEARCHER_PREFERRED = os.getenv("MODEL_RESEARCHER_PREFERRED", "gpt-oss-20b")
MODEL_RESEARCHER_FALLBACK = os.getenv("MODEL_RESEARCHER_FALLBACK", "gpt-oss-20b")

MODEL_TOOL_AGENT_PREFERRED = os.getenv("MODEL_TOOL_AGENT_PREFERRED", "gpt-oss-20b")
MODEL_TOOL_AGENT_FALLBACK = os.getenv("MODEL_TOOL_AGENT_FALLBACK", "gpt-oss-20b")

MODEL_CODE_EXECUTOR_PREFERRED = os.getenv("MODEL_CODE_EXECUTOR_PREFERRED", "Llama-3.3-70B-Instruct")
MODEL_CODE_EXECUTOR_FALLBACK = os.getenv("MODEL_CODE_EXECUTOR_FALLBACK", "gpt-oss-20b")

MODEL_REVIEWER_PREFERRED = os.getenv("MODEL_REVIEWER_PREFERRED", "qwen3.5-122b")
MODEL_REVIEWER_FALLBACK = os.getenv("MODEL_REVIEWER_FALLBACK", "gpt-oss-20b")

MODEL_REPORT_WRITER_PREFERRED = os.getenv("MODEL_REPORT_WRITER_PREFERRED", "gpt-oss-20b")
MODEL_REPORT_WRITER_FALLBACK = os.getenv("MODEL_REPORT_WRITER_FALLBACK", "gpt-oss-20b")

MODEL_BUDGET_CONTROLLER = os.getenv("MODEL_BUDGET_CONTROLLER", "gpt-oss-20b")

# Dynamic Budget & Routing Constraints
TOTAL_PIPELINE_TOKEN_BUDGET = int(os.getenv("TOTAL_PIPELINE_TOKEN_BUDGET", "25000"))
BUDGET_WARNING_THRESHOLD = float(os.getenv("BUDGET_WARNING_THRESHOLD", "0.75"))
ENABLE_SEMANTIC_ROUTING = os.getenv("ENABLE_SEMANTIC_ROUTING", "true").lower() in ("true", "1", "yes")
ENABLE_DYNAMIC_ESCALATION = os.getenv("ENABLE_DYNAMIC_ESCALATION", "true").lower() in ("true", "1", "yes")

# Directory paths
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True, parents=True)

TELEMETRY_FILE = DATA_DIR / "telemetry.json"
HARNESS_OUTPUT_DIR = DATA_DIR / "synthesized_harness"
HARNESS_OUTPUT_DIR.mkdir(exist_ok=True, parents=True)

SAMPLE_REPOS_DIR = BASE_DIR / "sample_repos"
SAMPLE_REPOS_DIR.mkdir(exist_ok=True, parents=True)

SANDBOX_WORK_DIR = DATA_DIR / "sandboxes"
SANDBOX_WORK_DIR.mkdir(exist_ok=True, parents=True)

# Background Services Configuration (Docker Backends)
QDRANT_HOST = os.getenv("QDRANT_HOST", "127.0.0.1")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_URL = os.getenv("QDRANT_URL", f"http://{QDRANT_HOST}:{QDRANT_PORT}")

MCP_SANDBOX_HOST = os.getenv("MCP_SANDBOX_HOST", "127.0.0.1")
MCP_SANDBOX_PORT = int(os.getenv("MCP_SANDBOX_PORT", "8900"))
MCP_SANDBOX_URL = os.getenv("MCP_SANDBOX_URL", f"http://{MCP_SANDBOX_HOST}:{MCP_SANDBOX_PORT}")

# Sub-Agent Architectural Profiles & Governance Specs
SUBAGENT_PROFILES: Dict[str, Dict[str, Any]] = {
    "planner": {
        "role_name": "Deep Agent Planner",
        "description": "Decomposes high-level goal into dependency DAG, allocates sub-agent budgets & critical paths.",
        "preferred_model": MODEL_PLANNER_PREFERRED,
        "fallback_model": MODEL_PLANNER_FALLBACK,
        "escalation_model": "qwen3.5-122b",
        "token_limit": int(os.getenv("MAX_TOKENS_PLANNER", "3000")),
        "timeout_sec": int(os.getenv("TIMEOUT_PLANNER", "45")),
        "allowed_tools": ["read_repo_tree", "inspect_entrypoints", "estimate_dag_complexity"],
        "escalation_threshold": 7.5,
        "temperature": 0.2,
        "criticality": "HIGH",
    },
    "researcher": {
        "role_name": "API & Tool Researcher",
        "description": "Extracts raw API contracts, signatures, rate limit headers, edge cases and parameter schemas.",
        "preferred_model": MODEL_RESEARCHER_PREFERRED,
        "fallback_model": MODEL_RESEARCHER_FALLBACK,
        "escalation_model": "GLM-5.2",
        "token_limit": int(os.getenv("MAX_TOKENS_RESEARCHER", "2500")),
        "timeout_sec": int(os.getenv("TIMEOUT_RESEARCHER", "30")),
        "allowed_tools": ["inspect_api_docs", "extract_signatures", "grep_code", "parse_docstrings"],
        "escalation_threshold": 6.0,
        "temperature": 0.1,
        "criticality": "MEDIUM",
    },
    "browser_tool_agent": {
        "role_name": "Tool & Sandbox Prober",
        "description": "Interacts with live/mock endpoints, tests request schemas, verifies status codes and response shapes.",
        "preferred_model": MODEL_TOOL_AGENT_PREFERRED,
        "fallback_model": MODEL_TOOL_AGENT_FALLBACK,
        "escalation_model": "GLM-5.2",
        "token_limit": int(os.getenv("MAX_TOKENS_TOOL_AGENT", "2000")),
        "timeout_sec": int(os.getenv("TIMEOUT_TOOL_AGENT", "30")),
        "allowed_tools": ["probe_endpoint", "validate_json_schema", "test_mcp_ping", "inspect_network_response"],
        "escalation_threshold": 6.5,
        "temperature": 0.1,
        "criticality": "MEDIUM",
    },
    "code_executor": {
        "role_name": "MCP Code Executor & Synthesizer",
        "description": "Synthesizes typed Python MCP tools, Pydantic input models, error handlers and runs sandbox tests.",
        "preferred_model": MODEL_CODE_EXECUTOR_PREFERRED,
        "fallback_model": MODEL_CODE_EXECUTOR_FALLBACK,
        "escalation_model": "qwen3.5-122b",
        "token_limit": int(os.getenv("MAX_TOKENS_CODE_EXECUTOR", "4000")),
        "timeout_sec": int(os.getenv("TIMEOUT_CODE_EXECUTOR", "60")),
        "allowed_tools": ["write_mcp_tool", "run_sandbox_tests", "generate_pydantic_schema", "compile_validator"],
        "escalation_threshold": 7.0,
        "temperature": 0.2,
        "criticality": "HIGH",
    },
    "reviewer": {
        "role_name": "Harness & Spec Reviewer",
        "description": "Evaluates MCP tool compliance, schema strictness, docstring quality, context pollution & error handling.",
        "preferred_model": MODEL_REVIEWER_PREFERRED,
        "fallback_model": MODEL_REVIEWER_FALLBACK,
        "escalation_model": "qwen3.5-122b",
        "token_limit": int(os.getenv("MAX_TOKENS_REVIEWER", "3000")),
        "timeout_sec": int(os.getenv("TIMEOUT_REVIEWER", "45")),
        "allowed_tools": ["audit_schema_types", "verify_mcp_spec", "check_context_efficiency", "test_hallucination_resistance"],
        "escalation_threshold": 8.0,
        "temperature": 0.1,
        "criticality": "CRITICAL",
    },
    "report_writer": {
        "role_name": "Harness Report & Doc Synthesizer",
        "description": "Synthesizes comprehensive Agent Tool Harness documentation, tool registry spec, and telemetry benchmark.",
        "preferred_model": MODEL_REPORT_WRITER_PREFERRED,
        "fallback_model": MODEL_REPORT_WRITER_FALLBACK,
        "escalation_model": "GLM-5.2",
        "token_limit": int(os.getenv("MAX_TOKENS_REPORT_WRITER", "3500")),
        "timeout_sec": int(os.getenv("TIMEOUT_REPORT_WRITER", "40")),
        "allowed_tools": ["compile_harness_doc", "generate_benchmark_table", "export_tool_manifest"],
        "escalation_threshold": 6.0,
        "temperature": 0.2,
        "criticality": "LOW",
    },
    "budget_controller": {
        "role_name": "Active Budget Controller",
        "description": "Monitors token consumption per sub-agent, checks residual pipeline budget, triggers dynamic downscaling.",
        "preferred_model": MODEL_BUDGET_CONTROLLER,
        "fallback_model": MODEL_BUDGET_CONTROLLER,
        "escalation_model": "gpt-oss-20b",
        "token_limit": int(os.getenv("MAX_TOKENS_BUDGET_CONTROLLER", "1000")),
        "timeout_sec": int(os.getenv("TIMEOUT_BUDGET_CONTROLLER", "15")),
        "allowed_tools": ["calculate_token_burn", "enforce_sla", "trigger_downscale", "compute_cost_delta"],
        "escalation_threshold": 5.0,
        "temperature": 0.0,
        "criticality": "HIGH",
    },
}

# Pricing estimation in USD per 1M tokens (Regolo.ai catalog vs Single Frontier baseline)
PRICING_CATALOG: Dict[str, Dict[str, float]] = {
    "brick_routed_regolo": {
        "gpt-oss-20b": {"prompt": 0.15, "completion": 0.30},
        "GLM-5.2": {"prompt": 0.60, "completion": 1.80},
        "Llama-3.3-70B-Instruct": {"prompt": 0.50, "completion": 1.50},
        "qwen3.5-122b": {"prompt": 1.20, "completion": 3.60},
        "brick-complexity-pro": {"prompt": 0.10, "completion": 0.20},
    },
    "single_frontier_baseline": {
        "frontier_omni_pro": {"prompt": 3.00, "completion": 15.00},
    },
}
