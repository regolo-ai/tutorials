<div align="center">
  <img src="https://regolo.ai/wp-content/uploads/2026/06/Regolo_logo_positive.png" alt="Regolo.ai Logo" width="300" />
</div>

# SoL-Pi + Regolo: Context Reduction Benchmark

<div align="center">
  <img src="https://img.shields.io/badge/build-passing-brightgreen.svg" alt="Build passing" />
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg?logo=python&logoColor=white" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/SoL--Pi-0.85-green.svg" alt="SoL-Pi 0.85" />
  <img src="https://img.shields.io/badge/Pi_Code_Agent-0.85-green.svg" alt="Pi Coding Agent 0.85" />
  <img src="https://img.shields.io/badge/API-OpenAI_Compatible-313236.svg" alt="API OpenAI Compatible" />
  <img src="https://img.shields.io/badge/License-Apache--2.0-blue.svg" alt="License: Apache-2.0" />
</div>

<br />

A reproducible smoke-test and paired benchmark for SoL-Pi, Pi Coding Agent, and Regolo — measuring observation-level context reduction (**Action Fusion + ObservationPack**) and session token savings on identical workloads powered by **Regolo `qwen3.5-122b`**.

**Reference article:**
👉 [SoL-Pi: Scalable Observation-Level Context Reduction for Coding Agents](https://arxiv.org/abs/2609.20519)

**Walkthrough video:**
👉 [SoL-Pi + Regolo: Benchmarking Token Savings on the Pi Coding Agent](https://youtu.be/bqQgXi-707g)

---

### How to Use
1. Clone this repository: `git clone https://github.com/regolo-ai/tutorials.git`
2. Navigate to the tutorial folder: `cd tutorials/sol-pi-tutorial`
3. Run the interactive setup script with green REGOLO TUI: `./setup.sh`
4. Get a free API key from Regolo to run the benchmark: [Sign Up for Free Trial](https://regolo.ai/pricing).
5. Launch the benchmark and inspect the paired token reduction report:
   ```bash
   ./run.sh --max-tasks 1   # Quick pilot (1 task across both arms)
   ./run.sh                 # Full 51-task two-arm benchmark
   ```

> [!IMPORTANT]
> ## 🎁 Special Offer: 30 Days Free Trial
>
> To power your AI coding agent, you need an API key. Sign up for Regolo today and get **30 days completely free**, plus a massive **70% discount for the following 3 months!**
>
> 🚀 **[CLICK HERE TO GET STARTED AND CLAIM YOUR FREE TRIAL](https://regolo.ai/pricing)** 🚀
>
> ---
> **Explore Regolo:** [Platform](https://regolo.ai) | [Models Library](https://regolo.ai/models-library/) | [Documentation & Guides](https://regolo.ai/docs) | [YouTube](https://www.youtube.com/@regoloai) | [Discord](https://discord.gg/wHxwWCC8)

---

```text
======================================================================
 [REGOLO] SOL-PI BENCHMARK REPORT — Regolo Qwen 3.5 122B
======================================================================
 Suite:      51 deterministic tasks (logs / csv / jsonl)
 Arms:       A = baseline (Action Fusion off)
             B = local profile (Action Fusion on, ObservationPack on)
 Attempted:  102 runs | Paired & verified: 49 / 51

 ----------------------------------------------------------------------
 INPUT TOKENS (Prompt-side observations)
 ----------------------------------------------------------------------
 Arm A total: 7,342,733 | Arm B total: 5,948,075
 Reduction:   17.2% mean (median 20.2%, pooled 19.0%)
 95% CI:      [12.1%, 21.3%]

 ----------------------------------------------------------------------
 OUTPUT TOKENS (Generated completions)
 ----------------------------------------------------------------------
 Arm A total:    32,680 | Arm B total:    33,489
 Reduction:     -2.9% mean (median -0.3%, pooled -2.5%)
 95% CI:        [-7.5%, 1.0%]

 ----------------------------------------------------------------------
 COMBINED (Input + Output)
 ----------------------------------------------------------------------
 Total A: 7,375,413 | Total B: 5,981,564
 Reduction: 17.1% mean (median 20.1%, pooled 18.9%)
 95% CI: [12.0%, 21.2%]

 ----------------------------------------------------------------------
 GATE DECISION: INCONCLUSIVE — input savings confirmed,
                output impact not significant at n=49
======================================================================
```

---

## The Efficiency Challenge

AI coding agents spend a major fraction of their context window on tool observations — verbose compiler logs, file diffs, grep results, and error traces. In multi-turn coding sessions, this observation bloat inflates context size, degrades reasoning performance, and drives up token costs.

**SoL-Pi** addresses this challenge directly at the observation layer:
- **Action Fusion:** Automatically detects and consolidates redundant or intermediate tool actions into single composite operations.
- **ObservationPack:** Losslessly compresses observation payloads before injecting them into the model's active context window.

The open question for any provider integration is:

> **Does the selected Regolo model, running behind the native Pi RPC interface, consume fewer session tokens on a paired workload while maintaining exact output correctness?**

This repository provides an automated, paired 51-task benchmark (102 runs across two arms) that rigorously measures this difference with statistical confidence intervals.

---

## Core Capabilities

1. **Two-Arm Paired Benchmarking**: Executes 51 deterministic tasks across Arm A (baseline: mechanisms disabled) vs Arm B (Action Fusion + ObservationPack enabled) under identical seeds and prompts.
2. **Deterministic Multi-Family Fixtures**: Generates synthetic `logs`, `csv`, and `jsonl` tasks from seed `54011 + task_id`, with hidden `expected.json` ground truth for automated exact-match verification.
3. **Rigorous Statistical Verification**: Computes 95% percentile bootstrap confidence intervals (5,000 resamples) across paired input, output, cache, and total token deltas.
4. **Native Pi + Regolo RPC Integration**: Configures Regolo as an OpenAI-compatible provider with `qwen3.5-122b` (262k context), utilizing Pi's RPC event protocol for accurate session-level token accounting.
5. **Interactive Cyber-Green TUI & Fast Launcher**: Complete setup script (`./setup.sh`) with brand styling, virtualenv isolation, automatic SoL-Pi checkout, and a seamless launcher script (`./run.sh`).

---

## Setup

> [!NOTE]
> The `.pi/` directory, `.venv/`, and `SoL-Pi/` checkout are **not tracked in git**. On a fresh clone, run `./setup.sh` to recreate the entire environment through the branded REGOLO green TUI.

### One-Command Setup (Recommended)

```bash
./setup.sh
```

This automated, branded TUI script executes an 8-step initialization:
1. **Verifies Prerequisites:** Checks Node.js 22+, npm, Python 3.10+, git, and the Pi CLI.
2. **Creates & Activates `.venv`:** Creates an isolated Python virtual environment.
3. **Installs Dependencies:** Upgrades pip and installs `requirements.txt` (`python-dotenv`, `rich`, `requests`).
4. **Configures Regolo Provider:** Registers `regolo` with model `qwen3.5-122b` into `~/.pi/agent/models.json`.
5. **Downloads SoL-Pi:** Clones NVLabs' SoL-Pi repository directly into `./SoL-Pi`.
6. **Registers Pi Extension:** Links `./SoL-Pi` as a project-local package (`pi install ./SoL-Pi --local --approve`).
7. **Generates Arm B Profile:** Creates `.pi/sol-pi.json` (Action Fusion + ObservationPack ON).
8. **Configures Credentials:** Prepares `.env`, validates `REGOLO_API_KEY`, and checks provider connectivity via `pi --list-models regolo`.

### Manual Setup Alternative

If you prefer manual setup:

```bash
# 1. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Clone SoL-Pi into this folder and install locally
git clone --depth 1 https://github.com/NVlabs/SoL-Pi.git SoL-Pi
pi install "$(realpath ./SoL-Pi)" --local --approve

# 3. Create Arm B profile
mkdir -p .pi
cat > .pi/sol-pi.json << 'EOF'
{
  "version": 1,
  "actionFusion": true,
  "observationPack": true,
  "evidencePreservingReducer": false,
  "onlineContextCompact": false,
  "cacheWriteReadRatio": 12.5
}
EOF

# 4. Set credentials
cp .env.example .env
export REGOLO_API_KEY="your-regolo-api-key"
```

---

## Quickstart & Usage

### 1. Launch the Benchmark via Runner Script

The `./run.sh` launcher automatically activates the virtual environment and imports `.env`:

```bash
# Quick Pilot: run 1 task across both Arm A and Arm B
./run.sh --max-tasks 1

# Full Benchmark: run all 51 tasks across both arms (102 executions)
./run.sh

# Fixture Dry-run: generate test fixtures without spending API tokens
./run.sh --dry-run
```

### 2. Routine CLI Commands & Flags

You can also run `sol_pi_two_arms.py` directly:

```bash
source .venv/bin/activate

# Run with custom model or provider
python3 sol_pi_two_arms.py --project . --provider regolo --model qwen3.5-122b

# Resume an interrupted run without re-running completed tasks
python3 sol_pi_two_arms.py --project . --resume ./sol-pi-51-20260923-XXXXXX

# Increase timeout per arm (default: 600s)
python3 sol_pi_two_arms.py --project . --timeout 900
```

| Flag | Default | Description |
|---|---|---|
| `--project` | `.` | Target project directory containing `.pi/sol-pi.json` |
| `--provider` | `regolo` | Provider identifier configured in `models.json` |
| `--model` | `qwen3.5-122b` | Regolo model identifier under test |
| `--timeout` | `600` | Maximum seconds allowed per arm execution |
| `--max-tasks` | `51` | Subset pilot runs (1 to 51) |
| `--dry-run` | off | Generates fixtures and manifest only; skips API calls |
| `--resume` | none | Resumes an existing run directory, skipping completed arms |

---

## Benchmark Design & Comparability

This suite answers a targeted operational question: **does the selected Regolo model, running this two-mechanism SoL-Pi profile, use fewer Pi-reported session tokens on comparable large-observation workloads while retaining exact output correctness?**

| Dimension | Official SoL-Pi Study | This Repository Suite | What the Difference Evaluates |
|---|---|---|---|
| **Task Suite** | 51 held-out EdgeBench long-horizon coding tasks | 51 deterministic synthetic tasks (logs, CSV, JSONL) | Generalization on coding tasks vs. controlled efficiency on repeatable workloads |
| **Active Profile** | Full SoL-Pi mechanism set (Fusion, Pack, EPR, OCC) | Action Fusion + ObservationPack; EPR/OCC disabled | Full-harness impact vs. local two-mechanism profile |
| **Model Tested** | GPT-5.6 Sol and Opus 5 | Regolo Qwen 3.5 122B (`qwen3.5-122b`) | Cross-backend robustness vs. compatibility with Regolo inference |
| **Token Metrics** | Recorded network token traffic & modeled costs | Pi RPC session tokens and local Pi cost estimates | Official study metric vs. agent session-level operational observability |
| **Quality Gate** | EdgeBench benchmark verifiers | Exact `result.json` equality with hidden `expected.json` | Broad repository modification vs. aggregation correctness |

### Statistical Interpretation

The runner pairs Arm A and Arm B for each task $i$:

$$\text{Reduction \%} = \frac{\text{Tokens}_A - \text{Tokens}_B}{\text{Tokens}_A} \times 100$$

`report.json` outputs:
- **Mean & Median Paired Reduction:** Central tendency of percentage savings across verified pairs.
- **Pooled Reduction:** Total tokens saved across all verified tasks combined: $100 \times \frac{\sum A - \sum B}{\sum A}$.
- **95% Percentile Bootstrap CI:** 5,000 Monte Carlo bootstrap resamples. A confidence interval entirely above zero confirms statistically significant token reduction.

---

## Troubleshooting

| Symptom | Cause | Resolution |
|---|---|---|
| `Model missing` | Model not declared or key missing | Check `REGOLO_API_KEY` in `.env` and verify via `pi --list-models regolo` |
| `Extension missing` | SoL-Pi not installed locally | Run `./setup.sh` or execute `pi install ./SoL-Pi --local --approve` |
| `Run failed / early exit` | Agent crashed or timed out | Inspect that arm's `pi.jsonl` and `pi.stderr` inside the task directory |
| `Inconclusive / No savings` | Small sample or simple prompts | Run full suite (`--max-tasks 51`) on observation-heavy workloads |
| `Pi command not found` | Pi CLI missing from PATH | Run `npm install -g @earendil-works/pi-coding-agent@0.85.1` |

---

## Repository Structure

```text
sol-pi-tutorial/
├── sol_pi_two_arms.py          # Deterministic 51-task paired benchmark runner
├── setup.sh                    # Automated setup script with REGOLO green TUI
├── run.sh                      # Benchmark launcher script (auto-activates .venv & loads .env)
├── requirements.txt            # Python dependencies (python-dotenv, rich, requests)
├── .env.example                # Template for REGOLO_API_KEY
├── .env                        # Your Regolo API key (git-ignored)
├── .venv/                      # Isolated Python virtual environment (created by setup.sh)
├── SoL-Pi/                     # Local clone of NVlabs/SoL-Pi (created by setup.sh)
├── .pi/                        # Local Pi configuration (created by setup.sh)
│   ├── settings.json           # Pi local package configuration
│   └── sol-pi.json             # Active profile: Action Fusion + ObservationPack
├── .gitignore                  # Excludes .env, .venv, SoL-Pi, .pi/, results
├── README.md                   # This file
└── sol-pi-51-*                 # Full-run output (manifest, results.csv, report.json, task-*)
```

---

## Dependencies

- **Pi Coding Agent** (`@earendil-works/pi-coding-agent@0.85.1`): Runs the agent loop, hosts extensions, and emits RPC telemetry.
- **SoL-Pi** (`github.com/NVlabs/SoL-Pi`): Observation-level context management extensions (Action Fusion & ObservationPack).
- **Regolo AI API**: OpenAI-compatible completions endpoint serving `qwen3.5-122b` with ultra-low latency and 262k context.
- **python-dotenv**: Automated loading of `.env` configuration.
- **rich**: Terminal formatting and green TUI components.
- **requests**: HTTP client for API health and provider validation.
- **Python 3.10+**: Standard library used for benchmark orchestration, fixture generation, and bootstrap statistics.

---

## Sources and References

- [SoL-Pi Paper (ArXiv)](https://arxiv.org/abs/2609.20519)
- [NVlabs SoL-Pi GitHub Repository](https://github.com/NVlabs/SoL-Pi)
- [Pi Coding Agent Documentation](https://pi.dev)
- [Regolo AI Platform & Pricing](https://regolo.ai/pricing)
- [Regolo Models Library](https://regolo.ai/models-library/)
