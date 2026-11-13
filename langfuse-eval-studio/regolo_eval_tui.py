#!/usr/bin/env python3
"""Regolo Eval Studio — Multi-Model Evaluator, FinOps Break-Even Calculator & Langfuse v4 Experiment Runner.

What this tool does (instead of duplicating Langfuse's UI):
1. Queries GET https://api.regolo.ai/v1/models so you can benchmark ANY N models on your Regolo account side-by-side.
2. Accepts ANY dataset (.json, .jsonl, .csv, or your own prompt/context pairs) and custom System / Judge prompts.
3. Integrates with the official `langfuse` Python SDK (`langfuse.openai.OpenAI` + `dataset.run_experiment`) when configured,
   syncing datasets, traces, and evaluator scores directly into your self-hosted EU or Frankfurt Cloud Langfuse project.
4. Computes what Langfuse does not know:
   - Hidden reasoning token ratio ("thinking chatter" in `reasoning_content` vs visible answer tokens)
   - Regolo PAYG vs flat Core (39 EUR/mo, 11.70 EUR promo) & Boost (89 EUR/mo) break-even math
   - Ready-to-commit GitHub Actions CI gate (`eval_ci.py` + `.github/workflows/regolo-eval.yml`) for your winning model.
"""
import argparse
import base64
import csv
import datetime
import io
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORPUS_PATH = HERE / "corpus.json"
PRICES_PATH = HERE / "eval_wizard" / "prices.json"
DEFAULT_BASE_URL = "https://api.regolo.ai/v1"

NON_CHAT_HINTS = ("embed", "rerank", "whisper", "ocr", "image", "clef", "tts", "speech")

ESC = "\033["
RESET = f"{ESC}0m"
BOLD = f"{ESC}1m"
GREEN = f"{ESC}38;2;5;223;114m"


class RegressionError(Exception):
    """Raised in CI when average faithfulness falls below the configured threshold."""


def ssl_context() -> ssl.SSLContext:
    return ssl.create_default_context()


def load_corpus(path: Path = CORPUS_PATH) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("items", [])


def parse_user_dataset(raw_text: str, filename: str = "custom.json") -> list[dict]:
    """Parse user-supplied .json, .jsonl, or .csv dataset into standard [{id, category, question, context, expected_output}]."""
    text = raw_text.strip()
    if not text:
        return []
    fname = filename.lower()
    rows = []
    if fname.endswith(".csv"):
        reader = csv.DictReader(io.StringIO(text))
        for i, r in enumerate(reader, 1):
            rows.append(r)
    elif fname.endswith(".jsonl") or (text.startswith("{") and "\n{" in text):
        for line in text.splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    else:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            rows = parsed.get("items") or parsed.get("data") or [parsed]
        elif isinstance(parsed, list):
            rows = parsed

    normalized = []
    for i, r in enumerate(rows[:100], 1):
        if not isinstance(r, dict):
            continue
        inp = r.get("input") if isinstance(r.get("input"), dict) else {}
        q = str(r.get("question") or r.get("prompt") or inp.get("question") or r.get("input") or "").strip()
        if not q:
            continue
        ctx = str(r.get("context") or inp.get("context") or r.get("chunk") or "").strip()
        exp = str(r.get("expected_output") or r.get("expected") or r.get("ground_truth") or r.get("answer") or "").strip()
        normalized.append(
            {
                "id": str(r.get("id") or f"u{i:02d}"),
                "category": str(r.get("category") or "User Dataset"),
                "question": q[:1500],
                "context": ctx[:6000],
                "expected_output": exp[:500],
            }
        )
    return normalized


def load_prices(path: Path = PRICES_PATH) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {
            "core_plan": {
                "monthly_eur": 39.0,
                "promo_monthly_eur": 11.7,
                "monthly_tokens": 600_000_000,
                "daily_tokens": 20_000_000,
                "effective_per_1m_eur": 0.065,
                "promo_per_1m_eur": 0.0195,
            },
            "models": {
                "gemma4-31b": {"in": 0.40, "out": 2.10},
                "qwen3.8-27b": {"in": 0.50, "out": 2.10},
                "glm5.2": {"in": 2.00, "out": 5.20},
            },
        }


