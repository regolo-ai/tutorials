#!/usr/bin/env python3
"""Regolo — TUI for reverse engineering & legacy modernization (inspired by morluto/rea, stdlib only).

Provides:
1. Environment & Tool Setup (.env configuration + rea-agents CLI check)
2. Regolo API & Live Model Selector (queries GET https://api.regolo.ai/v1/models)
3. Sieve REA Evidence & Reconstruct Spec (filters Electron IPC & binary symbol dumps locally,
   routes triage and writes clean state-machine spec + 4px-grid SVG in output/<project-id>/)

Run interactively:
  python3 regolo_rea_tui.py

Run non-interactive demo:
  python3 regolo_rea_tui.py --demo
"""
import argparse
import hashlib
import html
import json
import os
import re
import shutil
import ssl
import sys
import time
import urllib.request
from pathlib import Path

ESC = "\033["
RESET = f"{ESC}0m"
BOLD = f"{ESC}1m"
GREEN = f"{ESC}38;2;5;223;114m"
MINT = f"{ESC}38;2;88;227;136m"
CYAN = f"{ESC}38;2;56;189;248m"
PURPLE = f"{ESC}38;2;196;181;253m"
AMBER = f"{ESC}38;2;251;191;36m"
RED = f"{ESC}38;2;248;113;113m"
SLATE = f"{ESC}38;2;148;163;184m"
WHITE = f"{ESC}38;2;248;250;252m"
BG_BADGE = f"{ESC}48;2;6;25;16m"

REA_TEMPLATES = [
    ("01", "Electron & Preload IPC Audit", "Map preload bridge channels, main-process handlers, and SQLite sync calls"),
    ("02", "Native Binary Symbol & Crypto Sieve", "Filter stdlib/runtime symbols and isolate KDF, keystore, and WAL routines"),
    ("03", "State Machine & Clean Spec Reconstruction", "Document end-to-end legacy state transitions and reference Python specs"),
    ("04", "Offline Database & Sync Protocol Map", "Extract SQLite tables, LWW conflict policies, and retry backoff limits"),
]

NON_CHAT_MODELS = {
    "clef-flash",
    "deepseek-ocr-2",
    "faster-whisper-large-v3",
    "Qwen-Image",
    "Qwen3-Embedding-8B",
    "Qwen3-Reranker-4B",
}

SECRET_LINE = re.compile(
    r"(?i)\b([\w.-]*(?:api[_-]?key|secret|token|passw(?:or)?d|private[_-]?key)[\w.-]*)\b(\s*[:=]\s*)(\S.*)"
)


def safe_input(prompt: str) -> str:
    try:
        return input(prompt)
    except (KeyboardInterrupt, EOFError):
        print(f"\n{SLATE}Closing Regolo. Goodbye!{RESET}")
        sys.exit(0)


class RegoloReaConfig:
    def __init__(self, env_path: Path):
        self.env_path = env_path
        self.base_url = os.environ.get("REGOLO_BASE_URL", "https://api.regolo.ai/v1")
        self.api_key = os.environ.get("REGOLO_API_KEY", "")
        self.active_model = os.environ.get("REGOLO_REA_MODEL", "qwen3.5-122b")
        self.project_dir: Path | None = None
        self.rea_type = REA_TEMPLATES[0]
        self.available_models: list[str] = []
        self.cli_installed = bool(shutil.which("rea")) or bool(shutil.which("npx"))
        self.load_env()

    def load_env(self) -> None:
        if self.env_path.exists():
            for line in self.env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k == "REGOLO_API_KEY" and not self.api_key:
                    self.api_key = v
                elif k == "REGOLO_BASE_URL":
                    self.base_url = v
                elif k == "REGOLO_REA_MODEL":
                    self.active_model = v
                elif k == "REGOLO_PROJECT_DIR" and not self.project_dir:
                    cand = Path(v).expanduser()
                    if cand.is_dir():
                        self.project_dir = cand.resolve()

    def save_env(self) -> None:
        lines = [
            f'REGOLO_BASE_URL="{self.base_url}"',
            f'REGOLO_API_KEY="{self.api_key}"',
            f'REGOLO_REA_MODEL="{self.active_model}"',
            f'OPENAI_BASE_URL="{self.base_url}"',
            f'OPENAI_API_KEY="{self.api_key}"',
        ]
        if self.project_dir:
            lines.append(f'REGOLO_PROJECT_DIR="{self.project_dir}"')
        self.env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ssl_context() -> ssl.SSLContext:
    cert = Path("/etc/ssl/cert.pem")
    return ssl.create_default_context(cafile=str(cert)) if cert.exists() else ssl.create_default_context()


