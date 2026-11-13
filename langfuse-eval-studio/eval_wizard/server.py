#!/usr/bin/env python3
"""Regolo Eval Studio: Multi-Model Benchmark, FinOps Calculator & Langfuse v4 CI Generator (stdlib only).

  python3 eval_wizard/server.py            # http://127.0.0.1:8230
  python3 eval_wizard/server.py --port 8230 --no-open
"""
import argparse
import json
import re
import sys
import threading
import time
import urllib.error
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import regolo_eval_tui as T  # noqa: E402

STATIC = HERE / "static"
BASE_URL = T.DEFAULT_BASE_URL
MAX_BODY = 4 * 1024 * 1024
MIME = {
    ".html": "text/html; charset=utf-8",
    ".png": "image/png",
    ".woff2": "font/woff2",
    ".svg": "image/svg+xml",
    ".css": "text/css",
    ".js": "text/javascript",
}

PREFERRED_MODELS = ("gemma4-31b", "gemma-4-31b", "qwen3.8-27b", "glm5.2", "glm-5.2", "qwen3.5-122b")
JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()


class UserError(Exception):
    """An error whose message is safe and useful to show in the UI."""


def explain_http_error(exc: urllib.error.HTTPError) -> str:
    try:
        detail = json.loads(exc.read().decode("utf-8", "ignore"))
        detail = (detail.get("error") or {}).get("message") or detail.get("detail") or ""
    except Exception:
        detail = ""
    if exc.code in (401, 403):
        return "Regolo rejected this API key. Check that you copied the whole key."
    if exc.code == 429:
        return "Regolo rate limit reached. Wait a few seconds and try again."
    return f"Regolo returned HTTP {exc.code}. {str(detail)[:200]}".strip()


def list_models(api_key: str) -> list[str]:
    try:
        ids = T.fetch_regolo_models(BASE_URL, api_key)
    except urllib.error.HTTPError as exc:
        raise UserError(explain_http_error(exc))
    except Exception as exc:
        raise UserError(f"Could not reach Regolo: {exc}")
    if not ids:
        raise UserError("The key is valid but no chat models are available for this account.")
    return ids


def chat_with_retry(api_key: str, model: str, system: str, user: str, max_tokens: int = 450) -> dict:
    effort = "none"
    for attempt in range(3):
        try:
            return T.call_regolo_chat(BASE_URL, api_key, model, system, user, max_tokens=max_tokens, reasoning_effort=effort)
        except urllib.error.HTTPError as exc:
            if exc.code == 400 and effort is not None:
                effort = None
                continue
            if exc.code == 429 and attempt < 2:
                time.sleep(2.0 * (attempt + 1))
                continue
            raise UserError(explain_http_error(exc))
        except TimeoutError:
            raise UserError(f"Model {model} timed out. Try fewer items or a faster model.")
    raise UserError("Regolo is busy. Wait a few seconds and try again.")


