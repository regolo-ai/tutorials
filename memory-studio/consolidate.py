#!/usr/bin/env python3
"""Write Memory Studio's wiki pages and handoff brief into a real project, without the web app (stdlib only).

  export REGOLO_API_KEY=...          # or put it in a .env file and pass --env-file
  python3 consolidate.py --project ~/code/my-app --out ~/code/my-app/docs/memory

The pages land in <out>/decisions/, <out>/procedures/ and <out>/handoffs/handoff-<template>.md. Commit them, and
point your agents' instruction files (CLAUDE.md, AGENTS.md, .cursor/rules) at the handoff. Same scan, redaction and
routing as the web app: wiki consolidation on brick-v1-beta, the handoff brief on --model.
"""
import argparse
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "memory_wizard"))
import server as S  # noqa: E402


def read_key(env_file: str | None) -> str:
    key = os.environ.get("REGOLO_API_KEY", "").strip()
    if not key and env_file:
        m = re.search(r'^REGOLO_API_KEY="?([^"\n]+)', Path(env_file).expanduser().read_text(), re.M)
        key = m.group(1).strip() if m else ""
    if not key:
        sys.exit("Set REGOLO_API_KEY or pass --env-file with a REGOLO_API_KEY line.")
    return key


def main():
    p = argparse.ArgumentParser(description="Write wiki pages and a handoff brief for the next coding agent into a project.")
    p.add_argument("--project", required=True, help="project folder to read (its .gitignore is applied)")
    p.add_argument("--out", help="where to write the pages (default: <project>/docs/memory)")
    p.add_argument("--model", default=S.PREFERRED_MODEL, help=f"model for the handoff brief (default: {S.PREFERRED_MODEL})")
    p.add_argument("--template", default="claude-to-opencode", choices=[c for c, _, _ in S.T.HARNESS_PAIRS])
    p.add_argument("--no-routing", action="store_true", help="run every step on --model instead of the router")
    p.add_argument("--env-file", help="file with a REGOLO_API_KEY= line")
    a = p.parse_args()

    key = read_key(a.env_file)
    info = S.inspect_project(a.project)
    out = Path(a.out).expanduser() if a.out else Path(info["root"]) / "docs" / "memory"
    project = re.sub(r"[^\w .-]", "", info["name"])[:60] or "project"
    print(f"{info['total']} files after ignore rules ({info['mode']}), {len(info['selected'])} sent as a compressed skeleton")

    r = S.execute_run(key, a.model, a.template, project, info, routed=not a.no_routing, compact=True,
                      report=lambda *_: None, wiki_dir=out)
    for s in r["stages"]:
        served = f" -> {s['served_model']}" if s["served_model"] != s["model"] else ""
        cost = "n/a" if s["cost_eur"] is None else f"EUR {s['cost_eur']:.4f}"
        print(f"  {s['stage']}: {s['model']}{served}, {s['prompt_tokens']:,} in / {s['completion_tokens']:,} out, {s['latency_s']} s, {cost}")
    if r["router_retry"]:
        print(f"  {S.ROUTER_MODEL} returned unusable pages, so consolidation was repeated on {a.model}.")
    t = r["totals"]
    print(f"Total: {t['total_tokens']:,} tokens, {t['wall_s']} s" + ("" if t["cost_eur"] is None else f", EUR {t['cost_eur']:.4f}"))
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
