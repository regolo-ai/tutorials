import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent

REGOLO_API_KEY = os.getenv("REGOLO_API_KEY", "")
REGOLO_BASE_URL = os.getenv("REGOLO_BASE_URL", "https://api.regolo.ai/v1")
REGOLO_MODEL = os.getenv("REGOLO_MODEL", "gpt-oss-120b")
REGOLO_THINKING_EFFORT = os.getenv("REGOLO_THINKING_EFFORT", None)
REGOLO_TIMEOUT = int(os.getenv("REGOLO_TIMEOUT", "60"))
REGOLO_MAX_RETRIES = int(os.getenv("REGOLO_MAX_RETRIES", "2"))
REGOLO_MAX_TOKENS = int(os.getenv("REGOLO_MAX_TOKENS", "4096"))
REGOLO_TEMPERATURE = float(os.getenv("REGOLO_TEMPERATURE", "0.1"))
REPORT_DIR = BASE_DIR / "reports"
BENCHMARK_DIR = BASE_DIR / "benchmark"

for d in [REPORT_DIR, BENCHMARK_DIR]:
    d.mkdir(parents=True, exist_ok=True)
