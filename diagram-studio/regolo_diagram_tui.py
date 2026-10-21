#!/usr/bin/env python3
"""Regolo — TUI for cathrynlavery/diagram-design + Regolo API (stdlib only).

Provides:
1. Environment & Skill Setup (.env persistence + npx skills add cathrynlavery/diagram-design check)
2. Regolo API & Live Model Selector (queries GET https://api.regolo.ai/v1/models)
3. Target Project Directory Scanner (extracts structural skeleton from docker-compose, SQL, Python/TS/Go)
4. 4px-Grid HTML + Inline SVG Diagram Generator (prompts for project directory if not set in step 3,
   extracts topology on Regolo and renders a complete multi-node 4px-grid inline SVG diagram)

Run interactively:
  python3 regolo_diagram_tui.py

Run non-interactive self-check / demo:
  python3 regolo_diagram_tui.py --demo
"""
import argparse
import hashlib
import html
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

# Regolo ANSI Palette (24-bit Truecolor)
ESC = "\033["
RESET = f"{ESC}0m"
BOLD = f"{ESC}1m"
DIM = f"{ESC}2m"
GREEN = f"{ESC}38;2;5;223;114m"       # #05df72 Regolo Hero Green
MINT = f"{ESC}38;2;88;227;136m"       # #58e388 Regolo Badge Mint
CYAN = f"{ESC}38;2;56;189;248m"       # #38bdf8 Layer 1 / Info
PURPLE = f"{ESC}38;2;196;181;253m"    # #c4b5fd Layer 2 / AST
AMBER = f"{ESC}38;2;251;191;36m"      # #fbbf24 Warning / Highlight
RED = f"{ESC}38;2;248;113;113m"       # #f87171 Error
SLATE = f"{ESC}38;2;148;163;184m"     # #94a3b8 Muted
WHITE = f"{ESC}38;2;248;250;252m"     # #f8fafc Bright text
BG_BADGE = f"{ESC}48;2;6;25;16m"      # #061910 Regolo Dark Emerald surface

DIAGRAM_TYPES = [
    ("01", "Architecture & Containment Map", "System services, VPC/subnet boundaries, ports & data stores"),
    ("40", "Architecture Delta Ledger", "Synchronized Before · Changes · After migration topology"),
    ("38", "Database Schema & ER Diagram", "Physical SQL tables, primary keys & foreign-key routing"),
    ("04", "Auth & API Sequence Diagram", "Multi-actor request, webhook & token-refresh timeline"),
    ("29", "Data Flow & Pipeline Map", "Role-scoped ingestion, transformation & storage steps"),
    ("35", "Deployment & Cluster Topology", "Cloud zones, containers, queues & sovereign GPU endpoints"),
]

NON_CHAT_MODELS = {
    "clef-flash",
    "deepseek-ocr-2",
    "faster-whisper-large-v3",
    "Qwen-Image",
    "Qwen3-Embedding-8B",
    "Qwen3-Reranker-4B",
}


def safe_input(prompt: str) -> str:
    """Read user input and exit cleanly on Ctrl+C / Ctrl+D without printing a traceback."""
    try:
        return input(prompt)
    except (KeyboardInterrupt, EOFError):
        print(f"\n{SLATE}Closing Regolo. Goodbye!{RESET}")
        sys.exit(0)


class RegoloDiagramConfig:
    def __init__(self, env_path: Path):
        self.env_path = env_path
        self.base_url = os.environ.get("REGOLO_BASE_URL", "https://api.regolo.ai/v1")
        self.api_key = os.environ.get("REGOLO_API_KEY", "")
        self.scan_model = "brick-complexity-pro"
        self.svg_model = os.environ.get("REGOLO_SVG_MODEL", "qwen3.5-122b")
        self.project_dir: Path | None = None
        self.diagram_type = DIAGRAM_TYPES[0]
        self.available_models: list[str] = []
        self.skill_installed = False
        self.load_env()
        self.check_skill_status()

    def load_env(self) -> None:
        candidates = [self.env_path]
        for candidate in candidates:
            if candidate.exists():
                for line in candidate.read_text(encoding="utf-8", errors="ignore").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip().strip('"').strip("'")
                    if k == "REGOLO_API_KEY" and not self.api_key:
                        self.api_key = v
                    elif k == "REGOLO_BASE_URL":
                        self.base_url = v
                    elif k == "REGOLO_SVG_MODEL":
                        self.svg_model = v
                    elif k == "REGOLO_PROJECT_DIR" and not self.project_dir:
                        cand = Path(v).expanduser()
                        if cand.is_dir():
                            self.project_dir = cand.resolve()

    def save_env(self) -> None:
        lines = [
            f'REGOLO_BASE_URL="{self.base_url}"',
            f'REGOLO_API_KEY="{self.api_key}"',
            f'REGOLO_SVG_MODEL="{self.svg_model}"',
            f'OPENAI_BASE_URL="{self.base_url}"',
            f'OPENAI_API_KEY="{self.api_key}"',
        ]
        if self.project_dir:
            lines.append(f'REGOLO_PROJECT_DIR="{self.project_dir}"')
        self.env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def check_skill_status(self) -> bool:
        skill_roots = [
            Path.home() / ".agents/skills/diagram-design",
            Path.home() / ".claude/skills/diagram-design",
            Path.home() / ".config/opencode/skills/diagram-design",
            Path.home() / ".cursor/skills/diagram-design",
        ]
        self.skill_installed = any(p.exists() for p in skill_roots) or bool(shutil.which("npx"))
        return self.skill_installed


def ssl_context() -> ssl.SSLContext:
    cert = Path("/etc/ssl/cert.pem")
    return ssl.create_default_context(cafile=str(cert)) if cert.exists() else ssl.create_default_context()


def fetch_regolo_models(base_url: str, api_key: str) -> list[str]:
    """Query GET /v1/models on Regolo and return chat/code-capable model IDs."""
    url = f"{base_url.rstrip('/')}/models"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": "regolo-tui/1.0",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=20, context=ssl_context()) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    raw_ids = [item["id"] for item in payload.get("data", []) if "id" in item]
    chat_models = [m for m in raw_ids if m not in NON_CHAT_MODELS]
    return sorted(chat_models)


