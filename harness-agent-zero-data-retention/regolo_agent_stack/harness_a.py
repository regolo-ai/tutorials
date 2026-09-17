import time

from .client import RegoloClient
from .config import REGOLO_MODEL

def run_harness_a(task_prompt: str, model: str = None) -> dict:
    client = RegoloClient()
    start = time.time()
    messages = [
        {"role": "system", "content": "You are a coding assistant. Write Python code to solve the task. All code, comments, and docstrings must be strictly in English."},
        {"role": "user", "content": task_prompt},
    ]
    target_model = model or REGOLO_MODEL
    response = client.complete(messages=messages, model=target_model, temperature=0.2)
    msg = response.choices[0].message
    raw = msg.content or ""
    # In case of reasoning models that exhaust token budget before emitting content
    if not raw and hasattr(msg, "reasoning_content") and getattr(msg, "reasoning_content"):
        raw = f"# [REASONING EXHAUSTED - NO CODE PRODUCED]\n# Finish reason: {response.choices[0].finish_reason}"
    code = raw.replace("```python", "").replace("```", "").strip()
    usage = getattr(response, "usage", None)
    return {
        "harness": "Harness A (Baseline)",
        "model": target_model,
        "code": code,
        "turns": 1,
        "prompt_tokens": getattr(usage, "prompt_tokens", 0) if usage else 0,
        "completion_tokens": getattr(usage, "completion_tokens", 0) if usage else 0,
        "total_tokens": getattr(usage, "total_tokens", 0) if usage else 0,
        "latency_sec": round(time.time() - start, 2),
    }
