"""
src/config.py
-------------
Configuration dataclasses and environment loading.
"""
import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"


def load_env_file() -> None:
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip().replace(" ", "")
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            val = val.strip('"').strip("'")
            if key not in os.environ:
                os.environ[key] = val


@dataclass
class PricingConfig:
    input_cost_per_1k: float = 0.0020
    output_cost_per_1k: float = 0.0060


@dataclass
class Settings:
    base_url: str = "https://api.regolo.ai/v1"
    maker_model: str = "gpt-oss-120b"
    checker_model: str = "gemma4-31b"
    max_iterations: int = 3
    default_input_cost_per_1k: float = 0.0020
    default_output_cost_per_1k: float = 0.0060
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    reranker_model: str = "Qwen/Qwen3-Reranker-4B"
    reranker_endpoint: str = ""  # Regolo rerank endpoint if different from base_url
    use_qdrant: bool = True
    use_reranker: bool = True

    @classmethod
    def from_env(cls) -> "Settings":
        load_env_file()
        return cls(
            base_url=os.environ.get("BASE_URL", "https://api.regolo.ai/v1"),
            maker_model=os.environ.get("REGOLO_MAKER_MODEL", "gpt-oss-120b"),
            checker_model=os.environ.get("REGOLO_CHECKER_MODEL", "gemma4-31b"),
            max_iterations=int(os.environ.get("MAX_ITERATIONS", "3")),
            default_input_cost_per_1k=float(os.environ.get("DEFAULT_INPUT_COST_PER_1K", "0.0020")),
            default_output_cost_per_1k=float(os.environ.get("DEFAULT_OUTPUT_COST_PER_1K", "0.0060")),
            qdrant_url=os.environ.get("QDRANT_URL", "http://localhost:6333"),
            qdrant_api_key=os.environ.get("QDRANT_API_KEY", ""),
            reranker_model=os.environ.get("RERANKER_MODEL", "Qwen/Qwen3-Reranker-4B"),
            reranker_endpoint=os.environ.get("RERANKER_ENDPOINT", ""),
            use_qdrant=os.environ.get("USE_QDRANT", "true").lower() == "true",
            use_reranker=os.environ.get("USE_RERANKER", "true").lower() == "true",
        )
