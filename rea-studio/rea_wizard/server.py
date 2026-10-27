#!/usr/bin/env python3
"""Regolo REA Studio: a local web PoC & Clean-Room Specification Builder for morluto/rea + Regolo (stdlib only).

Zero SVG / zero diagram-design code. Inspects:
- `morluto/rea` static evidence dumps (web HAR captures, Electron ASAR/IPC bundles, Go/Rust/.NET binaries, SQLite snapshots)
- `REA_MCP_INPUT_SCHEMA_PROFILE=compact` and `REA_MCP_OUTPUT_SCHEMA_PROFILE=compact`
- Client-ready Proof-of-Concept (PoC) specifications and API contracts (`poc/evidence-ledger.json` & `poc/poc-spec-*.md`)
- Side-by-side Compare mode (Unfiltered REA Dumps vs Sieved Evidence + Regolo routing)

  python3 rea_wizard/server.py            # http://127.0.0.1:8220
"""
import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import uuid
import webbrowser
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import regolo_rea_tui as T  # noqa: E402

STATIC = HERE / "static"
BASE_URL = "https://api.regolo.ai/v1"
MIME = {".html": "text/html; charset=utf-8", ".png": "image/png", ".woff2": "font/woff2", ".css": "text/css", ".js": "text/javascript"}

NON_CHAT_HINTS = ("embed", "rerank", "whisper", "ocr", "image", "clef", "tts", "speech")
PREFERRED_MODEL = "qwen3.5-122b"
ROUTER_MODEL = "brick-complexity-pro"
PRICES_PATH = HERE / "prices.json"
STAGE_PCT = {"scan": 12, "triage": 45, "reconstruct": 80}

ALLOWED_EXTS = {".json", ".har", ".yml", ".yaml", ".sql", ".py", ".ts", ".js", ".go", ".rs", ".toml"}
BUILTIN_IGNORE = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next", "output"}
SKIP_NAMES = {"benchmark_results.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock"}
SENSITIVE_NAME = re.compile(r"(?i)secret|credential|private|\.pem$|id_rsa")
MAX_FILES, MAX_READ, MAX_SIZE = 16, 25000, 500_000

JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()


class UserError(Exception):
    pass


def list_models(api_key: str) -> list[str]:
    try:
        ids = T.fetch_regolo_models(BASE_URL, api_key)
    except Exception as exc:
        raise UserError(f"Could not reach Regolo: {exc}")
    ids = [m for m in ids if not any(h in m.lower() for h in NON_CHAT_HINTS)]
    if not ids:
        raise UserError("No chat models are available for this account.")
    return ids


def chat(api_key, model, system, user, max_tokens):
    effort = "none"
    for attempt in range(3):
        try:
            return T.call_regolo_chat(BASE_URL, api_key, model, effort, system, user, max_tokens)
        except urllib.error.HTTPError as exc:
            if exc.code == 400 and effort is not None:
                effort = None
                continue
            if exc.code == 429 and attempt < 2:
                time.sleep(2.0 * (attempt + 1))
                continue
            raise UserError(f"Regolo returned HTTP {exc.code}.")
    raise UserError("Regolo is busy.")


def scan_uploaded(files: list[dict], project_name: str, compact: bool = True) -> dict:
    chunks, summaries, raw_chars = [], [], 0
    for f in files[:24]:
        path, text = str(f.get("path", ""))[:200], str(f.get("content", ""))[:30000]
        if not path or Path(path).suffix.lower() not in ALLOWED_EXTS:
            continue
        raw_chars += len(text)
        body = T.sieve_evidence_content(path, text, compact=compact)
        summaries.append({"path": path, "raw_chars": len(text), "compact_chars": len(body)})
        chunks.append(f"=== REA EVIDENCE: {path} ===\n{body}")
    if not summaries:
        raise UserError("No inspectable evidence or code files were found in that folder.")
    skeleton = "\n\n".join(chunks)
    return {
        "project_dir": project_name,
        "files_scanned": len(summaries),
        "raw_chars": raw_chars,
        "compact_chars": len(skeleton),
        "files": summaries,
        "skeleton_text": skeleton,
        "reduction_pct": round(100 * (1 - len(skeleton) / max(raw_chars, 1)), 1),
    }


