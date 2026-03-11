# Build Faster: LLM as a Service for Developers with Qwen 3.5 122b

Runnable code for the article:
https://regolo.ai/build-faster-llm-as-a-service-for-developers-with-qwen-3-5-122b/

## What you get

- OpenAI-compatible Regolo client for chat and streaming
- 4 practical use cases from the article
- Minimal RAG demo with retrieval + grounded response prompt
- Structured extraction flow with JSON parsing safeguards
- Test suite with local checks + live API validation

## Project structure

- `config.py`: environment-based settings
- `regolo_client.py`: chat + streaming client
- `use_cases/use_case_1_boilerplate.py`: FastAPI boilerplate generator
- `use_cases/use_case_2_streaming.py`: streaming assistant patterns
- `use_cases/use_case_3_rag.py`: lightweight RAG flow
- `use_cases/use_case_4_structured_output.py`: JSON extraction
- `main.py`: runs all use cases
- `tests/test_article_examples.py`: automated tests

## Quick start

```bash
cd build-faster-llm-as-a-service-for-developers-with-qwen-3-5-122b
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set API key in `.env`:

```bash
REGOLO_API_KEY=your_key_here
```

Run all demos:

```bash
python main.py
```

Run tests:

```bash
pytest -q
```

## Labels

- `Python`
- `Runnable`
- `GPU 100% Ready`
