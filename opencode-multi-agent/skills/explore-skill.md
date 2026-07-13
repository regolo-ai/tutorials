---
name: explore
description: Use the explore subagent for fast, read-only codebase navigation — finding files by name, searching code by content, and answering "where is X" / "what does Y do" questions. Trigger on requests like "find where auth is handled", "locate the config loader", "what calls this function", or any quick codebase lookup that should not spin up a large model.
---

# Explore skill

The explore agent is a fast codebase navigator. It does **not** edit files and does **not** run bash (except read-only commands if needed).

## When to use
- "Where is feature X implemented?"
- "Find files matching pattern Y."
- "What does function Z do?"
- "Which modules depend on this?"
- Any quick structural question before delegating real work.

## Thoroughness levels
- **quick** — basic file lookup, 1–2 searches.
- **medium** — multiple searches, read a few files.
- **very thorough** — comprehensive search across locations and naming conventions.

## Rules
- Return concise, factual answers with file paths and line numbers.
- Prefer `glob`/`grep` over `ls`/`find` for speed.
- No edits, no writes, no state changes.

## Model
`regolo/qwen3.5-9b` — small and fast, ideal for cheap lookups where deep reasoning is unnecessary.
