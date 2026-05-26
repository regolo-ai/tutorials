# Context Engineered Agent

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Ollama Compatible](https://img.shields.io/badge/Ollama-Compatible-black)](https://ollama.com)
[![Runnable Code](https://img.shields.io/badge/Code-Runnable%20Examples-1F9D55)](https://github.com)

This repository contains all the code from the article [Context Engineering Tutorial: Build Lightweight Local AI Agents in Python](https://regolo.ai/context-engineering-tutorial-build-lightweight-local-ai-agents-in-python/).

This project is a compact demonstration of **context engineering** for long-horizon AI agents.

The goal is to show how an agent can avoid prompt stuffing by managing its working context dynamically at runtime. Instead of loading entire files, full histories, tool logs, and persistent state into every LLM call, the agent retrieves only the information needed for the current step, stores durable findings externally, and delegates heavier analysis to an isolated sub-agent.

## Why This Exists

Many agent prototypes solve complex tasks by pushing more and more data into the prompt. That approach is simple, but it creates three serious problems:

- **Context rot:** as the prompt grows, important information becomes harder for the model to retrieve reliably.
- **Latency:** larger prompts increase time to first token and overall generation time.
- **Cost waste:** sending repeated, redundant context on every step burns tokens without adding signal.

This project demonstrates a different pattern: the orchestrator treats the LLM context window as a limited attention budget. Every runtime step should justify the tokens it adds.

## Core Strategies Demonstrated

### 1. Just-In-Time Data Ingestion

The agent does not preload the full CSV into the prompt. It first lists available files, inspects metadata, then reads a small chunk only when needed.

Implemented in:

- `ToolManager.list_files()`
- `ToolManager.get_file_metadata()`
- `ToolManager.read_file_chunk()`

### 2. Active Compaction

The agent monitors the estimated size of its message history. When the configured context threshold is exceeded, it summarizes older interaction history and keeps only compact state plus recent turns.

Implemented in:

- `ContextEngineAgent._ensure_compact_context()`
- `MAX_CONTEXT_TOKENS` in `config.py`

The current token counter is intentionally simple because this is a local demo. In production, this should use the tokenizer of the target model.

### 3. Structured External Memory

Important findings are written to `data/memory.json` instead of being kept only in the chat history.

For the default task, the agent computes the top active user and persists it as:

```json
{
  "top_active_user": "USR_9201"
}
```

Implemented in:

- `ToolManager.write_note()`
- `ToolManager.read_notes()`

### 4. Sub-Agent Isolation

Revenue aggregation is delegated to an isolated sub-agent with its own short-lived context. The sub-agent can inspect the CSV and run the revenue aggregation tool, then returns only a compact result to the main orchestrator.

Implemented in:

- `ContextEngineAgent._run_isolated_sub_agent()`
- `ToolManager.aggregate_revenue()`

This keeps the main agent context smaller and prevents heavy intermediate reasoning or raw data from polluting the main thread.

## Project Structure

```text
.
├── agent.py              # Main orchestration loop, guardrails, compaction, sub-agent runtime
├── config.py             # Context and local LLM configuration
├── llm_client.py          # Ollama client with deterministic fallback behavior
├── main.py               # Demo entry point
├── requirements.txt      # Runtime dependency notes
├── tools.py              # File, memory, and deterministic CSV analysis tools
├── ui.py                 # Terminal UI helpers
└── data/
    ├── memory.json       # External structured notes
    └── user_activity.csv # Demo CSV dataset
```

## How The Demo Runs

The default task in `main.py` is:

```text
Analyze 'user_activity.csv' to locate the top active user, write it to persistent notes, then run a sub-agent to compute the aggregated transaction revenues.
```

At runtime, the agent performs this sequence:

1. Shows the terminal UI header and current context load.
2. Lists available files in `data/`.
3. Reads CSV metadata instead of loading the whole file.
4. Reads a small CSV chunk for evidence.
5. Computes the top active user with a deterministic streaming tool.
6. Writes the verified top user to `data/memory.json`.
7. Spawns an isolated sub-agent for transaction revenue aggregation.
8. Produces a final report only after all required runtime steps have completed.

The final result should look like this:

```text
Top active user: USR_9201
Total transaction revenue: 1068.99 USD
```

## Runtime Guardrails

The orchestrator tracks which tools are required for the task. If the LLM attempts to produce a final answer before completing the required runtime evidence-gathering steps, the answer is rejected and the model is asked to continue with the missing tool call.

This matters because the project is not trying to demonstrate a model that can guess plausible answers. It is demonstrating an agent that must earn its final answer through inspectable runtime actions.

Implemented in:

- `ContextEngineAgent._infer_required_tools()`
- `ContextEngineAgent._missing_required_tools()`
- `ContextEngineAgent._tool_succeeded()`

## LLM Backend

By default, the project points to a local Ollama server:

```python
OLLAMA_MODEL = "llama3"
OLLAMA_URL = "http://localhost:11434/api/chat"
```

If Ollama is unavailable, `llm_client.py` falls back to deterministic mock behavior. The fallback is intentionally implemented as a small state machine so the demo still follows the context-engineered workflow step by step.

## Prerequisites

- Python 3.10+
- **One of the following LLM backends:**
  - [Ollama](https://ollama.com) running locally with a model pulled (e.g. `ollama pull llama3`)
  - Any OpenAI-compatible endpoint via `OLLAMA_URL` override in `config.py`

No external dependencies beyond the Python standard library are required.

## Configuration

The runtime parameters live in `config.py`:

```python
MAX_CONTEXT_TOKENS = 1500  # threshold that triggers active compaction
OLLAMA_MODEL = "llama3"
OLLAMA_URL   = "http://localhost:11434/api/chat"
```

Change `OLLAMA_MODEL` and `OLLAMA_URL` to point at a different local server or model.

## Quick Start

```bash
# Clone and enter the project
cd context-engineered-agent

# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# No pip install needed — only stdlib is used
python main.py
```

To verify syntax without running the full demo:

```bash
python -m py_compile main.py agent.py tools.py llm_client.py ui.py
```

## What This Project Is Not

This is not a production-grade agent framework. It is a focused engineering demo.

Known simplifications:

- Token counting uses a rough character-based heuristic.
- The CSV tools support the demo schema, not arbitrary analytical workloads.
- External memory is a simple JSON file, not a database or vector store.
- The sub-agent is local and sequential, not a distributed execution system.
- The fallback LLM behavior is deterministic so the demo remains runnable without Ollama.

## Main Takeaway

The important idea is not the CSV analysis itself. The important idea is the architecture:

**Keep the active context small, high-signal, and task-specific. Move raw data access, durable memory, and heavy intermediate analysis outside the main prompt whenever possible.**

---

## Related Article

- [Context Engineering Tutorial: Build Lightweight Local AI Agents in Python](https://regolo.ai/context-engineering-tutorial-build-lightweight-local-ai-agents-in-python/)

---

## Powered by Regolo

Run this agent against cloud GPU inference instead of a local Ollama server — no hardware required.

[Get Started](https://regolo.ai) · [**Free Trial**](https://regolo.ai/pricing)

Questions? [Open an issue](https://github.com/Regolo-AI/tutorials/issues) or join our [Discord](https://discord.gg/wHxwWCC8).