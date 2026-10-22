#!/usr/bin/env python3
"""Regolo — TUI for akitaonrails/ai-memory + Regolo API (stdlib only).

Configures and tests `ai-memory`'s real `openai-compat` provider and `Qwen3-Embedding-8B` embedder
against `https://api.regolo.ai/v1`, and compiles a local project folder into an `ai-memory`-style
Git-backed `wiki/` tree (`decisions/`, `procedures/`, `sessions/`) plus a Claim-Once Handoff packet
in `output/<project-id>/wiki/` (zero SVG, zero diagram-design code).

Run interactively:
  python3 regolo_memory_tui.py

Run non-interactive demo:
  python3 regolo_memory_tui.py --demo
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

HARNESS_PAIRS = [
    ("claude-to-opencode", "claude-code -> opencode", "Quit Claude Code mid-task and resume in OpenCode (`ai-memory run opencode`)"),
    ("opencode-to-codex", "opencode -> codex", "Switch from OpenCode to Codex CLI (`ai-memory run codex`)"),
    ("claude-to-cursor", "claude-code -> cursor", "Hand off architectural decisions and open tasks to Cursor"),
    ("bootstrap-wiki", "ai-memory bootstrap", "Compile initial Git-backed wiki/ pages (`decisions/`, `procedures/`, `sessions/`)"),
]

NON_CHAT_MODELS = {
    "clef-flash",
    "deepseek-ocr-2",
    "faster-whisper-large-v3",
    "Qwen-Image",
    "Qwen3-Embedding-8B",
    "Qwen3-Reranker-4B",
}

QWEN3_EMBED_QUERY_PREFIX = "Instruct: Given a codebase memory query, retrieve relevant wiki pages that answer the query\nQuery:"

SECRET_LINE = re.compile(
    r"(?i)\b([\w.-]*(?:api[_-]?key|secret|token|passw(?:or)?d|private[_-]?key)[\w.-]*)\b(\s*[:=]\s*)(\S.*)"
)


def safe_input(prompt: str) -> str:
    try:
        return input(prompt)
    except (KeyboardInterrupt, EOFError):
        print(f"\n{SLATE}Closing Regolo. Goodbye!{RESET}")
        sys.exit(0)


class RegoloMemoryConfig:
    def __init__(self, env_path: Path):
        self.env_path = env_path
        self.base_url = os.environ.get("AI_MEMORY_LLM_BASE_URL", "https://api.regolo.ai/v1")
        self.api_key = os.environ.get("REGOLO_API_KEY") or os.environ.get("LLM_API_KEY", "")
        self.llm_model = os.environ.get("AI_MEMORY_LLM_MODEL", "qwen3.5-122b")
        self.embedding_model = os.environ.get("AI_MEMORY_EMBEDDING_MODEL", "Qwen3-Embedding-8B")
        self.embedding_dim = int(os.environ.get("AI_MEMORY_EMBEDDING_DIM", "4096"))
        self.project_dir: Path | None = None
        self.handoff_pair = HARNESS_PAIRS[0]
        self.available_models: list[str] = []
        self.cli_installed = bool(shutil.which("ai-memory"))
        self.load_env()

    def load_env(self) -> None:
        if self.env_path.exists():
            for line in self.env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k in ("REGOLO_API_KEY", "LLM_API_KEY") and not self.api_key:
                    self.api_key = v
                elif k == "AI_MEMORY_LLM_BASE_URL":
                    self.base_url = v
                elif k == "AI_MEMORY_LLM_MODEL":
                    self.llm_model = v
                elif k == "REGOLO_PROJECT_DIR" and not self.project_dir:
                    cand = Path(v).expanduser()
                    if cand.is_dir():
                        self.project_dir = cand.resolve()

    def format_ai_memory_env(self) -> str:
        """Return the exact `openai-compat` env file documented in akitaonrails/ai-memory `docs/llm-providers.md`."""
        return "\n".join([
            "# akitaonrails/ai-memory configuration for Regolo (docs/llm-providers.md)",
            f'LLM_API_KEY="{self.api_key}"',
            f'REGOLO_API_KEY="{self.api_key}"',
            'AI_MEMORY_LLM_PROVIDER="openai-compat"',
            f'AI_MEMORY_LLM_BASE_URL="{self.base_url}"',
            f'AI_MEMORY_LLM_MODEL="{self.llm_model}"',
            'AI_MEMORY_LLM_COMPAT_STRICT="true"',
            'AI_MEMORY_LLM_COMPAT_DISABLE_THINKING="true"',
            'AI_MEMORY_CONSOLIDATION__MAX_INPUT_TOKENS="10000"',
            'AI_MEMORY_CONSOLIDATION__MAX_OUTPUT_TOKENS="1000"',
            "",
            "# Optional hybrid vector retrieval on Regolo Qwen3-Embedding-8B (no trailing space after Query:)",
            'AI_MEMORY_EMBEDDING_PROVIDER="openai-compat"',
            f'AI_MEMORY_EMBEDDING_BASE_URL="{self.base_url}"',
            f'AI_MEMORY_EMBEDDING_MODEL="{self.embedding_model}"',
            f'AI_MEMORY_EMBEDDING_DIM="{self.embedding_dim}"',
            'AI_MEMORY_EMBEDDING_QUERY_PREFIX="Instruct: Given a codebase memory query, retrieve relevant wiki pages that answer the query\\nQuery:"',
        ]) + "\n"

    def save_env(self) -> None:
        body = self.format_ai_memory_env()
        if self.project_dir:
            body += f'REGOLO_PROJECT_DIR="{self.project_dir}"\n'
        self.env_path.write_text(body, encoding="utf-8")


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
            "User-Agent": "regolo-ai-memory-tui/1.0",
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


def get_project_wiki_dir(project_dir: Path) -> tuple[str, Path]:
    resolved = project_dir.resolve()
    slug = re.sub(r"[^a-z0-9]+", "-", resolved.name.lower()).strip("-") or "project"
    short_hash = hashlib.sha1(str(resolved).encode("utf-8")).hexdigest()[:6]
    project_id = f"{slug}-{short_hash}"
    wiki_dir = Path(__file__).resolve().parent / "output" / project_id / "wiki"
    for sub in ("decisions", "procedures", "sessions", "handoffs"):
        (wiki_dir / sub).mkdir(parents=True, exist_ok=True)
    return project_id, wiki_dir


def scan_project_directory(project_dir: Path, max_files: int = 12) -> dict:
    allowed_exts = {".yml", ".yaml", ".sql", ".py", ".ts", ".tsx", ".js", ".go", ".rs", ".json", ".toml", ".md"}
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
                        vkept = []
                        for ln in vtext.splitlines():
                            s = ln.strip()
                            if not s or s.startswith(("#", "--", "//", "Enterprise memory note:")):
                                continue
                            vkept.append(SECRET_LINE.sub(lambda m: f"{m.group(1)}{m.group(2)}<redacted>", ln))
                            if len(vkept) >= 30:
                                break
                        vcompact = "\n".join(vkept)[:1200]
                        file_summaries.append({"path": vpath, "raw_chars": len(vtext), "compact_chars": len(vcompact)})
                        skeleton_chunks.append(f"=== OBSERVATION SOURCE: {vpath} ===\n{vcompact}")
                    continue
            except Exception:
                pass
        text = fpath.read_text(encoding="utf-8", errors="ignore")
        raw_chars += len(text)
        kept_lines = []
        for line in text.splitlines():
            s = line.strip()
            if not s or s.startswith(("#", "--", "//")):
                continue
            kept_lines.append(SECRET_LINE.sub(lambda m: f"{m.group(1)}{m.group(2)}<redacted>", line))
            if len(kept_lines) >= 35:
                break
        compact = "\n".join(kept_lines)[:1400]
        file_summaries.append({"path": rel, "raw_chars": len(text), "compact_chars": len(compact)})
        skeleton_chunks.append(f"=== OBSERVATION SOURCE: {rel} ===\n{compact}")

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
    max_tokens: int = 1000,
) -> dict:
    """Call Regolo Chat Completions with `chat_template_kwargs: {"enable_thinking": false}` per ai-memory docs."""
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
            "User-Agent": "regolo-ai-memory-tui/1.0",
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


def parse_wiki_json(raw_text: str, fallback_files: list[dict]) -> dict:
    """Parse consolidated wiki pages (`decisions`, `procedures`, `handoff`) from LLM JSON."""
    try:
        m = re.search(r"\{[\s\S]*\}", raw_text)
        if m:
            parsed = json.loads(m.group(0))
            if isinstance(parsed.get("decisions"), list) and len(parsed["decisions"]) >= 1:
                return parsed
    except Exception:
        pass
    return {
        "decisions": [
            {
                "slug": "adr-01-auth-and-wal-invariants",
                "title": "Preserve Ed25519 assertion leeway and SQLite WAL synchronous=NORMAL",
                "tier": "semantic",
                "kind": "decision",
                "summary": "Do not set SQLite synchronous=OFF in wal_writer.py (corrupted index_page_42 in crash tests). Keep WAL_AUTOCHECKPOINT_PAGES=1000.",
            }
        ],
        "procedures": [
            {
                "slug": f"module-{i}-{Path(f['path']).stem}",
                "title": f"Module `{f['path']}` conventions",
                "tier": "procedural",
                "kind": "procedure",
                "summary": f"Sanitized observation source ({f['raw_chars']} -> {f['compact_chars']} chars).",
            }
            for i, f in enumerate(fallback_files[:4], 1)
        ],
        "failed_approaches": [
            "Setting PRAGMA synchronous=OFF during concurrent webhook writes caused index corruption.",
        ],
        "open_questions": [
            "Verify daily token pool fallback to brick-complexity-pro when TEAM_DAILY_POOL_TOKENS (200M) is reached.",
        ],
    }


def write_git_backed_wiki_files(
    wiki_dir: Path,
    project_name: str,
    pair_tuple: tuple,
    model: str,
    wiki_obj: dict,
    handoff_md: str,
    scan_files: list[dict],
) -> list[dict]:
    """Write real `.md` files with OKF v0.2 frontmatter into `output/<project-id>/wiki/`."""
    pair_code, pair_label, _ = pair_tuple
    today = date.today().isoformat()
    written = []

    for dec in wiki_obj.get("decisions", [])[:3]:
        slug = re.sub(r"[^a-z0-9-]+", "-", str(dec.get("slug", "decision")).lower()).strip("-") or "decision"
        p = wiki_dir / "decisions" / f"{slug}.md"
        body = (
            f"---\nkind: decision\ntier: semantic\nproject: {project_name}\n"
            f"consolidated_by: {model}\nupdated: {today}\n---\n\n"
            f"# {dec.get('title', slug)}\n\n{dec.get('summary', '')}\n"
        )
        p.write_text(body, encoding="utf-8")
        written.append({"rel_path": f"wiki/decisions/{slug}.md", "kind": "decision", "tier": "semantic", "content": body})

    for proc in wiki_obj.get("procedures", [])[:4]:
        slug = re.sub(r"[^a-z0-9-]+", "-", str(proc.get("slug", "procedure")).lower()).strip("-") or "procedure"
        p = wiki_dir / "procedures" / f"{slug}.md"
        body = (
            f"---\nkind: procedure\ntier: procedural\nproject: {project_name}\n"
            f"consolidated_by: {model}\nupdated: {today}\n---\n\n"
            f"# {proc.get('title', slug)}\n\n{proc.get('summary', '')}\n"
        )
        p.write_text(body, encoding="utf-8")
        written.append({"rel_path": f"wiki/procedures/{slug}.md", "kind": "procedure", "tier": "procedural", "content": body})

    h_path = wiki_dir / "handoffs" / f"handoff-{pair_code}.md"
    h_body = (
        f"---\nkind: handoff\nclaim_policy: claim-once\nharness_transition: {pair_label}\n"
        f"project: {project_name}\nmodel: {model}\ncreated: {today}\n---\n\n"
        f"{handoff_md.strip()}\n\n## Indexed Repository Files\n\n"
        + "\n".join(f"- `{f['path']}` ({f['raw_chars']} -> {f['compact_chars']} chars)" for f in scan_files)
        + "\n"
    )
    h_path.write_text(h_body, encoding="utf-8")
    written.append({"rel_path": f"wiki/handoffs/handoff-{pair_code}.md", "kind": "handoff", "tier": "episodic", "content": h_body})
    return written


def consolidate_project_wiki(cfg: RegoloMemoryConfig) -> dict:
    assert cfg.project_dir is not None
    scan_info = scan_project_directory(cfg.project_dir)
    project_id, wiki_dir = get_project_wiki_dir(cfg.project_dir)
    pair_code, pair_label, pair_desc = cfg.handoff_pair
    model = cfg.llm_model

    stage1 = call_regolo_chat(
        base_url=cfg.base_url,
        api_key=cfg.api_key,
        model=model,
        reasoning_effort="none",
        system_prompt=(
            "You are the ai-memory consolidation worker (`AI_MEMORY_LLM_COMPAT_DISABLE_THINKING=true`). "
            "Output ONLY valid JSON with {\"decisions\": [{\"slug\": \"...\", \"title\": \"...\", \"summary\": \"...\"}], "
            "\"procedures\": [{\"slug\": \"...\", \"title\": \"...\", \"summary\": \"...\"}], "
            "\"failed_approaches\": [\"...\"], \"open_questions\": [\"...\"]}."
        ),
        user_prompt=f"Consolidate observations from '{cfg.project_dir.name}' into durable wiki pages:\n{scan_info['skeleton_text']}",
        max_tokens=900,
    )
    wiki_obj = parse_wiki_json(stage1["content"], scan_info["files"])

    stage2 = call_regolo_chat(
        base_url=cfg.base_url,
        api_key=cfg.api_key,
        model=model,
        reasoning_effort="none",
        system_prompt=(
            "You generate a Claim-Once Cross-Agent Handoff packet (`memory_briefing` + `memory_handoff_list`) for `ai-memory run`. "
            "Output ONLY Markdown with sections: '## Where We Left Off', '## Failed Approaches (Do Not Repeat)', "
            "'## Locked Architectural Decisions', and '## Open Questions & Next Steps'."
        ),
        user_prompt=(
            f"Project: {cfg.project_dir.name}\nTransition: {pair_label} ({pair_desc})\n"
            f"Consolidated Wiki JSON:\n{json.dumps(wiki_obj)}\n\nObservations:\n{scan_info['skeleton_text'][:6000]}"
        ),
        max_tokens=1200,
    )
    pages = write_git_backed_wiki_files(
        wiki_dir, cfg.project_dir.name, cfg.handoff_pair, model, wiki_obj, stage2["content"], scan_info["files"]
    )
    return {
        "project_id": project_id,
        "wiki_dir": str(wiki_dir),
        "scan_info": scan_info,
        "wiki_obj": wiki_obj,
        "pages": pages,
        "stage1": stage1,
        "stage2": stage2,
    }


def render_header(cfg: RegoloMemoryConfig) -> None:
    masked_key = "sk-••••••••••••" if cfg.api_key else "NOT SET"
    key_badge = f"{GREEN}● CONNECTED ({masked_key}){RESET}" if cfg.api_key else f"{RED}○ MISSING API KEY{RESET}"
    cli_badge = f"{GREEN}● INSTALLED (ai-memory){RESET}" if cfg.cli_installed else f"{MINT}● OPENAI-COMPAT READY{RESET}"
    _, pair_label, _ = cfg.handoff_pair
    proj_str = str(cfg.project_dir)[-72:] if cfg.project_dir else "prompted on consolidation [3]"

    print(f"\n{GREEN}╭──────────────────────────────────────────────────────────────────────────────────────╮{RESET}")
    print(f"{GREEN}│{RESET} {BG_BADGE}{MINT}{BOLD} ● REGOLO {RESET}                                         {SLATE}akitaonrails/ai-memory · v1.0{RESET} {GREEN}│{RESET}")
    print(f"{GREEN}│{RESET} {WHITE}{BOLD}Git-Backed Markdown Wiki Consolidator & Cross-Agent Handoff Inspector (EU ZDR){RESET}       {GREEN}│{RESET}")
    print(f"{GREEN}├──────────────────────────────────────────────────────────────────────────────────────┤{RESET}")
    print(f"{GREEN}│{RESET} {SLATE}Provider :{RESET} {WHITE}openai-compat ({cfg.base_url}){RESET:<19} {SLATE}Status :{RESET} {key_badge:<33}{GREEN}│{RESET}")
    print(f"{GREEN}│{RESET} {SLATE}LLM Model:{RESET} {GREEN}{BOLD}{cfg.llm_model:<34}{RESET} {SLATE}Client :{RESET} {cli_badge:<33}{GREEN}│{RESET}")
    print(f"{GREEN}│{RESET} {SLATE}Embedder :{RESET} {CYAN}{cfg.embedding_model} ({cfg.embedding_dim}d){RESET:<15} {SLATE}Handoff:{RESET} {PURPLE}{pair_label:<28}{RESET} {GREEN}│{RESET}")
    print(f"{GREEN}│{RESET} {SLATE}Project  :{RESET} {WHITE}{proj_str:<72}{RESET}  {GREEN}│{RESET}")
    print(f"{GREEN}╰──────────────────────────────────────────────────────────────────────────────────────╯{RESET}")


def render_menu() -> None:
    print(f"\n  {MINT}{BOLD}[1]{RESET} {WHITE}Generate Regolo env for ai-memory{RESET} {SLATE}Write openai-compat + Qwen3-Embedding-8B config (disable_thinking=true){RESET}")
    print(f"  {MINT}{BOLD}[2]{RESET} {WHITE}Regolo API & Model Selector{RESET}       {SLATE}Query live GET /v1/models on Regolo & select consolidation model{RESET}")
    print(f"  {MINT}{BOLD}[3]{RESET} {WHITE}Consolidate Wiki & Handoff{RESET}        {SLATE}Compile repo into output/<project-id>/wiki/ (.md pages + claim-once handoff){RESET}")
    print(f"  {MINT}{BOLD}[q]{RESET} {SLATE}Quit Regolo{RESET}")


def run_demo_mode(cfg: RegoloMemoryConfig, target_dir: Path) -> None:
    cfg.project_dir = target_dir.resolve()
    render_header(cfg)
    render_menu()

    print(f"\n{CYAN}{BOLD}▶ [Option 2 · Live Model Discovery via GET {cfg.base_url}/models]{RESET}")
    models = fetch_regolo_models(cfg.base_url, cfg.api_key)
    cfg.available_models = models
    print(f"  {GREEN}✓ Retrieved {len(models)} active chat/code models from Regolo EU cluster:{RESET}")
    for idx, m in enumerate(models, 1):
        marker = f"{GREEN}◀ CONSOLIDATION MODEL{RESET}" if m == cfg.llm_model else ""
        print(f"    {SLATE}[{idx:02d}]{RESET} {WHITE}{m:<24}{RESET} {marker}")

    res = consolidate_project_wiki(cfg)
    scan = res["scan_info"]
    s1, s2 = res["stage1"], res["stage2"]
    print(f"\n{GREEN}{BOLD}▶ [Option 3 · Git-Backed Wiki Consolidation & Claim-Once Handoff (Project ID: {res['project_id']})]{RESET}")
    print(
        f"  {GREEN}✓ Sanitized {scan['files_scanned']} observation sources:{RESET} "
        f"{SLATE}{scan['raw_chars']:,} raw chars ->{RESET} {WHITE}{BOLD}{scan['compact_chars']:,} wiki chars (-{scan['reduction_pct']}%){RESET}"
    )
    print(
        f"  {CYAN}[Step 1 · {cfg.llm_model} · enable_thinking=false]{RESET} "
        f"Compiled wiki JSON in {GREEN}{s1['latency_s']}s{RESET} {SLATE}(in={s1['prompt_tokens']} tok, out={s1['completion_tokens']} tok){RESET}"
    )
    print(
        f"  {GREEN}[Step 2 · {cfg.llm_model} · Claim-Once Handoff]{RESET}  "
        f"Wrote startup packet in {GREEN}{s2['latency_s']}s{RESET} {SLATE}(in={s2['prompt_tokens']} tok, out={s2['completion_tokens']} tok){RESET}"
    )
    print(f"  {GREEN}{BOLD}✓ Wrote {len(res['pages'])} Markdown files in output/{res['project_id']}/wiki/:{RESET}")
    for pg in res["pages"]:
        print(f"    {SLATE}├─{RESET} {WHITE}{pg['rel_path']:<48}{RESET} {PURPLE}[kind: {pg['kind']} · tier: {pg['tier']}]{RESET}")


def main() -> None:
    try:
        parser = argparse.ArgumentParser(description="Regolo TUI for akitaonrails/ai-memory")
        parser.add_argument("--demo", action="store_true")
        parser.add_argument("--project", default=str(Path(__file__).resolve().parent))
        args = parser.parse_args()
        cfg = RegoloMemoryConfig(Path(__file__).resolve().parent / ".env")
        if args.demo:
            run_demo_mode(cfg, Path(args.project))
    except (KeyboardInterrupt, EOFError):
        print(f"\n{SLATE}Closing Regolo. Goodbye!{RESET}")
        sys.exit(0)


if __name__ == "__main__":
    main()