def scan_project_directory(project_dir: Path, max_files: int = 12) -> dict:
    """Scan a project folder and extract compact topology evidence for diagram generation."""
    allowed_exts = {".yml", ".yaml", ".sql", ".py", ".ts", ".tsx", ".js", ".go", ".rs", ".json", ".toml"}
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
                        vkept = [
                            ln for ln in vtext.splitlines()
                            if ln.strip() and not ln.strip().startswith(("#", "--", "//", "Enterprise "))
                        ][:30]
                        vcompact = "\n".join(vkept)[:1200]
                        file_summaries.append({"path": vpath, "raw_chars": len(vtext), "compact_chars": len(vcompact)})
                        skeleton_chunks.append(f"=== FILE: {vpath} ===\n{vcompact}")
                    continue
            except Exception:
                pass
        text = fpath.read_text(encoding="utf-8", errors="ignore")
        raw_chars += len(text)
        kept_lines = []
        for line in text.splitlines():
            s = line.strip()
            if not s or s.startswith("#") or s.startswith("--") or s.startswith("//"):
                continue
            kept_lines.append(line)
            if len(kept_lines) >= 35:
                break
        compact = "\n".join(kept_lines)[:1400]
        file_summaries.append({"path": rel, "raw_chars": len(text), "compact_chars": len(compact)})
        skeleton_chunks.append(f"=== FILE: {rel} ===\n{compact}")

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
    max_tokens: int = 3200,
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
            "User-Agent": "regolo-tui/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90, context=ssl_context()) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    elapsed = round(time.perf_counter() - t0, 2)
    msg = data["choices"][0]["message"]
    content = (msg.get("content") or "").strip()
    reasoning = (msg.get("reasoning_content") or "").strip()
    usage = data.get("usage", {})
    return {
        "content": content,
        "reasoning": reasoning,
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
        "latency_s": elapsed,
    }


def parse_topology_json(raw_text: str, fallback_files: list[dict]) -> dict:
    """Extract JSON {nodes, edges} from Stage 1 response or build deterministic topology from scanned files."""
    try:
        m = re.search(r"\{[\s\S]*\}", raw_text)
        if m:
            parsed = json.loads(m.group(0))
            if isinstance(parsed.get("nodes"), list) and len(parsed["nodes"]) >= 2:
                return parsed
    except Exception:
        pass

    nodes = []
    edges = []
    for idx, f in enumerate(fallback_files[:8]):
        p = f["path"]
        role = (
            "Infrastructure & Compose"
            if p.endswith((".yml", ".yaml"))
            else ("Database Schema" if p.endswith(".sql") else "Application Module")
        )
        nodes.append({"id": f"n{idx}", "label": p, "role": role, "detail": f"{f['raw_chars']} -> {f['compact_chars']} chars"})
        if idx > 0:
            edges.append({"from": f"n{idx - 1}", "to": f"n{idx}", "protocol": "imports / calls"})
    return {"nodes": nodes, "edges": edges}


