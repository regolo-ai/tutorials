#!/usr/bin/env python3
"""Regolo Memory Studio: a local web inspector for akitaonrails/ai-memory + Regolo (stdlib only).

Zero SVG / zero diagram-design code. Inspects:
- `ai-memory`'s real `openai-compat` + `Qwen3-Embedding-8B` configuration for Regolo (`AI_MEMORY_LLM_COMPAT_DISABLE_THINKING=true`)
- Git-backed Markdown `wiki/` pages (`wiki/decisions/*.md`, `wiki/procedures/*.md`, `wiki/handoffs/*.md`) with OKF v0.2 frontmatter
- Claim-Once Cross-Agent Handoff packets (`claude-code -> opencode -> codex`)
- Side-by-side Compare mode (Cold Session Rescan vs Consolidated Wiki + Regolo routing)

  python3 memory_wizard/server.py            # http://127.0.0.1:8210
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
import regolo_memory_tui as T  # noqa: E402

STATIC = HERE / "static"
BASE_URL = "https://api.regolo.ai/v1"
MIME = {".html": "text/html; charset=utf-8", ".png": "image/png", ".woff2": "font/woff2", ".css": "text/css", ".js": "text/javascript"}

NON_CHAT_HINTS = ("embed", "rerank", "whisper", "ocr", "image", "clef", "tts", "speech")
PREFERRED_MODEL = "qwen3.5-122b"
ROUTER_MODEL = "brick-complexity-pro"
PRICES_PATH = HERE / "prices.json"
STAGE_PCT = {"scan": 12, "consolidate": 45, "handoff": 80}

ALLOWED_EXTS = {".yml", ".yaml", ".sql", ".py", ".ts", ".tsx", ".js", ".go", ".rs", ".toml", ".tf", ".proto", ".prisma", ".java", ".json", ".md"}
SECRET_LINE = T.SECRET_LINE
BUILTIN_IGNORE = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next", "output", "target", "vendor", ".idea", ".cache"}
READ_EXTS = {".yml", ".yaml", ".sql", ".py", ".ts", ".tsx", ".js", ".go", ".rs", ".toml", ".tf", ".proto", ".prisma", ".java"}
JSON_OK = {"package.json", "composer.json", "deno.json"}
SKIP_NAMES = {"package-lock.json", "pnpm-lock.yaml", "yarn.lock", "poetry.lock", "Cargo.lock", "benchmark_results.json"}
SENSITIVE_NAME = re.compile(r"(?i)secret|credential|private|\.pem$|id_rsa")
MAX_FILES, MAX_READ, MAX_SIZE = 16, 12000, 400_000

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
        path, text = str(f.get("path", ""))[:200], str(f.get("content", ""))[:20000]
        if not path or Path(path).suffix.lower() not in ALLOWED_EXTS:
            continue
        raw_chars += len(text)
        kept = []
        for line in text.splitlines():
            s = line.strip()
            if compact and (not s or s.startswith(("#", "--", "//"))):
                continue
            kept.append(SECRET_LINE.sub(lambda m: f"{m.group(1)}{m.group(2)}<redacted>", line))
            if compact and len(kept) >= 35:
                break
        body = "\n".join(kept)
        body = body[:1400] if compact else body
        summaries.append({"path": path, "raw_chars": len(text), "compact_chars": len(body)})
        chunks.append(f"=== OBSERVATION SOURCE: {path} ===\n{body}")
    if not summaries:
        raise UserError("No code or config files were found in that folder.")
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


def list_project_files(root: Path) -> tuple[list[str], str]:
    if shutil.which("git"):
        try:
            r = subprocess.run(
                ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                capture_output=True,
                timeout=60,
            )
            names = [p for p in r.stdout.decode("utf-8", "replace").split("\0") if p]
            if r.returncode == 0 and names:
                return names, "git"
        except (subprocess.TimeoutExpired, OSError):
            pass
    found = []
    for rdir, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in BUILTIN_IGNORE and not d.startswith(".")]
        for fname in sorted(files):
            found.append(str((Path(rdir) / fname).relative_to(root)))
    return found, ".gitignore files" if (root / ".gitignore").is_file() else "built-in ignore list"


def inspect_project(raw: str) -> dict:
    root = T.clean_user_path(str(raw), Path.home())
    if not root.is_dir():
        raise UserError(f"Folder not found: {root}")
    names, mode = list_project_files(root)
    eligible = []
    for n in names:
        parts = n.split("/")
        name = parts[-1]
        if any(d in BUILTIN_IGNORE for d in parts[:-1]) or name.startswith(".") or name in SKIP_NAMES or SENSITIVE_NAME.search(name):
            continue
        ext = os.path.splitext(name)[1].lower()
        if not (name in JSON_OK if ext == ".json" else ext in READ_EXTS):
            continue
        fp = root / n
        try:
            if fp.is_symlink() or not fp.is_file() or fp.stat().st_size > MAX_SIZE:
                continue
        except OSError:
            continue
        eligible.append(n)
    picked = sorted(eligible)[:MAX_FILES]
    files = [{"path": n, "content": (root / n).read_text(encoding="utf-8", errors="ignore")[:MAX_READ]} for n in picked]
    return {"root": str(root), "name": root.name, "mode": mode, "total": len(names), "readable": len(eligible), "selected": picked, "files": files}


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


def render_wiki_inspector_html(project: str, pair_label: str, model: str, pages: list[dict], wiki_obj: dict) -> str:
    """Render an authentic Git-Backed Wiki & Claim-Once Handoff Inspector view (NOT an SVG diagram)."""
    cards = []
    for pg in pages:
        badge_col = "#05df72" if pg["kind"] == "handoff" else ("#c4b5fd" if pg["kind"] == "decision" else "#38bdf8")
        cards.append(
            f'<div style="padding:16px 18px;border-radius:12px;background:#090f0d;border:1px solid rgba(148,163,184,0.24);margin-bottom:12px;">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;font-family:ui-monospace,monospace;font-size:12px;">'
            f'<span style="color:#ffffff;font-weight:700;">{html.escape(pg["rel_path"])}</span>'
            f'<span style="padding:2px 9px;border-radius:999px;background:rgba(255,255,255,0.06);color:{badge_col};font-weight:700;">kind: {html.escape(pg["kind"])} · tier: {html.escape(pg["tier"])}</span>'
            f'</div>'
            f'<pre style="margin:0;padding:12px;border-radius:8px;background:#050807;color:#cbd5e1;font-family:ui-monospace,monospace;font-size:12.5px;line-height:1.55;white-space:pre-wrap;">{html.escape(pg["content"].strip())}</pre>'
            f'</div>'
        )
    env_preview = (
        f'LLM_API_KEY="sk-••••••••••••"\n'
        f'AI_MEMORY_LLM_PROVIDER="openai-compat"\n'
        f'AI_MEMORY_LLM_BASE_URL="https://api.regolo.ai/v1"\n'
        f'AI_MEMORY_LLM_MODEL="{html.escape(model)}"\n'
        f'AI_MEMORY_LLM_COMPAT_STRICT="true"\n'
        f'AI_MEMORY_LLM_COMPAT_DISABLE_THINKING="true"\n'
        f'AI_MEMORY_EMBEDDING_PROVIDER="openai-compat"\n'
        f'AI_MEMORY_EMBEDDING_BASE_URL="https://api.regolo.ai/v1"\n'
        f'AI_MEMORY_EMBEDDING_MODEL="Qwen3-Embedding-8B"\n'
        f'AI_MEMORY_EMBEDDING_DIM="4096"\n'
        f'AI_MEMORY_EMBEDDING_QUERY_PREFIX="Instruct: Given a codebase memory query, retrieve relevant wiki pages\\nQuery:"'
    )
    return (
        f'<div style="font-family:\'Space Grotesk\',sans-serif;color:#e2e8f0;padding:8px 4px;">'
        f'<div style="display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:10px;margin-bottom:14px;padding-bottom:12px;border-bottom:1px solid rgba(148,163,184,0.2);">'
        f'<div><span style="font-family:ui-monospace,monospace;font-size:11.5px;color:#58e388;font-weight:700;letter-spacing:0.06em;">GIT-BACKED WIKI &amp; CLAIM-ONCE HANDOFF INSPECTOR · OKF v0.2</span>'
        f'<h3 style="margin:4px 0 0;font-size:20px;color:#ffffff;">&lt;data_dir&gt;/wiki/{html.escape(project)}/ ({len(pages)} Markdown pages compiled)</h3></div>'
        f'<span style="font-family:ui-monospace,monospace;font-size:12px;padding:4px 10px;border-radius:6px;background:rgba(5,223,114,0.12);border:1px solid rgba(5,223,114,0.4);color:#58e388;">Transition: {html.escape(pair_label)}</span>'
        f'</div>'
        + "".join(cards)
        + f'<div style="margin-top:16px;padding:14px 18px;border-radius:12px;background:rgba(5,223,114,0.06);border:1px solid rgba(5,223,114,0.35);">'
        f'<div style="font-family:ui-monospace,monospace;font-size:11.5px;font-weight:700;color:#05df72;margin-bottom:6px;">GENERATED ~/.config/ai-memory/regolo.env (READY FOR AI-MEMORY DAEMON)</div>'
        f'<pre style="margin:0;font-family:ui-monospace,monospace;font-size:12px;line-height:1.55;color:#e2e8f0;white-space:pre-wrap;">{env_preview}</pre>'
        f'</div></div>'
    )


def execute_run(key, model, pcode, project, info, routed: bool, compact: bool, report) -> dict:
    pair = next((t for t in T.HARNESS_PAIRS if t[0] == pcode), T.HARNESS_PAIRS[0])
    code, name, desc = pair
    t_start, stages = time.perf_counter(), []
    report("scan", STAGE_PCT["scan"])
    scan = scan_uploaded(info["files"], project, compact=compact)

    report("consolidate", STAGE_PCT["consolidate"])
    sys1 = (
        "You are the ai-memory consolidation worker (`AI_MEMORY_LLM_COMPAT_DISABLE_THINKING=true`). "
        "Output ONLY valid JSON with {\"decisions\": [{\"slug\": \"...\", \"title\": \"...\", \"summary\": \"...\"}], "
        "\"procedures\": [{\"slug\": \"...\", \"title\": \"...\", \"summary\": \"...\"}], "
        "\"failed_approaches\": [\"...\"], \"open_questions\": [\"...\"]}. At most 2 decisions and 3 procedures."
    )
    usr1 = f"Consolidate observations from '{project}' for {name} ({desc}):\n{scan['skeleton_text']}"
    cons_model, router_fallback = (ROUTER_MODEL if routed else model), False
    try:
        s1 = metered_chat(key, cons_model, sys1, usr1, 900, "Consolidate wiki pages", stages)
    except UserError:
        if cons_model == model:
            raise
        cons_model, router_fallback = model, True
        s1 = metered_chat(key, model, sys1, usr1, 900, "Consolidate wiki pages", stages)

    wiki_obj = T.parse_wiki_json(s1["content"], scan["files"])
    from_model = lambda w: not str(w["decisions"][0].get("slug", "")).startswith("adr-01-auth-and-wal")
    router_retry = False
    if routed and cons_model == ROUTER_MODEL and not from_model(wiki_obj):
        router_retry = True
        s1 = metered_chat(key, model, sys1, usr1, 900, "Consolidate wiki pages (retry)", stages)
        wiki_obj = T.parse_wiki_json(s1["content"], scan["files"])

    report("handoff", STAGE_PCT["handoff"])
    evidence = scan["skeleton_text"][:8000 if compact else 40000]
    s2 = metered_chat(
        key,
        model,
        "You generate a Claim-Once Cross-Agent Handoff packet (`memory_briefing` + `memory_handoff_list`) for `ai-memory run`. "
        "Output ONLY Markdown with sections: '## Where We Left Off', '## Failed Approaches (Do Not Repeat)', "
        "'## Locked Architectural Decisions', and '## Open Questions & Next Steps'.",
        f"Project: {project}\nTransition: {name}\nConsolidated Wiki JSON:\n{json.dumps(wiki_obj)}\n\nScanned files:\n{evidence}",
        1200,
        "Compile claim-once handoff packet",
        stages,
    )
    _, wiki_dir = T.get_project_wiki_dir(Path(info.get("root", Path.cwd())))
    pages = T.write_git_backed_wiki_files(wiki_dir, project, pair, model, wiki_obj, s2["content"], scan["files"])
    inspector_html = render_wiki_inspector_html(project, name, model, pages, wiki_obj)
    markdown = "\n\n".join(f"### `{p['rel_path']}`\n\n{p['content']}" for p in pages)

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
                r = execute_run(key, model, req.get("type_code", "claude-to-opencode"), project, info, routed, compact, reporter(i))
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
        pair = next((t for t in T.HARNESS_PAIRS if t[0] == req.get("type_code")), T.HARNESS_PAIRS[0])
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
                    "type": {"code": pair[0], "name": pair[1]},
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
            return self.json(200, [{"code": c, "name": n, "description": d} for c, n, d in T.HARNESS_PAIRS])
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
    p = argparse.ArgumentParser(description="Regolo Memory Studio")
    p.add_argument("--port", type=int, default=8210)
    p.add_argument("--no-open", action="store_true")
    args = p.parse_args()
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}"
    print(f"Regolo Memory Studio running at {url}")
    if not args.no_open:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
