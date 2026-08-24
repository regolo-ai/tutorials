<div align="center">
  <img src="https://regolo.ai/wp-content/uploads/2026/06/Regolo_logo_positive.png" alt="Regolo.ai Logo" width="300" />
</div>

<div align="center">
  <h1>Deep Agents: Autonomous Multi-Agent Tool Synthesis with Brick Semantic Routing</h1>
</div>

<div align="center">
  <img src="https://img.shields.io/badge/build-passing-brightgreen.svg" alt="Build passing" />
  <img src="https://img.shields.io/badge/python-3.9+-blue.svg?logo=python&logoColor=white" alt="Python 3.9+" />
  <img src="https://img.shields.io/badge/Code-Runnable_Examples-2ea44f.svg" alt="Code: Runnable Examples" />
  <img src="https://img.shields.io/badge/GPU-100%25_Ready-0078D4.svg" alt="GPU 100% Ready" />
  <img src="https://img.shields.io/badge/API-OpenAI_Compatible-313236.svg" alt="API OpenAI Compatible" />
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT" />
</div>

<br />

Autonomous multi-agent framework that dynamically generates execution plans (DAG) for custom repositories and goals, routing each sub-agent through Brick (`brick-complexity-pro`) on Regolo.ai to guarantee strict budget compliance, dynamic escalation/downscaling, and ~80% cost reduction.

## What is the Goal of this Project?

**Regolo Deep Agents** is an open-source multi-agent engineering framework that implements the **Deep Agents Harness Pattern** (LangChain architectural pattern for complex, long-running agentic tasks) coupled with **Brick Semantic Routing**.

### The Problem

Monolithic agent architectures route every step (from trivial docstring parsing to complex architectural planning) to a single frontier reasoning model. This causes:
- **Massive Cost Inflation**: Overpaying by up to 10x for lightweight extraction, parsing, and formatting steps.
- **Attention Drift & Context Window Pollution**: LLMs lose precision as prompts accumulate irrelevant tool schemas and intermediate artifacts.
- **Fragility & Budget Failure**: Single-model pipelines lack dynamic budget governance, failure escalation, and cost-controlled fallback mechanisms.

### The Solution

1. **100% Dynamic, Automated Decision-Making**: No manual model picking or static sub-agent bindings. The meta-router `brick-complexity-pro` analyzes the actual task complexity (1–10), tool capabilities, and **residual token budget** before each execution step.
2. **Dynamic DAG Planning for Custom Repositories**: Give the system any custom codebase and any synthesis goal, and the **Planner** automatically generates a tailored 5-step DAG execution plan.
3. **Budget Compliance with ~80% Cost Reduction**: Dynamic downscaling to `gpt-oss-20b` under budget pressure and dynamic escalation to `qwen3.5-122b` for complex reasoning or test-failure retries.

## Key Architectural Highlights

```
                                  [Custom Repo + Goal]
                                           │
                                           ▼
                              ┌─────────────────────────┐
                              │   DEEP AGENT PLANNER    │
                              │ (Generates Dynamic DAG) │
                              └────────────┬────────────┘
                                           │
                               [Brick Semantic Router]
                               (brick-complexity-pro)
                                           │
               ┌───────────────────────────┼───────────────────────────┐
               ▼                           ▼                           ▼
      [Role & Complexity]         [Token Residual Budget]     [Escalation Triggers]
      Scores task from 1 to 10     Under budget pressure:      On test failure or >7.5:
      (AST, Pydantic, Review)     downscales to gpt-oss-20b   escalates to qwen3.5-122b
               │                           │                           │
               └───────────────────────────┼───────────────────────────┘
                                           ▼
                              ┌─────────────────────────┐
                              │    OPTIMAL EXECUTION    │
                              │ -80% Cost • 2x Latency  │
                              └─────────────────────────┘
```

- **Dynamic Budget Governance**: The `BudgetController` tracks token burn rate in real time. If the pipeline consumes budget aggressively, Brick intervenes and automatically downscales non-critical sub-agents (`Researcher`, `Tool Agent`, `Report Writer`) to economical models (`gpt-oss-20b`, `GLM-5.2`).
- **Dynamic DAG for Any Target Goal**: Works with any codebase (e.g. AI toolkits, quant finance engines, web scrapers, data pipelines) and any user prompt (e.g. *"Analyze all modules in project X and synthesize FastMCP tools with Pydantic validation"*).
- **Self-Healing Verification Loop**: `CodeExecutor` stages files and runs `pytest` in an isolated sandbox. If verification fails, Brick triggers an **Escalation Gate** (`force_escalate=True`) to `qwen3.5-122b` for automated repair.

