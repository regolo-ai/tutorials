<div align="center">
  <img src="https://regolo.ai/wp-content/uploads/2026/06/Regolo_logo_positive.png" alt="Regolo.ai Logo" width="300" />
</div>

# Thinker → Worker → Verifier — Stateful System (CrewAI)

<div align="center">
  <img src="https://img.shields.io/badge/build-passing-brightgreen.svg" alt="Build passing" />
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg?logo=python&logoColor=white" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/Code-Runnable_Examples-2ea44f.svg" alt="Code: Runnable Examples" />
  <img src="https://img.shields.io/badge/GPU-100%25_Ready-0078D4.svg" alt="GPU 100% Ready" />
  <img src="https://img.shields.io/badge/API-OpenAI_Compatible-313236.svg" alt="API OpenAI Compatible" />
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT" />
</div>

<br />

This folder contains the runnable code for the article:
https://regolo.ai/how-to-build-self-improving-agents-that-actually-get-better-over-time/

Complete implementation of the multi-agent pattern with **session memory**, **dynamic worker pool**, **autonomous Feedback node**, and routing policies **Retry / Reassign / Replan**.

---

## Architecture

```
USER INPUT
    │
    ▼
┌──────────────────────────────────────────────────────────────────┐
│                       TWVOrchestrator                            │
│                                                                  │
│  ┌──────────┐  PlanPacket  ┌──────────────────────────────┐     │
│  │  THINKER │─────────────►│        WORKER POOL           │     │
│  │ Decompose│◄─────────────│  writer / coder / analyst    │     │
│  │ + Route  │  self-call   └─────────────┬────────────────┘     │
│  └─────┬────┘                            │ WorkerResult          │
│        │                                 │                       │
│        │ Store/Context    ┌──────────────┼───────────────┐       │
│        ├─────────────────►│    MEMORY — Session State    │       │
│        │                  │  /twv/session/input          │       │
│        │◄─────────────────│  /twv/session/plan           │       │
│        │   recall         │  /twv/session/verification   │       │
│        │                  │  /twv/workers/<id>           │       │
│        │                  └──────────────────────────────┘       │
│        │                                 │                       │
│        │                                 ▼                       │
│        │                       ┌─────────────────┐              │
│        │                       │    VERIFIER     │              │
│        │                       │ Test/Check/QA   │              │
│        │                       └────────┬────────┘              │
│        │                                │ VerificationReport     │
│        │                                ▼                       │
│        │                     ┌──────────────────────┐           │
│        │              ┌──────┤  FEEDBACK CONTROLLER │           │
│        │              │      └──────────────────────┘           │
│        │    ┌──────────┴─────────────────────┐─────────────┐                  │
│        │    │                                │                  │
│      REPLAN RETRY / REASSIGN            OK → FINISH             │
│        │    │                                │                  │
│        └────┘                                ▼                  │
│                                        FINAL OUTPUT             │
└──────────────────────────────────────────────────────────────────┘
*The diagram above shows the integration of session memory with hierarchical scopes and the autonomous feedback node.*

### Software Mapping

| Component            | File                     | Role in the diagram                        |
|----------------------|--------------------------|--------------------------------------------|
| `TWVOrchestrator`    | `orchestrator.py`        | Control layer — state and transitions      |
| `Thinker`            | `agents.py`              | Decompose + Route                          |
| `WorkerPool`         | `worker_pool.py`         | LLM A / B / C                             |
| `Verifier`           | `agents.py`              | Test / Compile / Check                     |
| `FeedbackController` | `feedback_controller.py` | FEEDBACK node — Retry / Reassign           |
| `MemoryManager`      | `memory_layer.py`        | MEMORY node — Session State                |
| Domain models        | `models.py`              | JSON contracts between agents              |
| Task factory         | `tasks.py`               | Contractual prompts for each agent         |
| Parsers              | `parsers.py`             | Robust JSON extraction from LLM outputs    |

---

## Installation

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Add OPENAI_API_KEY to the .env file
```

---

## Usage

```bash
# Interactive mode
python main.py

# Pipe input
echo "Write a tutorial on Docker" | python main.py
```

---

## File Structure

```
twv_stateful/
├── main.py                  Entry point
├── orchestrator.py          State machine and control loop
├── agents.py                Factory for Thinker, Worker, Verifier
├── worker_pool.py           Catalog of specialized workers
├── memory_layer.py          Memory node with hierarchical scopes
├── feedback_controller.py   Decision engine for Retry/Reassign/Replan
├── tasks.py                 Factory for CrewAI tasks with prompts
├── parsers.py               Robust JSON parsing from LLM outputs
├── models.py                Pydantic domain models
├── config.py                Centralized configuration
├── requirements.txt
└── .env.example
```

