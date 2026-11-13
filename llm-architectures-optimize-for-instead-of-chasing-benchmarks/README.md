<div align="center">
  <img src="https://regolo.ai/wp-content/uploads/2026/06/Regolo_logo_positive.png" alt="Regolo.ai Logo" width="300" />
</div>

# LLM Architectures in 2026: Optimize for What Matters, Not Benchmarks

<div align="center">
  <img src="https://img.shields.io/badge/build-passing-brightgreen.svg" alt="Build passing" />
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg?logo=python&logoColor=white" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/Code-Runnable_Examples-2ea44f.svg" alt="Code: Runnable Examples" />
  <img src="https://img.shields.io/badge/GPU-100%25_Ready-0078D4.svg" alt="GPU 100% Ready" />
  <img src="https://img.shields.io/badge/API-OpenAI_Compatible-313236.svg" alt="API OpenAI Compatible" />
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT" />
</div>

<br />

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
### How to Use
1. Clone this repository: `git clone https://github.com/regolo-ai/tutorials.git`
2. Navigate to the desired tutorial folder.
3. Follow the instructions in the folder's README.md. 
4. Get a free API key from Regolo to run the code: [Sign Up for Free Trial](https://regolo.ai/pricing).
5. Run the code and see the results in minutes.