def inspect_project(raw: str) -> dict:
    root = T.clean_user_path(str(raw), Path.home())
    if not root.is_dir():
        raise UserError(f"Folder not found: {root}")
    corpus_file = root / "corpus.json"
    if corpus_file.is_file():
        cdata = json.loads(corpus_file.read_text(encoding="utf-8"))
        if isinstance(cdata, dict) and "files" in cdata:
            vfiles = cdata["files"]
            return {
                "root": str(root),
                "name": root.name,
                "mode": "rea evidence dumps",
                "total": len(vfiles),
                "readable": len(vfiles),
                "selected": [f["path"] for f in vfiles],
                "files": vfiles,
            }
    eligible = []
    for rdir, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in BUILTIN_IGNORE and not d.startswith(".")]
        for fname in sorted(files):
            if fname in SKIP_NAMES or fname.startswith(".") or SENSITIVE_NAME.search(fname):
                continue
            fp = Path(rdir) / fname
            if fp.suffix.lower() in ALLOWED_EXTS and fp.stat().st_size <= MAX_SIZE:
                eligible.append(str(fp.relative_to(root)))
    picked = sorted(eligible)[:MAX_FILES]
    files = [{"path": n, "content": (root / n).read_text(encoding="utf-8", errors="ignore")[:MAX_READ]} for n in picked]
    return {"root": str(root), "name": root.name, "mode": "git", "total": len(eligible), "readable": len(eligible), "selected": picked, "files": files}


def load_prices() -> dict:
    try:
        return json.loads(PRICES_PATH.read_text(encoding="utf-8"))["models"]
    except Exception:
        return {}


def cost_eur(model: str, prompt_tokens: int, completion_tokens: int, prices: dict | None = None) -> float | None:
    p = (load_prices() if prices is None else prices).get(model)
    return None if not p else (prompt_tokens * p["in"] + completion_tokens * p["out"]) / 1e6


def metered_chat(key, model, system, user, max_tokens, label, stages):
    r = chat(key, model, system, user, max_tokens)
    stages.append({
        "stage": label,
        "model": model,
        "prompt_tokens": r["prompt_tokens"],
        "completion_tokens": r["completion_tokens"],
        "latency_s": r["latency_s"],
        "cost_eur": cost_eur(model, r["prompt_tokens"], r["completion_tokens"]),
    })
    return r


def totals_of(stages: list[dict], wall_s: float) -> dict:
    pt = sum(x["prompt_tokens"] for x in stages)
    ct = sum(x["completion_tokens"] for x in stages)
    costs = [x["cost_eur"] for x in stages]
    return {
        "prompt_tokens": pt,
        "completion_tokens": ct,
        "total_tokens": pt + ct,
        "latency_s": round(sum(x["latency_s"] for x in stages), 2),
        "wall_s": round(wall_s, 2),
        "cost_eur": None if any(c is None for c in costs) else round(sum(costs), 6),
        "unpriced_models": sorted({x["model"] for x in stages if x["cost_eur"] is None}),
    }


def pct_change(base, new):
    return None if not base or new is None else round(100 * (new - base) / base, 1)


def render_poc_inspector_html(project: str, tmpl_name: str, model: str, artifacts: list[dict]) -> str:
    """Render an authentic REA PoC & Clean-Room Specification Inspector view (NOT an SVG diagram)."""
    cards = []
    for art in artifacts:
        badge_col = "#05df72" if "Specification" in art["kind"] else "#fbbf24"
        cards.append(
            f'<div style="padding:16px 18px;border-radius:12px;background:#090f0d;border:1px solid rgba(148,163,184,0.24);margin-bottom:12px;">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;font-family:ui-monospace,monospace;font-size:12px;">'
            f'<span style="color:#ffffff;font-weight:700;">{html.escape(art["rel_path"])}</span>'
            f'<span style="padding:2px 9px;border-radius:999px;background:rgba(255,255,255,0.06);color:{badge_col};font-weight:700;">{html.escape(art["kind"])} · {html.escape(art["tier"])}</span>'
            f'</div>'
            f'<pre style="margin:0;padding:12px;border-radius:8px;background:#050807;color:#cbd5e1;font-family:ui-monospace,monospace;font-size:12.5px;line-height:1.55;white-space:pre-wrap;">{html.escape(art["content"].strip()[:1600])}</pre>'
            f'</div>'
        )
    cli_preview = (
        f'# 1. Inspect target app or HAR session locally with REA (compact MCP schema profile)\n'
        f'export REA_MCP_INPUT_SCHEMA_PROFILE="compact"\n'
        f'export REA_MCP_OUTPUT_SCHEMA_PROFILE="compact"\n'
        f'npx -y rea-agents@latest analyze-javascript-application ./target-app --json > rea-evidence.json\n'
        f'# Or build an interactive agent environment from a recorded browser HAR session:\n'
        f'rea environment-build ./session.har ./client-poc-env --name client-poc --json'
    )
    return (
        f'<div style="font-family:\'Space Grotesk\',sans-serif;color:#e2e8f0;padding:8px 4px;">'
        f'<div style="display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:10px;margin-bottom:14px;padding-bottom:12px;border-bottom:1px solid rgba(148,163,184,0.2);">'
        f'<div><span style="font-family:ui-monospace,monospace;font-size:11.5px;color:#58e388;font-weight:700;letter-spacing:0.06em;">REA EVIDENCE SIEVE &amp; CLIENT POC BUILDER · EU ZERO RETENTION</span>'
        f'<h3 style="margin:4px 0 0;font-size:20px;color:#ffffff;">output/{html.escape(project)}/poc/ ({len(artifacts)} PoC deliverables generated)</h3></div>'
        f'<span style="font-family:ui-monospace,monospace;font-size:12px;padding:4px 10px;border-radius:6px;background:rgba(5,223,114,0.12);border:1px solid rgba(5,223,114,0.4);color:#58e388;">Workflow: {html.escape(tmpl_name)}</span>'
        f'</div>'
        + "".join(cards)
        + f'<div style="margin-top:16px;padding:14px 18px;border-radius:12px;background:rgba(5,223,114,0.06);border:1px solid rgba(5,223,114,0.35);">'
        f'<div style="font-family:ui-monospace,monospace;font-size:11.5px;font-weight:700;color:#05df72;margin-bottom:6px;">UPSTREAM REA CLI &amp; COMPACT MCP PROFILE COMMANDS</div>'
        f'<pre style="margin:0;font-family:ui-monospace,monospace;font-size:12px;line-height:1.55;color:#e2e8f0;white-space:pre-wrap;">{cli_preview}</pre>'
        f'</div></div>'
    )