def evaluate_model_on_items(
    api_key: str,
    model: str,
    judge_model: str | None,
    items: list[dict],
    system_prompt: str,
    judge_prompt: str,
    threshold: float,
    langfuse_cfg: dict | None,
    progress_cb,
) -> dict:
    pdata = T.load_prices()
    traces = []
    total_prompt = 0
    total_comp = 0
    total_reasoning = 0
    total_latency = 0.0
    total_payg = 0.0
    any_unpriced = False
    total_core = 0.0
    total_promo = 0.0
    langfuse_sent = 0
    langfuse_urls = []

    sys_rag = system_prompt.strip() or "Answer using only the provided documentation. Be concise and include exact numbers and units."
    sys_judge = judge_prompt.strip() or "Reply with 1 if the answer uses only facts supported by the context, else 0. Output only 1 or 0."

    n = max(len(items), 1)
    for idx, item in enumerate(items):
        progress_cb("generate", int(10 + 55 * (idx / n)))
        q = str(item.get("question", "")).strip()
        ctx = str(item.get("context", "")).strip()
        exp = str(item.get("expected_output", "")).strip()
        item_id = str(item.get("id") or f"q{idx + 1:02d}")
        cat = str(item.get("category") or "Custom")

        user_msg = f"Context: {ctx}\nQuestion: {q}" if ctx else q
        gen = chat_with_retry(api_key, model, sys_rag, user_msg, max_tokens=450)
        output = gen["content"]
        p_tok = gen["prompt_tokens"]
        c_tok = gen["completion_tokens"]
        r_tok = gen["reasoning_tokens"]
        lat = gen["latency_s"]

        fact_score = T.exact_fact_evaluator(output, exp)

        progress_cb("judge", int(65 + 25 * ((idx + 1) / n)))
        judge_p_tok = 0
        judge_c_tok = 0
        if judge_model:
            j_res = chat_with_retry(
                api_key,
                judge_model,
                sys_judge,
                f"Context: {ctx}\nQuestion: {q}\nAnswer: {output}",
                max_tokens=32,
            )
            faith_score = T.parse_judge_score(j_res["content"])
            judge_p_tok = j_res["prompt_tokens"]
            judge_c_tok = j_res["completion_tokens"]
        else:
            faith_score = fact_score

        gen_cost = T.compute_costs(model, p_tok, c_tok, pdata)
        judge_cost = T.compute_costs(judge_model, judge_p_tok, judge_c_tok, pdata) if judge_model else {"payg_eur": 0.0, "core_eur": 0.0, "promo_core_eur": 0.0}

        item_payg = None
        if gen_cost["payg_eur"] is not None and judge_cost["payg_eur"] is not None:
            item_payg = round(gen_cost["payg_eur"] + judge_cost["payg_eur"], 7)
            total_payg += item_payg
        else:
            any_unpriced = True

        item_core = round(gen_cost["core_eur"] + judge_cost["core_eur"], 8)
        item_promo = round(gen_cost["promo_core_eur"] + judge_cost["promo_core_eur"], 8)
        total_core += item_core
        total_promo += item_promo

        total_prompt += p_tok + judge_p_tok
        total_comp += c_tok + judge_c_tok
        total_reasoning += r_tok
        total_latency += lat

        trace_id = uuid.uuid4().hex
        sent, lf_url = T.send_langfuse_trace(
            langfuse_cfg,
            trace_id=trace_id,
            name="regolo-rag-eval",
            model=model,
            question=q,
            context=ctx,
            output=output,
            prompt_tokens=p_tok,
            completion_tokens=c_tok,
            scores={"contains_expected_fact": fact_score, "faithfulness": faith_score},
        )
        if sent:
            langfuse_sent += 1
            if lf_url:
                langfuse_urls.append(lf_url)

        traces.append(
            {
                "id": item_id,
                "trace_id": trace_id,
                "langfuse_url": lf_url,
                "category": cat,
                "question": q,
                "context": ctx,
                "expected_output": exp,
                "output": output,
                "exact_fact": fact_score,
                "faithfulness": faith_score,
                "prompt_tokens": p_tok,
                "completion_tokens": c_tok,
                "reasoning_tokens": r_tok,
                "judge_tokens": judge_p_tok + judge_c_tok,
                "latency_s": lat,
                "payg_eur": item_payg,
                "core_eur": item_core,
                "promo_core_eur": item_promo,
                "langfuse_synced": sent,
            }
        )

    avg_fact = round(sum(t["exact_fact"] for t in traces) / n, 4)
    avg_faith = round(sum(t["faithfulness"] for t in traces) / n, 4)
    ci_passed = avg_faith >= threshold
    payg_final = None if any_unpriced else round(total_payg, 6)
    reasoning_pct = round(100.0 * total_reasoning / max(total_comp, 1), 1)
    breakeven_runs_std = int(39.0 / payg_final) if payg_final and payg_final > 0 else None
    breakeven_runs_promo = int(11.70 / payg_final) if payg_final and payg_final > 0 else None

    ci_kit = T.generate_ci_kit(model, judge_model or model, threshold, sys_rag)

    summary = {
        "model": model,
        "judge_model": judge_model,
        "items_count": len(traces),
        "avg_exact_fact": avg_fact,
        "avg_faithfulness": avg_faith,
        "threshold": threshold,
        "ci_passed": ci_passed,
        "prompt_tokens": total_prompt,
        "completion_tokens": total_comp,
        "reasoning_tokens": total_reasoning,
        "reasoning_pct": reasoning_pct,
        "total_tokens": total_prompt + total_comp,
        "total_latency_s": round(total_latency, 2),
        "avg_latency_s": round(total_latency / n, 2),
        "total_payg_eur": payg_final,
        "total_core_eur": round(total_core, 7),
        "total_promo_core_eur": round(total_promo, 7),
        "breakeven_runs_std": breakeven_runs_std,
        "breakeven_runs_promo": breakeven_runs_promo,
        "langfuse_sent": langfuse_sent,
        "traces": traces,
        "ci_kit": ci_kit,
    }
    summary["markdown_report"] = T.build_ci_markdown_report(summary, threshold)
    return summary


