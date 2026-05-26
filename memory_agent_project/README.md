# Stateful Agent Memory & Dreaming Pipeline

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Powered by Regolo](https://img.shields.io/badge/Powered%20by-Regolo%20GPU-green)](https://regolo.ai)

This repository contains all the code from the article [Implementing Stateful AI Agents: How to Build Anthropic's Memory Store and Dreaming Architecture in Python](https://regolo.ai/implementing-stateful-ai-agents-how-to-build-anthropics-memory-store-and-dreaming-architecture-in-python/) — ready to run locally or on cloud GPU.

This project implements a local, stateful three-layer memory architecture for AI agents. Inspired by Anthropic's memory system, it decouples live, interactive runtime execution from background contextual database consolidation.

Supports two LLM backends selectable at startup:
- **OLLAMA** — runs fully locally via Ollama, no API key required.
- **Regolo** — cloud-hosted inference via [regolo.ai](https://regolo.ai), free tier available.

The CLI uses colored step-by-step output, shows which memory files were loaded, and lists the files produced by the Dream cycle.

---

### Get Started Free

Sign up for Regolo and start for free with Pay as You Go pricing:

[Get Started](https://regolo.ai) · [**REGOLO FREE TRIAL**](https://regolo.ai/pricing)

### Questions? Open an issue or join our [Discord](https://discord.gg/wHxwWCC8)

---

## Architecture Overview

```
                      ┌──────────────────┐
                      │    User Input    │
                      └────────┬─────────┘
                               │
                    ┌──────────▼──────────┐
                    │    Session Agent    │
                    └────┬───────────▲────┘
                         │           │
            Writes Event │           │ Reads Context
            Logs         │           │
                    ┌────▼───────────┴────┐
                    │ Mounted Workspace  │◄──┐
                    │ (data/input_memory) │   │
                    └──────────┬──────────┘   │
                               │              │ Replaces and
                               │ Consolidated │ Swaps In
                               │ Async        │
                    ┌──────────▼──────────┐   │
                    │   Dreaming Engine   │───┘
                    │ (data/output_memory)│
                    └─────────────────────┘
```

1. **Session Layer (Ephemeral):** Handles active user interactions. It constructs a context window by reading files from a mounted workspace.
2. **Memory Store (Persistent):** Local directories containing raw Markdown data. The agent reads from this store to retrieve facts and appends event logs during session execution.
3. **Dreaming Layer (Asynchronous):** An offline consolidation process. It reads raw transaction logs and messy notes, merges duplicates, resolves factual contradictions, and writes an optimized, indexed representation to the output store.

---

## Directory Structure

Running the build script generates the following file layout:

```
memory_agent_project/
├── data/
│   ├── input_memory/     # Mounted live session storage directory
│   │   └── sessions.md   # Active agent notes and events
│   ├── transcripts/      # Raw historical session transaction logs
│   │   ├── session_1.json
│   │   └── session_2.json
│   └── output_memory/    # Consolidated memory written by the Dreaming routine
├── src/
│   ├── __init__.py
│   ├── agent.py          # Session Agent managing active memory lookups
│   ├── console.py        # Colored terminal output helpers
│   ├── dream.py          # Asynchronous Dreaming and index build operations
│   ├── llm.py            # LocalLLM (Ollama) and RegoloLLM clients
│   └── memory_store.py   # Index-aware filesystem memory abstraction
├── .env                  # API key store — created automatically on first Regolo run
├── dream_job.py          # Offline Dream-only entry point for scheduled consolidation
├── main.py               # Application entry point and interactive provider menu
└── requirements.txt      # Project dependencies
```

---

## Installation and Execution

### 1. Generate the Project Structure
Run the bootstrapping script to programmatically build directories, populate code files, seed mock transaction files, and bundle the output into a local `.zip` file:

```bash
python create_project.py
```

### 2. Unpack the Project
You can navigate directly into the auto-generated project folder:

```bash
cd memory_agent_project
```

*(Alternatively, extract the `agent_memory_project.zip` file generated in your root directory).*

### 3. Install Dependencies
Install the required packages. This implementation relies on the standard `requests` library to interface with your local LLM engine:

```bash
pip install -r requirements.txt
```

### 4. Configure Your LLM Backend

On startup, the script presents an interactive menu to select the LLM provider:

```
====================================================
  Memory Agent — Select LLM Provider
====================================================

  [1]  OLLAMA   (local, no API key required)
  [2]  Regolo  (cloud, free with API key)

Enter 1 or 2:
```

#### Option 1 — OLLAMA (local)
Ensure Ollama is running on your machine and pull the default model:

```bash
ollama pull llama3
```

*If Ollama is offline or unreachable, the system automatically falls back to a deterministic mock response, so the full pipeline executes without any external dependency.*

#### Option 2 — Regolo (cloud)

Regolo is an OpenAI-compatible cloud inference API with a free Pay-as-You-Go tier.

1. Select **Regolo** from the startup menu.
2. Choose a model from the list fetched live from `api.regolo.ai/v1/models`.
3. To get a free API key:
   - Go to **https://regolo.ai/pricing**
   - Click **"Pay as You Go"** and sign up (no credit card required)
  - Copy your key from the dashboard

4. Paste the key directly into the terminal when prompted. The script creates `.env` for you:

  ```
  REGOLO_API_KEY=<your_key>
  ```

On later runs, the script reads the key from `.env` automatically.

> The `.env` file is listed in `.gitignore` and will never be committed to version control.

### 5. Run the Execution Pipeline
Run the main script to launch the provider menu, execute an active user session, register real-time logs, and trigger a simulated background dreaming process:

```bash
python main.py
```

### 6. Run Only the Dream Job

Use the Dream-only entry point when you want consolidation to run as an offline job without starting a live session:

```bash
python dream_job.py
```

This is the command to schedule with cron, launchd, CI, or another background runner.

---

## Technical Details

### Live Session Storage (`src/agent.py`)
The `LiveSessionAgent` reads mounted Markdown resources in real-time. It now uses an index-aware context loader, preferring `_index.md` plus a small set of relevant files instead of dumping the entire memory store into the prompt. When completing a turn, it performs incremental file writes rather than rewriting complete datasets.

### Fact Reconciling & Indexing (`src/dream.py`)
The `DreamingOrchestrator` aggregates current files and historical transcripts. It prompts the LLM to resolve logical contradictions, deduplicate parameters, and output a compact memory representation. It materializes discrete Markdown files in `data/output_memory`, writes a top-level map file (`_index.md`), and emits `_review.diff` for human review before swapping memory stores.

Typical generated files include:
- `cwc_2026_knowledge.md`
- `event-logistics.md`
- `_dream_report.md`
- `_index.md`
- `_review.diff`

### LLM Clients (`src/llm.py`)

| Class | Backend | Auth |
|---|---|---|
| `LocalLLM` | Ollama (`localhost:11434`) | None — local process |
| `RegoloLLM` | Regolo API (`api.regolo.ai`) | `Bearer` token from `.env` |

Both classes expose the same `query(system_prompt, user_prompt) -> str` interface, making the provider fully interchangeable across the pipeline.

---

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `REGOLO_API_KEY` | Your Regolo API key | Only for Regolo provider |

The `.env` file is created automatically the first time you run with the Regolo provider. It is listed in `.gitignore` and will never be committed to version control.

Copy the template if you prefer to configure it manually:

```bash
cp .env.example .env
```

---

## Links

- [Full article](https://regolo.ai/implementing-stateful-ai-agents-how-to-build-anthropics-memory-store-and-dreaming-architecture-in-python/) — detailed walkthrough of the architecture and implementation choices
- [Regolo.ai](https://regolo.ai) — European OpenAI-compatible GPU inference
- [Free API key](https://regolo.ai/pricing) — Pay as You Go, no commitment
- [Anthropic memory patterns](https://www.anthropic.com/research/building-effective-agents) — the original research this project is inspired by