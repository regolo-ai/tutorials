#!/usr/bin/env python3
"""Regolo Memory Studio: a local web wizard around regolo_memory_tui.py (stdlib only).

  python3 memory_wizard/server.py            # http://127.0.0.1:8210
  python3 memory_wizard/server.py --port 8210 --no-open
"""
import argparse
import json
import os
import platform
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
MAX_BODY = 4 * 1024 * 1024
MIME = {".html": "text/html; charset=utf-8", ".png": "image/png", ".woff2": "font/woff2",
        ".svg": "image/svg+xml", ".css": "text/css", ".js": "text/javascript"}

NON_CHAT_HINTS = ("embed", "rerank", "whisper", "ocr", "image", "clef", "tts", "speech")
PREFERRED_MODEL = "qwen3.5-122b"
ROUTER_MODEL = "brick-complexity-pro"
PRICES_PATH = HERE / "prices.json"
STAGE_PCT = {"scan": 10, "consolidate": 35, "handoff": 72}

SAMPLE_MEMORY = {
    "modules": [
        {"id": "m0", "path": "src/session_auth.py", "role": "Auth Module", "invariant": "Ed25519 · leeway=45s"},
        {"id": "m1", "path": "src/wal_writer.py", "role": "SQLite Store", "invariant": "WAL · sync=NORMAL"},
        {"id": "m2", "path": "src/quota_enforcer.py", "role": "Pool Guard", "invariant": "200M/day -> brick-pro"},
    ]
}

ALLOWED_EXTS = {".yml", ".yaml", ".sql", ".py", ".ts", ".tsx", ".js", ".go", ".rs", ".toml", ".tf", ".proto", ".prisma", ".java", ".json", ".md"}
SECRET_LINE = T.SECRET_LINE
BUILTIN_IGNORE = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next", "output", "target", "vendor", ".idea", ".cache"}
READ_EXTS = {".yml", ".yaml", ".sql", ".py", ".ts", ".tsx", ".js", ".go", ".rs", ".toml", ".tf", ".proto", ".prisma", ".java"}
JSON_OK = {"package.json", "composer.json", "deno.json"}
SKIP_NAMES = {"package-lock.json", "pnpm-lock.yaml", "yarn.lock", "poetry.lock", "Cargo.lock", "benchmark_results.json"}
SENSITIVE_NAME = re.compile(r"(?i)secret|credential|private|\.pem$|id_rsa")
MAX_FILES, MAX_READ, MAX_SIZE, MAX_LISTED = 16, 12000, 400_000, 60_000

JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()


class UserError(Exception):
    pass


def explain_http_error(exc: urllib.error.HTTPError) -> str:
    if exc.code in (401, 403):
        return "Regolo rejected this API key. Check that you copied the whole key."
    if exc.code == 429:
        return "Regolo rate limit reached. Wait a few seconds and try again."
    return f"Regolo returned HTTP {exc.code}."


def list_models(api_key: str) -> list[str]:
    try:
        ids = T.fetch_regolo_models(BASE_URL, api_key)
    except urllib.error.HTTPError as exc:
        raise UserError(explain_http_error(exc))
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
            raise UserError(explain_http_error(exc))
    raise UserError("Regolo is busy. Wait a few seconds and try again.")


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
        chunks.append(f"=== WIKI SOURCE: {path} ===\n{body}")
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
            rel = str((Path(rdir) / fname).relative_to(root))
            found.append(rel)
    return found, ".gitignore files" if (root / ".gitignore").is_file() else "built-in ignore list"


def resolve_project_dir(raw: str) -> Path:
    if not str(raw).strip():
        raise UserError("Choose a project folder first.")
    cand = T.clean_user_path(str(raw), Path.home())
    if not cand.is_dir():
        raise UserError(f"Folder not found: {cand}")
    return cand


def inspect_project(raw: str) -> dict:
    root = resolve_project_dir(raw)
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


