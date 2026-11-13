<div align="center">
  <img src="https://regolo.ai/wp-content/uploads/2026/06/Regolo_logo_positive.png" alt="Regolo.ai Logo" width="300" />
</div>

<div align="center">
  <h1>Closed-Loop: Self-Correcting AI Code Reviewer</h1>
</div>

<div align="center">
  <img src="https://img.shields.io/badge/build-passing-brightgreen.svg" alt="Build passing" />
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg?logo=python&logoColor=white" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/Code-Runnable_Examples-2ea44f.svg" alt="Code: Runnable Examples" />
  <img src="https://img.shields.io/badge/GPU-100%25_Ready-0078D4.svg" alt="GPU 100% Ready" />
  <img src="https://img.shields.io/badge/API-OpenAI_Compatible-313236.svg" alt="API OpenAI Compatible" />
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT" />
</div>

<br />

Production-ready implementation of the article:
https://regolo.ai/how-to-build-a-closed-loop-ai-agent-that-catches-its-own-hallucinations/


Ship self-correcting AI code reviews that learn from past failures.

## Why this project matters

- Eliminates stateless AI reviews that repeat hallucinations
- Compounds knowledge over time through a semantic feedback loop
- Reduces false positives and first-attempt success rate
- Catches structural and semantic bugs with dual-gate verification
- Works without Qdrant (stateless mode) for quick deployment
- Cost tracking per iteration and aggregate usage

## Project Overview

This repository implements a **closed-loop AI agent** that generates code patches and verifies them through multiple gates. When verification fails, the exact error is fed back into the LLM for another generation attempt. Each cycle is logged, and lesson summaries accumulate into a persistent skill file that improves future generations.

### Key Features

| Feature | Description | Benefit |
|---------|-------------|---------|
| **Closed-loop retries** | Up to N iterations; each failure becomes feedback | Eliminates hallucinated fixes |
| **Dual-gate verification** | Gate 1: deterministic compile/syntax/markdown; Gate 2: LLM semantic checker | High-confidence patch acceptance |
| **Semantic retrieval** | Qdrant indexes code chunks, docs, prior reviews | Context-aware patch generation |
| **Cross-encoder reranking** | Qwen3-Reranker-4B filters top-k candidates | Reduced noise, improved precision |
| **Persistent knowledge** | Lessons accumulate in `code_review_skill.md` | System learns over time |
| **Full audit trail** | `review_audit.json` logs every LLM call, cost, iteration | Compliance and debugging |
| **Graceful degradation** | Works without Qdrant or reranker via env flags | Easy to shoehorn into existing CI |
| **Multi-tenant filtering** | Payload fields: `repo_id`, `team`, `language` | Isolated context per squad |

## Architecture

```
+------------------------------------------------------------------
|                    CLOSED-LOOP PIPELINE
+------------------------------------------------------------------
|
  [PR / IDE / CLI Event]
          │
          ▼
  +------------------------+
  |    Review Orchestrator   |  ← policy, workflow state, cost limits
  +------------------------+
              │
  +-----------+-----------+----------------------+
  ▼                               ▼
+--------------------+    +------------------+
|  Retrieval Layer   │    |  Operational Store  |
|  Qdrant            │    |  audit JSON, STATE, |
|  · code_chunks     │    |  review_audit.json  |
|  · tech_docs       │    +------------------+
|  · review_memory   │
+--------+-----------+
         │ top-k candidates
         ▼
  +------------------------+
  |   Rerank Layer          |  ← Qwen3-Reranker-4B cross-encoder
  +------------------------+
         │ top-n context
         ▼
  +------------------------+
  |   Reviewer Model         |  ← gpt-oss-120b (making)
  |   call_model()          |
  +------------------------+
         │
  +-----------+---------------------------+
  ▼                                       ▼
+--------------------+      +----------------------+
|   Gate 1           │      │   Gate 2              |
|   Deterministic    │      │   Semantic Checker    |
|   compile/lint     │      │   checker LLM         |
|   markdown check   │      │   gemma4-31b default  |
+--------------------+      +----------+------------+
                                       │
                              +--------+--------+
                              │      PASS       │
                              ▼
  +------------------------+
  |   EXECUTE              |  ← deploy patch to disk
  |   backup + write       |
  +------------+-----------+
               │
               ▼
  +------------------------+
  |   Feedback Layer        |  ← persist to Qdrant  |
  |   · flush lessons       |  ← append to skill file
  |   · propose doc patch   |  ← re-index next run
  +------------------------+
```

