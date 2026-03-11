# Build Faster: LLM as a Service for Developers with Qwen 3.5 122b

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Runnable Code](https://img.shields.io/badge/Code-Runnable%20Examples-1F9D55)
![GPU Ready](https://img.shields.io/badge/GPU-100%25%20Ready-0A84FF)
![OpenAI Compatible](https://img.shields.io/badge/API-OpenAI%20Compatible-black)

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
