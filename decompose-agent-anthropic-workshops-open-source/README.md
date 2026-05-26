# StockPilot — Decomposed AI Agent (Anthropic Workshop Style)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Powered by Regolo](https://img.shields.io/badge/Powered%20by-Regolo%20GPU-green)](https://regolo.ai)

A hands-on implementation of **decomposed AI agents** inspired by Anthropic's workshop patterns.  
StockPilot is an inventory management agent that routes queries to specialized subagents and code-execution tools — with full support for both local Ollama and cloud Regolo GPU inference.

---

### 🎁 Get Started Free

Sign up for Regolo and start for free with Pay as You Go pricing:

[Get Started](https://regolo.ai) · [**REGOLO FREE TRIAL**](https://regolo.ai/pricing)

### Questions? Open an issue or join our [Discord](https://discord.gg/wHxwWCC8)

---

## Overview

This project demonstrates the **decomposed agent pattern**: instead of a single monolithic LLM prompt, the orchestrator:

1. **Routes** the incoming query to the correct execution path
2. **Injects** a skill-specific context (rules, formulas, constraints)
3. **Delegates** computation to tools (Python code execution) or subagents
4. **Returns** a structured, verifiable result

Two inventory scenarios are tested end-to-end:

| Test | Scenario | Primitive used |
|------|----------|----------------|
| F1 | Low-stock sweep — identify SKUs below reorder point | Python code execution |
| R8 | Promo-month demand forecast with multiplier | Specialized forecasting subagent |

---

## Architecture

```
main.py (provider selection)
    │
    ▼
StockPilotOrchestrator
    │
    ├── route_and_execute(query)
    │       │
    │       ├── [LOW_STOCK_SWEEP] → inject reorder-policy skill
    │       │       └── LLM generates Python → run_python_analysis()
    │       │
    │       └── [PROMO_FORECAST] → inject forecasting skill
    │               └── forecaster_subagent(sku, velocity, horizon, promo)
    │
    └── query_llm()  ──► Ollama (local)  or  Regolo (cloud GPU)
```

**Skills** (plain-text rule files in `skills/`):

- `reorder-policy.txt` — reorder trigger rule and `Order_Qty` formula
- `forecasting.txt` — demand forecast formula with promo multiplier (3.1×)

---

## Prerequisites

- Python 3.10+
- **One of the following LLM providers:**
  - [Ollama](https://ollama.com) running locally with a pulled model (e.g. `llama3`)
  - A Regolo API key — [get one free at regolo.ai/pricing](https://regolo.ai/pricing)

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the agent

```bash
python main.py
```

An interactive menu will appear:

```
====================================================
   StockPilot — Decomposed Agent (Anthropic style)
====================================================

  Select LLM provider:

  [1] OLLAMA  — local, no API key required
  [2] Regolo  — cloud GPU, free API key
```

#### Option 1 — Ollama

Make sure Ollama is running and the model is available:

```bash
ollama pull llama3
ollama serve
```

Then select `1` and confirm the model name.

#### Option 2 — Regolo

Select `2`. If no `.env` file is found, the script will:

1. Show the registration link: [https://regolo.ai/pricing](https://regolo.ai/pricing) (click **Pay as You Go**)
2. Ask you to paste your API key
3. Save it to `.env` automatically
4. Fetch the list of available models from `https://api.regolo.ai/v1/models`
5. Let you pick the model, then start the tests

On subsequent runs the key is loaded silently from `.env`.

---

## Project Structure

```
decompose-agent-anthropic-workshops-open-source/
├── main.py                  # Entry point: provider menu + E2E test runner
├── requirements.txt
├── .env.example             # API key template
├── agent/
│   ├── llm_client.py        # Unified LLM interface (Ollama + Regolo)
│   ├── orchestrator.py      # Query router and skill injector
│   ├── subagents.py         # Specialized forecasting subagent
│   └── tools.py             # Python code execution tool
├── skills/
│   ├── reorder-policy.txt   # Reorder rules and formula
│   └── forecasting.txt      # Demand forecast rules and formula
└── data/
    ├── stock_levels.csv      # Inventory snapshot (SKU, Stock, ReorderPoint)
    └── sales_history.csv     # Historical sales velocity per SKU
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `REGOLO_API_KEY` | Your Regolo API key (only needed for Regolo provider) |

Copy the template and fill in your key:

```bash
cp .env.example .env
```

---

## Expected Test Output

```
[TEST 1] SUCCESSFUL: Low-stock identified accurately via code primitive.
[TEST 2] SUCCESSFUL: Subagent correctly computed the promo multiplier without prompt leakage.
```

Test 1 verifies that `SKU-0116` and `SKU-0300` are flagged as low-stock while `SKU-0200` (sufficient stock) is not.  
Test 2 verifies that `forecasted_demand = 12 × 30 × 3.1 = 1116.0` is computed exactly by the subagent without leaking the formula from the orchestrator prompt.

---

## Links

- [Regolo.ai](https://regolo.ai) — European OpenAI-compatible GPU inference
- [Free API key](https://regolo.ai/pricing) — Pay as You Go, no commitment
- [Anthropic agent patterns](https://www.anthropic.com/research/building-effective-agents)
