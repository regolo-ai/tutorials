<div align="center">
  <img src="https://regolo.ai/wp-content/uploads/2026/06/Regolo_logo_positive.png" alt="Regolo.ai Logo" width="300" />
</div>

# Advanced RAG in 2026: Long Context Is Not Memory

<div align="center">
  <img src="https://img.shields.io/badge/build-passing-brightgreen.svg" alt="Build passing" />
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg?logo=python&logoColor=white" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/Code-Runnable_Examples-2ea44f.svg" alt="Code: Runnable Examples" />
  <img src="https://img.shields.io/badge/GPU-100%25_Ready-0078D4.svg" alt="GPU 100% Ready" />
  <img src="https://img.shields.io/badge/API-OpenAI_Compatible-313236.svg" alt="API OpenAI Compatible" />
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT" />
</div>

<br />

**A practical ticket-triage demo that routes support incidents to Regolo for structured enterprise analysis**

This repository contains the code used in the article [Advanced RAG in 2026: Long Context Is Not Memory](https://regolo.ai/advanced-rag-in-2026-long-context-is-not-memory/).

---

## What This Demo Does

This script takes a raw support ticket and turns it into a structured operational response.

It can:
- build a detailed enterprise prompt for incident triage
- send the prompt to Regolo through an OpenAI-compatible API
- parse the model output into JSON when possible
- fall back to a local mock response when no API key is configured
- print example ticket outcomes from the command line

---

## How It Works

1. `RegoloClient` prepares the request and handles API communication.
2. `route_ticket` sends each ticket to the enterprise prompt pipeline.
3. Regolo returns a structured answer with fields like:
   - category
   - priority
   - impact
   - root cause hypothesis
   - mitigation steps
   - escalation path
4. The script prints the final response for each sample ticket.

---

## Project Structure

- `main.py`: ticket routing logic, prompt builder, and Regolo client
- `requirements.txt`: Python dependencies
- `.env`: local environment variables, including `REGOLO_API_KEY`

---

## Quick Start

```bash
cd advanced-rag-in-2026-long-context-is-not-memory
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

If you want to call the live API, set:

```bash
REGOLO_API_KEY=your_key_here
REGOLO_REASONING_MODEL=Llama-3.3-70B-Instruct
```

Without an API key, the script uses the built-in mock response.

---

## Article

- [Read the article](https://regolo.ai/advanced-rag-in-2026-long-context-is-not-memory/)

---

## Labels

- `Python`
- `Runnable`
- `Enterprise Triage`
- `OpenAI Compatible`

### How to Use
1. Clone this repository: `git clone https://github.com/regolo-ai/tutorials.git`
2. Navigate to the desired tutorial folder.
3. Follow the instructions in the folder's README.md. 
4. Get a free API key from Regolo to run the code: [Sign Up for Free Trial](https://regolo.ai/pricing).
5. Run the code and see the results in minutes.
