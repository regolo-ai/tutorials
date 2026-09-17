import re
import time

from .client import RegoloClient
from .config import REGOLO_MODEL

SYSTEM_PROMPT_B = """You are a senior systems engineer on Regolo EU Zero Data Retention infrastructure.
Write robust, thread-safe Python code that passes deterministic unit tests.
All code, comments, docstrings, and scratchpad reasoning must be strictly in English.

Rules:
1. In <scratchpad> tags, reason briefly about edge cases, concurrency invariants, and boundaries in English.
2. In <code> tags, output ONLY the final clean Python code. No markdown fences or conversational filler.
3. Match exact class and method signatures from the specification.
"""

def run_harness_b(task_prompt: str, model: str = None) -> dict:
    client = RegoloClient()
    start = time.time()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_B},
        {"role": "user", "content": f"Task specification:\n{task_prompt}"},
    ]
    target_model = model or REGOLO_MODEL
    response = client.complete(messages=messages, model=target_model, temperature=0.1)
    msg = response.choices[0].message
    content = msg.content or ""
    # Se il modello è un reasoning model e non ha prodotto content finale
    if not content and hasattr(msg, "reasoning_content") and getattr(msg, "reasoning_content"):
        content = f"<code># [REASONING EXHAUSTED - NO CODE PRODUCED]\n# Finish reason: {response.choices[0].finish_reason}</code>"
    match = re.search(r"<code>(.*?)</code>", content, re.DOTALL)
    if match:
        code = match.group(1).strip()
    else:
        code = content.replace("```python", "").replace("```", "").strip()
    usage = getattr(response, "usage", None)
    return {
        "harness": "Harness B (Regolo Optimized)",
        "model": target_model,
        "code": code,
        "turns": 1,
        "prompt_tokens": getattr(usage, "prompt_tokens", 0) if usage else 0,
        "completion_tokens": getattr(usage, "completion_tokens", 0) if usage else 0,
        "total_tokens": getattr(usage, "total_tokens", 0) if usage else 0,
        "latency_sec": round(time.time() - start, 2),
    }