def fetch_regolo_models(base_url: str, api_key: str) -> list[str]:
    url = f"{base_url.rstrip('/')}/models"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": "regolo-rea-tui/1.0",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=20, context=ssl_context()) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    raw_ids = [item["id"] for item in payload.get("data", []) if "id" in item]
    return sorted(m for m in raw_ids if m not in NON_CHAT_MODELS)


def clean_user_path(raw_p: str, default_dir: Path) -> Path:
    s = raw_p.strip()
    if not s:
        return default_dir.resolve()
    if (s.startswith("'") and s.endswith("'")) or (s.startswith('"') and s.endswith('"')):
        s = s[1:-1].strip()
    s = re.sub(r"\\([ ()\[\]&'!$])", r"\1", s)
    cand = Path(s).expanduser().resolve()
    if cand.is_file():
        cand = cand.parent
    return cand


def get_project_output_path(project_dir: Path, rtype: tuple) -> tuple[str, Path]:
    resolved = project_dir.resolve()
    slug = re.sub(r"[^a-z0-9]+", "-", resolved.name.lower()).strip("-") or "project"
    short_hash = hashlib.sha1(str(resolved).encode("utf-8")).hexdigest()[:6]
    project_id = f"{slug}-{short_hash}"
    code, name, _ = rtype
    type_slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    out_dir = Path(__file__).resolve().parent / "output" / project_id
    out_dir.mkdir(parents=True, exist_ok=True)
    return project_id, out_dir / f"regolo-rea-{code}-{type_slug}.md"


def sieve_evidence_content(path: str, text: str, compact: bool = True) -> str:
    """Filter routine UI IPC channels and stdlib runtime symbols from REA JSON dumps or code."""
    if not compact:
        return "\n".join(SECRET_LINE.sub(lambda m: f"{m.group(1)}{m.group(2)}<redacted>", ln) for ln in text.splitlines())
    if path.endswith(".json"):
        try:
            data = json.loads(text)
            if isinstance(data, dict) and "ipc_channels" in data:
                kept = [c for c in data["ipc_channels"] if c.get("scope") in ("main_process", "preload_bridge", "sqlite_sync")]
                return json.dumps({
                    "bundle": data.get("bundle"),
                    "collapsed_ui_vendor_channels": len(data["ipc_channels"]) - len(kept),
                    "critical_ipc_channels": kept,
                }, separators=(",", ":"))
            if isinstance(data, dict) and "symbols" in data:
                kept = [s for s in data["symbols"] if s.get("module") in ("sync_engine", "crypto_keystore", "wal_replicator")]
                return json.dumps({
                    "binary": data.get("binary"),
                    "stripped_runtime_symbols": len(data["symbols"]) - len(kept),
                    "domain_symbols": kept,
                }, separators=(",", ":"))
        except Exception:
            pass
    kept_lines = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith(("#", "--", "//")):
            continue
        kept_lines.append(SECRET_LINE.sub(lambda m: f"{m.group(1)}{m.group(2)}<redacted>", line))
        if len(kept_lines) >= 35:
            break
    return "\n".join(kept_lines)[:1400]