def execute_run(key, model, tcode, project, info, routed: bool, compact: bool, report) -> dict:
    tmpl = next((t for t in T.POC_TEMPLATES if t[0] == tcode), T.POC_TEMPLATES[0])
    code, name, desc = tmpl
    t_start, stages = time.perf_counter(), []
    report("scan", STAGE_PCT["scan"])
    scan = scan_uploaded(info["files"], project, compact=compact)

    report("triage", STAGE_PCT["triage"])
    sys1 = (
        'You are a fast reverse-engineering evidence triage engine. Output ONLY a valid JSON object '
        '{"evidence": [{"symbol": "...", "surface": "...", "contract": "..."}], '
        '"poc_endpoints": [{"route": "...", "purpose": "..."}]}. At most 4 evidence items and 3 PoC routes.'
    )
    usr1 = f"Isolate critical IPC channels, API payloads, crypto routines, and SQLite tables for '{name}' ({desc}) from:\n{scan['skeleton_text']}"
    tri_model, router_fallback = (ROUTER_MODEL if routed else model), False
    try:
        s1 = metered_chat(key, tri_model, sys1, usr1, 900, "Triage REA evidence dump", stages)
    except UserError:
        if tri_model == model:
            raise
        tri_model, router_fallback = model, True
        s1 = metered_chat(key, model, sys1, usr1, 900, "Triage REA evidence dump", stages)

    rea_obj = T.parse_rea_json(s1["content"], scan["files"])
    from_model = lambda r: not str(r["evidence"][0].get("symbol", "")).startswith("ipc:sync:flush_offline_queue ->")
    router_retry = False
    if routed and tri_model == ROUTER_MODEL and not from_model(rea_obj):
        router_retry = True
        s1 = metered_chat(key, model, sys1, usr1, 900, "Triage REA evidence dump (retry)", stages)
        rea_obj = T.parse_rea_json(s1["content"], scan["files"])

    report("reconstruct", STAGE_PCT["reconstruct"])
    evidence = scan["skeleton_text"][:8000 if compact else 40000]
    s2 = metered_chat(
        key,
        model,
        "You write client-ready Proof-of-Concept (PoC) specifications from static REA evidence for software agencies and dev teams. "
        "Output ONLY Markdown with sections: '## Extracted Feature & Evidence Summary', '## Critical IPC / API / Database Contracts', "
        "'## Clean-Room PoC Architecture', and '## Fast-Track Implementation Plan'.",
        f"Project: {project}\nPoC Workflow: {name}\nTriaged Evidence JSON:\n{json.dumps(rea_obj)}\n\nEvidence:\n{evidence}",
        1200,
        "Build client PoC specification",
        stages,
    )
    _, poc_dir = T.get_project_poc_dir(Path(info.get("root", Path.cwd())))
    artifacts = T.write_poc_artifacts(poc_dir, project, tmpl, model, rea_obj, s2["content"], scan["files"])
    inspector_html = render_poc_inspector_html(project, name, model, artifacts)
    markdown = "\n\n".join(f"### `{a['rel_path']}`\n\n{a['content']}" for a in artifacts)

    return {
        "svg": inspector_html,
        "html": inspector_html,
        "markdown": markdown,
        "router_fallback": router_fallback,
        "router_retry": router_retry,
        "routed": routed,
        "compact": compact,
        "stages": stages,
        "totals": totals_of(stages, time.perf_counter() - t_start),
        "scan": {
            "files": scan["files_scanned"],
            "raw_chars": scan["raw_chars"],
            "sent_chars": len(scan["skeleton_text"]),
            "reduction_pct": scan["reduction_pct"],
        },
    }


