# Build a controlled Analytics Assistant with LangChain, Qdrant, and Regolo

This reference implementation answers a KPI question by combining three bounded capabilities: company-policy retrieval from Qdrant, metric lookup, and a non-destructive CRM workflow. It is deliberately not a generic chatbot: each external capability is a typed tool and the only permitted write action is creating a follow-up list.

## What you will build

The example asks: **“Compare activation in 2026-W29 with 2026-W28, explain the largest decline, and create a follow-up list.”** The agent retrieves the activation definition and CRM policy, queries structured metrics, then may create a list. The sample data makes the expected finding reproducible: Self-serve activation declines from 45% (54/120) to 30% (39/130), a 15 percentage-point drop.

## Architecture

`User -> ChatOpenAI (Regolo endpoint) -> tool calls -> [Qdrant knowledge | metrics API adapter | CRM adapter] -> answer`

Qdrant holds unstructured operational context. The `query_activation_metrics` tool is a stand-in for a warehouse or BI semantic layer. Replace its `DATA` lookup with parameterised queries against your approved analytics endpoint; do not grant the model database credentials directly. The CRM tool is deliberately safe-by-default: it returns a pending follow-up list and cannot contact anyone or update a record.

## Prerequisites

Python 3.10+ and a Regolo API key are required for the live agent run. Regolo exposes an OpenAI-compatible endpoint at `https://api.regolo.ai/v1`, so the example uses LangChain's standard `ChatOpenAI` integration. The model must support tool/function calling; choose the exact enabled model name in your Regolo dashboard and set `REGOLO_MODEL` accordingly.

## Install and configure

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Set `REGOLO_API_KEY` in `.env`. If your available model has another name, change `REGOLO_MODEL`. Run the local component tests first:

```bash
pytest -q
```

Then run the end-to-end agent, which makes live model requests and therefore needs a valid key and a function-calling model:

```bash
python app.py
```

## Production changes before connecting data

Replace the in-process `DATA` array with a read-only analytics service that enforces tenant, role, and date filters. Replace the demo `create_crm_followup_list` body with your CRM API call, retain human approval for every external communication or record mutation, and log tool inputs, outputs, caller identity, and approval IDs. Keep the knowledge base scoped by document permissions; vector retrieval is not an authorization system.

## Why this pattern

The model decides *which* allowed tool to use, but your application decides *what each tool can do*. This preserves the useful multi-tool behavior while making the automation measurable: tool success rate, grounded-answer rate, activation-analysis completion rate, and approved-list-to-outreach conversion.

## Files

- `app.py` — agent, Qdrant retrieval, tools, and live run
- `knowledge_base.py` — demo business context
- `test_app.py` — deterministic tests for retrieval, metrics, and action safeguards
- `.env.example` — configuration template