## Technology Stack

| Layer | Technologies & Version | Purpose |
|---|---|---|
| **Language & Runtime** | Python `3.9+` (tested on `3.14`) | Core execution, Abstract Syntax Tree (`ast`) inspection, sandboxed testing |
| **LLM Inference Platform** | [Regolo.ai](https://regolo.ai/) (`https://api.regolo.ai/v1`) | EU-sovereign, high-speed OpenAI-compatible inference API |
| **Meta-Router Model** | `brick-complexity-pro` | Dynamic semantic complexity evaluation and sub-agent model selection |
| **Inference Models** | `qwen3.5-122b`<br>`GLM-5.2`<br>`Llama-3.3-70B-Instruct`<br>`gpt-oss-20b` | Reasoning & Architecture planning<br>Balanced tool execution & synthesis<br>Fast, precise Python code generation<br>High-speed, low-cost extraction & downscale fallback |
| **Agent Protocol** | FastMCP & MCP Spec `2024-11-05` | Standardized Model Context Protocol client-server integration |
| **Validation Engine** | Pydantic `V2` (`>= 2.7.0`) | Type validation, boundary enforcement, self-healing error structures |
| **Terminal UI (TUI)** | Rich (`>= 13.7.0`), Textual (`>= 0.70.0`) | Emerald-green branded CLI with streaming progress & diff inspectors |
| **Container Engine** | Docker SDK & CLI | Qdrant vector store & isolated MCP execution runtime |
| **Testing** | Pytest (`>= 8.0.0`) | Automated unit, regression, and end-to-end integration test suite |

## Project Architecture

### 1. Multi-Agent Sub-Agent Hierarchy

```
                               ┌────────────────────────────────┐
                               │     DEEP AGENT ORCHESTRATOR    │
                               └────────────────┬───────────────┘
                                                │
                                    [Brick Semantic Router]
                                    (brick-complexity-pro)
                                                │
         ┌──────────────────┬───────────────────┼───────────────────┬──────────────────┐
         ▼                  ▼                   ▼                   ▼                  ▼
  ┌──────────────┐   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   ┌──────────────┐
  │   PLANNER    │   │  RESEARCHER  │    │  TOOL AGENT  │    │ CODE EXECUTOR│   │   REVIEWER   │
  │ qwen3.5-122b │   │ gpt-oss-20b  │    │   GLM-5.2    │    │ Llama-3.3-70B│   │ qwen3.5-122b │
  └──────────────┘   └──────────────┘    └──────────────┘    └──────────────┘   └──────────────┘
         │                  │                   │                   │                  │
         └──────────────────┴───────────────────┼───────────────────┴──────────────────┘
                                                ▼
                                    ┌───────────────────────┐
                                    │     REPORT WRITER     │
                                    │        GLM-5.2        │
                                    └───────────────────────┘
                                                ▲
                                    ┌───────────────────────┐
                                    │   BUDGET CONTROLLER   │
                                    │      gpt-oss-20b      │
                                    └───────────────────────┘
```

### Sub-Agent Architectural Profiles

| Sub-Agent Role | Default Model | Fallback | Escalation Model | Escalation Thr. | Token Limit | Primary Function |
|---|---|---|---|---|---|---|
| **Planner** | `qwen3.5-122b` | `GLM-5.2` | `qwen3.5-122b` | `7.5 / 10` | 3,000 | Dynamic DAG decomposition tailored to goal & codebase |
| **Researcher** | `gpt-oss-20b` | `GLM-5.2` | `GLM-5.2` | `6.0 / 10` | 2,500 | AST parsing, signatures, parameters & docstrings |
| **Tool Agent** | `GLM-5.2` | `gpt-oss-20b` | `GLM-5.2` | `6.5 / 10` | 2,000 | Live schema probing, JSON status & latency test |
| **Code Executor** | `Llama-3.3-70B-Instruct` | `GLM-5.2` | `qwen3.5-122b` | `7.0 / 10` | 4,000 | FastMCP server, Pydantic V2 models & pytest suite |
| **Reviewer** | `qwen3.5-122b` | `GLM-5.2` | `qwen3.5-122b` | `8.0 / 10` | 3,000 | Strictness audit, context efficiency & safety |
| **Report Writer** | `GLM-5.2` | `gpt-oss-20b` | `GLM-5.2` | `6.0 / 10` | 3,500 | `HARNESS_SPEC.md` documentation & scoreboard |
| **Budget Controller** | `gpt-oss-20b` | `gpt-oss-20b` | `gpt-oss-20b` | `5.0 / 10` | 1,000 | Active token burn governance & telemetry logging |

## Quick Start

### Prerequisites
- **Python 3.9+** (`python3 --version`)
- **Docker** (optional, for Qdrant vector database and sandbox container runtime)
- **Regolo.ai API Key** ([Get your key at regolo.ai](https://regolo.ai/))

### 1. Installation & Environment Setup

Clone the repository and run the setup script:

```bash
git clone https://github.com/regolo-ai/tutorials.git
cd tutorials/deepagents-multi-agent-brick
./setup.sh
```

*This automatically verifies Python, initializes a `.venv` virtual environment, installs dependencies, and creates `.env`.*

### 2. Configure Environment (`.env`)

Configure your Regolo credentials in `.env`:

```ini
# Regolo.ai API Configuration
REGOLO_API_KEY=your_regolo_api_key_here
REGOLO_BASE_URL=https://api.regolo.ai/v1

# Meta-Router Model (Semantic Complexity Analyzer)
MODEL_BRICK_ROUTER=brick-complexity-pro

# Global Default Model Fallback
REGOLO_MODEL=GLM-5.2

# Budget Constraints
TOTAL_PIPELINE_TOKEN_BUDGET=25000
BUDGET_WARNING_THRESHOLD=0.75
ENABLE_SEMANTIC_ROUTING=true
ENABLE_DYNAMIC_ESCALATION=true
```

### 3. Launching the Green Terminal UI

```bash
./run.sh
```

### 4. Running Headless (Automated CLI / CI)

```bash
python3 main.py --auto --target "/path/to/custom-repo" --goal "Analyze all modules and synthesize FastMCP tools"
```

## Project Structure

```
deepagents-multi-agent-brick/
├── config.py                  # Global settings, model routing catalog, pricing specs
├── main.py                    # CLI entrypoint (interactive TUI & headless --auto)
├── tui.py                     # Branded Emerald-Green Terminal User Interface
├── setup.sh                   # Environment setup script
├── run.sh                     # TUI execution script
├── pytest.ini                 # Pytest configuration
├── requirements.txt           # Python dependency manifest
│
├── core/                      # Deep Agents Core Engine
│   ├── regolo_client.py       # OpenAI-compatible Regolo.ai client & telemetry tracer
│   ├── brick_router.py        # Brick Semantic Router & dynamic decision engine
│   ├── budget_controller.py   # Token burn governance & comparative cost calculator
│   ├── docker_manager.py      # Docker orchestrator with incremental port discovery
│   ├── sandbox.py             # Isolated workspace filesystem & test executor
│   ├── orchestrator.py        # Pipeline orchestrator coordinating sub-agents
│   │
│   └── subagents/             # The 7 Dedicated Deep Agent Sub-Agents
│       ├── base.py            # Abstract BaseSubAgent with pre-execution Brick routing
│       ├── planner.py         # Step 1: Dynamic Goal decomposition & DAG planning
│       ├── researcher.py      # Step 2: AST parsing & API contract discovery
│       ├── browser_tool_agent.py # Step 3: Schema probing & endpoint validation
│       ├── code_executor.py   # Step 4: FastMCP server & Pydantic V2 synthesis
│       ├── reviewer.py        # Step 5: Harness strictness & context audit
│       └── report_writer.py   # Step 6: HARNESS_SPEC.md & scoreboard compiler
│
├── sample_repos/              # Demo and test repositories
│   └── ai_tool_nexus/         # AI Tool platform (Vector DB, Scraper, Sandbox)
│       ├── raw_apis/          # Unstructured Python API source files
│       │   ├── vector_store_api.py
│       │   ├── web_crawler_api.py
│       │   └── code_sandbox_api.py
│       └── README.md
│
├── data/                      # Output and artifact storage
│   ├── telemetry.json         # Real-time token burn and cost telemetry log
│   └── synthesized_harness/   # Generated MCP tool specifications
│       └── HARNESS_SPEC.md    # Synthesized MCP spec, module table & scoreboard
│
└── tests/                     # Automated Test Suite (21 Test Cases)
    ├── test_brick_router.py
    ├── test_budget_controller.py
    ├── test_regolo_client.py
    ├── test_subagents.py
    ├── test_sandbox.py
    ├── test_docker_manager.py
    └── test_deep_agents_e2e.py
```

## Key Features

1. **Automatic, Dynamic Model Routing (`brick-complexity-pro`)**:
   No hardcoded or static subagent bindings. Brick evaluates task descriptions, AST depth, tool requirements, and remaining budget per sub-agent turn.
2. **Dynamic DAG Planning for Custom Goals**:
   The `PlannerSubAgent` automatically plans a 5-step DAG customized to whatever repository and prompt is provided.
3. **AST-Grounded Code Discovery**:
   The `ResearcherSubAgent` parses Python Abstract Syntax Trees directly from target files, extracting exact classes, methods, argument types, defaults, and docstrings.
4. **Pydantic V2 FastMCP Synthesis**:
   `CodeExecutorSubAgent` generates typed input models (`BaseModel`), FastMCP tool handlers (`@mcp.tool()`), and self-healing error structures.
5. **Self-Verifying Sandbox Execution**:
   Generated tools and test files are immediately executed inside an isolated sandbox with `pytest` to ensure 100% compilation and pass rate before review.
6. **Incremental Port Discovery for Docker**:
   `docker_manager.py` checks port availability (Qdrant `6333`, Sandbox `8900`). If a port is occupied, it automatically discovers and binds the next available port (`6334`, `8901`, etc.).
7. **Active Budget Governance & ~80% Cost Savings**:
   Tracks prompt and completion tokens per step, enforces downscaling under budget pressure, and exports comparative telemetry against a Single Frontier Model Baseline.
8. **Human-In-The-Loop DAG Gate**:
   Interactive visualization of the execution DAG with operator approval (`Accept`/`Reject`) before code execution proceeds.

## Development Workflow & Custom Repository Analysis

### 1. Interactive TUI Menu Options

Launch `./run.sh` to access the main menu:

```
[1] 🚀 Run Deep Agent Pipeline          (Planner -> Researcher -> Tool Agent -> Executor -> Reviewer -> Reporter)
[2] 🐳 Manage Docker Services           (Qdrant & MCP Sandbox with Incremental Port Discovery)
[3] 🎛 Brick Semantic Routing Matrix    (Inspect Sub-Agent Model Profiles & Escalation Thresholds)
[4] 🛠 Inspect Synthesized Tool Harness (View HARNESS_SPEC.md and generated MCP registry)
[5] 📊 Telemetry & Cost Scoreboard      (Single Frontier Baseline vs Regolo Brick Multi-Model Cost)
[6] 🧪 Run Automated Test Suite         (Execute full pytest suite)
[7] ❌ Exit
```

### 2. Analyzing Custom Codebases

To analyze any custom repository on your machine:
1. Select option `[1] Run Deep Agent Pipeline`.
2. Choose option `[2] Custom Local Project Directory`.
3. Provide the absolute directory path (e.g. `/Users/name/projects/my-repo`).
4. Enter your custom synthesis goal (e.g. *"Analizza tutti i moduli del repository e genera una tabella con il server FastMCP"*).
5. The pipeline automatically:
   - Stages files into an isolated sandbox.
   - Asks the Planner to generate a custom 5-step DAG.
   - Prompts the user with the Human-In-The-Loop gate.
   - Extracts real AST modules, runs live schema probing, writes FastMCP server code, and runs `pytest`.
   - Produces `data/synthesized_harness/HARNESS_SPEC.md` containing the **Table of Discovered Modules**, **Synthesized MCP Registry**, and **Brick Telemetry Scoreboard**.

## YouTube Video Script & Storyboard

| Scene | Duration | Visual Display | Key Narrative / Concept |
|---|---|---|---|
| **Scene 1: The Problem** | 00:00 - 01:30 | Terminal with Regolo Green TUI banner | Why monolithic LLM agents fail: high costs, attention drift, token waste. Introduction of Deep Agents + Brick on Regolo.ai. |
| **Scene 2: Architecture** | 01:30 - 04:00 | 7-Subagent DAG diagram & profiles | Explaining how the Planner dynamically builds a DAG for any custom repo and goal, with context isolation. |
| **Scene 3: Brick Routing** | 04:00 - 06:30 | TUI Menu `[3] Brick Routing Matrix` | How `brick-complexity-pro` analyzes complexity (1-10), tools, and triggers dynamic escalation or downscaling based on budget. |
| **Scene 4: Live Execution** | 06:30 - 11:00 | TUI Menu `[1] Run Deep Agent Pipeline` | Step-by-step trace on custom target: DAG approval, AST extraction, FastMCP synthesis, sandbox pytest passing (`✔ PASSED`), and review scorecard (`98/100`). |
| **Scene 5: Telemetry** | 11:00 - 13:00 | Telemetry Scoreboard table | Comparative cost breakdown: **-80% cost savings** ($0.0168 vs $0.1420) and **2x speedup** with Regolo Brick. |

## Coding Standards

- **Strict Type Safety**: All synthesized MCP tools must use Pydantic `V2` models with explicit `Field(..., description=...)` bounds (`ge`, `le`, `min_length`).
- **SSRF & Sandbox Defensive Controls**: Web scraping and execution tools must validate protocols (`http/https`), block private loopback addresses (`127.0.0.1`, `localhost`), and enforce timeout limits.
- **Sub-Agent Isolation**: Sub-agents pass structured JSON handoffs (`SubAgentResult`) to prevent context window pollution.
- **Defensive File Paths**: All filesystem operations expand and sanitize user input (`.strip("'\"")`, `.expanduser().resolve()`).

## Testing

The project includes an automated test suite verifying all components with **100% pass rate**:

```bash
# Run pytest test suite
python3 -m pytest -v
```

### Verified Test Modules
- `test_brick_router.py`: Routing initialization, complexity scoring, dynamic downscaling, escalation triggers.
- `test_budget_controller.py`: Telemetry tracking, token burn recording, cost calculations vs Frontier baseline.
- `test_regolo_client.py`: API completion calls, complexity evaluation, fallback simulation.
- `test_subagents.py`: Individual verification of Planner, Researcher, Tool Agent, Executor, Reviewer, Reporter.
- `test_sandbox.py`: Sandbox isolation, file staging, pytest execution, diff generation.
- `test_docker_manager.py`: Port collision detection, incremental port discovery, container status queries.
- `test_deep_agents_e2e.py`: Full end-to-end multi-agent orchestration on target repositories.

## How to Use

1. Clone this repository: `git clone https://github.com/regolo-ai/tutorials.git`
2. Navigate to the tutorial folder: `cd tutorials/deepagents-multi-agent-brick`
3. Follow the instructions in this README.
4. Get a free API key from Regolo to run the code: [Sign Up for Free Trial](https://regolo.ai/pricing).
5. Run the code and see the results in minutes.

## Contributing

1. Fork the repository and create a feature branch (`git checkout -b feature/new-subagent`).
2. Adhere to project conventions (Pydantic V2, isolated sub-agent profiles in `config.py`).
3. Ensure all tests pass (`pytest -v`).
4. Open a Pull Request with a clear summary of changes.

## Links

- [Regolo.ai](https://regolo.ai) — European OpenAI-compatible GPU inference
- [Free API key](https://regolo.ai/pricing) — Pay as You Go, no commitment
- [Models Library](https://regolo.ai/models-library/)
- [Documentation](https://regolo.ai/docs)
- [Discord](https://discord.gg/wHxwWCC8)

## License

MIT — see [LICENSE](LICENSE) for details.

## Powered By

- [Regolo.ai](https://regolo.ai) — OpenAI-compatible LLM API & Brick Semantic Router
- [FastMCP](https://github.com/jlowin/fastmcp) — Standardized Model Context Protocol framework
- [Pydantic V2](https://docs.pydantic.dev/latest/) — High-performance data validation