Each iteration that fails feeds its exact error message back into the next `GENERATE` call — this is the **closed loop**.

## Included use cases

1. Interactive CLI menu: run built-in demo or review a target file
2. Programmatic Python API: integrate into custom workflows
3. CI-ready: stateless mode (`USE_QDRANT=false`) avoids vector DB requirements
4. Demo file generator: `src_to_review/math_service.py` auto-created

## Project structure

- `main.py`: entry point — menu, client setup, orchestrator call
- `src/`
  - `__init__.py`: package init
  - `config.py`: Settings dataclass + env loading
  - `models.py`: UsageRecord, IterationRecord, RetrievalResult
  - `utils.py`: shared helpers: clean_llm_text, safe_json_parse
  - `retrieval.py`: QdrantRetriever — index, search, persist_outcome
  - `reranker.py`: Qwen3Reranker — POST /v1/rerank integration
  - `reviewer.py`: CodeReviewer — call_model, verify, generate_patch
  - `feedback.py`: FeedbackManager — lessons, skill file, Qdrant persistence
  - `orchestrator.py`: ReviewOrchestrator — full 7-stage pipeline
- `src_to_review/`: default directory for target files to review
- `review_output/`
  - `review_audit.json`: full audit trail (created at runtime)
  - `review_summary.json`: summary for CI/CD consumption
- `code_review_skill.md`: persistent knowledge — grows with each run
- `STATE.md`: timeline of review events
- `requirements.txt`: Python dependencies
- `.env.example`: template for configuration

## Quick Start

### Branded CLI Setup & Launch

The fastest way to get started is by using our custom branded CLI utility **`setup.sh`**, which automates the setup of python environments, requirements, `.env` file key bindings, and launches local services like Qdrant automatically.

Simply run the executable in the project root:

```bash
./setup.sh
```

This interactive utility will:
1. Initialize/detect your Python 3.10+ Virtual Environment (`.venv`) and install dependencies automatically.
2. Prompt you for your `REGOLO_API_KEY` and write it safely into `.env`.
3. Check for Docker/Qdrant and spin up the vector database, or gracefully configure **Stateless Mode** if Docker isn't running.
4. Offer an elegant menu to test connectivity, show services health status, or immediately launch the closed-loop code reviewer.

### Quick Command Reference

For terminal automation or pipeline integration, the `./setup.sh` utility supports CLI arguments:

```bash
./setup.sh setup   # Run non-interactive full environment/service setup
./setup.sh run     # Launch the Closed-Loop Code Reviewer pipeline directly
./setup.sh status  # Display health and availability of all project components
./setup.sh help    # Display the branded CLI usage guidelines
```

### Manual Installation (Fallback)

If you prefer to configure everything manually:

#### 1. Prerequisites