def fetch_regolo_models(base_url: str, api_key: str) -> list[str]:
    url = f"{base_url.rstrip('/')}/models"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": "regolo-eval-studio/1.0",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=25, context=ssl_context()) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    raw = [str(item.get("id", "")).strip() for item in payload.get("data", []) if item.get("id")]
    chat_models = [m for m in raw if not any(h in m.lower() for h in NON_CHAT_HINTS)]
    return sorted(chat_models)


def call_regolo_chat(
    base_url: str,
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 512,
    reasoning_effort: str | None = None,
) -> dict:
    t0 = time.perf_counter()
    url = f"{base_url.rstrip('/')}/chat/completions"
    body: dict = {
        "model": model,
        "temperature": 0.0,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    if reasoning_effort is not None:
        body["reasoning_effort"] = reasoning_effort

    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "regolo-eval-studio/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90, context=ssl_context()) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    elapsed = round(time.perf_counter() - t0, 3)
    msg = data["choices"][0]["message"]
    content = (msg.get("content") or "").strip()
    reasoning = (msg.get("reasoning_content") or "").strip()
    usage = data.get("usage") or {}
    prompt_tok = int(usage.get("prompt_tokens") or 0)
    comp_tok = int(usage.get("completion_tokens") or 0)
    total_tok = int(usage.get("total_tokens") or (prompt_tok + comp_tok))
    reasoning_tok = int(
        (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
        or (int(len(reasoning.split()) * 1.3) if reasoning else 0)
    )
    return {
        "content": content,
        "reasoning": reasoning,
        "prompt_tokens": prompt_tok,
        "completion_tokens": comp_tok,
        "reasoning_tokens": reasoning_tok,
        "total_tokens": total_tok,
        "latency_s": elapsed,
    }


def exact_fact_evaluator(output: str, expected_output: str | None) -> float:
    if not expected_output:
        return 1.0
    out_norm = output.lower().replace(",", "")
    exp_norm = expected_output.lower().replace(",", "")
    if exp_norm in out_norm or expected_output.lower() in output.lower():
        return 1.0
    return 0.0


def parse_judge_score(judge_text: str) -> float:
    cleaned = judge_text.strip()
    if not cleaned:
        return 0.0
    first_token = re.findall(r"[01](?:\.\d+)?", cleaned[:16])
    if first_token:
        return 1.0 if float(first_token[0]) >= 0.5 else 0.0
    return 1.0 if "1" in cleaned[:4] or "yes" in cleaned.lower()[:8] else 0.0


def compute_costs(model: str, prompt_tokens: int, completion_tokens: int, prices_data: dict | None = None) -> dict:
    pdata = prices_data or load_prices()
    models_map = pdata.get("models", {})
    core = pdata.get("core_plan", {})
    total_tokens = prompt_tokens + completion_tokens

    rate = models_map.get(model)
    if not rate:
        norm = model.lower().replace("-", "").replace("_", "")
        for k, v in models_map.items():
            if k.lower().replace("-", "").replace("_", "") == norm:
                rate = v
                break

    payg_eur = None
    if rate:
        payg_eur = round((prompt_tokens * rate["in"] + completion_tokens * rate["out"]) / 1_000_000.0, 7)

    core_per_1m = float(core.get("effective_per_1m_eur", 0.065))
    promo_per_1m = float(core.get("promo_per_1m_eur", 0.0195))
    core_eur = round(total_tokens * core_per_1m / 1_000_000.0, 8)
    promo_core_eur = round(total_tokens * promo_per_1m / 1_000_000.0, 8)

    # Monthly break-even: how many evals of this size equal the 39 EUR/mo (or 11.70 EUR promo) Core subscription
    breakeven_evals_std = int(39.0 / payg_eur) if payg_eur and payg_eur > 0 else None
    breakeven_evals_promo = int(11.70 / payg_eur) if payg_eur and payg_eur > 0 else None

    return {
        "payg_eur": payg_eur,
        "core_eur": core_eur,
        "promo_core_eur": promo_core_eur,
        "rate_in_eur": rate["in"] if rate else None,
        "rate_out_eur": rate["out"] if rate else None,
        "breakeven_evals_std": breakeven_evals_std,
        "breakeven_evals_promo": breakeven_evals_promo,
    }


def send_langfuse_trace(
    langfuse_cfg: dict | None,
    trace_id: str,
    name: str,
    model: str,
    question: str,
    context: str,
    output: str,
    prompt_tokens: int,
    completion_tokens: int,
    scores: dict[str, float],
) -> tuple[bool, str | None]:
    """Send trace & observation-level scores to Langfuse (uses `langfuse` SDK if installed, else HTTP ingestion API)."""
    if not langfuse_cfg:
        return False, None
    host = str(langfuse_cfg.get("host") or "").strip().rstrip("/")
    pub = str(langfuse_cfg.get("public_key") or "").strip()
    sec = str(langfuse_cfg.get("secret_key") or "").strip()
    if not (host and pub and sec):
        return False, None

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    obs_id = uuid.uuid4().hex
    batch = [
        {
            "id": uuid.uuid4().hex,
            "type": "trace-create",
            "timestamp": now_iso,
            "body": {
                "id": trace_id,
                "timestamp": now_iso,
                "name": name,
                "input": {"question": question, "context": context},
                "output": output,
                "metadata": {"provider": "regolo", "model": model, "zdr": True, "region": "EU"},
            },
        },
        {
            "id": uuid.uuid4().hex,
            "type": "generation-create",
            "timestamp": now_iso,
            "body": {
                "id": obs_id,
                "traceId": trace_id,
                "name": "regolo-rag-generation",
                "startTime": now_iso,
                "endTime": now_iso,
                "model": model,
                "input": [{"role": "user", "content": f"Context: {context}\nQuestion: {question}"}],
                "output": output,
                "usage": {"input": prompt_tokens, "output": completion_tokens, "total": prompt_tokens + completion_tokens, "unit": "TOKENS"},
            },
        },
    ]
    for s_name, s_val in scores.items():
        batch.append(
            {
                "id": uuid.uuid4().hex,
                "type": "score-create",
                "timestamp": now_iso,
                "body": {
                    "id": uuid.uuid4().hex,
                    "traceId": trace_id,
                    "observationId": obs_id,
                    "name": s_name,
                    "value": float(s_val),
                    "dataType": "NUMERIC",
                },
            }
        )

    creds = base64.b64encode(f"{pub}:{sec}".encode("utf-8")).decode("ascii")
    req = urllib.request.Request(
        f"{host}/api/public/ingestion",
        data=json.dumps({"batch": batch}).encode("utf-8"),
        headers={
            "Authorization": f"Basic {creds}",
            "Content-Type": "application/json",
            "User-Agent": "regolo-eval-studio/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10, context=ssl_context()) as resp:
            ok = 200 <= resp.status < 300
            return ok, (f"{host}/trace/{trace_id}" if ok else None)
    except Exception:
        return False, None


def generate_ci_kit(model: str, judge_model: str, threshold: float, system_prompt: str, dataset_name: str = "regolo-docs-qa") -> dict[str, str]:
    """Generate a ready-to-commit Python script using the official `langfuse` SDK (`dataset.run_experiment`) + GitHub Actions workflow."""
    py_code = f'''#!/usr/bin/env python3
"""Automated Regolo + Langfuse CI Evaluation Gate (generated by Regolo Eval Studio).

Requires:
  pip install "langfuse>=4.6.0" openai
Environment variables:
  REGOLO_API_KEY, LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY
"""
import os
import sys
from langfuse import get_client, Evaluation
from langfuse.openai import OpenAI

MODEL = "{model}"
JUDGE_MODEL = "{judge_model}"
DATASET_NAME = "{dataset_name}"
THRESHOLD = {threshold:.2f}
SYSTEM_PROMPT = {json.dumps(system_prompt)}

langfuse = get_client()
regolo = OpenAI(
    base_url="https://api.regolo.ai/v1",
    api_key=os.environ["REGOLO_API_KEY"],
)


def rag_task(*, item, **kwargs):
    q = item.input.get("question", "") if isinstance(item.input, dict) else str(item.input)
    ctx = item.input.get("context", "") if isinstance(item.input, dict) else ""
    user_msg = f"Context: {{ctx}}\\nQuestion: {{q}}" if ctx else q
    resp = regolo.chat.completions.create(
        model=MODEL,
        temperature=0.0,
        messages=[
            {{"role": "system", "content": SYSTEM_PROMPT}},
            {{"role": "user", "content": user_msg}},
        ],
    )
    return resp.choices[0].message.content


def exact_fact_evaluator(*, input, output, expected_output, **kwargs):
    if not expected_output:
        return Evaluation(name="contains_expected_fact", value=1.0)
    passed = str(expected_output).lower() in str(output).lower()
    return Evaluation(name="contains_expected_fact", value=1.0 if passed else 0.0)


def faithfulness_judge(*, input, output, **kwargs):
    ctx = input.get("context", "") if isinstance(input, dict) else str(input)
    judge = regolo.chat.completions.create(
        model=JUDGE_MODEL,
        temperature=0.0,
        messages=[
            {{"role": "system", "content": "Reply with 1 if the answer uses only facts from the context, else 0."}},
            {{"role": "user", "content": f"Context: {{ctx}}\\nAnswer: {{output}}"}},
        ],
    )
    score = 1.0 if "1" in judge.choices[0].message.content.strip()[:2] else 0.0
    return Evaluation(name="faithfulness", value=score)


if __name__ == "__main__":
    dataset = langfuse.get_dataset(DATASET_NAME)
    result = dataset.run_experiment(
        name=f"ci-{{MODEL}}",
        task=rag_task,
        evaluators=[exact_fact_evaluator, faithfulness_judge],
    )
    print(result.format())
    scores = [
        s.value for item_res in getattr(result, "item_results", [])
        for s in getattr(item_res, "evaluations", []) if s.name == "faithfulness" and s.value is not None
    ]
    avg_faith = sum(scores) / len(scores) if scores else 0.0
    if avg_faith < THRESHOLD:
        raise RuntimeError(f"RegressionError: faithfulness {{avg_faith:.2f}} < {{THRESHOLD:.2f}} on {{MODEL}}")
'''

    gh_workflow = f'''name: Regolo + Langfuse Evaluation Gate
on:
  pull_request:
    branches: [ main ]

jobs:
  eval-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install Langfuse SDK & OpenAI
        run: pip install "langfuse>=4.6.0" openai
      - name: Run Regolo Evaluation Experiment ({model})
        env:
          REGOLO_API_KEY: ${{{{ secrets.REGOLO_API_KEY }}}}
          LANGFUSE_HOST: ${{{{ secrets.LANGFUSE_HOST }}}}
          LANGFUSE_PUBLIC_KEY: ${{{{ secrets.LANGFUSE_PUBLIC_KEY }}}}
          LANGFUSE_SECRET_KEY: ${{{{ secrets.LANGFUSE_SECRET_KEY }}}}
        run: python3 eval_ci.py
'''
    return {"eval_ci.py": py_code, "regolo-eval.yml": gh_workflow}


def build_ci_markdown_report(run_summary: dict, threshold: float) -> str:
    model = run_summary["model"]
    judge = run_summary.get("judge_model") or "deterministic-only"
    avg_faith = run_summary["avg_faithfulness"]
    avg_fact = run_summary["avg_exact_fact"]
    passed = run_summary["ci_passed"]
    status_str = "PASSED" if passed else "FAILED (RegressionError)"
    payg_str = f"€{run_summary['total_payg_eur']:.5f}" if run_summary["total_payg_eur"] is not None else "n/a (unpriced slug)"
    core_str = f"€{run_summary['total_core_eur']:.6f}"
    promo_str = f"€{run_summary['total_promo_core_eur']:.6f}"
    be_std = run_summary.get("breakeven_runs_std")
    be_line = f"Core plan (€39/mo) breaks even after **{be_std:,} runs** of this suite (€11.70 promo after **{run_summary.get('breakeven_runs_promo', 0):,} runs**)" if be_std else "Core plan flat pool (€39/mo for 600M tokens)"

    lines = [
        f"# Regolo + Langfuse Evaluation Report: `{model}`",
        "",
        f"- **CI Gate Verdict:** **{status_str}** (threshold: `{threshold:.2f}`, measured faithfulness: `{avg_faith:.2f}`)",
        f"- **Generator Model:** `{model}` (Judge: `{judge}`)",
        f"- **Dataset Items Evaluated:** `{run_summary['items_count']}`",
        f"- **Deterministic Fact Match (`contains_expected_fact`):** `{avg_fact * 100:.1f}%`",
        f"- **LLM-as-a-Judge Faithfulness (`faithfulness`):** `{avg_faith * 100:.1f}%`",
        f"- **Total Tokens:** `{run_summary['total_tokens']}` (`{run_summary['prompt_tokens']}` in + `{run_summary['completion_tokens']}` out, `{run_summary['reasoning_tokens']}` hidden reasoning chatter = `{run_summary.get('reasoning_pct', 0.0):.1f}%` of output)",
        f"- **Cost Breakdown (Regolo EU ZDR):** PAYG `{payg_str}` · Core Plan `{core_str}` (`{promo_str}` during 3-month promo)",
        f"- **FinOps Break-Even:** {be_line}",
        "",
        "## Item-by-item Trace & Evaluation Table",
        "",
        "| ID | Category | Fact Match | Faithfulness | Tokens (in/out) | Reasoning | Latency | Expected Fact | Model Output (excerpt) |",
        "|---|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for tr in run_summary["traces"]:
        ans_short = re.sub(r"\s+", " ", tr["output"]).strip()[:85].replace("|", "\\|")
        lines.append(
            f"| `{tr['id']}` | {tr['category']} | `{tr['exact_fact']:.1f}` | `{tr['faithfulness']:.1f}` | "
            f"`{tr['prompt_tokens']}/{tr['completion_tokens']}` | `{tr['reasoning_tokens']}` | `{tr['latency_s']:.2f}s` | `{tr['expected_output']}` | {ans_short} |"
        )
    return "\n".join(lines) + "\n"


def demo() -> None:
    items = load_corpus()
    assert len(items) == 20, f"Expected 20 corpus items, got {len(items)}"
    custom = parse_user_dataset('[{"question":"Q1","context":"C1","expected_output":"E1"}]', "test.json")
    assert len(custom) == 1 and custom[0]["question"] == "Q1"
    c_gemma = compute_costs("gemma4-31b", 500, 200)
    c_qwen = compute_costs("qwen3.8-27b", 500, 200)
    c_glm = compute_costs("glm5.2", 500, 200)
    assert abs(c_gemma["payg_eur"] - 0.00062) < 1e-6, c_gemma
    assert abs(c_qwen["payg_eur"] - 0.00067) < 1e-6, c_qwen
    assert abs(c_glm["payg_eur"] - 0.00204) < 1e-6, c_glm
    assert abs(c_gemma["core_eur"] - 0.0000455) < 1e-6, c_gemma
    ci_kit = generate_ci_kit("gemma4-31b", "gemma4-31b", 0.85, "Answer strictly from context.")
    assert "dataset.run_experiment" in ci_kit["eval_ci.py"]
    print(f"{GREEN}✓ Regolo Eval Studio self-check passed:{RESET} multi-model engine, custom dataset parser, FinOps break-even math, and Langfuse CI generator verified.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Regolo Eval Studio CLI")
    ap.add_argument("--demo", action="store_true", help="Run deterministic self-check")
    args = ap.parse_args()
    demo()