---

## Runtime Flow

### 1. Planning (Thinker)
The Thinker receives the task, the worker catalog, and memory context.
It produces a `PlanPacket` JSON with decomposition, success criteria, selected worker, and a `requires_self_call` flag.

### 2. Execution (Worker)
The selected Worker receives the plan, memory context, and feedback from the Verifier.
It produces the final output directly.

### 3. Verification (Verifier)
The Verifier evaluates the output against the plan's success criteria and produces a `VerificationReport` JSON.

### 4. Feedback Loop (FeedbackController)

| Recommendation | Condition               | Actual Action    |
|----------------|-------------------------|------------------|
| FINISH         | status = OK             | FINISH           |
| RETRY          | retry_count < max       | RETRY            |
| RETRY          | retry_count >= max      | REASSIGN         |
| REASSIGN       | reassign_count < max    | REASSIGN         |
| REASSIGN       | reassign_count >= max   | REPLAN           |
| REPLAN         | replan_count < max      | REPLAN           |
| REPLAN         | replan_count >= max     | RETRY forced     |

### 5. Memory

| Event            | Scope                          |
|------------------|--------------------------------|
| User input       | `/twv/session/input`           |
| Thinker plan     | `/twv/session/plan`            |
| Verifier report  | `/twv/session/verification`    |
| Worker output    | `/twv/workers/<worker_id>`     |

---

## Configuration

```env
TWV_MAX_RETRIES=2       # Retry before scaling to REASSIGN
TWV_MAX_REASSIGNS=2     # Reassign before scaling to REPLAN
TWV_MAX_REPLANS=2       # Replan before final forced retry
TWV_VERBOSE=true        # Agent logging (false for clean output)
```

---

## Differences from Prototype v1

| Aspect               | Prototype v1           | Stateful System v2         |
|----------------------|------------------------|----------------------------|
| Memory               | Prompt context only    | MemoryManager with scopes  |
| Worker               | Single fixed           | Dynamic pool: writer/coder/analyst |
| Feedback             | String in prompt       | Autonomous FeedbackController |
| Routing              | Only RETRY             | RETRY / REASSIGN / REPLAN  |
| Thinker Self-call    | Not supported          | Via `requires_self_call=true` |
| Session State        | Local variables        | SessionState Pydantic model|
| Agent JSON Output    | Fragile parsing        | Pydantic validation        |

---

## Why Custom State over Native CrewAI Flows?

While CrewAI provides built-in `Flows` with a Pydantic-based state machine, it is insufficient for production-grade self-improving agents.

| Aspect | Native CrewAI Flows | Our Custom Stateful System (TWV) |
| :--- | :--- | :--- |
| **Persistence** | Volatile in-memory. State is lost on application crash or restart. | **Physical store (SQLite)**. Full audit trail and crash recovery. |
| **Crash Recovery** | Cannot resume a failed or interrupted run. | **Pause and Resume**. Can reload any past session and resume execution from the last step. |
| **Escalation Logic** | Linear listener methods (`@router`, `@listen`) that clutter the orchestrator. | **Decoupled Controller**. Autonomous decision engine (`FeedbackController`) with dynamic retry/reassign/replan rules. |
| **Memory Isolation** | Global state structure shared directly across all agents. | **Hierarchical Scopes** (`/twv/session/*`, `/twv/workers/*`) to prevent prompt context clutter. |

---

## Adding a New Worker

```python
# In worker_pool.py, add to the _workers dictionary:
"researcher": WorkerProfile(
    worker_id="researcher",
    specialty="web research",
    description="Ideal for web research, data collection, and fact-checking.",
    agent=worker_agent("researcher", "web research",
        "You are a methodical researcher..."),
),
```

---

## Adding Tools to a Worker

```python
# In agents.py, modify worker_agent():
from crewai_tools import SerperDevTool
return Agent(..., tools=[SerperDevTool()])
```

---

## Using an Alternative LLM

```env
# OpenAI-compatible setup
# OPENAI_API_BASE=
# OPENAI_BASE_URL=

# Agent's LLM models
THINKER_MODEL=brick-v1-beta
WORKER_MODEL=qwen3.5-122b
VERIFIER_MODEL=gemma4-31b

# Fallback for embedding-based memory search
OPENAI_MODEL_NAME=qwen3.5-122b

OPENAI_EMBEDDING_MODEL=Qwen3-Embedding-8B
TWV_MAX_RETRIES=2
TWV_MAX_REASSIGNS=2
TWV_MAX_REPLANS=2
TWV_VERBOSE=true

```

---

## Requisiti

- Python 3.10 – 3.13
- crewai >= 0.85.0
- Chiave API OpenAI o provider compatibile