def run_job(job_id: str, req: dict) -> None:
    job = JOBS[job_id]
    mode = req.get("mode", "routed")
    plans = {
        "routed": [("Optimized", True, True)],
        "single": [("Single model", False, True)],
        "compare": [("Baseline", False, False), ("Optimized", True, True)],
    }[mode]
    progress = [{"stage": "scan", "pct": 5} for _ in plans]

    def reporter(i):
        def report(stage_key: str, pct: int):
            with JOBS_LOCK:
                progress[i] = {"stage": stage_key, "pct": pct}
                job["progress"] = round(sum(p["pct"] for p in progress) / len(progress))
                job["stage"] = min((p["stage"] for p in progress), key=lambda k: STAGE_PCT[k])
        return report

    try:
        key, model = req["api_key"], req["model"]
        info = inspect_project(req["path"])
        project = re.sub(r"[^\w .-]", "", info["name"])[:60] or "project"
        results, errors = [None] * len(plans), []

        def work(i, label, routed, compact):
            try:
                r = execute_run(key, model, req.get("type_code", "web-har-to-poc"), project, info, routed, compact, reporter(i))
                r["label"] = label
                results[i] = r
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=work, args=(i, *p), daemon=True) for i, p in enumerate(plans)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        if errors:
            raise errors[0]
        compare = None
        if mode == "compare":
            a, d = results[0]["totals"], results[1]["totals"]
            compare = {
                "prompt_tokens_pct": pct_change(a["prompt_tokens"], d["prompt_tokens"]),
                "total_tokens_pct": pct_change(a["total_tokens"], d["total_tokens"]),
                "wall_pct": pct_change(a["wall_s"], d["wall_s"]),
                "cost_pct": pct_change(a["cost_eur"], d["cost_eur"]),
            }
        tmpl = next((t for t in T.POC_TEMPLATES if t[0] == req.get("type_code")), T.POC_TEMPLATES[0])
        with JOBS_LOCK:
            job.update(
                status="done",
                stage="done",
                progress=100,
                result={
                    "project": project,
                    "scope": {"mode": info["mode"], "total": info["total"]},
                    "mode": mode,
                    "model": model,
                    "router": ROUTER_MODEL,
                    "type": {"code": tmpl[0], "name": tmpl[1]},
                    "runs": results,
                    "compare": compare,
                },
            )
    except Exception as exc:
        with JOBS_LOCK:
            job.update(status="error", error=str(exc)[:200])


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def send(self, code: int, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def json(self, code: int, obj):
        self.send(code, json.dumps(obj).encode(), "application/json")

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/types":
            return self.json(200, [{"code": c, "name": n, "description": d} for c, n, d in T.POC_TEMPLATES])
        m = re.fullmatch(r"/api/jobs/([0-9a-f]{32})", path)
        if m:
            with JOBS_LOCK:
                job = JOBS.get(m.group(1))
                return self.json(200 if job else 404, job or {"error": "unknown job"})
        rel = "index.html" if path == "/" else path.lstrip("/").removeprefix("static/")
        f = (STATIC / rel).resolve()
        if STATIC not in f.parents or not f.is_file():
            return self.json(404, {"error": "not found"})
        self.send(200, f.read_bytes(), MIME.get(f.suffix, "application/octet-stream"))

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(n) or b"{}")
            if self.path == "/api/scan":
                info = inspect_project(data.get("path", ""))
                return self.json(200, {k: info[k] for k in ("root", "name", "mode", "total", "readable", "selected")})
            key = str(data.get("api_key", "")).strip()
            if self.path == "/api/models":
                models = list_models(key)
                default = PREFERRED_MODEL if PREFERRED_MODEL in models else models[0]
                return self.json(200, {"models": models, "default": default, "router": ROUTER_MODEL, "router_available": ROUTER_MODEL in models})
            if self.path == "/api/generate":
                job_id = uuid.uuid4().hex
                JOBS[job_id] = {"status": "running", "stage": "scan", "progress": 5}
                threading.Thread(target=run_job, args=(job_id, data), daemon=True).start()
                return self.json(200, {"job_id": job_id})
            return self.json(404, {"error": "unknown endpoint"})
        except Exception as exc:
            return self.json(400, {"error": str(exc)})


def main():
    p = argparse.ArgumentParser(description="Regolo REA Studio")
    p.add_argument("--port", type=int, default=8220)
    p.add_argument("--no-open", action="store_true")
    args = p.parse_args()
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}"
    print(f"Regolo REA Studio running at {url}")
    if not args.no_open:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