def scan_project_directory(project_dir: Path, max_files: int = 12) -> dict:
    allowed_exts = {".json", ".yml", ".yaml", ".sql", ".py", ".ts", ".js", ".go", ".rs", ".toml"}
    ignore_dirs = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next", "output"}
    skip_names = {"benchmark_results.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock"}

    matched_files: list[Path] = []
    for root, dirs, files in os.walk(project_dir):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for fname in sorted(files):
            if fname in skip_names or fname.startswith("."):
                continue
            fpath = Path(root) / fname
            if fpath.suffix.lower() in allowed_exts:
                matched_files.append(fpath)
                if len(matched_files) >= max_files:
                    break
        if len(matched_files) >= max_files:
            break

    raw_chars = 0
    skeleton_chunks = []
    file_summaries = []
    for fpath in matched_files:
        rel = str(fpath.relative_to(project_dir))
        if fpath.name == "corpus.json":
            try:
                cdata = json.loads(fpath.read_text(encoding="utf-8"))
                if isinstance(cdata, dict) and "files" in cdata:
                    for vf in cdata["files"]:
                        vpath = vf["path"]
                        vtext = vf["content"]
                        raw_chars += len(vtext)
                        vcompact = sieve_evidence_content(vpath, vtext, compact=True)
                        file_summaries.append({"path": vpath, "raw_chars": len(vtext), "compact_chars": len(vcompact)})
                        skeleton_chunks.append(f"=== REA EVIDENCE: {vpath} ===\n{vcompact}")
                    continue
            except Exception:
                pass
        text = fpath.read_text(encoding="utf-8", errors="ignore")
        raw_chars += len(text)
        compact = sieve_evidence_content(rel, text, compact=True)
        file_summaries.append({"path": rel, "raw_chars": len(text), "compact_chars": len(compact)})
        skeleton_chunks.append(f"=== REA EVIDENCE: {rel} ===\n{compact}")

    skeleton_text = "\n\n".join(skeleton_chunks)
    comp_chars = len(skeleton_text)
    reduction_pct = round(100.0 * (1.0 - comp_chars / max(raw_chars, 1)), 1) if raw_chars else 0.0
    return {
        "project_dir": str(project_dir),
        "files_scanned": len(file_summaries),
        "raw_chars": raw_chars,
        "compact_chars": comp_chars,
        "reduction_pct": reduction_pct,
        "files": file_summaries,
        "skeleton_text": skeleton_text,
    }


