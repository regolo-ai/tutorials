# Advanced RAG in 2026: Long Context Is Not Memory

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