- Python 3.10+
- A [Regolo.ai](https://regolo.ai) API key
- (Optional) Qdrant running locally or on cloud

#### 2. Install

```bash
git clone https://github.com/alexgenovese/closed-loop.git
cd closed-loop
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

#### 3. Configure

```bash
cp .env.example .env
# Edit .env and set your REGOLO_API_KEY
```

Minimal `.env`:
```env
REGOLO_API_KEY=your_api_key_here
BASE_URL=https://api.regolo.ai/v1
```

Full `.env` with all options:
```env
REGOLO_API_KEY=your_api_key_here
BASE_URL=https://api.regolo.ai/v1

REGOLO_MAKER_MODEL=gpt-oss-120b
REGOLO_CHECKER_MODEL=gemma4-31b
MAX_ITERATIONS=3

# Qdrant — disable with USE_QDRANT=false if not available
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=
USE_QDRANT=true

# Reranker
RERANKER_MODEL=Qwen/Qwen3-Reranker-4B
USE_RERANKER=true
```

#### 4. (Optional) Start Qdrant

```bash
docker run -p 6333:6333 qdrant/qdrant
```

#### 5. Run

```bash
python main.py
```

Choose **option 1** to run the built-in demo on a buggy Python file, or **option 2** to review any file on disk.

## Programmatic Usage

Integrate Closed-Loop into your own codebase:

```python
from pathlib import Path
from openai import OpenAI
from src.config import Settings, PricingConfig
from src.orchestrator import ReviewOrchestrator

settings = Settings.from_env()
client = OpenAI(api_key="YOUR_KEY", base_url=settings.base_url)
pricing = PricingConfig()

orchestrator = ReviewOrchestrator(
    client=client,
    pricing=pricing,
    settings=settings,
    target_file=Path("src_to_review/my_service.py"),
)
result = orchestrator.run()
print(result["status"])       # SUCCESS or FAILED_AFTER_RETRIES
print(result["usage"])        # token counts and cost
print(result["iteration_log"]) # full audit trail
```

## Running on Your Own Code

```bash
# Option 2 from the interactive menu:
python main.py
> Choose an option [1]: 2
> Enter path to Python file to review: /path/to/your/service.py
```

## Enterprise Use Cases

### Fintech — Payment Service Validation

A payment processing team runs Closed-Loop on every PR touching transaction logic. Gate 1 catches syntax regressions before CI starts. Gate 2 uses a checker model to verify that currency rounding behavior is preserved. Past accepted fixes for `Decimal` precision bugs are stored in Qdrant and retrieved automatically the next time a similar file is reviewed — reducing review time from 45 minutes to under 5.

```python
# Index your entire payments module into Qdrant once
from src.retrieval import QdrantRetriever
retriever = QdrantRetriever(url="http://qdrant:6333")
for py_file in Path("payments/").rglob("*.py"):
    retriever.index_file(py_file, repo_id="payments-service", language="python")
```

### SaaS Platform — Multi-Tenant Code Safety

A SaaS platform with 12 engineering squads uses payload filters to scope retrieval per team. When Squad A's auth service is reviewed, only `owner_team=auth` code chunks and ADRs are retrieved. This prevents cross-team context noise and ensures the reviewer model sees the most relevant ownership context.

```python
# Retrieve only auth-team context
results = retriever.search(
    query="JWT token expiry validation bug",
    filters={"owner_team": "auth", "language": "python"},
    top_k=10,
)
```

### CI/CD Integration — GitHub Actions

```yaml
# .github/workflows/code-review.yml
name: Closed-Loop Code Review
on: [pull_request]

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt
      - name: Run closed-loop review
        env:
          REGOLO_API_KEY: ${{ secrets.REGOLO_API_KEY }}
          USE_QDRANT: "false"   # stateless mode for CI
          USE_RERANKER: "false"
        run: |
          python -c "
          from pathlib import Path
          from openai import OpenAI
          from src.config import Settings, PricingConfig
          from src.orchestrator import ReviewOrchestrator
          settings = Settings.from_env()
          client = OpenAI(api_key='${{ secrets.REGOLO_API_KEY }}', base_url=settings.base_url)
          orch = ReviewOrchestrator(client, PricingConfig(), settings, Path('src_to_review/target.py'))
          r = orch.run()
          exit(0 if r['status'] == 'SUCCESS' else 1)
          "
      - uses: actions/upload-artifact@v4
        with:
          name: review-audit
          path: review_output/
```

### Compliance & Audit Trail

Every review produces a structured JSON artifact at `review_output/review_audit.json`:

```json
{
  "status": "SUCCESS",
  "iterations": 2,
  "target_file": "src_to_review/payment_processor.py",
  "verifier_reason": "Patch correctly adds missing colon and preserves all function signatures.",
  "usage": {
    "total_prompt_tokens": 1842,
    "total_completion_tokens": 387,
    "total_estimated_cost_usd": 0.006
  },
  "iteration_log": [
    {"iteration": 1, "stage": "VERIFY_STRUCTURAL", "status": "FAIL", "reason": "SyntaxError on line 14: invalid syntax"},
    {"iteration": 2, "stage": "EXECUTE", "status": "PASS", "reason": "Patch is minimal and correct."}
  ]
}
```

This artifact is consumable by SIEM, compliance dashboards, or custom audit tooling.

## Labels

- `Python`
- `Runnable`
- `GPU 100% Ready`

### How to Use

1. Clone this repository: `git clone https://github.com/regolo-ai/tutorials.git`
2. Navigate to the desired tutorial folder.
3. Follow the instructions in the folder's README.md.
4. Get a free API key from Regolo to run the code: [Sign Up for Free Trial](https://regolo.ai/pricing).
5. Run the code and see the results in minutes.

## Qdrant Payload Schema

As defined in the ROADMAP, these payload fields are indexed for filtered search:

| Field | Type | Purpose |
|---|---|---|
| `tenant_id` | keyword | Multi-tenant isolation |
| `repo_id` | keyword | Repository-scoped retrieval |
| `path` | text | File path filtering |
| `language` | keyword | Language-specific routing |
| `owner_team` | keyword | Ownership-aware context |
| `source_kind` | keyword | `code` / `doc` / `review` / `incident` |
| `updated_at` | float (epoch) | Freshness ranking |
| `content` | text | Raw chunk text for retrieval |

## Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `REGOLO_API_KEY` | — | **Required.** Regolo.ai API key |
| `BASE_URL` | `https://api.regolo.ai/v1` | Regolo API base URL |
| `REGOLO_MAKER_MODEL` | `gpt-oss-120b` | Model that generates patches |
| `REGOLO_CHECKER_MODEL` | `gemma4-31b` | Independent semantic verifier model |
| `MAX_ITERATIONS` | `3` | Max retry attempts per review |
| `DEFAULT_INPUT_COST_PER_1K` | `0.0020` | USD cost per 1K input tokens |
| `DEFAULT_OUTPUT_COST_PER_1K` | `0.0060` | USD cost per 1K output tokens |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant instance URL |
| `QDRANT_API_KEY` | `` | Qdrant API key (Qdrant Cloud) |
| `USE_QDRANT` | `true` | Enable/disable retrieval layer |
| `RERANKER_MODEL` | `Qwen/Qwen3-Reranker-4B` | Reranker model name |
| `RERANKER_ENDPOINT` | `` | Override reranker URL (defaults to `BASE_URL`) |
| `USE_RERANKER` | `true` | Enable/disable reranking |

## How the Feedback Loop Improves Reviews Over Time

```
Review outcome
     │
     ▼
Normalize finding → classify pattern → persist to Qdrant review_memory
     │
     ▼
Append lesson to code_review_skill.md
     │
     ▼
Next review: lesson injected into GENERATE prompt
Next review: similar outcome retrieved from review_memory
     │
     ▼
Reviewer model sees: "In a previous review of a similar file,
the fix was X. The structural gate failed because Y."
```

Over time the system stops repeating the same mistakes, stops generating the same false positives, and starts producing first-attempt patches that pass both verification gates — reducing iteration count and LLM cost.

## Links

- [Regolo.ai](https://regolo.ai) — European OpenAI-compatible GPU inference
- [Free API key](https://regolo.ai/pricing) — Pay as You Go, no commitment
- [Models Library](https://regolo.ai/models-library/)
- [Documentation](https://regolo.ai/docs)
- [Discord](https://discord.gg/wHxwWCC8)

## License

MIT — see [LICENSE](LICENSE) for details.

## Powered By

- [Regolo.ai](https://regolo.ai) — OpenAI-compatible LLM API
- [Qdrant](https://qdrant.tech) — Vector database for semantic memory
- [Qwen3-Reranker-4B](https://huggingface.co/Qwen/Qwen3-Reranker-4B) — Cross-encoder reranker