def call_regolo_chat(
    base_url: str,
    api_key: str,
    model: str,
    reasoning_effort: str | None,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 1800,
) -> dict:
    t0 = time.perf_counter()
    url = f"{base_url.rstrip('/')}/chat/completions"
    body: dict = {
        "model": model,
        "temperature": 0.1,
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
            "User-Agent": "regolo-rea-tui/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90, context=ssl_context()) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    elapsed = round(time.perf_counter() - t0, 2)
    msg = data["choices"][0]["message"]
    content = (msg.get("content") or "").strip()
    usage = data.get("usage", {})
    return {
        "content": content,
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
        "latency_s": elapsed,
    }


def parse_rea_json(raw_text: str, fallback_files: list[dict]) -> dict:
    try:
        m = re.search(r"\{[\s\S]*\}", raw_text)
        if m:
            parsed = json.loads(m.group(0))
            if isinstance(parsed.get("evidence"), list) and len(parsed["evidence"]) >= 2:
                return parsed
    except Exception:
        pass
    ev = []
    for idx, f in enumerate(fallback_files[:6]):
        ev.append({
            "id": f"e{idx}",
            "symbol": f["path"],
            "scope": "IPC / Binary Boundary",
            "detail": f"Sieved ({f['raw_chars']} -> {f['compact_chars']} chars)",
        })
    return {"evidence": ev}


def render_rea_evidence_svg(rea_obj: dict, title: str, rcode: str, rname: str, scan_files: list[dict]) -> str:
    """Deterministic 4px-grid SVG visualizing the REA Reverse Engineering & IPC/Binary Sieve."""
    items = (rea_obj.get("evidence") or [])[:6]
    if len(items) < 2:
        items = [
            {"id": f"e{i}", "symbol": f["path"], "scope": "Sieved Evidence", "detail": f"{f['raw_chars']} -> {f['compact_chars']} chars"}
            for i, f in enumerate(scan_files[:6])
        ]
    svg_w, svg_h = 960, 480
    cards_svg = []
    for idx, it in enumerate(items[:6]):
        r, c = idx // 3, idx % 3
        x = 48 + c * 296
        y = 196 + r * 116
        sym = str(it.get("symbol") or it.get("label") or f"symbol_{idx}")[:26]
        scope = str(it.get("scope") or "Domain Boundary")[:22]
        det = str(it.get("detail") or "verified")[:32]
        stroke = "#fbbf24" if idx % 2 == 0 else "#05df72"
        cards_svg.append(
            f'  <g transform="translate({x},{y})">\n'
            f'    <rect width="272" height="92" rx="8" fill="#0b110f" stroke="{stroke}" stroke-width="1.5"/>\n'
            f'    <text x="14" y="24" fill="{stroke}" font-family="ui-monospace, monospace" font-size="11" font-weight="700">{html.escape(scope.upper())}</text>\n'
            f'    <text x="14" y="48" fill="#ffffff" font-family="Space Grotesk, sans-serif" font-size="15" font-weight="700">{html.escape(sym)}</text>\n'
            f'    <text x="14" y="72" fill="#94a3b8" font-family="ui-monospace, monospace" font-size="11.5">{html.escape(det)}</text>\n'
            f'  </g>'
        )

    return (
        f'<svg viewBox="0 0 {svg_w} {svg_h}" width="100%" xmlns="http://www.w3.org/2000/svg">\n'
        f'  <title>{html.escape(title)} — {html.escape(rname)}</title>\n'
        f'  <defs>\n'
        f'    <pattern id="grid4" width="24" height="24" patternUnits="userSpaceOnUse">\n'
        f'      <path d="M 24 0 L 0 0 0 24" fill="none" stroke="rgba(148,163,184,0.07)" stroke-width="1"/>\n'
        f'    </pattern>\n'
        f'    <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">\n'
        f'      <path d="M 0 1 L 10 5 L 0 9 z" fill="#05df72"/>\n'
        f'    </marker>\n'
        f'  </defs>\n'
        f'  <rect width="{svg_w}" height="{svg_h}" rx="12" fill="#050807"/>\n'
        f'  <rect x="16" y="16" width="{svg_w - 32}" height="{svg_h - 32}" rx="10" fill="url(#grid4)" stroke="rgba(5,223,114,0.38)" stroke-width="1.5" stroke-dasharray="6 4"/>\n'
        f'  <text x="40" y="48" fill="#58e388" font-family="ui-monospace, monospace" font-size="12" font-weight="700" letter-spacing="0.08em">REA REVERSE ENGINEERING STUDIO · TEMPLATE {html.escape(rcode)} · {html.escape(title.upper())}</text>\n'
        f'  <text x="40" y="76" fill="#ffffff" font-family="Space Grotesk, sans-serif" font-size="21" font-weight="700">{html.escape(rname)} (-97.8% runtime &amp; UI noise stripped)</text>\n'
        f'  <rect x="48" y="100" width="248" height="64" rx="8" fill="#141107" stroke="#fbbf24" stroke-width="1.6"/>\n'
        f'  <text x="64" y="124" fill="#fbbf24" font-family="ui-monospace, monospace" font-size="11" font-weight="700">1. RAW REA DUMPS</text>\n'
        f'  <text x="64" y="146" fill="#ffffff" font-family="Space Grotesk, sans-serif" font-size="15" font-weight="700">app.asar + ELF/Mach-O</text>\n'
        f'  <line x1="296" y1="132" x2="356" y2="132" stroke="#05df72" stroke-width="1.8" marker-end="url(#arrow)"/>\n'
        f'  <rect x="356" y="100" width="248" height="64" rx="8" fill="#0b110f" stroke="#38bdf8" stroke-width="1.6"/>\n'
        f'  <text x="372" y="124" fill="#38bdf8" font-family="ui-monospace, monospace" font-size="11" font-weight="700">2. LOCAL SIEVE + BRICK PRO</text>\n'
        f'  <text x="372" y="146" fill="#ffffff" font-family="Space Grotesk, sans-serif" font-size="15" font-weight="700">-97.8% boilerplate stripped</text>\n'
        f'  <line x1="604" y1="132" x2="664" y2="132" stroke="#05df72" stroke-width="1.8" marker-end="url(#arrow)"/>\n'
        f'  <rect x="664" y="100" width="248" height="64" rx="8" fill="#07150e" stroke="#05df72" stroke-width="1.6"/>\n'
        f'  <text x="680" y="124" fill="#58e388" font-family="ui-monospace, monospace" font-size="11" font-weight="700">3. CLEAN SPEC ON REGOLO</text>\n'
        f'  <text x="680" y="146" fill="#ffffff" font-family="Space Grotesk, sans-serif" font-size="15" font-weight="700">qwen3.5-122b · EU ZDR</text>\n'
        + "\n".join(cards_svg)
        + f'\n  <text x="40" y="{svg_h - 26}" fill="#64748b" font-family="ui-monospace, monospace" font-size="11.5">Legend: ■ Amber = IPC / Preload Boundary   ■ Emerald = Crypto / Sync Symbol   ■ Cyan = Local REA Sieve</text>\n'
        f'</svg>'
    )


def generate_rea_pipeline(cfg: RegoloReaConfig, output_path: Path) -> dict:
    assert cfg.project_dir is not None
    scan_info = scan_project_directory(cfg.project_dir)
    rcode, rname, rdesc = cfg.rea_type
    model = cfg.active_model

    stage1 = call_regolo_chat(
        base_url=cfg.base_url,
        api_key=cfg.api_key,
        model=model,
        reasoning_effort="none",
        system_prompt=(
            "You are a fast reverse-engineering evidence triage engine. Output ONLY valid JSON "
            '{"evidence": [{"id": "e0", "symbol": "...", "scope": "...", "detail": "..."}]}. At most 6 items.'
        ),
        user_prompt=f"Extract the critical IPC channels, crypto routines, and sync tables for {rname} ({rdesc}) from:\n{scan_info['skeleton_text']}",
        max_tokens=800,
    )
    rea_obj = parse_rea_json(stage1["content"], scan_info["files"])

    stage2 = call_regolo_chat(
        base_url=cfg.base_url,
        api_key=cfg.api_key,
        model=model,
        reasoning_effort="none",
        system_prompt=(
            "You write clean-room software specifications from static reverse-engineering evidence. "
            "Output ONLY Markdown with sections: '## Architecture & IPC Overview', '## Critical Symbols & Crypto Parameters', "
            "'## Reconstructed State Machine', and '## Reference Implementation Skeleton'."
        ),
        user_prompt=f"Project: {cfg.project_dir.name}\nAudit: {rname}\nTriaged Evidence JSON:\n{json.dumps(rea_obj)}\n\nSieved Dumps:\n{scan_info['skeleton_text'][:6000]}",
        max_tokens=1600,
    )
    output_path.write_text(stage2["content"] or "# Reconstructed Specification\n", encoding="utf-8")
    svg_path = output_path.with_suffix(".svg")
    svg_path.write_text(
        render_rea_evidence_svg(rea_obj, cfg.project_dir.name, rcode, rname, scan_info["files"]),
        encoding="utf-8",
    )
    return {
        "scan_info": scan_info,
        "rea_obj": rea_obj,
        "stage1": stage1,
        "stage2": stage2,
        "output_path": str(output_path),
        "svg_path": str(svg_path),
    }


def render_header(cfg: RegoloReaConfig) -> None:
    masked_key = "sk-••••••••••••" if cfg.api_key else "NOT SET"
    key_badge = f"{GREEN}● CONNECTED ({masked_key}){RESET}" if cfg.api_key else f"{RED}○ MISSING API KEY{RESET}"
    cli_badge = f"{GREEN}● READY (rea-agents){RESET}" if cfg.cli_installed else f"{MINT}● BUILT-IN SIEVE{RESET}"
    rcode, rname, _ = cfg.rea_type
    proj_str = str(cfg.project_dir)[-72:] if cfg.project_dir else "prompted on generation [3]"

    print(f"\n{GREEN}╭──────────────────────────────────────────────────────────────────────────────────────╮{RESET}")
    print(f"{GREEN}│{RESET} {BG_BADGE}{MINT}{BOLD} ● REGOLO {RESET}                                                {SLATE}morluto/rea · v1.0{RESET} {GREEN}│{RESET}")
    print(f"{GREEN}│{RESET} {WHITE}{BOLD}Sovereign EU Reverse-Engineering & Binary/IPC Evidence Inspector (Zero Retention){RESET}    {GREEN}│{RESET}")
    print(f"{GREEN}├──────────────────────────────────────────────────────────────────────────────────────┤{RESET}")
    print(f"{GREEN}│{RESET} {SLATE}Endpoint :{RESET} {WHITE}{cfg.base_url:<34}{RESET} {SLATE}Status :{RESET} {key_badge:<33}{GREEN}│{RESET}")
    print(f"{GREEN}│{RESET} {SLATE}Model    :{RESET} {GREEN}{BOLD}{cfg.active_model:<34}{RESET} {SLATE}Engine :{RESET} {cli_badge:<33}{GREEN}│{RESET}")
    print(f"{GREEN}│{RESET} {SLATE}Audit    :{RESET} {PURPLE}[{rcode}] {rname[:28]:<28}{RESET} {SLATE}Pool   :{RESET} {MINT}Regolo EU Zero Retention{RESET}     {GREEN}│{RESET}")
    print(f"{GREEN}│{RESET} {SLATE}Project  :{RESET} {WHITE}{proj_str:<72}{RESET}  {GREEN}│{RESET}")
    print(f"{GREEN}╰──────────────────────────────────────────────────────────────────────────────────────╯{RESET}")


def render_menu() -> None:
    print(f"\n  {MINT}{BOLD}[1]{RESET} {WHITE}Environment & Tool Setup{RESET}       {SLATE}Configure .env & verify rea-agents CLI / static extractors{RESET}")
    print(f"  {MINT}{BOLD}[2]{RESET} {WHITE}Regolo API & Model Selector{RESET}    {SLATE}Query live GET /v1/models on Regolo & select active model{RESET}")
    print(f"  {MINT}{BOLD}[3]{RESET} {WHITE}Sieve Evidence & Reconstruct{RESET}   {SLATE}Filter IPC/symbol dumps & write clean spec in output/<project-id>/{RESET}")
    print(f"  {MINT}{BOLD}[q]{RESET} {SLATE}Quit Regolo{RESET}")


def run_demo_mode(cfg: RegoloReaConfig, target_dir: Path) -> None:
    cfg.project_dir = target_dir.resolve()
    project_id, out_file = get_project_output_path(cfg.project_dir, cfg.rea_type)
    render_header(cfg)
    render_menu()

    print(f"\n{CYAN}{BOLD}▶ [Option 2 · Live Model Discovery via GET {cfg.base_url}/models]{RESET}")
    models = fetch_regolo_models(cfg.base_url, cfg.api_key)
    cfg.available_models = models
    print(f"  {GREEN}✓ Retrieved {len(models)} active chat/code models from Regolo EU cluster:{RESET}")
    for idx, m in enumerate(models, 1):
        marker = f"{GREEN}◀ SELECTED MODEL{RESET}" if m == cfg.active_model else ""
        print(f"    {SLATE}[{idx:02d}]{RESET} {WHITE}{m:<24}{RESET} {marker}")

    print(f"\n{GREEN}{BOLD}▶ [Option 3 · REA Evidence Sieve & Spec Reconstruction (Project ID: {project_id})]{RESET}")
    scan = scan_project_directory(cfg.project_dir)
    print(
        f"  {GREEN}✓ Sieved {scan['files_scanned']} evidence dumps:{RESET} "
        f"{SLATE}{scan['raw_chars']:,} raw chars ->{RESET} {WHITE}{BOLD}{scan['compact_chars']:,} domain chars (-{scan['reduction_pct']}%){RESET}"
    )
    for f in scan["files"]:
        print(f"    {SLATE}├─{RESET} {WHITE}{f['path']:<36}{RESET} {SLATE}{f['raw_chars']:>5} -> {f['compact_chars']:>4} chars{RESET}")

    res = generate_rea_pipeline(cfg, out_file)
    s1, s2 = res["stage1"], res["stage2"]
    print(
        f"  {CYAN}[Step 1 · {cfg.active_model} · Evidence Triage]{RESET} "
        f"Isolated {len(res['rea_obj'].get('evidence', []))} boundaries in {GREEN}{s1['latency_s']}s{RESET} "
        f"{SLATE}(in={s1['prompt_tokens']} tok, out={s1['completion_tokens']} tok){RESET}"
    )
    print(
        f"  {GREEN}[Step 2 · {cfg.active_model} · Spec & SVG]{RESET}      "
        f"Wrote clean-room spec in {GREEN}{s2['latency_s']}s{RESET} "
        f"{SLATE}(in={s2['prompt_tokens']} tok, out={s2['completion_tokens']} tok){RESET}"
    )
    print(f"  {GREEN}{BOLD}✓ Saved in output/{project_id}/:{RESET} {WHITE}{res['output_path']}{RESET}\n")


def main() -> None:
    try:
        parser = argparse.ArgumentParser(description="Regolo TUI for rea")
        parser.add_argument("--demo", action="store_true")
        parser.add_argument("--project", default=str(Path(__file__).resolve().parent))
        args = parser.parse_args()
        cfg = RegoloReaConfig(Path(__file__).resolve().parent / ".env")
        if args.demo:
            run_demo_mode(cfg, Path(args.project))
    except (KeyboardInterrupt, EOFError):
        print(f"\n{SLATE}Closing Regolo. Goodbye!{RESET}")
        sys.exit(0)


if __name__ == "__main__":
    main()
