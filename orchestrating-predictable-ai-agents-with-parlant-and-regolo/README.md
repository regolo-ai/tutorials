# Orchestrating Predictable AI Agents with Parlant and Regolo

This folder contains the runnable code for the article:
https://regolo.ai/orchestrating-predictable-ai-agents-with-parlant-and-regolo/

## What this project does

- Applies deterministic policy routing (Parlant-style) before generation
- Uses Regolo's OpenAI-compatible endpoint for responses
- Demonstrates a minimal orchestrator that is easy to extend
- Includes tests for policy logic and live API integration

## Project structure

- `agents/parlant_agent.py`: deterministic policy and intent routing
- `agents/regolo_agent.py`: Regolo chat completion client
- `orchestrator/workflow_manager.py`: orchestrates policy + generation
- `main.py`: CLI entrypoint for a sample orchestrated run
- `tests/test_orchestrator.py`: local and live integration tests

## Quick start

```bash
cd orchestrating-predictable-ai-agents-with-parlant-and-regolo
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set your API key in `.env`:

```bash
REGOLO_API_KEY=your_key_here
```

Run the demo:

```bash
python main.py
```

Run tests:

```bash
pytest -q
```

## Docker

```bash
docker compose up --build
```
