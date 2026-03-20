# Small Language Models Are Growing Up: How to Build a Hybrid Inference Stack Without Sacrificing Quality

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Runnable Code](https://img.shields.io/badge/Code-Runnable%20Examples-1F9D55)
![OpenAI Compatible](https://img.shields.io/badge/API-OpenAI%20Compatible-black)
![Logging](https://img.shields.io/badge/Logs-Colored%20Status%20Output-7B61FF)

Production-ready tutorial code for the article:
https://regolo.ai/small-language-models-are-growing-up-how-to-build-a-hybrid-inference-stack-without-sacrificing-quality/

This example shows how to route every incident through Regolo while keeping the code path simple, observable, and easy to run locally.

## What This Demo Does

This script takes a production incident description and turns it into a structured Regolo response.

It can:
- load local `.env` values automatically
- send every request directly to Regolo's chat completions endpoint
- parse the model output into JSON when possible
- fall back to a safe structured response if the model returns invalid JSON
- print readable, colorized status logs in the terminal

## How It Works

1. The script loads environment variables from `.env` in the same folder.
2. `route_incident` sends the ticket into the Regolo-only flow.
3. `ask_regolo` builds the prompt and sends it to the Regolo API.
4. The response is parsed as JSON and printed to stdout.
5. If the output is not valid JSON, the script returns a safe fallback payload.

## Project Structure

- `main.py`: Regolo request flow, response parsing, and terminal logging
- `.env`: local environment variables, including `REGOLO_API_KEY`

## Quick Start

```bash
cd build-hybrid-inference-stack
python3 -m venv .venv
source .venv/bin/activate
pip install colorama certifi
python3 main.py
```

Configure `.env`:

```bash
REGOLO_API_KEY=your_key_here
REGOLO_BASE_URL=https://api.regolo.ai/v1
REGOLO_MODEL=Llama-3.3-70B-Instruct
# REGOLO_REASONING_MODEL is also supported as a fallback
```

## Runtime Notes

- `colorama` is used to color the log stages.
- `certifi` is optional but recommended for TLS verification on local Python installs.
- The script is Regolo-only: there is no local router or offline fallback path.

## Article

- [Read the article](https://regolo.ai/small-language-models-are-growing-up-how-to-build-a-hybrid-inference-stack-without-sacrificing-quality/)

## Labels

- `Python`
- `Runnable`
- `OpenAI Compatible`
- `Logging`