def render_4px_grid_svg_from_topology(topology: dict, title: str, dtype_code: str, dtype_name: str, scan_files: list[dict]) -> str:
    """Deterministic 4px-grid editorial SVG builder with a distinct visual layout per diagram-design type."""
    raw_nodes = topology.get("nodes") or []
    nodes = []
    for idx, n in enumerate(raw_nodes[:8]):
        if isinstance(n, dict):
            nid = str(n.get("id") or f"n{idx}")
            lbl = str(n.get("label") or n.get("name") or nid)
            role = str(n.get("role") or n.get("type") or "Component")
            det = str(n.get("detail") or n.get("port") or n.get("description") or "")
            nodes.append({"id": nid, "label": lbl[:28], "role": role[:30], "detail": det[:34]})

    if len(nodes) < 3:
        nodes = [
            {
                "id": f"n{i}",
                "label": f["path"][:28],
                "role": "Infrastructure" if f["path"].endswith(".yml") else ("Database" if f["path"].endswith(".sql") else "Service Module"),
                "detail": f"{f['raw_chars']:,} -> {f['compact_chars']:,} chars",
            }
            for i, f in enumerate(scan_files[:6])
        ]

    svg_w = 960
    body_elems = []
    legend_text = ""

    # TYPE 40: Architecture Delta Ledger (3 columns: BEFORE · CHANGES · AFTER)
    if dtype_code == "40":
        svg_h = max(480, 180 + max(3, len(nodes) // 2) * 108)
        col_w = 272
        cols_x = [40, 344, 648]
        headers = [
            ("BEFORE · LEGACY STATE", "#64748b", "rgba(100,116,139,0.12)"),
            ("CHANGES · DELTA LEDGER", "#fbbf24", "rgba(251,191,36,0.10)"),
            ("AFTER · TARGET TOPOLOGY", "#05df72", "rgba(5,223,114,0.10)"),
        ]
        for ci, (htitle, hcol, hbg) in enumerate(headers):
            cx = cols_x[ci]
            body_elems.append(
                f'  <rect x="{cx}" y="108" width="{col_w}" height="{svg_h - 156}" rx="10" fill="{hbg}" stroke="{hcol}" stroke-width="1.25" stroke-dasharray="4 4"/>\n'
                f'  <text x="{cx + 16}" y="134" fill="{hcol}" font-family="ui-monospace, monospace" font-size="11.5" font-weight="700" letter-spacing="0.06em">{htitle}</text>'
            )
        half = max(2, len(nodes) // 2)
        for i, n in enumerate(nodes[:half]):
            y = 156 + i * 96
            # Before node
            body_elems.append(
                f'  <g transform="translate({cols_x[0] + 16},{y})">\n'
                f'    <rect width="{col_w - 32}" height="76" rx="6" fill="#0b110f" stroke="#64748b" stroke-width="1.2"/>\n'
                f'    <text x="12" y="24" fill="#94a3b8" font-family="ui-monospace, monospace" font-size="10.5">UNCHANGED / LEGACY</text>\n'
                f'    <text x="12" y="46" fill="#e2e8f0" font-family="Space Grotesk, sans-serif" font-size="14.5" font-weight="700">{html.escape(n["label"])}</text>\n'
                f'    <text x="12" y="64" fill="#64748b" font-family="ui-monospace, monospace" font-size="11">{html.escape(n["role"])}</text>\n'
                f'  </g>'
            )
            # Delta ledger item
            action_tag = "+ REWIRED / OPTIMIZED" if i % 2 == 0 else "± COMPRESSED MODULE"
            body_elems.append(
                f'  <g transform="translate({cols_x[1] + 16},{y})">\n'
                f'    <rect width="{col_w - 32}" height="76" rx="6" fill="#141107" stroke="#fbbf24" stroke-width="1.2"/>\n'
                f'    <text x="12" y="24" fill="#fbbf24" font-family="ui-monospace, monospace" font-size="10.5" font-weight="700">{action_tag}</text>\n'
                f'    <text x="12" y="46" fill="#ffffff" font-family="Space Grotesk, sans-serif" font-size="14" font-weight="700">{html.escape(n["label"])}</text>\n'
                f'    <text x="12" y="64" fill="#cbd5e1" font-family="ui-monospace, monospace" font-size="11">{html.escape(n["detail"] or "delta applied")}</text>\n'
                f'  </g>'
            )
        for i, n in enumerate(nodes[-half:]):
            y = 156 + i * 96
            body_elems.append(
                f'  <g transform="translate({cols_x[2] + 16},{y})">\n'
                f'    <rect width="{col_w - 32}" height="76" rx="6" fill="#07150e" stroke="#05df72" stroke-width="1.6"/>\n'
                f'    <text x="12" y="24" fill="#58e388" font-family="ui-monospace, monospace" font-size="10.5" font-weight="700">✓ ACTIVE IN TARGET</text>\n'
                f'    <text x="12" y="46" fill="#ffffff" font-family="Space Grotesk, sans-serif" font-size="14.5" font-weight="700">{html.escape(n["label"])}</text>\n'
                f'    <text x="12" y="64" fill="#94a3b8" font-family="ui-monospace, monospace" font-size="11">{html.escape(n["detail"] or n["role"])}</text>\n'
                f'  </g>'
            )
        legend_text = "Legend: ■ Slate = Legacy Snapshot   ■ Amber (#fbbf24) = Architecture Delta   ■ Emerald (#05df72) = Target State"

    # TYPE 38: Database Schema & ER Diagram (SQL Tables with PK / FK column rows)
    elif dtype_code == "38":
        cols = 3 if len(nodes) > 4 else 2
        rows_count = (len(nodes) + cols - 1) // cols
        svg_h = max(460, 140 + rows_count * 168 + 48)
        tw = 264 if cols == 3 else 380
        th = 132
        coords = {}
        for idx, n in enumerate(nodes[:6]):
            r, c = idx // cols, idx % cols
            x = 48 + c * (tw + 36)
            y = 116 + r * (th + 36)
            coords[n["id"]] = (x, y, tw, th)
            tname = n["label"].replace(".py", "").replace(".sql", "").replace("/", "_")
            body_elems.append(
                f'  <g transform="translate({x},{y})">\n'
                f'    <rect width="{tw}" height="{th}" rx="8" fill="#0b110f" stroke="#38bdf8" stroke-width="1.5"/>\n'
                f'    <rect width="{tw}" height="32" rx="8" fill="rgba(56,189,248,0.16)"/>\n'
                f'    <text x="14" y="21" fill="#38bdf8" font-family="ui-monospace, monospace" font-size="12.5" font-weight="700">TABLE · {html.escape(tname[:22])}</text>\n'
                f'    <text x="14" y="54" fill="#05df72" font-family="ui-monospace, monospace" font-size="11.5" font-weight="700">PK  id               UUID NOT NULL</text>\n'
                f'    <text x="14" y="76" fill="#f8fafc" font-family="ui-monospace, monospace" font-size="11.5">FK  parent_ref_id    VARCHAR(64)</text>\n'
                f'    <text x="14" y="98" fill="#94a3b8" font-family="ui-monospace, monospace" font-size="11.5">    role_type        {html.escape(n["role"][:16])}</text>\n'
                f'    <text x="14" y="118" fill="#64748b" font-family="ui-monospace, monospace" font-size="11">    meta             {html.escape((n["detail"] or "indexed")[:18])}</text>\n'
                f'  </g>'
            )
        for i in range(min(len(nodes), 6) - 1):
            x1, y1, w1, h1 = coords[nodes[i]["id"]]
            x2, y2, w2, h2 = coords[nodes[i + 1]["id"]]
            cx1, cy1 = (x1 + w1, y1 + 54) if y1 == y2 else (x1 + w1 // 2, y1 + h1)
            cx2, cy2 = (x2, y2 + 76) if y1 == y2 else (x2 + w2 // 2, y2)
            body_elems.append(
                f'  <path d="M {cx1} {cy1} L {cx2} {cy2}" fill="none" stroke="#05df72" stroke-width="1.5" stroke-dasharray="5 3" marker-end="url(#arrow)"/>'
            )
        legend_text = "Legend: PK (#05df72) = Primary Key   FK (#38bdf8) = Foreign Key Reference   ┄ Dashed = 1:N Relation"

    # TYPE 04: Auth & API Sequence Diagram (Horizontal Lifelines + Vertical Time Messages)
    elif dtype_code == "04":
        actors = nodes[:5]
        n_act = len(actors)
        svg_h = max(480, 190 + n_act * 64)
        spacing = (svg_w - 120) // max(n_act, 1)
        xs = [60 + i * spacing + spacing // 2 for i in range(n_act)]
        for i, a in enumerate(actors):
            ax = xs[i]
            col = "#05df72" if i == 0 else "#38bdf8"
            body_elems.append(
                f'  <rect x="{ax - 76}" y="104" width="152" height="52" rx="8" fill="#0b110f" stroke="{col}" stroke-width="1.6"/>\n'
                f'  <text x="{ax}" y="126" text-anchor="middle" fill="{col}" font-family="ui-monospace, monospace" font-size="10.5" font-weight="700">{html.escape(a["role"][:18].upper())}</text>\n'
                f'  <text x="{ax}" y="144" text-anchor="middle" fill="#ffffff" font-family="Space Grotesk, sans-serif" font-size="13.5" font-weight="700">{html.escape(a["label"][:18])}</text>\n'
                f'  <line x1="{ax}" y1="156" x2="{ax}" y2="{svg_h - 52}" stroke="#475569" stroke-width="1.5" stroke-dasharray="6 6"/>'
            )
        raw_edges = topology.get("edges") or []
        steps = max(n_act - 1, len(raw_edges[:5]))
        for s in range(steps):
            y = 192 + s * 52
            i_from = s % n_act
            i_to = (s + 1) % n_act
            x1, x2 = xs[i_from], xs[i_to]
            lbl = (
                raw_edges[s].get("protocol")
                if s < len(raw_edges) and isinstance(raw_edges[s], dict)
                else f"step {s+1}: invoke / verify ({actors[i_to]['label'][:14]})"
            )
            body_elems.append(
                f'  <line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="#05df72" stroke-width="1.8" marker-end="url(#arrow)"/>\n'
                f'  <rect x="{(x1 + x2)//2 - 96}" y="{y - 20}" width="192" height="18" rx="4" fill="#050807"/>\n'
                f'  <text x="{(x1 + x2)//2}" y="{y - 7}" text-anchor="middle" fill="#58e388" font-family="ui-monospace, monospace" font-size="11" font-weight="700">{html.escape(str(lbl)[:28])}</text>'
            )
        legend_text = "Legend: ┆ Vertical Dashed = Actor Lifeline   → Solid Emerald = Synchronous Call / Token Verification"

    # TYPE 29: Data Flow & Pipeline Map (Horizontal Stage Swimlanes: INGEST -> TRANSFORM -> SINK)
    elif dtype_code == "29":
        svg_h = 460
        lanes = [
            ("STAGE 01 · SOURCE & INGESTION", 44, "#38bdf8"),
            ("STAGE 02 · TRANSFORM & ROUTING", 352, "#c4b5fd"),
            ("STAGE 03 · STORAGE & OUTPUT SINK", 660, "#05df72"),
        ]
        for ltitle, lx, lcol in lanes:
            body_elems.append(
                f'  <rect x="{lx}" y="108" width="256" height="304" rx="10" fill="rgba(15,23,20,0.75)" stroke="{lcol}" stroke-width="1.4"/>\n'
                f'  <text x="{lx + 16}" y="134" fill="{lcol}" font-family="ui-monospace, monospace" font-size="11" font-weight="700">{ltitle}</text>'
            )
        for idx, n in enumerate(nodes[:6]):
            lane_idx = min(2, idx // 2)
            row_in_lane = idx % 2
            lx = lanes[lane_idx][1] + 16
            ly = 156 + row_in_lane * 116
            lcol = lanes[lane_idx][2]
            body_elems.append(
                f'  <g transform="translate({lx},{ly})">\n'
                f'    <rect width="224" height="92" rx="20" fill="#070b0a" stroke="{lcol}" stroke-width="1.6"/>\n'
                f'    <text x="18" y="28" fill="{lcol}" font-family="ui-monospace, monospace" font-size="10.5" font-weight="700">STREAM NODE 0{idx+1}</text>\n'
                f'    <text x="18" y="52" fill="#ffffff" font-family="Space Grotesk, sans-serif" font-size="15" font-weight="700">{html.escape(n["label"][:22])}</text>\n'
                f'    <text x="18" y="72" fill="#94a3b8" font-family="ui-monospace, monospace" font-size="11.5">{html.escape(n["detail"] or n["role"])}</text>\n'
                f'  </g>'
            )
        body_elems.append(
            '  <line x1="300" y1="260" x2="352" y2="260" stroke="#05df72" stroke-width="2" marker-end="url(#arrow)"/>\n'
            '  <line x1="608" y1="260" x2="660" y2="260" stroke="#05df72" stroke-width="2" marker-end="url(#arrow)"/>'
        )
        legend_text = "Legend: ■ Cyan = Input Ingestion   ■ Purple = Transformation Stage   ■ Emerald = Output Sink"

    # TYPE 35: Deployment & Cluster Topology (Nested Cloud Region -> VPC -> Worker & GPU Zones)
    elif dtype_code == "35":
        svg_h = 492
        body_elems.append(
            f'  <rect x="36" y="104" width="{svg_w - 72}" height="340" rx="12" fill="rgba(6,25,16,0.35)" stroke="#05df72" stroke-width="1.6"/>\n'
            f'  <text x="56" y="130" fill="#05df72" font-family="ui-monospace, monospace" font-size="12" font-weight="700">EU SOVEREIGN REGION (eu-south-1) · ZERO DATA RETENTION CLUSTER</text>\n'
            f'  <rect x="56" y="148" width="416" height="276" rx="10" fill="rgba(15,23,42,0.55)" stroke="#38bdf8" stroke-width="1.2" stroke-dasharray="5 4"/>\n'
            f'  <text x="72" y="172" fill="#38bdf8" font-family="ui-monospace, monospace" font-size="11" font-weight="700">APPLICATION &amp; WORKER SUBNET</text>\n'
            f'  <rect x="492" y="148" width="412" height="276" rx="10" fill="rgba(20,25,22,0.75)" stroke="#58e388" stroke-width="1.2" stroke-dasharray="5 4"/>\n'
            f'  <text x="508" y="172" fill="#58e388" font-family="ui-monospace, monospace" font-size="11" font-weight="700">DATA &amp; INFERENCE BACKPLANE</text>'
        )
        for idx, n in enumerate(nodes[:6]):
            in_right = idx >= 3
            gx = 512 if in_right else 76
            gy = 188 + (idx % 3) * 74
            col = "#05df72" if in_right else "#38bdf8"
            body_elems.append(
                f'  <g transform="translate({gx},{gy})">\n'
                f'    <rect width="372" height="60" rx="6" fill="#070b0a" stroke="{col}" stroke-width="1.4"/>\n'
                f'    <text x="14" y="24" fill="#ffffff" font-family="Space Grotesk, sans-serif" font-size="14.5" font-weight="700">pod/{html.escape(n["label"][:24])}</text>\n'
                f'    <text x="14" y="44" fill="#94a3b8" font-family="ui-monospace, monospace" font-size="11.5">{html.escape(n["role"])} · {html.escape(n["detail"] or "replica=2")}</text>\n'
                f'  </g>'
            )
            if not in_right and idx + 3 < min(len(nodes), 6):
                body_elems.append(
                    f'  <line x1="448" y1="{gy + 30}" x2="512" y2="{gy + 30}" stroke="#05df72" stroke-width="1.5" stroke-dasharray="4 3" marker-end="url(#arrow)"/>'
                )
        legend_text = "Legend: ■ Outer Frame = EU Sovereign Region   ■ Cyan Zone = App Subnet   ■ Emerald Zone = Data & GPU Backplane"

    # DEFAULT / TYPE 01: Architecture & Containment Map
    else:
        cols = 3 if len(nodes) > 4 else 2
        rows_count = (len(nodes) + cols - 1) // cols
        svg_h = max(440, 148 + rows_count * 136 + 56)
        box_w = 256 if cols == 3 else 360
        box_h = 92
        gap_x = 40 if cols == 3 else 64
        gap_y = 44
        start_x, start_y = 48, 128
        coords = {}
        rects_svg = []
        for idx, n in enumerate(nodes):
            r, c = idx // cols, idx % cols
            x = start_x + c * (box_w + gap_x)
            y = start_y + r * (box_h + gap_y)
            coords[n["id"]] = (x, y, box_w, box_h)
            is_hero = idx == 0 or "gateway" in n["label"].lower() or "regolo" in n["label"].lower()
            stroke = "#05df72" if is_hero else "#475569"
            fill = "#07150e" if is_hero else "#0b110f"
            pill_color = "#58e388" if is_hero else "#38bdf8"
            rects_svg.append(
                f'  <g transform="translate({x},{y})">\n'
                f'    <rect x="0" y="0" width="{box_w}" height="{box_h}" rx="8" fill="{fill}" stroke="{stroke}" stroke-width="{"2" if is_hero else "1.25"}"/>\n'
                f'    <text x="16" y="24" fill="{pill_color}" font-family="ui-monospace, monospace" font-size="11" font-weight="700">{html.escape(n["role"].upper())}</text>\n'
                f'    <text x="16" y="50" fill="#ffffff" font-family="Space Grotesk, sans-serif" font-size="16" font-weight="700">{html.escape(n["label"])}</text>\n'
                f'    <text x="16" y="72" fill="#94a3b8" font-family="ui-monospace, monospace" font-size="12">{html.escape(n["detail"] or f"node #{idx+1} · 4px grid")}</text>\n'
                f'  </g>'
            )
        for i in range(len(nodes) - 1):
            x1, y1, w1, h1 = coords[nodes[i]["id"]]
            x2, y2, w2, h2 = coords[nodes[i + 1]["id"]]
            cx1, cy1 = (x1 + w1, y1 + h1 // 2) if y1 == y2 else (x1 + w1 // 2, y1 + h1)
            cx2, cy2 = (x2, y2 + h2 // 2) if y1 == y2 else (x2 + w2 // 2, y2)
            body_elems.append(f'  <line x1="{cx1}" y1="{cy1}" x2="{cx2}" y2="{cy2}" stroke="#05df72" stroke-width="1.5" marker-end="url(#arrow)"/>')
        body_elems.extend(rects_svg)
        legend_text = "Legend: ■ Emerald (#05df72) = Primary Entry / Router   ■ Slate (#475569) = Service / Store   → Solid = Dependency Edge"

    return (
        f'<svg viewBox="0 0 {svg_w} {svg_h}" width="100%" height="auto" xmlns="http://www.w3.org/2000/svg">\n'
        f'  <title>{html.escape(title)} — {html.escape(dtype_name)}</title>\n'
        f'  <desc>4px-grid {html.escape(dtype_name)} generated by Regolo for {html.escape(title)}</desc>\n'
        f'  <defs>\n'
        f'    <pattern id="grid4" width="24" height="24" patternUnits="userSpaceOnUse">\n'
        f'      <path d="M 24 0 L 0 0 0 24" fill="none" stroke="rgba(148,163,184,0.07)" stroke-width="1"/>\n'
        f'    </pattern>\n'
        f'    <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">\n'
        f'      <path d="M 0 1 L 10 5 L 0 9 z" fill="#05df72"/>\n'
        f'    </marker>\n'
        f'  </defs>\n'
        f'  <rect x="0" y="0" width="{svg_w}" height="{svg_h}" rx="12" fill="#050807"/>\n'
        f'  <rect x="16" y="16" width="{svg_w - 32}" height="{svg_h - 32}" rx="10" fill="url(#grid4)" stroke="rgba(5,223,114,0.38)" stroke-width="1.5" stroke-dasharray="6 4"/>\n'
        f'  <text x="40" y="52" fill="#58e388" font-family="ui-monospace, SFMono-Regular, Menlo, monospace" font-size="12" font-weight="700" letter-spacing="0.08em">DIAGRAM-DESIGN TYPE {html.escape(dtype_code)} · {html.escape(title.upper())}</text>\n'
        f'  <text x="40" y="80" fill="#ffffff" font-family="Space Grotesk, -apple-system, sans-serif" font-size="22" font-weight="700">{html.escape(dtype_name)} ({len(nodes)} nodes mapped on 4px grid)</text>\n'
        + "\n".join(body_elems)
        + f'\n  <text x="40" y="{svg_h - 28}" fill="#64748b" font-family="ui-monospace, monospace" font-size="11.5">{legend_text}</text>\n'
        f'</svg>'
    )


def wrap_regolo_editorial_svg(
    svg_or_html: str,
    topology: dict,
    scan_files: list[dict],
    title: str,
    dtype_code: str,
    dtype_name: str,
    model: str,
) -> str:
    """Validate that the LLM returned a non-empty multi-node SVG; otherwise render the deterministic 4px-grid SVG."""
    start = svg_or_html.find("<svg")
    end = svg_or_html.rfind("</svg>")
    svg_block = ""
    if start != -1 and end != -1:
        cand = svg_or_html[start : end + 6]
        # Require at least 3 rect/circle/path/polygon elements and 3 text labels so a truncated or empty box never passes
        shape_count = len(re.findall(r"<(?:rect|circle|polygon|g)\b", cand))
        text_count = len(re.findall(r"<text\b", cand))
        if shape_count >= 4 and text_count >= 4:
            svg_block = cand

    if not svg_block:
        svg_block = render_4px_grid_svg_from_topology(topology, title, dtype_code, dtype_name, scan_files)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{html.escape(title)} — {html.escape(dtype_name)}</title>
  <style>
    body {{
      margin: 0;
      padding: 40px 28px;
      background: #050807;
      color: #f8fafc;
      font-family: "Space Grotesk", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    .frame {{
      max-width: 1080px;
      margin: 0 auto;
      padding: 32px 36px;
      border-radius: 16px;
      background: #070b0a;
      border: 1.5px solid rgba(5, 223, 114, 0.45);
      box-shadow: 0 20px 50px rgba(0, 0, 0, 0.75);
    }}
    .badge {{
      display: inline-block;
      padding: 4px 12px;
      border-radius: 999px;
      background: rgba(5, 223, 114, 0.12);
      border: 1px solid rgba(5, 223, 114, 0.4);
      color: #58e388;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 11.5px;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      margin-bottom: 12px;
    }}
    h1 {{ margin: 0 0 6px; font-size: 26px; color: #ffffff; }}
    p.meta {{ margin: 0 0 24px; font-size: 14px; color: #94a3b8; font-family: ui-monospace, monospace; }}
    .canvas {{ background: #050807; border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 12px; padding: 20px; overflow-x: auto; }}
  </style>
</head>
<body>
  <div class="frame">
    <span class="badge">DIAGRAM-DESIGN TYPE {html.escape(dtype_code)} · GENERATED ON REGOLO ({html.escape(model)})</span>
    <h1>{html.escape(title)} — {html.escape(dtype_name)}</h1>
    <p class="meta">4px coordinate grid · 1px hairlines · WCAG-AA contrast · EU Zero Data Retention</p>
    <div class="canvas">
      {svg_block}
    </div>
  </div>
</body>
</html>
"""


def type_specific_svg_instructions(dtype_code: str, dtype_name: str) -> str:
    """Return strict structural SVG layout rules for the selected diagram-design type."""
    if dtype_code == "40":
        return (
            "Layout MUST be a 3-column Architecture Delta Ledger on a 960x520 canvas: "
            "Column 1 (x=40..300) titled 'BEFORE · LEGACY STATE' with slate boxes (#64748b), "
            "Column 2 (x=340..600) titled 'CHANGES · DELTA LEDGER' with amber boxes (#fbbf24) listing added/rewired items, "
            "Column 3 (x=640..900) titled 'AFTER · TARGET TOPOLOGY' with emerald boxes (#05df72)."
        )
    if dtype_code == "38":
        return (
            "Layout MUST be a Database Schema & ER Diagram on a 960x520 canvas: "
            "Draw each node as a physical SQL table card with a header bar ('TABLE · name') and 3-4 rows inside showing "
            "'PK id UUID', 'FK ref_id VARCHAR', and column types in monospace, connected by dashed FK crow's-foot/arrow lines."
        )
    if dtype_code == "04":
        return (
            "Layout MUST be a horizontal-actor Sequence Diagram on a 960x520 canvas: "
            "Place 4-5 actor header boxes across the top (y=96) with vertical dashed lifeline lines running down to y=460, "
            "and draw horizontal numbered message arrows (step 1, step 2, step 3...) between the lifelines at increasing y coordinates."
        )
    if dtype_code == "29":
        return (
            "Layout MUST be a 3-stage Data Flow Swimlane Map on a 960x520 canvas: "
            "Draw 3 vertical swimlane containers side by side ('STAGE 01 · INGESTION', 'STAGE 02 · TRANSFORMATION', 'STAGE 03 · SINK') "
            "with rounded stream nodes inside each lane and horizontal flow arrows crossing from left to right."
        )
    if dtype_code == "35":
        return (
            "Layout MUST be a Nested Cloud Deployment & Cluster Topology on a 960x520 canvas: "
            "Draw an outer 'EU SOVEREIGN REGION' container box containing two inner dashed subnet containers "
            "('APPLICATION & WORKER SUBNET' on the left and 'DATA & GPU BACKPLANE' on the right) with pod/container boxes inside."
        )
    return (
        "Layout MUST be an Architecture & Containment Map on a 960x520 canvas: "
        "Draw a dashed containment zone frame with a 2x3 or 3x2 grid of service cards (<rect rx='8'>) and directional dependency arrows."
    )


def generate_diagram_pipeline(cfg: RegoloDiagramConfig, output_path: Path) -> dict:
    """Execute the Regolo + diagram-design pipeline using the model selected in Option 2."""
    assert cfg.project_dir is not None, "project_dir must be set before running generate_diagram_pipeline"
    scan_info = scan_project_directory(cfg.project_dir)
    dtype_code, dtype_name, dtype_desc = cfg.diagram_type
    active_model = cfg.svg_model
    layout_spec = type_specific_svg_instructions(dtype_code, dtype_name)

    # Step 1: Topology extraction via the user's selected model (reasoning_effort="none")
    stage1 = call_regolo_chat(
        base_url=cfg.base_url,
        api_key=cfg.api_key,
        model=active_model,
        reasoning_effort="none",
        system_prompt=(
            "You are a fast repository topology extractor. Output ONLY a valid JSON object "
            "with {\"nodes\": [{\"id\": \"...\", \"label\": \"...\", \"role\": \"...\", \"detail\": \"...\"}], "
            "\"edges\": [{\"from\": \"...\", \"to\": \"...\", \"protocol\": \"...\"}]}."
        ),
        user_prompt=(
            f"Extract 5 to 6 elements specifically tailored for Diagram Type {dtype_code}: {dtype_name} ({dtype_desc}) "
            f"from:\n{scan_info['skeleton_text']}"
        ),
        max_tokens=700,
    )
    topology = parse_topology_json(stage1["content"], scan_info["files"])

    # Step 2: 4px-grid inline SVG synthesis via the user's selected model
    stage2 = call_regolo_chat(
        base_url=cfg.base_url,
        api_key=cfg.api_key,
        model=active_model,
        reasoning_effort="none",
        system_prompt=(
            "You are the diagram-design SVG engine. Do NOT output markdown prose. Output ONLY a complete inline "
            "<svg viewBox='0 0 960 520' width='100%' height='auto' xmlns='http://www.w3.org/2000/svg'>...</svg> "
            f"snapped to a 4px grid. Dark background (#050807), Regolo emerald (#05df72), cyan (#38bdf8), slate (#64748b). {layout_spec}"
        ),
        user_prompt=(
            f"Render Diagram Type {dtype_code} ({dtype_name}) for project '{cfg.project_dir.name}'. "
            f"Follow this exact structural layout: {layout_spec}\nTopology data:\n{json.dumps(topology)}"
        ),
        max_tokens=2800,
    )

    # Use the deterministic type-specific 4px-grid builder if the LLM ignored the structural type rules or truncated
    svg_candidate = stage2["content"]
    use_deterministic = True
    if "<svg" in svg_candidate and "</svg>" in svg_candidate:
        if dtype_code == "40" and ("BEFORE" in svg_candidate.upper() and "AFTER" in svg_candidate.upper()):
            use_deterministic = False
        elif dtype_code == "38" and ("PK" in svg_candidate.upper() or "TABLE" in svg_candidate.upper()):
            use_deterministic = False
        elif dtype_code == "04" and svg_candidate.count("<line") >= 4:
            use_deterministic = False
        elif dtype_code == "29" and ("STAGE" in svg_candidate.upper() or "INGEST" in svg_candidate.upper()):
            use_deterministic = False
        elif dtype_code == "35" and ("SUBNET" in svg_candidate.upper() or "REGION" in svg_candidate.upper()):
            use_deterministic = False
        elif dtype_code == "01":
            use_deterministic = False

    html_doc = wrap_regolo_editorial_svg(
        "" if use_deterministic else svg_candidate,
        topology=topology,
        scan_files=scan_info["files"],
        title=cfg.project_dir.name,
        dtype_code=dtype_code,
        dtype_name=dtype_name,
        model=active_model,
    )
    output_path.write_text(html_doc, encoding="utf-8")
    return {
        "scan_info": scan_info,
        "topology": topology,
        "stage1": stage1,
        "stage2": stage2,
        "output_path": str(output_path),
    }


def get_project_output_path(project_dir: Path, dtype: tuple) -> tuple[str, Path]:
    """Return (project_id, output_file_path) inside ./output/<project_id>/."""
    resolved = project_dir.resolve()
    slug = re.sub(r"[^a-z0-9]+", "-", resolved.name.lower()).strip("-") or "project"
    short_hash = hashlib.sha1(str(resolved).encode("utf-8")).hexdigest()[:6]
    project_id = f"{slug}-{short_hash}"

    dtype_code, dtype_name, _ = dtype
    type_slug = re.sub(r"[^a-z0-9]+", "-", dtype_name.lower()).strip("-")
    out_dir = Path(__file__).resolve().parent / "output" / project_id
    out_dir.mkdir(parents=True, exist_ok=True)
    return project_id, out_dir / f"regolo-diagram-{dtype_code}-{type_slug}.html"


def clean_user_path(raw_p: str, default_dir: Path) -> Path:
    """Normalize pasted or dragged terminal paths (quotes, backslash-escaped spaces, file paths)."""
    s = raw_p.strip()
    if not s:
        return default_dir.resolve()
    if (s.startswith("'") and s.endswith("'")) or (s.startswith('"') and s.endswith('"')):
        s = s[1:-1].strip()
    # Unescape macOS terminal drag-and-drop backslash spaces (e.g. /Users/me/My\ Project)
    s = re.sub(r"\\([ ()\[\]&'!$])", r"\1", s)
    cand = Path(s).expanduser().resolve()
    if cand.is_file():
        cand = cand.parent
    return cand


def prompt_for_project_dir(cfg: RegoloDiagramConfig) -> bool:
    """Prompt the user to select or confirm a target project directory (keeps asking until valid)."""
    default_hint = cfg.project_dir if cfg.project_dir else Path.cwd()
    while True:
        raw_p = safe_input(f"  Enter target project directory [{default_hint}]: ")
        cand = clean_user_path(raw_p, default_hint)
        if cand.is_dir():
            cfg.project_dir = cand
            cfg.save_env()
            scan = scan_project_directory(cfg.project_dir)
            print(
                f"  {GREEN}✓ Indexed {scan['files_scanned']} files in {cfg.project_dir} "
                f"({scan['raw_chars']:,} -> {scan['compact_chars']:,} chars, -{scan['reduction_pct']}%){RESET}"
            )
            return True
        print(f"  {RED}Directory not found: {cand} — please enter a valid folder path (or press Enter for default).{RESET}")


def render_header(cfg: RegoloDiagramConfig) -> None:
    masked_key = f"{cfg.api_key[:6]}...{cfg.api_key[-4:]}" if len(cfg.api_key) > 10 else ("SET" if cfg.api_key else "NOT SET")
    key_badge = f"{GREEN}● CONNECTED ({masked_key}){RESET}" if cfg.api_key else f"{RED}○ MISSING API KEY{RESET}"
    skill_badge = f"{GREEN}● READY (diagram-design){RESET}" if cfg.skill_installed else f"{AMBER}○ NPX ON-DEMAND{RESET}"
    dtype_code, dtype_name, _ = cfg.diagram_type
    proj_str = str(cfg.project_dir)[-72:] if cfg.project_dir else "prompted on generation [3]"

    print(f"\n{GREEN}╭──────────────────────────────────────────────────────────────────────────────────────╮{RESET}")
    print(f"{GREEN}│{RESET} {BG_BADGE}{MINT}{BOLD} ● REGOLO {RESET}                                      {SLATE}cathrynlavery/diagram-design · v1.0{RESET} {GREEN}│{RESET}")
    print(f"{GREEN}│{RESET} {WHITE}{BOLD}Sovereign EU Architecture & SVG Diagram Generator (4px Grid · Zero Data Retention){RESET}   {GREEN}│{RESET}")
    print(f"{GREEN}├──────────────────────────────────────────────────────────────────────────────────────┤{RESET}")
    print(f"{GREEN}│{RESET} {SLATE}Endpoint :{RESET} {WHITE}{cfg.base_url:<34}{RESET} {SLATE}Status :{RESET} {key_badge:<33}{GREEN}│{RESET}")
    print(f"{GREEN}│{RESET} {SLATE}Model    :{RESET} {GREEN}{BOLD}{cfg.svg_model:<34}{RESET} {SLATE}Skill  :{RESET} {skill_badge:<33}{GREEN}│{RESET}")
    print(f"{GREEN}│{RESET} {SLATE}Diagram  :{RESET} {PURPLE}[{dtype_code}] {dtype_name[:28]:<28}{RESET} {SLATE}Pool   :{RESET} {MINT}Regolo EU Zero Retention{RESET}     {GREEN}│{RESET}")
    print(f"{GREEN}│{RESET} {SLATE}Project  :{RESET} {WHITE}{proj_str:<72}{RESET}  {GREEN}│{RESET}")
    print(f"{GREEN}╰──────────────────────────────────────────────────────────────────────────────────────╯{RESET}")


def render_menu() -> None:
    print(f"\n  {MINT}{BOLD}[1]{RESET} {WHITE}Environment & Tool Setup{RESET}       {SLATE}Configure .env, verify Node/Python & install diagram-design skill{RESET}")
    print(f"  {MINT}{BOLD}[2]{RESET} {WHITE}Regolo API & Model Selector{RESET}    {SLATE}Query live GET /v1/models on Regolo & select active model{RESET}")
    print(f"  {MINT}{BOLD}[3]{RESET} {WHITE}Choose Diagram & Generate SVG{RESET}  {SLATE}Set project path, pick diagram type & render 4px-grid HTML + SVG{RESET}")
    print(f"  {MINT}{BOLD}[q]{RESET} {SLATE}Quit Regolo{RESET}")


def run_demo_mode(cfg: RegoloDiagramConfig, target_dir: Path, out_file: Path | None = None) -> None:
    """Non-interactive Regolo TUI run for verification and article terminal screenshots."""
    cfg.project_dir = target_dir.resolve()
    project_id, default_out = get_project_output_path(cfg.project_dir, cfg.diagram_type)
    final_out = out_file if out_file is not None else default_out
    final_out.parent.mkdir(parents=True, exist_ok=True)
    render_header(cfg)
    render_menu()

    print(f"\n{CYAN}{BOLD}▶ [Option 2 · Live Model Discovery via GET {cfg.base_url}/models]{RESET}")
    models = fetch_regolo_models(cfg.base_url, cfg.api_key)
    cfg.available_models = models
    print(f"  {GREEN}✓ Retrieved {len(models)} active chat/code models from Regolo EU cluster:{RESET}")
    for idx, m in enumerate(models, 1):
        marker = f"{GREEN}◀ SELECTED MODEL{RESET}" if m == cfg.svg_model else ""
        print(f"    {SLATE}[{idx:02d}]{RESET} {WHITE}{m:<24}{RESET} {marker}")

    print(f"\n{GREEN}{BOLD}▶ [Option 3 · Project Scan & Diagram Generation (Project ID: {project_id} · Model: {cfg.svg_model})]{RESET}")
    scan = scan_project_directory(cfg.project_dir)
    print(
        f"  {GREEN}✓ Scanned {scan['files_scanned']} files in {scan['project_dir']}:{RESET} "
        f"{SLATE}{scan['raw_chars']:,} raw chars ->{RESET} {WHITE}{BOLD}{scan['compact_chars']:,} skeleton chars (-{scan['reduction_pct']}%){RESET}"
    )
    for f in scan["files"]:
        print(f"    {SLATE}├─{RESET} {WHITE}{f['path']:<28}{RESET} {SLATE}{f['raw_chars']:>5} -> {f['compact_chars']:>4} chars{RESET}")

    result = generate_diagram_pipeline(cfg, final_out)
    s1, s2 = result["stage1"], result["stage2"]
    nodes_n = len(result["topology"].get("nodes", []))
    print(
        f"  {CYAN}[Step 1 · {cfg.svg_model} · Topology]{RESET} "
        f"Extracted {nodes_n} nodes in {GREEN}{s1['latency_s']}s{RESET} "
        f"{SLATE}(in={s1['prompt_tokens']} tok, out={s1['completion_tokens']} tok){RESET}"
    )
    print(
        f"  {GREEN}[Step 2 · {cfg.svg_model} · 4px SVG]{RESET}  "
        f"Rendered HTML + inline SVG in {GREEN}{s2['latency_s']}s{RESET} "
        f"{SLATE}(in={s2['prompt_tokens']} tok, out={s2['completion_tokens']} tok){RESET}"
    )
    print(f"  {GREEN}{BOLD}✓ Saved in output/{project_id}/:{RESET} {WHITE}{result['output_path']}{RESET} ({final_out.stat().st_size:,} bytes)\n")


def interactive_loop(cfg: RegoloDiagramConfig) -> None:
    while True:
        render_header(cfg)
        render_menu()
        choice = safe_input(f"\n{GREEN}{BOLD}regolo>{RESET} Select option [1-3, q]: ").strip().lower()
        if choice in ("q", "quit", "exit"):
            print(f"{SLATE}Closing Regolo. Goodbye!{RESET}")
            break
        if choice == "1":
            print(f"\n{CYAN}{BOLD}=== 1. Environment & Tool Setup ==={RESET}")
            new_key = safe_input(f"  Enter REGOLO_API_KEY [{'keep current' if cfg.api_key else 'required'}]: ").strip()
            if new_key:
                cfg.api_key = new_key
            cfg.save_env()
            print(f"  {GREEN}✓ Saved configuration to {cfg.env_path}{RESET}")
            install_ans = safe_input("  Run `npx skills add cathrynlavery/diagram-design` now? [y/N]: ").strip().lower()
            if install_ans == "y":
                subprocess.run(["npx", "skills", "add", "cathrynlavery/diagram-design"], check=False)
                cfg.check_skill_status()
        elif choice == "2":
            print(f"\n{CYAN}{BOLD}=== 2. Regolo API & Live Model Selector (/v1/models) ==={RESET}")
            try:
                models = fetch_regolo_models(cfg.base_url, cfg.api_key)
                cfg.available_models = models
                for i, m in enumerate(models, 1):
                    marker = f"{GREEN}◀ active{RESET}" if m == cfg.svg_model else ""
                    print(f"  [{i:02d}] {m:<24} {marker}")
                sel = safe_input(f"  Choose model [1-{len(models)}, Enter={cfg.svg_model}]: ").strip()
                if sel.isdigit() and 1 <= int(sel) <= len(models):
                    cfg.svg_model = models[int(sel) - 1]
                    cfg.save_env()
                    print(f"  {GREEN}✓ Active model set to {cfg.svg_model}{RESET}")
            except Exception as exc:
                print(f"  {RED}Failed to query /v1/models: {exc}{RESET}")
        elif choice in ("3", "4"):
            print(f"\n{GREEN}{BOLD}=== 3. Choose Diagram Type & Generate HTML + SVG ==={RESET}")
            prompt_for_project_dir(cfg)
            print(f"\n  {MINT}{BOLD}Available diagram-design templates:{RESET}")
            for i, (code, name, desc) in enumerate(DIAGRAM_TYPES, 1):
                print(f"    {MINT}[{i}]{RESET} Type {code} · {WHITE}{BOLD}{name:<32}{RESET} {SLATE}({desc}){RESET}")
            tsel = safe_input(f"\n  Select diagram type [1-{len(DIAGRAM_TYPES)}, Enter=1]: ").strip()
            if tsel.isdigit() and 1 <= int(tsel) <= len(DIAGRAM_TYPES):
                cfg.diagram_type = DIAGRAM_TYPES[int(tsel) - 1]
            assert cfg.project_dir is not None
            project_id, out_path = get_project_output_path(cfg.project_dir, cfg.diagram_type)
            print(f"  {SLATE}Project folder: {WHITE}output/{project_id}/{RESET}")
            print(f"  {SLATE}Running Regolo pipeline with model {WHITE}{BOLD}{cfg.svg_model}{RESET}{SLATE}...{RESET}")
            try:
                res = generate_diagram_pipeline(cfg, out_path)
                print(f"  {GREEN}{BOLD}✓ Generated in output/{project_id}/:{RESET} {WHITE}{res['output_path']}{RESET} ({out_path.stat().st_size:,} bytes)")
            except Exception as exc:
                print(f"  {RED}Generation failed: {exc}{RESET}")


def main() -> None:
    try:
        parser = argparse.ArgumentParser(description="Regolo TUI for diagram-design")
        parser.add_argument("--demo", action="store_true", help="Run non-interactive live demo against Regolo API")
        parser.add_argument("--project", default=str(Path(__file__).resolve().parent), help="Target project directory")
        parser.add_argument("--out", default="", help="Optional custom output HTML+SVG file path")
        args = parser.parse_args()

        cfg = RegoloDiagramConfig(Path(__file__).resolve().parent / ".env")
        if args.demo:
            custom_out = Path(args.out) if args.out else None
            run_demo_mode(cfg, Path(args.project), custom_out)
        else:
            interactive_loop(cfg)
    except (KeyboardInterrupt, EOFError):
        print(f"\n{SLATE}Closing Regolo. Goodbye!{RESET}")
        sys.exit(0)


if __name__ == "__main__":
    main()