def run_job(job_id: str, req: dict) -> None:
    job = JOBS[job_id]
    try:
        key = str(req.get("api_key") or "").strip()
        # Accept either a list of `models` (multi-model benchmark) or single `model` + `compare_model`
        raw_models = req.get("models")
        if isinstance(raw_models, list) and raw_models:
            models_to_run = [str(m).strip() for m in raw_models if str(m).strip()][:6]
        else:
            m_a = str(req.get("model") or "").strip()
            m_b = str(req.get("compare_model") or "").strip()
            models_to_run = [m_a]
            if req.get("mode") == "compare" and m_b and m_b != m_a:
                models_to_run.append(m_b)

        mode = str(req.get("mode") or ("compare" if len(models_to_run) > 1 else "single"))
        use_judge = bool(req.get("use_judge", True)) and mode != "code_only"
        judge_model = str(req.get("judge_model") or models_to_run[0]).strip() if use_judge else None
        threshold = float(req.get("threshold", 0.85))
        sample_count = int(req.get("sample_count", 5))
        system_prompt = str(req.get("system_prompt") or "")
        judge_prompt = str(req.get("judge_prompt") or "")
        langfuse_cfg = req.get("langfuse") if isinstance(req.get("langfuse"), dict) else None

        # Use uploaded custom dataset if provided, else built-in corpus
        uploaded_ds = req.get("uploaded_dataset")
        if isinstance(uploaded_ds, dict) and str(uploaded_ds.get("content") or "").strip():
            corpus = T.parse_user_dataset(str(uploaded_ds["content"]), str(uploaded_ds.get("filename") or "custom.json"))
            if not corpus:
                raise UserError("Could not parse any {question, context, expected_output} rows from your uploaded file.")
            corpus = corpus[: max(1, min(sample_count, len(corpus)))]
        else:
            corpus = T.load_corpus()[: max(1, min(sample_count, 20))]

        custom_q = req.get("custom_item")
        if isinstance(custom_q, dict) and str(custom_q.get("question") or "").strip():
            corpus = [
                {
                    "id": "custom",
                    "category": "Custom Test",
                    "question": str(custom_q.get("question")).strip()[:1500],
                    "context": str(custom_q.get("context") or "").strip()[:4000],
                    "expected_output": str(custom_q.get("expected_output") or "").strip()[:300],
                }
            ] + corpus

        runs = []
        for idx, m in enumerate(models_to_run):
            def cb(stage: str, pct: int, idx=idx, total_m=len(models_to_run)):
                with JOBS_LOCK:
                    job["stage"] = stage
                    job["progress"] = int((idx * 100 + pct) / total_m)

            res = evaluate_model_on_items(
                key,
                m,
                judge_model,
                corpus,
                system_prompt,
                judge_prompt,
                threshold,
                langfuse_cfg,
                cb,
            )
            runs.append(res)

        with JOBS_LOCK:
            job.update(
                status="done",
                stage="report",
                progress=100,
                result={
                    "mode": mode,
                    "threshold": threshold,
                    "runs": runs,
                    "prices": T.load_prices(),
                },
            )
    except UserError as exc:
        with JOBS_LOCK:
            job.update(status="error", error=str(exc))
    except Exception as exc:
        with JOBS_LOCK:
            job.update(status="error", error=f"Unexpected error: {type(exc).__name__}: {str(exc)[:200]}")


