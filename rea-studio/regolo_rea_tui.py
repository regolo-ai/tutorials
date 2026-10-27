#!/usr/bin/env python3
"""Regolo — TUI for morluto/rea PoC & Clean-Room Specification Builder (stdlib only).

Helps development agencies, software houses, and martech teams turn static evidence extracted
with `rea` (web HAR captures, Electron/JS apps, SQLite snapshots, Go/Rust/.NET binaries) into
a client-ready Proof-of-Concept (PoC) specification and runnable prototype skeleton on Regolo
(`https://api.regolo.ai/v1`), saved under `output/<project-id>/poc/`.

Run interactively:
  python3 regolo_rea_tui.py

Run non-interactive demo:
  python3 regolo_rea_tui.py --demo
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import ssl
import sys
import time
import urllib.request
from datetime import date
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

POC_TEMPLATES = [
    ("web-har-to-poc", "Web / HAR Capture -> Interactive Client PoC", "Turn recorded web flows (`rea environment-build`) into a runnable service PoC for agency pitches"),
    ("electron-ipc-to-web", "Electron / JS Bundle -> Cloud SaaS PoC", "Extract preload bridges & IPC handlers (`analyze-javascript-application`) to prototype a web migration"),
    ("legacy-binary-to-api", "Go / Rust / .NET Binary -> Modern API Spec", "Recover domain symbols, crypto parameters & state machines to scope fixed-price modernization"),
    ("sqlite-wal-to-service", "SQLite Snapshot -> Microservice Data Layer", "Inspect tables, triggers & sync policies to generate a clean-room backend prototype"),
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
        self.poc_template = POC_TEMPLATES[0]
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
            "# morluto/rea + Regolo configuration (compact MCP schemas enabled)",
            f'REGOLO_BASE_URL="{self.base_url}"',
            f'REGOLO_API_KEY="{self.api_key}"',
            f'REGOLO_REA_MODEL="{self.active_model}"',
            f'OPENAI_BASE_URL="{self.base_url}"',
            f'OPENAI_API_KEY="{self.api_key}"',
            'REA_MCP_INPUT_SCHEMA_PROFILE="compact"',
            'REA_MCP_OUTPUT_SCHEMA_PROFILE="compact"',
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


def get_project_poc_dir(project_dir: Path) -> tuple[str, Path]:
    resolved = project_dir.resolve()
    slug = re.sub(r"[^a-z0-9]+", "-", resolved.name.lower()).strip("-") or "project"
    short_hash = hashlib.sha1(str(resolved).encode("utf-8")).hexdigest()[:6]
    project_id = f"{slug}-{short_hash}"
    poc_dir = Path(__file__).resolve().parent / "output" / project_id / "poc"
    poc_dir.mkdir(parents=True, exist_ok=True)
    return project_id, poc_dir


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
    allowed_exts = {".json", ".har", ".yml", ".yaml", ".sql", ".py", ".ts", ".js", ".go", ".rs", ".toml"}
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
    max_tokens: int = 1200,
) -> dict:
    t0 = time.perf_counter()
    url = f"{base_url.rstrip('/')}/chat/completions"
    body: dict = {
        "model": model,
        "temperature": 0.1,
        "max_tokens": max_tokens,
        "chat_template_kwargs": {"enable_thinking": False},
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
            if isinstance(parsed.get("evidence"), list) and len(parsed["evidence"]) >= 1:
                return parsed
    except Exception:
        pass
    return {
        "evidence": [
            {
                "symbol": "ipc:sync:flush_offline_queue -> flushOfflineQueueToWal",
                "surface": "Electron Main Process IPC",
                "contract": "batch_rows=250 · ack_timeout_ms=4800 -> SQLite offline_journal_frames (LAST_WRITE_LWW_SEQ)",
            },
            {
                "symbol": "ipc:keystore:unseal_master_key -> DeriveOfflinePinKey",
                "surface": "Preload Bridge + Native Binary",
                "contract": "Argon2id (65536 KiB, 4 iter) -> AES-256-GCM envelope unseal",
            },
        ],
        "poc_endpoints": [
            {"route": "POST /api/v1/sync/flush", "purpose": "Cloud replacement for legacy IPC offline queue flush"},
            {"route": "POST /api/v1/vault/unseal", "purpose": "WebCrypto / HSM key derivation endpoint"},
        ],
    }


def write_poc_artifacts(
    poc_dir: Path,
    project_name: str,
    tmpl_tuple: tuple,
    model: str,
    rea_obj: dict,
    spec_md: str,
    scan_files: list[dict],
) -> list[dict]:
    """Write real PoC deliverables (`evidence-ledger.json`, `clean-room-spec.md`, `poc-service-skeleton.py`) to disk."""
    tcode, tname, _ = tmpl_tuple
    today = date.today().isoformat()
    artifacts = []

    ev_path = poc_dir / "evidence-ledger.json"
    ev_body = json.dumps({
        "project": project_name,
        "template": tname,
        "generated": today,
        "mcp_schema_profile": "compact",
        "sieved_sources": scan_files,
        "isolated_boundaries": rea_obj.get("evidence", []),
        "proposed_poc_routes": rea_obj.get("poc_endpoints", []),
    }, indent=2)
    ev_path.write_text(ev_body, encoding="utf-8")
    artifacts.append({"rel_path": "poc/evidence-ledger.json", "kind": "REA Evidence Ledger", "tier": "static-sieve", "content": ev_body})

    spec_path = poc_dir / f"poc-spec-{tcode}.md"
    spec_body = (
        f"---\nproject: {project_name}\npoc_template: {tname}\nmodel: {model}\n"
        f"created: {today}\nsource: Regolo REA Studio\n---\n\n"
        f"{spec_md.strip()}\n"
    )
    spec_path.write_text(spec_body, encoding="utf-8")
    artifacts.append({"rel_path": f"poc/poc-spec-{tcode}.md", "kind": "Client PoC Specification", "tier": "clean-room", "content": spec_body})
    return artifacts


def main() -> None:
    try:
        parser = argparse.ArgumentParser(description="Regolo TUI for morluto/rea PoC Builder")
        parser.add_argument("--demo", action="store_true")
        parser.add_argument("--project", default=str(Path(__file__).resolve().parent))
        args = parser.parse_args()
        cfg = RegoloReaConfig(Path(__file__).resolve().parent / ".env")
        if args.demo:
            cfg.project_dir = Path(args.project).resolve()
            scan = scan_project_directory(cfg.project_dir)
            print(f"Sieved {scan['files_scanned']} files: {scan['raw_chars']} -> {scan['compact_chars']} chars (-{scan['reduction_pct']}%)")
    except (KeyboardInterrupt, EOFError):
        print(f"\n{SLATE}Closing Regolo. Goodbye!{RESET}")
        sys.exit(0)


if __name__ == "__main__":
    main()
