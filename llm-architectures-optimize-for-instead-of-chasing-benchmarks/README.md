# LLM Architectures in 2026: Optimize for What Matters, Not Benchmarks

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Powered by Regolo](https://img.shields.io/badge/Powered%20by-Regolo%20GPU-green)](https://regolo.ai)

This tutorial shows a small Regolo-powered architecture router for enterprise-style LLM usage.
It loads local environment variables from a `.env` file, reads `REGOLO_CORE_MODEL` as the preferred model, and falls back to task-based model selection when needed.

## Article

[Read the full article](https://regolo.ai/new-llm-architectures-in-2026-what-ctos-should-optimize-for-instead-of-chasing-benchmarks/)

## What it demonstrates

- Loading environment variables from a local `.env` file
- Selecting a preferred model from `REGOLO_CORE_MODEL`
- Falling back to reasoning-aware routing when the preferred model is not available
- Sending OpenAI-compatible chat requests to Regolo

## Files

- `main.py` — runnable example that loads the `.env`, selects a model, and calls the chat completions endpoint

## Setup

1. Create a `.env` file in this folder.
2. Add your Regolo credentials and preferred model:

   ```dotenv
   REGOLO_API_KEY=your_api_key_here
   REGOLO_CORE_MODEL=qwen3.5-122b
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

## Run

```bash
python main.py
```

## How it works

The script:

1. Reads `.env` from the current folder.
2. Loads `REGOLO_API_KEY` and `REGOLO_CORE_MODEL` into the process environment.
3. Fetches the available Regolo models.
4. Picks `REGOLO_CORE_MODEL` if it matches an available model.
5. Falls back to a simple reasoning-aware selector if needed.
6. Sends the final prompt to Regolo and prints the response.

## Notes

- The example is intentionally minimal.
- You can replace the sample prompt in `main.py` with your own use case.
- If you change the preferred model in `.env`, rerun the script to use the new value.