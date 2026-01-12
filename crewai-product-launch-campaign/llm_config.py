from crewai import LLM
import os

# Configure Regolo LLM with Qwen3-Coder-30B (as per API key restrictions)
regolo_llm = LLM(
    model="openai/qwen3-coder-30b",
    temperature=0.7,
    base_url=os.getenv("REGOLO_BASE_URL", "https://api.regolo.ai/v1"),
    api_key=os.getenv("REGOLO_API_KEY")
)
