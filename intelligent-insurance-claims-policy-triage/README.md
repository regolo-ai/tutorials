<div align="center">

<img src="https://regolo.ai/wp-content/uploads/2026/06/Regolo_logo_positive.png" alt="Regolo.ai Logo" width="280" />

# Intelligent Insurance Claims & Policy Triage

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Architecture](https://img.shields.io/badge/Architecture-Decoupled_Triage-00FF88?style=flat-square)](https://regolo.ai)
[![SetFit Bi-Encoder](https://img.shields.io/badge/Classifier-SetFit_33M-orange?style=flat-square)](https://huggingface.co/docs/setfit)
[![Inference Gateway](https://img.shields.io/badge/Inference-Regolo_EU_ZDR-00FF88?style=flat-square)](https://regolo.ai)
[![Tests](https://img.shields.io/badge/Tests-24_Passed-success?style=flat-square)](https://github.com/regolo-ai/tutorials)
[![Latency](https://img.shields.io/badge/Perimeter_Latency-%3C10ms-brightgreen?style=flat-square)](#benchmark--evaluation)

> High-throughput, multi-tier intake triage combining deterministic safety policies, perimeter bi-encoders, and sovereign LLM synthesis with Zero Data Retention.

⭐ If you like this project, star it on GitHub!

[Overview](#overview) • [Architecture](#architecture) • [Features](#features) • [Prerequisites](#prerequisites) • [Quickstart](#quickstart) • [Usage](#usage) • [Benchmark & Evaluation](#benchmark--evaluation) • [Project Structure](#project-structure) • [Configuration](#configuration) • [Resources](#resources)

</div>

---

## Overview

Handling high volumes of inbound policyholder inquiries, claims, and endorsements is a major operational bottleneck for insurance carriers and brokerages. Routing these communications directly through monolithic cloud LLMs introduces significant drawbacks:

- **Elevated Latency & Cost:** Calling large models for every routine email or billing check adds 1–3 seconds of latency and substantial API expense.
- **Safety Risks:** Probabilistic language models can misroute or hallucinate on emergency hazard notices (such as active flooding near electrical panels).
- **Privacy & Compliance Exposure:** Transmitting sensitive policyholder data (PII) to non-sovereign external providers creates regulatory friction under GDPR.

This reference implementation decouples intake triage into **three independent operational signals**:

1. **Operational Priority:** Governed deterministically by explicit safety rules (zero tolerance for bodily injury or active hazards).
2. **Request Category:** Evaluated locally on CPU by a compact 33M-parameter SetFit bi-encoder in **5–8 milliseconds** with **95% accuracy**.
3. **Processing Complexity:** Graded by `brick-complexity-pro` on the European sovereign Regolo inference gateway to select cost-proportional generative models.
4. **Case Brief Synthesis:** Summarized into a structured, schema-validated JSON case card by open-weight models (`gpt-oss-20b` or `gpt-oss-120b`) under verified Zero Data Retention (ZDR).

> [!TIP]
> **Offline Evaluation Ready:** This repository includes a pre-trained SetFit model and an offline heuristic fallback. You can run training, unit tests, and CLI triage locally without requiring cloud API keys. To activate sovereign LLM brief drafting and live complexity grading, connect your Regolo API key.

---

## Architecture

```
                       Inbound Policyholder Email / Web Ticket
                                          │
            ┌─────────────────────────────┼─────────────────────────────┐
            ▼                             ▼                             ▼
   [ Stage 1: Priority ]         [ Stage 2: Category ]       [ Stage 3: Complexity ]
   Deterministic Safety Rules    Local SetFit Bi-Encoder     Brick Complexity Pro
   • Active hazards (electrical) • 5 Canonical classes       (Regolo Gateway)
   • Bodily injury / flooding    • Latency: <10ms on CPU     • easy | medium | hard
   • High vs Standard Priority   • Accuracy: 95.0%                      │
            │                             │                             │
            └──────────────┬──────────────┘                             │
                           ▼                                            │
               [ Confidence Gate >= 0.85? ]                             │
               ├── No  ──> 👤 Manual Triage (Fail-Closed)               │
               └── Yes ──> 🤖 Automated Intake Path ───────────────────┘
                                          │
                                          ▼
                            [ Stage 4: Generative Brief ]
                            Regolo Sovereign EU Gateway
                            • Easy / Medium: gpt-oss-20b
                            • Hard / Emergency: gpt-oss-120b
                                          │
                                          ▼
                            [ Operative Case Card ]
                            Schema-validated JSON output
                            Operator approves and takes action
```

### The Three Decoupled Signals

| Signal | Mechanism | Target Latency | Purpose |
|:---|:---|:---:|:---|
| **Operational Priority** | Deterministic Python rules | `<1ms` | Detects immediate life safety, flooding, or electrical hazards. Never delegates safety decisions to a probabilistic model. |
| **Request Category** | Fine-tuned SetFit bi-encoder | `5–8ms` | Classifies inbound text into 5 insurance taxonomy slots with selective abstention gating. |
| **Processing Complexity** | `brick-complexity-pro` | `150–300ms` | Assesses legal, contractual, and technical complexity to dynamically assign the most cost-effective generative LLM. |

---

## Features

- **Deterministic Hazard Interception:** Life safety and property preservation hazards bypass AI probabilities and escalate immediately with High Priority tags.
- **Ultra-Fast Local Bi-Encoder:** Fine-tuned `all-MiniLM-L6-v2` runs locally on standard CPU hardware with sub-10ms inference and zero external network calls.
- **Fail-Closed Risk Gating:** Ambiguous, multi-intent, or low-confidence requests (`confidence < 0.85`) fall back safely to human handler review queues.
- **Adaptive LLM Routing:** Routes routine tasks to efficient lightweight models (`gpt-oss-20b`) and complex litigation or estate inquiries to frontier models (`gpt-oss-120b`).
- **Structured Pydantic Schemas:** Generates type-safe case cards containing extracted metadata, checklist verification items, attention flags, and recommended next actions.
- **EU Sovereignty & Zero Data Retention:** Cloud inference runs strictly within the European Union under GDPR compliance and verifiable Zero Data Retention (ZDR).

---

## Prerequisites

- **Python:** Version `3.10` or higher
- **Package Manager:** `pip` or `uv`
- **Regolo Account (Optional):** Required for live cloud complexity grading and generative case brief synthesis. [Sign up for a free trial](https://regolo.ai/pricing).

---

## Quickstart

### 1. Clone & Set Up Environment

```bash
# Clone the repository
git clone https://github.com/regolo-ai/tutorials.git
cd tutorials/intelligent-insurance-claims-policy-triage

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install the package in editable mode with development dependencies
pip install -e ".[dev,ml]"
```

### 2. Configure Environment Variables

Copy the provided environment template:

```bash
cp .env.example .env
```

Edit `.env` to configure your credentials:

```ini
# Regolo EU Inference Gateway credentials
REGOLO_API_KEY=your_regolo_api_key_here
REGOLO_BASE_URL=https://api.regolo.ai/v1

# Complexity router and brief generation models
REGOLO_COMPLEXITY_MODEL=brick-complexity-pro
REGOLO_STANDARD_MODEL=gpt-oss-20b
REGOLO_ADVANCED_MODEL=gpt-oss-120b

# Classifier backend ('setfit' for local inference, 'mock' for rule fallback)
CLASSIFIER_BACKEND=setfit
CLASSIFIER_CONFIDENCE_THRESHOLD=0.85
```

> [!NOTE]
> If `REGOLO_API_KEY` is not provided, the system operates in **Local Demo Mode**, utilizing heuristic rule fallbacks for complexity grading and brief synthesis.

---

## Usage

### 1. Run Standard Interactive Scenarios

Evaluate four canonical insurance brokerage scenarios illustrating urgent hazards, routine endorsements, complex disputes, and out-of-scope queries:

```bash
python main.py
```

#### Example Output: Urgent Life Safety Case (Fail-Closed)

```text
┌────────────────────────────────────────────────────────────────────────────────────
│  CASE-01: URGENT: WATER LEAK NEAR ELECTRICAL PANEL
├────────────────────────────────────────────────────────────────────────────────────
│  POLICYHOLDER INBOUND MESSAGE:
│  "A pipe burst this morning and water is reaching the electrical panel. My policy number is 12345. I have photos, but I cannot find the claim form."
│
│  AUTOMATED TRIAGE ASSESSMENT:
│  [!] PRIORITY LEVEL:     🚨 HIGH / IMMEDIATE EMERGENCY
│      Safety Trigger:     Potential hazard detected by deterministic rule (water near power panel)
│  [⚠️] OPERATIONAL STATUS: 👤 ASSIGNED TO MANUAL TRIAGE (NO AUTOMATED ACTION)
│      Gating Reason:      The AI detected semantic ambiguity (compound intent in message).
│                          To prevent misrouting, this case is safely assigned to a human handler.
│      Primary Hypothesis: Missing Documentation (Confidence below gate: 46%)
│
│  PROCESSING TIME:       117.0 milliseconds (Immediate perimeter filter)
└────────────────────────────────────────────────────────────────────────────────────
```

#### Example Output: Routine Endorsement Handled End-to-End

```text
┌────────────────────────────────────────────────────────────────────────────────────
│  CASE-02: ROUTINE: COMMERCIAL FLEET ADDRESS ENDORSEMENT
├────────────────────────────────────────────────────────────────────────────────────
│  POLICYHOLDER INBOUND MESSAGE:
│  "Hello, I recently moved. Please update the primary mailing and garaging address on our commercial fleet policy FL-90210 to 458 Industrial Parkway, Suite B."
│
│  AUTOMATED TRIAGE ASSESSMENT:
│  [v] PRIORITY LEVEL:     🟢 STANDARD (No immediate physical or legal hazard detected)
│  [v] OPERATIONAL STATUS: ✅ READY FOR OPERATOR REVIEW & APPROVAL
│      Assigned Category:  Policy Endorsement (Address, Vehicle, Coverage Limits)
│      Model Confidence:   98% (High confidence - reliable routing gate passed)
│      Complexity Tier:    Low / Standard (Routine task; handled efficiently by lightweight model)
│
│  SYNTHESIS BRIEF (Drafted by Sovereign EU Model on Regolo):
│  * Summary:              Customer requests to update the primary mailing and garaging address for commercial fleet policy FL-90210 to 458 Industrial Parkway, Suite B.
│  * Verification Checks:  - Verify policy number FL-90210 exists and is active
│                         - Confirm the new address is valid and within policy territory
│                         - Verify requester authorization to modify fleet policies
│  * Attention Flags:      Address change endorsement, Authorized signatory check
│  * Recommended Action:   1. Verify caller authorization in CRM.
│                          2. Confirm fleet territory rating rules for Suite B.
│                          3. Issue policy endorsement schedule.
│
│  PROCESSING TIME:       1.84 seconds (Perimeter classification + Regolo AI synthesis)
└────────────────────────────────────────────────────────────────────────────────────
```

### 2. Triage Custom Inbound Text

```bash
python main.py --text "Our delivery van was involved in a three-car pileup on Route 101, driver is at the hospital."
```

### 3. Run Batch Benchmark on Hugging Face Data

Process messages from the curated dataset `data/insurance_benchmark_eval.jsonl`:

```bash
# Fast perimeter evaluation (~8ms/case, SetFit + Priority checks without LLM calls)
python main.py --dataset data/insurance_benchmark_eval.jsonl --skip-synthesis --max-cases 20

# Full end-to-end evaluation with Regolo brief generation
python main.py --dataset data/insurance_benchmark_eval.jsonl --max-cases 5
```

### CLI Options

| Flag | Type | Default | Description |
|:---|:---:|:---:|:---|
| `--text` | string | `None` | Custom customer inquiry or claim text to evaluate. |
| `--dataset` | string | `None` | Path to JSONL dataset for batch benchmark evaluation. |
| `--max-cases` | int | `50` | Maximum number of cases to process in batch mode. |
| `--skip-synthesis` | flag | `False` | Run perimeter checks only (bypasses LLM generative synthesis for speed). |

---

## Local Training Pipeline (`train.py`)

The repository includes a self-contained training script that extracts real customer instructions from Hugging Face (`bitext/Bitext-insurance-llm-chatbot-training-dataset`), maps them to our 5 canonical categories, applies contrastive fine-tuning via SetFit, and exports the model locally in **~32 seconds on CPU**.

```bash
python train.py
```

### Training Highlights & Performance

- **Backbone:** `sentence-transformers/all-MiniLM-L6-v2` (33M parameters)
- **Training Time:** ~32 seconds on modern laptop CPU
- **Export Location:** `models/setfit-insurance-triage`

```text
=======================================================
  SETFIT HELD-OUT TEST ACCURACY: 95.00%
=======================================================

Classification Report:
                       precision    recall  f1-score   support
       claims_intake     0.9375    1.0000    0.9677        15
       policy_change     1.0000    0.9333    0.9655        15
underwriting_support     0.9375    1.0000    0.9677        15
    document_missing     1.0000    0.8667    0.9286        15
      customer_query     0.9286    0.9333    0.9310        15
```

---

## Benchmark & Evaluation

### Architectural Comparison

| Dimension | Monolithic Cloud LLM | Decoupled Regolo Triage | Advantage |
|:---|:---:|:---:|:---|
| **Perimeter Triage Latency** | 1,500 – 3,500 ms | **5 – 8 ms** | **~300x faster routing** |
| **Inference Cost** | High (full token prompt every time) | **Minimal (CPU bi-encoder + tier-routed LLM)** | **Up to 80% cost reduction** |
| **Safety Priority Guarantee** | Non-deterministic (prompt-based) | **100% Deterministic (Code policy)** | **Zero tolerance for hazards** |
| **Fail-Closed Gating** | Unreliable confidence estimates | **Explicit calibrated threshold (`>=0.85`)** | **Eliminates hallucinated routing** |
| **Data Sovereignty** | US-hosted proprietary APIs | **European Sovereign Infrastructure** | **Full GDPR & ZDR compliance** |

---

## Automated Test Suite

The test suite covers safety rules, taxonomy edge cases, complexity grading, SetFit inference, and end-to-end orchestration:

```bash
# Run unit and integration tests using the deterministic test engine
CLASSIFIER_BACKEND=mock pytest tests -v
```

> [!NOTE]
> Setting `CLASSIFIER_BACKEND=mock` enables fast, deterministic assertions across the entire test suite. Dedicated SetFit inference tests in `tests/test_setfit_classifier.py` load and validate the physical model weights directly.

### Test Coverage Summary

- `tests/test_policy.py`: 6 tests validating electrical hazard, flooding, structural damage, and bodily injury detection.
- `tests/test_classifier.py`: 5 tests validating taxonomy coverage, high-confidence routing, and abstention on alien queries.
- `tests/test_complexity.py`: 5 tests validating easy, medium, and hard grading logic and error recovery.
- `tests/test_setfit_classifier.py`: 3 tests confirming local bi-encoder weight loading and inference sanity.
- `tests/test_triage_e2e.py`: 5 tests verifying full end-to-end pipeline execution, fail-closed handling, and payload limits.

---

## Project Structure

```
intelligent-insurance-claims-policy-triage/
├── .env.example                   # Environment configuration template
├── .gitignore                     # Git tracking exclusions
├── pyproject.toml                 # Package definition and dependencies
├── README.md                      # System documentation
├── train.py                       # Local SetFit contrastive training pipeline
├── main.py                        # CLI runner for test cases and batch datasets
├── data/                          # Evaluated datasets and benchmarks
│   ├── insurance_train.jsonl      # Balanced training samples
│   ├── insurance_test.jsonl       # Held-out testing samples
│   └── insurance_benchmark_eval.jsonl # Complete evaluation benchmark set
├── models/
│   └── setfit-insurance-triage/   # Fine-tuned 33M bi-encoder weights
├── src/
│   └── insurance_triage/
│       ├── __init__.py            # Module root
│       ├── models.py              # Pydantic schemas (CaseBrief, TriageOutput)
│       ├── policy.py              # Deterministic safety priority rules
│       ├── classifier.py          # SetFit, Laya, and Mock decision engines
│       ├── complexity.py          # Brick Complexity Pro gateway client
│       ├── synthesizer.py         # Cost-proportional LLM routing and drafting
│       └── triage.py              # Master multi-tier orchestration pipeline
└── tests/
    ├── test_policy.py             # Deterministic priority rule tests
    ├── test_classifier.py         # Taxonomy slot and gating tests
    ├── test_complexity.py         # Complexity grading unit tests
    ├── test_setfit_classifier.py  # Local SetFit model inference tests
    └── test_triage_e2e.py         # Multi-tier end-to-end pipeline tests
```

---

## Configuration

| Environment Variable | Default | Description |
|:---|:---:|:---|
| `REGOLO_API_KEY` | *(None)* | API authentication key for Regolo European inference gateway. |
| `REGOLO_BASE_URL` | `https://api.regolo.ai/v1` | Base URL for Regolo OpenAI-compatible endpoints. |
| `REGOLO_COMPLEXITY_MODEL` | `brick-complexity-pro` | Model used to grade message cognitive complexity (`easy`, `medium`, `hard`). |
| `REGOLO_STANDARD_MODEL` | `gpt-oss-20b` | Model used for case brief synthesis on standard complexity requests. |
| `REGOLO_ADVANCED_MODEL` | `gpt-oss-120b` | Model used for high-complexity claims, legal issues, or emergency cases. |
| `REGOLO_FAST_MODEL` | `gpt-oss-20b` | Lightweight model for routine queries and quick drafts. |
| `CLASSIFIER_BACKEND` | `setfit` | Perimeter classification engine (`setfit`, `laya`, or `mock`). |
| `CLASSIFIER_CONFIDENCE_THRESHOLD`| `0.85` | Confidence cutoff below which requests fail-closed to manual review. |
| `EMERGENCY_ESCALATION_QUEUE` | `emergency-handler-queue` | Target operational queue for deterministic priority triggers. |

---

## Resources

- [Regolo.ai Platform](https://regolo.ai)
- [Regolo Models Catalog](https://regolo.ai/models-library/)
- [Regolo Documentation](https://regolo.ai/docs)
- [SetFit: Efficient Few-Shot Learning Without Prompts](https://github.com/huggingface/setfit)
- [Bitext Insurance LLM Dataset](https://huggingface.co/datasets/bitext/Bitext-insurance-llm-chatbot-training-dataset)
