#!/usr/bin/env python3
"""Regolo Diagram Studio: a local, branded wizard around regolo_diagram_tui.py (stdlib only).

The project is chosen by path (native folder dialog or pasted path) and read by this server, honouring .gitignore.

  python3 diagram_wizard/server.py            # http://127.0.0.1:8200
  python3 diagram_wizard/server.py --port 8300 --no-open

The API key is typed in the browser and kept in memory there. It is sent to this local server on each
request and forwarded to the Regolo API; it is never written to disk and the .env file is never read.
Only a compact skeleton of at most 16 code and config files reaches the model.
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
import regolo_diagram_tui as T  # noqa: E402  (the original tool: scanner, prompts, SVG builders)

STATIC = HERE / "static"
BASE_URL = "https://api.regolo.ai/v1"
MAX_BODY = 4 * 1024 * 1024
MIME = {".html": "text/html; charset=utf-8", ".png": "image/png", ".woff2": "font/woff2",
        ".svg": "image/svg+xml", ".css": "text/css", ".js": "text/javascript"}

# Words in a model id that mean "not a chat model" (the original tool lists exact ids; this also catches new ones).
NON_CHAT_HINTS = ("embed", "rerank", "whisper", "ocr", "image", "clef", "tts", "speech")
PREFERRED_MODEL = "qwen3.5-122b"

SAMPLE_TOPOLOGY = {
    "nodes": [
        {"id": "n0", "label": "API Gateway", "role": "Entry point", "detail": "REST · :443"},
        {"id": "n1", "label": "Auth Service", "role": "Service", "detail": "JWT · OAuth2"},
        {"id": "n2", "label": "Orders Service", "role": "Service", "detail": "REST · :8080"},
        {"id": "n3", "label": "PostgreSQL", "role": "Database", "detail": "primary · :5432"},
        {"id": "n4", "label": "Event Queue", "role": "Queue", "detail": "AMQP · :5672"},
        {"id": "n5", "label": "Worker", "role": "Worker", "detail": "replica=2"},
    ],
    "edges": [
        {"from": "n0", "to": "n1", "protocol": "verify token"},
        {"from": "n0", "to": "n2", "protocol": "POST /orders"},
        {"from": "n2", "to": "n3", "protocol": "SQL"},
        {"from": "n2", "to": "n4", "protocol": "publish"},
        {"from": "n4", "to": "n5", "protocol": "consume"},
    ],
}

ALLOWED_EXTS = {".yml", ".yaml", ".sql", ".py", ".ts", ".tsx", ".js", ".go", ".rs", ".toml", ".tf", ".proto", ".prisma", ".java", ".json"}
SECRET_LINE = re.compile(r"(?i)\b([\w.-]*(?:api[_-]?key|secret|token|passw(?:or)?d|private[_-]?key)[\w.-]*)\b(\s*[:=]\s*)(\S.*)")

JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()


class UserError(Exception):
    """An error whose message is safe and useful to show in the UI."""


# ---------------------------------------------------------------- Regolo calls

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
    ids = [m for m in ids if not any(h in m.lower() for h in NON_CHAT_HINTS)]
    if not ids:
        raise UserError("The key is valid but no chat models are available for this account.")
    return ids


def chat(api_key, model, system, user, max_tokens):
    """call_regolo_chat with a retry for models that do not accept reasoning_effort and one retry after a 429."""
    effort = "none"
    for attempt in range(3):
        try:
            return T.call_regolo_chat(BASE_URL, api_key, model, effort, system, user, max_tokens)
        except urllib.error.HTTPError as exc:
            if exc.code == 400 and effort is not None:
                effort = None
                continue
            if exc.code == 429 and attempt < 2:
                time.sleep(2.5 * (attempt + 1))
                continue
            raise UserError(explain_http_error(exc))
        except TimeoutError:
            raise UserError("The model took too long to answer. Try a smaller model or fewer files.")
    raise UserError("Regolo is busy. Wait a few seconds and try again.")


# ------------------------------------------------------------------- scanning

def scan_uploaded(files: list[dict], project_name: str, compact: bool = True) -> dict:
    """Same output shape as T.scan_project_directory. compact=True keeps a skeleton (no comments, 35 lines, 1400 chars per
    file); compact=False keeps the whole text we read, for the uncompressed baseline. Secret values are redacted either way."""
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
        chunks.append(f"=== FILE: {path} ===\n{body}")
    if not summaries:
        raise UserError("No code or config files were found in that folder.")
    skeleton = "\n\n".join(chunks)
    return {"project_dir": project_name, "files_scanned": len(summaries), "raw_chars": raw_chars,
            "compact_chars": len(skeleton), "files": summaries, "skeleton_text": skeleton,
            "reduction_pct": round(100 * (1 - len(skeleton) / max(raw_chars, 1)), 1)}


# ------------------------------------------------------------- project folder

BUILTIN_IGNORE = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next", "output", "target",
                  "vendor", ".idea", ".cache", "coverage", ".terraform"}
READ_EXTS = {".yml", ".yaml", ".sql", ".py", ".ts", ".tsx", ".js", ".go", ".rs", ".toml", ".tf", ".proto", ".prisma", ".java"}
JSON_OK = {"package.json", "composer.json", "deno.json"}
SKIP_NAMES = {"package-lock.json", "pnpm-lock.yaml", "yarn.lock", "poetry.lock", "Cargo.lock"}
SENSITIVE_NAME = re.compile(r"(?i)secret|credential|private|\.pem$|id_rsa")
MAX_FILES, MAX_READ, MAX_SIZE, MAX_LISTED = 16, 12000, 400_000, 60_000


def glob_to_regex(pat: str) -> str:
    out, i = "", 0
    while i < len(pat):
        c = pat[i]
        if pat.startswith("**/", i):
            out += "(?:.*/)?"; i += 3
        elif pat.startswith("/**", i) and i + 3 == len(pat):
            out += "/.*"; i += 3
        elif pat.startswith("**", i):
            out += ".*"; i += 2
        elif c == "*":
            out += "[^/]*"; i += 1
        elif c == "?":
            out += "[^/]"; i += 1
        elif c == "[" and "]" in pat[i + 1:]:
            j = pat.index("]", i + 1); cls = pat[i + 1:j]; neg = cls.startswith("!")
            out += "[" + ("^" if neg else "") + (cls[1:] if neg else cls).replace("\\", "\\\\") + "]"; i = j + 1
        elif c == "\\" and i + 1 < len(pat):
            out += re.escape(pat[i + 1]); i += 2
        else:
            out += re.escape(c); i += 1
    return out


def parse_gitignore(path: Path) -> list[tuple[re.Pattern, bool, bool]]:
    """-> [(regex over the path relative to this .gitignore's folder, negated, dir_only)], last match wins."""
    rules = []
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return rules
    for line in lines:
        line = line.rstrip("\n").rstrip()
        if not line or line.startswith("#"):
            continue
        neg = line.startswith("!")
        line = line[1:] if neg else line
        if line.startswith("\\#") or line.startswith("\\!"):
            line = line[1:]
        dir_only = line.endswith("/")
        line = line.rstrip("/")
        if not line:
            continue
        anchored = "/" in line
        body = glob_to_regex(line.lstrip("/"))
        rules.append((re.compile(("^" if anchored else "^(?:.*/)?") + body + "$"), neg, dir_only))
    return rules


def walk_respecting_gitignore(root: Path) -> list[str]:
    """Fallback for folders that are not git repos: os.walk that honours every .gitignore from root downwards."""
    found: list[str] = []

    def ignored(rel_parts: tuple, is_dir: bool, stack) -> bool:
        verdict = False
        for base_depth, rules in stack:  # outer .gitignore first, inner ones override
            rel = "/".join(rel_parts[base_depth:])
            for rx, neg, dir_only in rules:
                if (not dir_only or is_dir) and rx.match(rel):
                    verdict = not neg
        return verdict

    def rec(d: Path, parts: tuple, stack):
        gi = d / ".gitignore"
        if gi.is_file():
            stack = stack + [(len(parts), parse_gitignore(gi))]
        try:
            entries = sorted(os.scandir(d), key=lambda e: e.name)
        except OSError:
            return
        for e in entries:
            if len(found) > MAX_LISTED:
                return
            rp = parts + (e.name,)
            if e.is_symlink():
                continue
            if e.is_dir(follow_symlinks=False):
                if e.name not in BUILTIN_IGNORE and not ignored(rp, True, stack):
                    rec(Path(e.path), rp, stack)
            elif not ignored(rp, False, stack):
                found.append("/".join(rp))

    rec(root, (), [])
    return found


def list_project_files(root: Path) -> tuple[list[str], str]:
    """Every file the project's own .gitignore rules do not exclude. Uses git when available (exact rules,
    nested and global ignores), otherwise parses the .gitignore files itself."""
    if shutil.which("git"):
        try:
            r = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                               capture_output=True, timeout=60)
            names = [p for p in r.stdout.decode("utf-8", "replace").split("\0") if p]
            if r.returncode == 0 and names:
                return names, "git"
        except (subprocess.TimeoutExpired, OSError):
            pass
    files = walk_respecting_gitignore(root)
    return files, ".gitignore files" if (root / ".gitignore").is_file() else "built-in ignore list"


def file_score(path: str) -> int:
    p = path.lower(); name = p.rsplit("/", 1)[-1]; depth = p.count("/")
    s = 10 - min(depth, 6)
    if re.search(r"docker-compose|compose\.ya?ml", name): s += 100
    elif name.endswith((".sql", ".proto")) or name == "schema.prisma": s += 90
    elif name.endswith(".tf") or re.search(r"(^|/)(k8s|kubernetes|helm|deploy)/", p): s += 80
    elif re.match(r"(main|app|server|index|routes?|api|urls|settings|config)\.", name): s += 70
    elif name in JSON_OK or name in ("pyproject.toml", "go.mod"): s += 60
    if re.search(r"(test|spec|mock|fixture|__tests__|migrations?/\d)", p): s -= 40
    return s


def resolve_project_dir(raw: str) -> Path:
    if not str(raw).strip():
        raise UserError("Choose a project folder first.")
    cand = T.clean_user_path(str(raw), Path.home())
    if not cand.is_dir():
        raise UserError(f"Folder not found: {cand}")
    if cand == Path(cand.anchor) or cand == Path.home():
        raise UserError("That folder is too broad. Choose a specific project folder.")
    return cand


def inspect_project(raw: str) -> dict:
    root = resolve_project_dir(raw)
    names, mode = list_project_files(root)
    if len(names) > MAX_LISTED:
        raise UserError("That folder has too many files. Choose a specific project folder, not a parent of many projects.")
    eligible = []
    for n in names:
        parts = n.split("/"); name = parts[-1]
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
    picked = sorted(eligible, key=lambda n: (-file_score(n), n))[:MAX_FILES]
    files = [{"path": n, "content": (root / n).read_text(encoding="utf-8", errors="ignore")[:MAX_READ]} for n in picked]
    return {"root": str(root), "name": root.name, "mode": mode, "total": len(names), "readable": len(eligible),
            "selected": picked, "files": files}


def pick_folder() -> dict:
    """Native folder dialog on the machine running this app (the browser cannot reveal real paths)."""
    system = platform.system()
    if system == "Darwin":
        cmd = ["osascript", "-e", 'POSIX path of (choose folder with prompt "Choose the project folder for Regolo Diagram Studio")']
    elif shutil.which("zenity"):
        cmd = ["zenity", "--file-selection", "--directory", "--title=Choose the project folder"]
    else:
        raise UserError("No folder dialog is available on this system. Paste the folder path instead.")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        raise UserError("The folder dialog timed out. Paste the folder path instead.")
    path = r.stdout.strip()
    if r.returncode != 0 or not path:
        return {"path": ""}  # cancelled
    return {"path": path.rstrip("/") or "/"}


# ------------------------------------------------------------------- pipeline

def accept_llm_svg(code: str, svg: str) -> bool:
    """Same acceptance rules as generate_diagram_pipeline: keep the model's SVG only if it followed the layout type."""
    if "<svg" not in svg or "</svg>" not in svg:
        return False
    u = svg.upper()
    return {
        "40": "BEFORE" in u and "AFTER" in u,
        "38": "PK" in u or "TABLE" in u,
        "04": svg.count("<line") >= 4,
        "29": "STAGE" in u or "INGEST" in u,
        "35": "SUBNET" in u or "REGION" in u,
    }.get(code, True)


BARE_AMP = re.compile(r"&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)")


def clean_svg(svg: str) -> str:
    """Make the SVG valid standalone XML: the 29 and 35 layouts emit bare '&', and models drop 'auto' heights in."""
    svg = BARE_AMP.sub("&amp;", svg)
    return re.sub(r"""\sheight=(["'])auto\1""", "", svg, count=1)  # invalid SVG length; the CSS sizes it


def extract_svg(text: str) -> str:
    s, e = text.find("<svg"), text.rfind("</svg>")
    block = text[s:e + 6] if s != -1 and e != -1 else ""
    if len(re.findall(r"<(?:rect|circle|polygon|g)\b", block)) >= 4 and len(re.findall(r"<text\b", block)) >= 4:
        return block
    return ""


def mermaid_from(topology: dict) -> str:
    ids, lines = {}, ["flowchart LR"]
    for i, n in enumerate(topology.get("nodes", [])[:8]):
        ids[str(n.get("id", f"n{i}"))] = f"n{i}"
        label = re.sub(r'["\[\]{}()<>|]', " ", str(n.get("label", f"node {i}")))[:40]
        role = re.sub(r'["\[\]{}()<>|]', " ", str(n.get("role", "")))[:30]
        lines.append(f'  n{i}["{label}<br/><i>{role}</i>"]')
    for ed in topology.get("edges", []):
        a, b = ids.get(str(ed.get("from"))), ids.get(str(ed.get("to")))
        if a and b:
            proto = re.sub(r'["|]', " ", str(ed.get("protocol", "")))[:30]
            lines.append(f"  {a} -->|{proto}| {b}" if proto.strip() else f"  {a} --> {b}")
    return "\n".join(lines)


def fallback_kb_body(topology: dict) -> str:
    rows = ["| Component | Role | Detail |", "|---|---|---|"]
    for n in topology.get("nodes", []):
        rows.append(f"| {n.get('label','')} | {n.get('role','')} | {n.get('detail','')} |")
    edges = [f"- `{e.get('from')}` -> `{e.get('to')}`: {e.get('protocol','')}" for e in topology.get("edges", [])]
    return "## Components\n\n" + "\n".join(rows) + "\n\n## Relationships\n\n" + ("\n".join(edges) or "- Not determined from the scanned files.")


ROUTER_MODEL = "brick-complexity-pro"
PRICES_PATH = HERE / "prices.json"
STAGE_PCT = {"scan": 8, "topology": 18, "diagram": 38, "markdown": 78}


def load_prices() -> dict:
    try:
        return json.loads(PRICES_PATH.read_text(encoding="utf-8"))["models"]
    except (OSError, ValueError, KeyError):
        return {}


def cost_eur(model: str, prompt_tokens: int, completion_tokens: int, prices: dict | None = None) -> float | None:
    p = (load_prices() if prices is None else prices).get(model)
    return None if not p else (prompt_tokens * p["in"] + completion_tokens * p["out"]) / 1e6


def metered_chat(key, model, system, user, max_tokens, label, stages):
    r = chat(key, model, system, user, max_tokens)
    stages.append({"stage": label, "model": model, "prompt_tokens": r["prompt_tokens"], "completion_tokens": r["completion_tokens"],
                   "latency_s": r["latency_s"], "cost_eur": cost_eur(model, r["prompt_tokens"], r["completion_tokens"])})
    return r


def totals_of(stages: list[dict], wall_s: float) -> dict:
    pt, ct = sum(x["prompt_tokens"] for x in stages), sum(x["completion_tokens"] for x in stages)
    costs = [x["cost_eur"] for x in stages]
    return {"prompt_tokens": pt, "completion_tokens": ct, "total_tokens": pt + ct,
            "latency_s": round(sum(x["latency_s"] for x in stages), 2), "wall_s": round(wall_s, 2),
            "cost_eur": None if any(c is None for c in costs) else round(sum(costs), 6),
            "unpriced_models": sorted({x["model"] for x in stages if x["cost_eur"] is None})}


def execute_run(key, model, tcode, project, info, routed: bool, compact: bool, report) -> dict:
    """One complete diagram run. routed: topology extraction goes to the Regolo router model, drawing and write-up to `model`.
    compact: send the compressed skeleton (True) or the files as read (False, the uncompressed baseline)."""
    code, name, desc = next(t for t in T.DIAGRAM_TYPES if t[0] == tcode)
    t_start, stages = time.perf_counter(), []
    report("scan", STAGE_PCT["scan"])
    scan = scan_uploaded(info["files"], project, compact=compact)

    report("topology", STAGE_PCT["topology"])
    sys1 = ('You are a fast repository topology extractor. Output ONLY a valid JSON object with {"nodes": [{"id": "...", "label": "...", '
            '"role": "...", "detail": "..."}], "edges": [{"from": "...", "to": "...", "protocol": "..."}]}. '
            'Use ids n0, n1, n2 and so on. At most 6 nodes and 8 edges. Each detail at most 10 words.')
    usr1 = f"Extract 5 to 6 elements specifically tailored for Diagram Type {code}: {name} ({desc}) from:\n{scan['skeleton_text']}"
    topo_model, router_fallback = (ROUTER_MODEL if routed else model), False
    try:
        s1 = metered_chat(key, topo_model, sys1, usr1, 900, "Extract components", stages)
    except UserError:
        if topo_model == model:
            raise
        topo_model, router_fallback = model, True  # router not available for this key: fall back to the chosen model
        s1 = metered_chat(key, model, sys1, usr1, 900, "Extract components", stages)
    topology = T.parse_topology_json(s1["content"], scan["files"])
    from_model = lambda t: t["nodes"][0].get("id") != "n0" or not t["nodes"][0].get("detail", "").endswith("chars")
    router_retry = False
    if routed and topo_model == ROUTER_MODEL and not from_model(topology):
        router_retry = True  # the router's JSON was unusable (truncated or malformed): redo this one step on the chosen model
        s1 = metered_chat(key, model, sys1, usr1, 900, "Extract components (retry)", stages)
        topology = T.parse_topology_json(s1["content"], scan["files"])
    topology_from_model = from_model(topology)

    # The knowledge base needs only the topology and the evidence, not the SVG, so it runs while the diagram is drawn.
    evidence = scan["skeleton_text"][:9000 if compact else 40000]
    kb_box = {}

    def write_kb():
        try:
            kb_box["r"] = metered_chat(key, model,
                                       "You write knowledge-base documents for AI coding agents. Output ONLY Markdown with these sections: "
                                       "'## Summary' (2-3 sentences), '## Components' (bullet per component: what it does, where it lives), "
                                       "'## Data flow' (numbered steps), '## Conventions and gotchas', '## Where to start when changing things'. "
                                       "State only what the evidence supports; write 'Not determined from the scanned files' otherwise. No preamble.",
                                       f"Project: {project}\nDiagram: {name}\nTopology JSON:\n{json.dumps(topology)}\n\nScanned files:\n{evidence}",
                                       1600, "Write the knowledge base", stages)
        except UserError:
            pass

    kb_thread = threading.Thread(target=write_kb, daemon=True); kb_thread.start()

    report("diagram", STAGE_PCT["diagram"])
    layout = T.type_specific_svg_instructions(code, name)
    s2 = metered_chat(key, model,
                      "You are the diagram-design SVG engine. Do NOT output markdown prose. Output ONLY a complete inline "
                      "<svg viewBox='0 0 960 520' width='100%' height='auto' xmlns='http://www.w3.org/2000/svg'>...</svg> "
                      f"snapped to a 4px grid. Dark background (#050807), Regolo emerald (#05df72), cyan (#38bdf8), slate (#64748b). {layout}",
                      f"Render Diagram Type {code} ({name}) for project '{project}'. Follow this exact structural layout: {layout}\nTopology data:\n{json.dumps(topology)}",
                      2800, "Draw the diagram", stages)
    svg = extract_svg(s2["content"]) if accept_llm_svg(code, s2["content"]) else ""
    svg_source = "model" if svg else "fallback"
    if not svg:
        svg = T.render_4px_grid_svg_from_topology(topology, project, code, name, scan["files"])
    svg = clean_svg(svg)
    page = T.wrap_regolo_editorial_svg(svg, topology, scan["files"], project, code, name, model)

    report("markdown", STAGE_PCT["markdown"])
    kb_thread.join()
    body, kb_source = "", "fallback"
    if "r" in kb_box and len(kb_box["r"]["content"]) > 200 and "##" in kb_box["r"]["content"]:
        body, kb_source = kb_box["r"]["content"].strip(), "model"
    if not body:
        body = fallback_kb_body(topology)
    order = ["Extract components", "Extract components (retry)", "Draw the diagram", "Write the knowledge base"]
    stages.sort(key=lambda x: order.index(x["stage"]))
    markdown = (
        f"---\nproject: {project}\ndiagram: {name} (type {code})\ngenerated: {date.today().isoformat()}\n"
        f"model: {model}\nsource: Regolo Diagram Studio\n---\n\n# {project}: {name}\n\n"
        f"> Knowledge base for AI agents. Built from {scan['files_scanned']} scanned files. Verify against the code before relying on details.\n\n"
        f"## Diagram (Mermaid)\n\n```mermaid\n{mermaid_from(topology)}\n```\n\n{body}\n\n"
        "## Scanned files\n\n" + "\n".join(f"- `{f['path']}`" for f in scan["files"]) + "\n")
    return {"svg": svg, "html": page, "markdown": markdown, "svg_source": svg_source, "kb_source": kb_source,
            "topology_source": "model" if topology_from_model else "fallback", "router_fallback": router_fallback, "router_retry": router_retry,
            "routed": routed, "compact": compact, "stages": stages, "totals": totals_of(stages, time.perf_counter() - t_start),
            "scan": {"files": scan["files_scanned"], "raw_chars": scan["raw_chars"], "sent_chars": len(scan["skeleton_text"]),
                     "reduction_pct": scan["reduction_pct"]}}


def pct_change(base, new):
    return None if not base or new is None else round(100 * (new - base) / base, 1)


def run_job(job_id: str, req: dict) -> None:
    job = JOBS[job_id]
    mode = req.get("mode", "routed")
    plans = {"routed": [("Optimized", True, True)], "single": [("Single model", False, True)],
             "compare": [("Baseline", False, False), ("Optimized", True, True)]}[mode]
    progress = [{"stage": "scan", "pct": 2} for _ in plans]

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
            except Exception as exc:  # reported once below
                errors.append(exc)

        threads = [threading.Thread(target=work, args=(i, *p), daemon=True) for i, p in enumerate(plans)]
        [t.start() for t in threads]; [t.join() for t in threads]
        if errors:
            raise errors[0]
        compare = None
        if mode == "compare":
            a, d = results[0]["totals"], results[1]["totals"]
            compare = {"prompt_tokens_pct": pct_change(a["prompt_tokens"], d["prompt_tokens"]), "total_tokens_pct": pct_change(a["total_tokens"], d["total_tokens"]),
                       "wall_pct": pct_change(a["wall_s"], d["wall_s"]), "cost_pct": pct_change(a["cost_eur"], d["cost_eur"])}
        code, name, _ = next(t for t in T.DIAGRAM_TYPES if t[0] == req["type_code"])
        with JOBS_LOCK:
            job.update(status="done", stage="done", progress=100, result={
                "project": project, "scope": {"mode": info["mode"], "total": info["total"]}, "mode": mode, "model": model,
                "router": ROUTER_MODEL, "type": {"code": code, "name": name}, "runs": results, "compare": compare,
                "prices": {k: v for k, v in load_prices().items() if k in {model, ROUTER_MODEL}}})
    except UserError as exc:
        with JOBS_LOCK:
            job.update(status="error", error=str(exc))
    except Exception as exc:  # unexpected: report without the traceback
        with JOBS_LOCK:
            job.update(status="error", error=f"Unexpected error: {type(exc).__name__}: {str(exc)[:200]}")


# ------------------------------------------------------------------- HTTP

class Handler(BaseHTTPRequestHandler):
    server_version = "RegoloDiagramStudio/1.0"

    def log_message(self, fmt, *args):  # quiet, and never log request bodies
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
        self.send(code, json.dumps(obj).encode(), "application/json")

    def host_ok(self) -> bool:
        """Local app only: reject foreign Host headers (DNS rebinding) and cross-site POSTs."""
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]")
        origin = self.headers.get("Origin")
        if host not in ("127.0.0.1", "localhost"):
            return False
        return not origin or origin.split("://", 1)[-1].rsplit(":", 1)[0] in ("127.0.0.1", "localhost")

    def do_GET(self):
        if not self.host_ok():
            return self.json(403, {"error": "forbidden"})
        path = self.path.split("?")[0]
        if path == "/api/types":
            return self.json(200, [{"code": c, "name": n, "description": d} for c, n, d in T.DIAGRAM_TYPES])
        m = re.fullmatch(r"/api/preview/(\d{2})\.svg", path)
        if m:
            t = next((t for t in T.DIAGRAM_TYPES if t[0] == m.group(1)), None)
            if not t:
                return self.json(404, {"error": "unknown type"})
            svg = clean_svg(T.render_4px_grid_svg_from_topology(SAMPLE_TOPOLOGY, "Example project", t[0], t[1], []))
            return self.send(200, svg.encode(), "image/svg+xml", {"Cache-Control": "max-age=3600"})
        m = re.fullmatch(r"/api/jobs/([0-9a-f]{32})", path)
        if m:
            with JOBS_LOCK:
                job = JOBS.get(m.group(1))
                if not job:
                    return self.json(404, {"error": "unknown job"})
                return self.json(200, {k: v for k, v in job.items() if k != "request"})
        rel = "index.html" if path == "/" else path.lstrip("/").removeprefix("static/")
        f = (STATIC / rel).resolve()
        if STATIC not in f.parents or not f.is_file():
            return self.json(404, {"error": "not found"})
        self.send(200, f.read_bytes(), MIME.get(f.suffix, "application/octet-stream"), {"Cache-Control": "max-age=300"} if f.suffix != ".html" else None)

    def body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY:
            raise UserError("That folder produced too much text. Pick a smaller folder.")
        return json.loads(self.rfile.read(n) or b"{}")

    def do_POST(self):
        try:
            if not self.host_ok() or "application/json" not in (self.headers.get("Content-Type") or ""):
                return self.json(403, {"error": "forbidden"})
            data = self.body()
            if self.path == "/api/pick-folder":
                return self.json(200, pick_folder())
            if self.path == "/api/scan":
                info = inspect_project(data.get("path", ""))
                return self.json(200, {k: info[k] for k in ("root", "name", "mode", "total", "readable", "selected")})
            key = str(data.get("api_key", "")).strip()
            if not key:
                raise UserError("Enter your Regolo API key.")
            if self.path == "/api/models":
                models = list_models(key)
                default = PREFERRED_MODEL if PREFERRED_MODEL in models else models[0]
                return self.json(200, {"models": models, "default": default, "router": ROUTER_MODEL,
                                       "router_available": ROUTER_MODEL in models, "priced": sorted(load_prices())})
            if self.path == "/api/generate":
                if not re.fullmatch(r"[\w.\-/:]{1,80}", str(data.get("model", ""))):
                    raise UserError("Choose a model first.")
                if data.get("type_code") not in {t[0] for t in T.DIAGRAM_TYPES}:
                    raise UserError("Choose a diagram type.")
                resolve_project_dir(data.get("path", ""))
                if data.get("mode", "routed") not in ("routed", "single", "compare"):
                    raise UserError("Choose a run mode.")
                job_id = uuid.uuid4().hex
                JOBS[job_id] = {"status": "running", "stage": "scan", "progress": 2, "started": time.time()}
                threading.Thread(target=run_job, args=(job_id, data), daemon=True).start()
                return self.json(200, {"job_id": job_id})
            return self.json(404, {"error": "not found"})
        except UserError as exc:
            return self.json(400, {"error": str(exc)})
        except json.JSONDecodeError:
            return self.json(400, {"error": "Invalid request."})


def main():
    ap = argparse.ArgumentParser(description="Regolo Diagram Studio")
    ap.add_argument("--port", type=int, default=8200)
    ap.add_argument("--no-open", action="store_true")
    a = ap.parse_args()
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)  # local only
    url = f"http://127.0.0.1:{a.port}/"
    print(f"Regolo Diagram Studio running on {url}  (Ctrl+C to stop)")
    if not a.no_open:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
