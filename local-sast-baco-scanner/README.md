# BACO Scanner TUI — Regolo.ai Edition

![BACO](https://img.shields.io/badge/BACO-v1.1.0-blue?logo=rust)
![Regolo.ai](https://img.shields.io/badge/Regolo.ai-EU%20Cloud-9254de?logo=openai)
![Brick Complexity Pro](https://img.shields.io/badge/Model-brick--complexity-pro-purple)
![Cost Currency](https://img.shields.io/badge/Cost-EUR-yellow)
![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)
![License](https://img.shields.io/badge/License-Apache%202.0-blue)

**Interactive Terminal User Interface for BACO Security Scanner**, powered
exclusively by **Regolo.ai** European cloud infrastructure with real-time cost
tracking via **Brick Complexity Pro** and automated AI vulnerability remediation.

<div align="center">

```
╔══════════════════════════════════════════════════════════╗
║  BACO — Bug Analysis & Cross-reference Orchestrator     ║
║  Powered by Regolo - Zero Data Retention, EU infra      ║
║  Cost: €0.12 / 1M tokens (Brick Complexity Pro)        ║
╚══════════════════════════╦═══════════════════════════════╝
                      ▼
   ┌────────────────────────────────────────────────────┐
   │  [1] Setup Environment (Regolo.ai API Key)        │
   │  [2] Scan Repository & View Findings + Cost       │
   │  [3] Generate AI Fixes for Vulnerabilities         │
   │  [4] Exit                                         │
   └────────────────────────────────────────────────────┘
```

</div>

---

## Prerequisites

| Requirement | Minimum |
|---|---|
| Python | 3.10+ |
| Rust/Cargo | 1.70+ (for compiling the BACO binary) |
| Semgrep | Optional but recommended (`pipx install semgrep` or `brew install semgrep`) |
| Regolo.ai API key | Get one at [regolo.ai](https://regolo.ai) |

> BACO is a research-backed SAST scanner combining Semgrep static analysis with
> an LLM-powered 24-phase pipeline (CWE routing, exploit synthesis, threat
> modeling, triage, and more).

---

## Quick Start

Launch the interactive TUI:

```bash
chmod +x launch.sh
./launch.sh
```

Or run directly with Python:

```bash
python3 baco_tui.py
```

> **Zero extra dependencies**: the TUI uses only Python 3 standard library.
> The BACO Rust binary is automatically cloned and compiled on first run.

### 🧪 Instant Demo / Test Target

An intentionally vulnerable sample application is included in `demo-vulnerable-app/`.
To test the scanner and AI remediation immediately:
1. Run `./launch.sh` and select **[2]**.
2. Enter target path: `demo-vulnerable-app`
3. View the findings, executive cost card in EUR, and choose **[3]** to generate AI patches.

---

## TUI Menu Options

### Option 1 — Setup Environment

- Securely stores `REGOLO_API_KEY` in `.env` (gitignored).
- Fetches available models from `https://api.regolo.ai/v1/models`.
- Defaults to `brick-complexity-pro`.
- Generates a fully optimized `my-config.toml`.

### Option 2 — Scan Repository & Cost Breakdown

- Select any repository path (drag-and-drop paths are sanitized).
- Live streamed output from all 24 BACO phases with colored, categorized logs:

| Badge | Color | Phase |
|---|---|---|
| `[SCANNER]` | Blue | Orchestrator, pipeline control |
| `[LLM]` | Magenta | Static analysis, discovery, verification |
| `[INDEXING]` | Cyan | File enumeration and hash tracking |
| `[SEMGREP]` | Yellow | Static pattern matching |
| `[CWE-ROUTING]` | Red | Vulnerability classification |
| `[REPORTING]` | Green | Final report generation |

- Executive summary card with:
  - Severity counts (Critical, High, Medium, Low, Info).
  - Files analyzed and estimated token consumption.
  - **Total scan cost in EUR** (Brick Complexity Pro: €0.12 per 1M tokens).
  - Link to the interactive HTML report.
  - One-click prompt to generate AI fixes for findings.

### Option 3 — Generate AI Fixes for Vulnerabilities

- Analyzes each finding with the selected Regolo.ai model.
- Produces root-cause analysis, security rationale, fixed code, and unified diffs.
- Packages remediations into a timestamped directory:

```
remediations/
└── 2026-09-08_14-17-41_crypto/
    ├── llm_fix_instructions.md   # Multi-LLM prompt (Claude Code, Cursor, Copilot)
    ├── fixes.json                # Structured remediation data
    ├── README.md                 # Executive summary table
    └── patches/
        ├── fix_01_CWE-79_input_valid.py.patch
        ├── fix_02_CWE-89_sql_injection.py.patch
        └── ...
```

---

## Command-Line Usage

The TUI can also be driven from shell scripts and CI pipelines:

```bash
# Scan a repository (non-interactive)
python3 baco_tui.py scan /path/to/repo

# Generate AI fixes from the last scan's findings
python3 baco_tui.py fix

# Print cost breakdown for the last scan
python3 baco_tui.py cost

# Configure API key and select a model
python3 baco_tui.py setup

# Show usage
python3 baco_tui.py --help
```

---

## Cost Calculation

All costs are calculated in **EUR (€)** based on Brick Complexity Pro pricing
on Regolo.ai (€0.12 per 1,000,000 tokens).

The formula accounts for:

1. **Base file analysis tokens** — ~5,100 tokens per file (prompt + completion)
   for the LLM Static Analysis phase.
2. **Code chunk tokens** — bytes of code analyzed divided by 4 (rough estimate).
3. **Finding triage tokens** — ~1,800 tokens per vulnerability finding.

Even with 0 findings, the LLM still analyzes every file, so cost is always > 0.

```
Example: 7 files, 48,209 tokens → €0.005785 EUR
```

---

## Project Structure

```
baco-scanner-tui/
├── launch.sh              # Executable entry point (launches Python TUI)
├── baco_tui.py            # Main TUI application (Python, stdlib only)
├── my-config.toml         # BACO configuration (Regolo.ai endpoint + model)
├── .env                   # Regolo AI API key (create at runtime via Option 1)
├── prompts/               # Symlink to prompt templates (auto-created)
├── baco-output/           # Scan results (gitignored)
│   ├── findings.json      # Structured vulnerability findings
│   ├── findings.md        # Human-readable findings report
│   ├── report.html        # Interactive HTML report
│   ├── checkpoint.json    # Resume checkpoint
│   └── file_hashes.json   # Incremental scan hash store
├── remediations/          # Generated fix packages (gitignored)
│   └── <timestamp>_<project>/
│       ├── llm_fix_instructions.md
│       ├── fixes.json
│       ├── README.md
│       └── patches/*.patch
└── baco-scanner/          # BACO Rust binary (cloned at runtime)
```

---

## Configuration Reference

The TUI generates `my-config.toml` during setup. Key sections:

| Section | Description |
|---|---|
| `[project]` | Target path, languages |
| `[scanner]` | File size limits, exclusion patterns |
| `[scanner.performance]` | Incremental scan, parallel tasks, confidence scoring |
| `[llm]` | Timeout, retries, temperature |
| `[llm.phases.*]` | Per-phase LLM config (all point to Regolo.ai) |
| `[brick]` | Brick Complexity Pro model configuration |

---

## Environment Variables

Copy `.env.example` to `.env` to configure your API key manually, or use Option 1 in the TUI:

| Variable | Required | Source | Description |
|---|---|---|---|
| `REGOLO_API_KEY` | **Yes** | `.env` / config | Regolo.ai API key (exclusively used for all LLM phases & fixes) |
| `NVD_API_KEY` | Optional | `.env` | NIST NVD API key (optional, only if CVE bootstrap is enabled) |

> Only Regolo.ai credentials are required. No third-party AI provider keys (OpenAI, Mistral, etc.) are needed.

---

## How BACO's 24-Phase Pipeline Works

BACO runs a sequential pipeline of phases, each producing intermediate results:

1. **Indexing** — file enumeration and hash tracking
2. **Semgrep** — static pattern matching (CWE rules)
3. **CPG Slice** — Code Property Graph analysis (optional)
4. **LLM Static Analysis** — per-file LLM vulnerability review
5. **CWE Routing** — classify findings by CWE
6. **Rule Synthesis** — generate custom detection rules
7. **LLM Discovery** — identify additional attack vectors
8. **LLM Verification** — verify finding credibility
9. **Validate** — confirm code reachability
10. **Security Agent Verification** — cross-check with security heuristics
11. **Ticket Cross-Reference** — link findings to known CVEs
12. **Git Analysis** — review commit history for context
13. **Cross-File Analysis** — data flow across modules
14. **Confidence Scoring** — assign risk scores
15. **AI Aggregation** — consolidate duplicate findings
16. **Threat Modeling** — attack tree generation
17. **Root Cause Dedup** — eliminate noise
18. **Multi-Verifier** — cross-validation (off by default)
19. **Auto-Patching** — automated fix generation (off by default)
20. **CVE Bootstrap** — seed known vulnerability database
21. **POC Compiler** — proof-of-concept generation (off by default)
22. **Exploit Synthesis** — generate exploit scenarios
23. **Variant Search** — find similar vulnerable patterns
24. **Reporting** — final report compilation (JSON, HTML, SARIF)

---

## Troubleshooting

### The TUI reports "Compiled binary not found"

The BACO Rust binary needs to be compiled on first run. Ensure `cargo` and
`rustc` are installed:

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

### Scan shows 0 findings

BACO uses incremental scanning with hash tracking. Files marked as "unchanged"
from a previous scan are skipped. To force a full re-scan, the TUI passes
`--force` automatically. If hashes are stale, delete `baco-output/` and rerun.

### HTML report appears empty

If findings.json contains `[]` (zero findings), the HTML report will correctly
display "No security issues detected." This is expected behavior, not a bug.

### Cost always shows €0.00

The cost calculation reads `file_hashes.json` from `baco-output/`. If this file
is missing or empty, the TUI falls back to scanning the target directory. Ensure
the target path contains source files in supported languages.

---

## License

Apache 2.0. See [LICENSE](LICENSE).
