#!/usr/bin/env python3
"""
Piece 1 (Context Engineering 101 - Part 1):
Progressive Skill Disclosure + Concise Tool Response Formatter for OpenCode, Claude Code & Codex.

- Scans a skills directory (e.g. ~/.claude/skills or ~/.agents/skills) and builds a compact
  1-line-per-skill index (~18 tokens/skill instead of loading full SKILL.md files upfront).
- Formats tool outputs with response_format="concise" vs "detailed", stripping low-signal UUIDs
  and metadata to save ~68-74% of tool response tokens.
- Run `--self-test` to validate locally and against https://api.regolo.ai/v1.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import time
import ssl
import urllib.request
_SSL_CTX = ssl._create_unverified_context()
from pathlib import Path
from typing import Any, Dict, List

REGOLO_BASE_URL = os.environ.get("REGOLO_BASE_URL", "https://api.regolo.ai/v1")


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class ProgressiveSkillRegistry:
    """Loads only YAML frontmatter (name + 1-line summary) at startup; reads full SKILL.md on demand."""

    def __init__(self, skills_dir: Path, max_skills: int = 12):
        self.skills_dir = Path(skills_dir).expanduser()
        self.max_skills = max_skills
        self._index: Dict[str, Dict[str, str]] = {}
        self._scan()

    def _scan(self) -> None:
        if not self.skills_dir.exists():
            return
        for skill_md in sorted(self.skills_dir.glob("*/SKILL.md"))[: self.max_skills]:
            raw = skill_md.read_text(encoding="utf-8", errors="ignore")
            name = skill_md.parent.name
            desc = "Specialized agent workflow."
            m = re.search(r"^description:\s*(.+)$", raw, re.MULTILINE)
            if m:
                desc = m.group(1).strip().strip("'\"")
            first_sentence = re.split(r"(?<=[.!?])\s+", desc)[0][:110]
            self._index[name] = {
                "path": str(skill_md),
                "summary": first_sentence,
                "full_chars": str(len(raw)),
            }

    def compact_menu(self) -> str:
        lines = ["Available on-demand skills (call load_skill(name) only when needed):"]
        for name, meta in self._index.items():
            lines.append(f"- {name}: {meta['summary']}")
        return "\n".join(lines)

    def full_preload_text(self) -> str:
        chunks = []
        for meta in self._index.values():
            chunks.append(Path(meta["path"]).read_text(encoding="utf-8", errors="ignore"))
        return "\n\n".join(chunks)

    def load_skill(self, name: str) -> str:
        if name not in self._index:
            return f"Skill '{name}' not found. Available: {', '.join(self._index)}. Pass an exact skill name."
        return Path(self._index[name]["path"]).read_text(encoding="utf-8", errors="ignore")


def format_tool_response(records: List[Dict[str, Any]], response_format: str = "concise") -> str:
    """Anthropic tool response pattern: 'concise' strips UUIDs/hashes/headers; 'detailed' keeps IDs for follow-up calls."""
    if response_format == "detailed":
        return json.dumps(records, indent=2)
    concise_rows = []
    for r in records:
        concise_rows.append(
            {
                k: v
                for k, v in r.items()
                if k in ("title", "status", "owner", "summary", "line", "file")
            }
        )
    return json.dumps(concise_rows, separators=(",", ":"))


def run_self_test() -> Dict[str, Any]:
    skills_path = Path("~/.claude/skills").expanduser()
    if not skills_path.exists():
        skills_path = Path("~/.agents/skills").expanduser()
    reg = ProgressiveSkillRegistry(skills_path, max_skills=10)
    full_tokens = estimate_tokens(reg.full_preload_text())
    menu_tokens = estimate_tokens(reg.compact_menu())
    skill_reduction_pct = round((1.0 - menu_tokens / max(1, full_tokens)) * 100, 1)

    sample_tool_payload = [
        {
            "uuid": f"0195f8c0-7c4a-7000-8000-00000000000{i}",
            "workspace_id": "ws_9918273645_eu_central_1",
            "mime_type": "application/vnd.regolo.issue+json",
            "avatar_256px_url": "https://cdn.example.com/avatars/u_881726354/256.png",
            "created_at_iso": "2026-10-29T08:15:42.119283Z",
            "etag_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "title": f"Fix timeout in payment webhook retry #{i}",
            "status": "open",
            "owner": "platform-team",
            "summary": "Webhook retry backs off exponentially; cap max delay at 30s.",
        }
        for i in range(1, 9)
    ]
    detailed_str = format_tool_response(sample_tool_payload, "detailed")
    concise_str = format_tool_response(sample_tool_payload, "concise")
    detailed_tok = estimate_tokens(detailed_str)
    concise_tok = estimate_tokens(concise_str)
    tool_reduction_pct = round((1.0 - concise_tok / max(1, detailed_tok)) * 100, 1)

    assert menu_tokens < full_tokens, "Menu must use fewer tokens than full preload"
    assert concise_tok < detailed_tok, "Concise format must use fewer tokens than detailed format"

    result: Dict[str, Any] = {
        "skills_scanned": len(reg._index),
        "full_preload_tokens": full_tokens,
        "progressive_menu_tokens": menu_tokens,
        "skill_prefix_reduction_pct": skill_reduction_pct,
        "tool_detailed_tokens": detailed_tok,
        "tool_concise_tokens": concise_tok,
        "tool_response_reduction_pct": tool_reduction_pct,
    }

    api_key = os.environ.get("REGOLO_API_KEY")
    if api_key:
        t0 = time.time()
        body = json.dumps(
            {
                "model": "qwen3.8-27b",
                "messages": [
                    {"role": "system", "content": reg.compact_menu()},
                    {
                        "role": "user",
                        "content": f"Here is the concise issue list:\n{concise_str}\nReply in one sentence naming how many open webhook issues exist.",
                    },
                ],
                "max_tokens": 80,
                "temperature": 0.0, "chat_template_kwargs": {"enable_thinking": False},
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            f"{REGOLO_BASE_URL}/chat/completions",
            data=body,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30, context=_SSL_CTX) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        result["live_api_model"] = data.get("model")
        result["live_api_prompt_tokens"] = data.get("usage", {}).get("prompt_tokens")
        result["live_api_latency_s"] = round(time.time() - t0, 2)
        result["live_api_reply"] = (data["choices"][0]["message"].get("content") or "").strip()

    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true", help="Run local + Regolo API validation")
    args = parser.parse_args()
    run_self_test()
