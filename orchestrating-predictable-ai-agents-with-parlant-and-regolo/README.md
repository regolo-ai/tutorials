<div align="center">
  <img src="https://regolo.ai/wp-content/uploads/2026/06/Regolo_logo_positive.png" alt="Regolo.ai Logo" width="300" />
</div>

# Orchestrating Predictable AI Agents with Parlant and Regolo

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

### How to Use
1. Clone this repository: `git clone https://github.com/regolo-ai/tutorials.git`
2. Navigate to the desired tutorial folder.
3. Follow the instructions in the folder's README.md. 
4. Get a free API key from Regolo to run the code: [Sign Up for Free Trial](https://regolo.ai/pricing).
5. Run the code and see the results in minutes.
