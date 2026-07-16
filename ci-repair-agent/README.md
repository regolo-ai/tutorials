<div align="center">
  <img src="https://regolo.ai/wp-content/uploads/2026/06/Regolo_logo_positive.png" alt="Regolo.ai Logo" width="300" />
</div>

[![Watch the preview](https://img.youtube.com/vi/56c7348w-G4/0.jpg)](https://youtu.be/56c7348w-G4)

# Regolo.ai Closed‑Loop Code Reviewer & CI Repair Agent

**Fast, deterministic Python code repair powered by Regolo.ai** – see the [Regolo blog guide](https://regolo.ai/agent-harness-evaluate-efficiency-production/).

<img src="https://img.shields.io/badge/build-passing-brightgreen.svg" alt="Build passing" />
<img src="https://img.shields.io/badge/python-3.10+-blue.svg?logo=python&logoColor=white" alt="Python 3.10+" />
<img src="https://img.shields.io/badge/Code-Runnable_Examples-2ea44f.svg" alt="Code: Runnable Examples" />
<img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT" />

## 📚 What this project contains

> This repository implements the code behind the article *Agent Harness – Evaluate efficiency on production* where a LangChain‑LangGraph agent repairs buggy Python code in a closed loop using **pytest** and **ruff** as feedback.

## 🚀 Key Features

```bash
Agent creates a patch
        ↓
Harness runs pytest + ruff
        ↓
Pass? ── Yes → verified_success
  │
  No
  ↓
Failure logs become feedback
        ↓
Agent retries the patch
        ↓
Max attempts reached?
  │
  Yes → needs_human_review
```

- ❄️ **Closed‑loop verification** – the agent proposes a patch, then `pytest` + `ruff` validate it; if it fails, the agent retries up to a configurable budget.
- 🔗 **OpenAI‑compatible** – works with any LLM endpoint that implements the OpenAI spec (Regolo.ai, Together.ai, Ollama, vLLM, LM Studio, …).
- 🔁 **Iterative self‑correction** – detailed traceback and test output are fed back as human‑readable comments to the model.
- ⚙️ **CLI wrapper** – `scripts/regolo.sh` manages a virtual environment, installs dependencies, and provides a menu‑driven way to run diagnostics, evaluate the pipeline, or launch benchmarks.

## ⚙️ Environment Variables

Copy `[ci-repair-agent/.env.example](ci-repair-agent/.env.example)` to `.env` and set your own values:

```text
OPENAI_API_KEY=   # your OpenAI‑compatible key
OPENAI_BASE_URL=  # e.g. https://api.regolo.ai/v1
OPENAI_MODEL=     # defaults to gpt-4o-mini
AGENT_MAX_ATTEMPTS= 3
AGENT_MODEL_CALL_LIMIT= 12
AGENT_TOOL_CALL_LIMIT= 30
TARGET_REPO_PATH= ./target-repo
```

<details><summary>Supported variables</summary>
- `OPENAI_API_KEY` – **required**
- `OPENAI_BASE_URL` – optional, defaults to the Standard OpenAI endpoint
- `OPENAI_MODEL` – optional, defaults to `gpt-4o-mini`
- `AGENT_MAX_ATTEMPTS` – maximum patch attempts for a single issue
- `AGENT_MODEL_CALL_LIMIT` – LLM call budget for a single issue
- `AGENT_TOOL_CALL_LIMIT` – tool call budget per issue
- `TARGET_REPO_PATH` – path to the repository that contains code to repair
</details>

> 👋 **NOTE**: Environment variables are automatically parsed from the `.env` file and from the OS environment.

## 📁 Project Structure

```
ci-repair-agent/
├── agent.py                 # [ci-repair-agent/agent.py](ci-repair-agent/agent.py)
├── config.py                # [ci-repair-agent/config.py](ci-repair-agent/config.py)
├── tools.py                 # [ci-repair-agent/tools.py](ci-repair-agent/tools.py)
├── evaluation.py            # [ci-repair-agent/evaluation.py](ci-repair-agent/evaluation.py)
├── requirements.txt
├── scripts/
│   └── regolo.sh            # [ci-repair-agent/scripts/regolo.sh](ci-repair-agent/scripts/regolo.sh)
├── benchmarks/
│   └── tasks.json
├── target-repo/             # Reference buggy workspace to repair
│   ├── app/
│   │   ├── __init__.py
│   │   └── user_service.py
│   ├── tests/
│   │   ├── __init__.py
│   │   └── test_users.py
│   └── pyproject.toml
└── tests/
    ├── __init__.py
    ├── test_tools.py
    ├── test_harness_gate.py
    ├── test_evaluation.py
    └── test_benchmark.py
```

## 🎉 Getting Started

1. **Ensure the shell script is executable**:
   ```bash
   chmod +x scripts/regolo.sh
   ```
2. **Set up the environment** (creates a virtual environment and installs dependencies):
   ```bash
   ./scripts/regolo.sh      # Option 1 – Set Environment
   ```
3. **Run the repair pipeline**:
   ```bash
   ./scripts/regolo.sh      # Option 3 – Run Project
   # or directly:
   python3 evaluation.py
   ```

## 🧪 Tests & Benchmarks

### Offline
No API key required; runs the deterministic harness only:

```bash
pip install -r requirements.txt
pytest tests/test_tools.py tests/test_harness_gate.py -v
```

### Live
Requires Regolo API key and a target repository:

```bash
./scripts/regolo.sh      # Option 3 – Run Project
# or
python3 evaluation.py
```

Run the built‑in benchmark:

```bash
python3 evaluation.py --tasks benchmarks/tasks.json
```

To see benchmark assertions (`pytest-benchmark`):

```bash
PYTHONPATH=. pytest tests/test_benchmark.py --benchmark-only
```

## 📦 CI Integration
Add a step in your build pipeline to invoke `scripts/regolo.sh` after tests to auto‑repair any failing tests. Example `GitHub Actions` snippet:

```yaml
- name: Run Regolo CI Repair
  run: ./scripts/regolo.sh
```

The script will either exit with status 0 or 1 based on the repair result.

## 📖 Resources

- Blog article: [Agent Harness – Evaluate efficiency on production](https://regolo.ai/agent-harness-evaluate-efficiency-production/)
- Full source: [ci-repair-agent repository](https://github.com/regolo-ai/tutorials/tree/main/ci-repair-agent)

## 📚 Example Workflow

```bash
# Inside the target repository
pytest            # Identify failing tests
python3 evaluation.py  # Run the repair loop
pytest            # Verify all tests now pass
```

## 📄 License
MIT – see the `LICENSE` file.