class Handler(BaseHTTPRequestHandler):
    server_version = "RegoloEvalStudio/1.0"

    def log_message(self, fmt, *args):
        pass

    def send(self, code: int, body: bytes, ctype: str, extra: dict | None = None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def json(self, code: int, obj):
        self.send(code, json.dumps(obj).encode("utf-8"), "application/json")

    def host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]")
        origin = self.headers.get("Origin")
        if host not in ("127.0.0.1", "localhost"):
            return False
        return not origin or origin.split("://", 1)[-1].rsplit(":", 1)[0] in ("127.0.0.1", "localhost")

    def do_GET(self):
        if not self.host_ok():
            return self.json(403, {"error": "forbidden"})
        path = self.path.split("?")[0]
        if path == "/api/dataset":
            return self.json(200, {"items": T.load_corpus(), "prices": T.load_prices()})
        m = re.fullmatch(r"/api/jobs/([0-9a-f]{32})", path)
        if m:
            with JOBS_LOCK:
                job = JOBS.get(m.group(1))
                if not job:
                    return self.json(404, {"error": "unknown job"})
                return self.json(200, job)
        rel = "index.html" if path == "/" else path.lstrip("/").removeprefix("static/")
        f = (STATIC / rel).resolve()
        if STATIC not in f.parents or not f.is_file():
            return self.json(404, {"error": "not found"})
        self.send(200, f.read_bytes(), MIME.get(f.suffix, "application/octet-stream"))

    def body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY:
            raise UserError("Request payload too large.")
        return json.loads(self.rfile.read(n) or b"{}")

    def do_POST(self):
        try:
            if not self.host_ok() or "application/json" not in (self.headers.get("Content-Type") or ""):
                return self.json(403, {"error": "forbidden"})
            data = self.body()
            key = str(data.get("api_key", "")).strip()
            if not key:
                raise UserError("Enter your Regolo API key.")
            if self.path == "/api/models":
                models = list_models(key)
                default = next((p for p in PREFERRED_MODELS if p in models), models[0])
                return self.json(200, {"models": models, "default": default, "prices": T.load_prices()})
            if self.path == "/api/evaluate":
                raw_models = data.get("models")
                first_m = str(raw_models[0] if isinstance(raw_models, list) and raw_models else data.get("model", "")).strip()
                if not re.fullmatch(r"[\w.\-/:]{1,80}", first_m):
                    raise UserError("Select at least one model first.")
                job_id = uuid.uuid4().hex
                with JOBS_LOCK:
                    JOBS[job_id] = {"status": "running", "stage": "dataset", "progress": 5, "started": time.time()}
                threading.Thread(target=run_job, args=(job_id, data), daemon=True).start()
                return self.json(200, {"job_id": job_id})
            return self.json(404, {"error": "not found"})
        except UserError as exc:
            return self.json(400, {"error": str(exc)})
        except json.JSONDecodeError:
            return self.json(400, {"error": "Invalid JSON request."})


def main():
    ap = argparse.ArgumentParser(description="Regolo Eval Studio")
    ap.add_argument("--port", type=int, default=8230)
    ap.add_argument("--no-open", action="store_true")
    a = ap.parse_args()
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    url = f"http://127.0.0.1:{a.port}/"
    print(f"Regolo Eval Studio running on {url}  (Ctrl+C to stop)")
    if not a.no_open:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