def execute_run(key, model, tcode, project, info, routed: bool, compact: bool, report) -> dict:
    code, name, desc = next(t for t in T.HANDOFF_TEMPLATES if t[0] == tcode)
    t_start, stages = time.perf_counter(), []
    report("scan", STAGE_PCT["scan"])
    scan = scan_uploaded(info["files"], project, compact=compact)

    report("consolidate", STAGE_PCT["consolidate"])
    sys1 = (
        'You are a fast codebase memory consolidator. Output ONLY a valid JSON object '
        '{"modules": [{"id": "m0", "path": "...", "role": "...", "invariant": "..."}], '
        '"decisions": [{"id": "d0", "status": "LOCKED", "rule": "..."}]}. At most 6 modules.'
    )
    usr1 = f"Consolidate 5 to 6 modules and invariants for {name} ({desc}) from:\n{scan['skeleton_text']}"
    cons_model, router_fallback = (ROUTER_MODEL if routed else model), False
    try:
        s1 = metered_chat(key, cons_model, sys1, usr1, 900, "Consolidate wiki index", stages)
    except UserError:
        if cons_model == model:
            raise
        cons_model, router_fallback = model, True
        s1 = metered_chat(key, model, sys1, usr1, 900, "Consolidate wiki index", stages)

    mem_obj = T.parse_memory_json(s1["content"], scan["files"])
    from_model = lambda m: not str(m["modules"][0].get("invariant", "")).startswith("Consolidated (")
    router_retry = False
    if routed and cons_model == ROUTER_MODEL and not from_model(mem_obj):
        router_retry = True
        s1 = metered_chat(key, model, sys1, usr1, 900, "Consolidate wiki index (retry)", stages)
        mem_obj = T.parse_memory_json(s1["content"], scan["files"])

    report("handoff", STAGE_PCT["handoff"])
    evidence = scan["skeleton_text"][:8000 if compact else 40000]
    s2 = metered_chat(
        key,
        model,
        "You write Claim-Once Cross-Agent Handoff briefs and git-backed repository wiki pages for coding agents "
        "(OpenCode, Claude Code, Codex). Output ONLY Markdown with sections: '## Handoff Brief', "
        "'## Consolidated Module Wiki', '## Locked Architectural Decisions', and '## Next Agent Action Plan'.",
        f"Project: {project}\nTemplate: {name}\nConsolidated JSON:\n{json.dumps(mem_obj)}\n\nScanned files:\n{evidence}",
        1500,
        "Write cross-agent handoff & wiki",
        stages,
    )
    svg = T.render_memory_handoff_svg(mem_obj, project, code, name, scan["files"])
    markdown = (
        f"---\nproject: {project}\nhandoff_template: {name} (type {code})\ngenerated: {date.today().isoformat()}\n"
        f"model: {model}\nsource: Regolo Memory Studio\n---\n\n# {project}: {name}\n\n"
        f"{s2['content'].strip()}\n\n## Indexed Wiki Sources\n\n"
        + "\n".join(f"- `{f['path']}` ({f['raw_chars']} -> {f['compact_chars']} chars)" for f in scan["files"])
        + "\n"
    )
    return {
        "svg": svg,
        "html": svg,
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
                r = execute_run(key, model, req["type_code"], project, info, routed, compact, reporter(i))
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
        code, name, _ = next(t for t in T.HANDOFF_TEMPLATES if t[0] == req["type_code"])
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
                    "type": {"code": code, "name": name},
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
            return self.json(200, [{"code": c, "name": n, "description": d} for c, n, d in T.HANDOFF_TEMPLATES])
        m = re.fullmatch(r"/api/preview/(\d{2})\.svg", path)
        if m:
            t = next((t for t in T.HANDOFF_TEMPLATES if t[0] == m.group(1)), T.HANDOFF_TEMPLATES[0])
            svg = T.render_memory_handoff_svg(SAMPLE_MEMORY, "Example repo", t[0], t[1], [])
            return self.send(200, svg.encode(), "image/svg+xml")
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
