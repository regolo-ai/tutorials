# Context Engineering for Agents 101 — Harness Kit for OpenCode, Claude Code & Codex

Runnable Python harness modules and a unified MCP stdio server (`regolo_harness_mcp.py`) tested against `https://api.regolo.ai/v1`.

## What's Inside

1. **`piece1_progressive_skills.py` (Part 1 — Attention Budgets & Progressive Disclosure)**
   - Scans `~/.claude/skills` or `~/.agents/skills`, replaces full `SKILL.md` preloading (`38,843` tokens) with a 1-line-per-skill index (`327` tokens, **-99.2%**), and formats tool responses with `response_format="concise"` (**-71.1%** tokens).
2. **`piece2_retrieve_offload_delegate.py` (Part 2 — Retrieve, Offload, Delegate)**
   - Runs semantic search on `Qwen3-Embedding-8B`, offloads oversized tool dumps (`>1,200` chars) to `.harness/large_tool_results/`, and delegates file reading to an isolated sub-agent routed via `brick-v1-beta` (served by `qwen3.5-9b`, **-99.0%** noise kept out of the main agent's window).
3. **`piece3_compaction_and_cache_memory.py` (Part 3 — Reversible Compaction & Cache-Safe Memory)**
   - Archives full transcripts to `.harness/conversation_history/<session_id>.md` before compacting older turns via `brick-v1-beta` (**-92.0%** history tokens), and orders `messages` so static `AGENTS.md` sits in the cached prefix while dynamic search hits go at the tail (**98.0%** prefix cache hit rate vs **0.0%** when injected into the system prompt).
4. **`piece4_long_running_harness.py` (Part 4 — Initializer, Context-Reset Worker & Evaluator Loop)**
   - Multi-session loop driven by `feature_list.json` and `progress.txt`. The Worker (`qwen3.8-27b`) starts each feature in a clean Context Reset window (`269` prompt tokens), and an independent Evaluator (`brick-v1-beta`) audits unit tests before flipping `"passes": true`.
5. **`regolo_harness_mcp.py` — Drop-in MCP Server for OpenCode, Claude Code, and Codex CLI**

## Quick Validation

```bash
export REGOLO_API_KEY="your-regolo-key"
python3 piece1_progressive_skills.py --self-test
python3 piece2_retrieve_offload_delegate.py --self-test
python3 piece3_compaction_and_cache_memory.py --self-test
python3 piece4_long_running_harness.py --self-test
python3 regolo_harness_mcp.py --self-test
```

## Plug Into Your Daily Coding Agent

### 1. OpenCode (`~/.config/opencode/opencode.json`)
```json
{
  "mcp": {
    "regolo-context-harness": {
      "type": "local",
      "command": ["python3", "/ABSOLUTE/PATH/TO/regolo_harness_mcp.py"],
      "environment": {
        "REGOLO_API_KEY": "{env:REGOLO_API_KEY}"
      }
    }
  }
}
```

### 2. Claude Code
```bash
claude mcp add regolo-context-harness -e REGOLO_API_KEY="$REGOLO_API_KEY" -- python3 /ABSOLUTE/PATH/TO/regolo_harness_mcp.py
```

### 3. Codex CLI (`~/.codex/config.toml`)
```toml
[mcp_servers.regolo_context_harness]
command = "python3"
args = ["/ABSOLUTE/PATH/TO/regolo_harness_mcp.py"]
env = { "REGOLO_API_KEY" = "your-regolo-key" }
```
