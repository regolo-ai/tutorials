<div align="center">
  <img src="https://regolo.ai/wp-content/uploads/2026/06/Regolo_logo_positive.png" alt="Regolo.ai Logo" width="300" />
</div>

# Build Faster: LLM as a Service for Developers with Qwen 3.5 122b

<div align="center">
  <img src="https://img.shields.io/badge/build-passing-brightgreen.svg" alt="Build passing" />
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg?logo=python&logoColor=white" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/Code-Runnable_Examples-2ea44f.svg" alt="Code: Runnable Examples" />
  <img src="https://img.shields.io/badge/GPU-100%25_Ready-0078D4.svg" alt="GPU 100% Ready" />
  <img src="https://img.shields.io/badge/API-OpenAI_Compatible-313236.svg" alt="API OpenAI Compatible" />
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT" />
</div>

<br />

Production-ready tutorial code for the article:
https://regolo.ai/build-faster-llm-as-a-service-for-developers-with-qwen-3-5-122b/

Ship real LLM features in hours, not weeks.

## Why this tutorial matters

- Remove infrastructure overhead and focus on product delivery
- Use OpenAI-compatible APIs with low integration friction
- Build with EU-hosted, zero retention workflows
- Move from prototype to deployable patterns fast

## Included use cases

1. Boilerplate code generator for FastAPI endpoints
2. Streaming chat assistant for responsive UX
3. Lightweight RAG flow for grounded answers
4. Structured output extraction with JSON safeguards

## Architecture

```
Client App -> RegoloClient -> Regolo OpenAI-compatible API -> Qwen 3.5 122b
							 \-> Streaming endpoint
							 \-> RAG prompt grounding layer
```

## Project structure

- `config.py`: environment-based settings
- `regolo_client.py`: chat + streaming API client
- `use_cases/use_case_1_boilerplate.py`: FastAPI boilerplate generation
- `use_cases/use_case_2_streaming.py`: streaming assistant logic
- `use_cases/use_case_3_rag.py`: retrieval + grounded answering flow
- `use_cases/use_case_4_structured_output.py`: typed extraction from raw text
- `main.py`: runs all use cases end-to-end
- `tests/test_article_examples.py`: local + live validation suite

## Quick start

```bash
cd build-faster-llm-as-a-service-for-developers-with-qwen-3-5-122b
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Configure `.env`:

```bash
REGOLO_API_KEY=your_key_here
REGOLO_BASE_URL=https://api.regolo.ai/v1
REGOLO_MODEL=qwen3.5-122b
REGOLO_REASONING_EFFORT=medium
```

Run all demos:

```bash
python main.py
```

Run tests:

```bash
pytest -q
```

## Test status

- Automated test suite passed locally
- Live API completion test passed
- End-to-end demo execution verified

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
