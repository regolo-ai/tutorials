<div align="center">
  <img src="https://regolo.ai/wp-content/uploads/2026/06/Regolo_logo_positive.png" alt="Regolo.ai Logo" width="300" />
</div>

# SearXNG Private Research Scraper

<div align="center">
  <img src="https://img.shields.io/badge/build-passing-brightgreen.svg" alt="Build passing" />
  <img src="https://img.shields.io/badge/python-3.11%2B-blue.svg?logo=python&logoColor=white" alt="Python 3.11+" />
  <img src="https://img.shields.io/badge/Code-Runnable_Examples-2ea44f.svg" alt="Code: Runnable Examples" />
  <img src="https://img.shields.io/badge/GPU-100%25_Ready-0078D4.svg" alt="GPU 100% Ready" />
  <img src="https://img.shields.io/badge/API-OpenAI_Compatible-313236.svg" alt="API OpenAI Compatible" />
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT" />
</div>

<br />

Production-oriented starter for private web research agents powered by **SearXNG**, concurrent **6-worker subagent query expansion**, **spatial context chunking**, and **Regolo.ai OpenAI-compatible inference (`brick-v1-beta`)**.

This repository contains the code from the companion article [Building a Private AI Research Agent with SearXNG and Regolo.ai](article.md).

---

## Project Overview

Regolo Private Search Starter is an advanced asynchronous Python application designed to execute private, high-signal web research. It deploys a fleet of specialized subagents to query self-hosted SearXNG search engines concurrently, cleans DOM noise from scraped web pages, indexes text into spatial chunks, scores them by factual density, and optionally synthesizes grounded reports and per-result sentiment analysis using Regolo.ai (`brick-v1-beta`).

---

## Key Features

1. **6-Worker Subagent Fleet**: Automatically expands research queries into 6 specialized facets (Primary Discovery, Technical Specs, Regulatory Compliance, Market & Trend Analysis, Academic Research, and Security/Vulnerabilities) executed concurrently via `asyncio.gather`.
2. **Robust Fault-Tolerant Search**: Queries SearXNG JSON API with an automatic HTML scraping fallback parser (`HTMLParser`) and strict `User-Agent` headers.
3. **Spatial Context Chunking**: Splits web content into 300-word context blocks, calculating factual density scores (based on numbers, uppercase terms, version numbers, and technical tokens).
4. **Deduplication**: Eliminates redundancy by deduplicating search results by URL and chunks by `(source_url, spatial_index)`.
5. **Regolo.ai Grounded Synthesis & Sentiment Analysis**: Integrates with Regolo's `brick-v1-beta` model to generate citation-backed summaries (`[Source N]`) and per-result sentiment scores (`-1.0` to `1.0`) with inferred insights.
6. **Fantastic CLI TUI**: Interactive terminal interface with live per-second elapsed timers and subagent creation logs.

---

## Technology Stack

- **Python**: `>=3.11` (optimized for Python 3.11–3.14)
- **Framework**: FastAPI (`>=0.115,<1`), Uvicorn (`[standard]`)
- **Validation**: Pydantic v2 (`>=2.7,<3`)
- **HTTP Client**: `httpx` (`>=0.27,<1`) with async client support and explicit `User-Agent: Mozilla/5.0` headers
- **HTML Parsing**: `beautifulsoup4` and Python built-in `HTMLParser` fallback
- **Search Backend**: Self-hosted **SearXNG** (Docker image `searxng/searxng:latest`)
- **AI Inference Engine**: Regolo.ai OpenAI-compatible API (`brick-v1-beta`)

---

## Project Structure

```text
searxng-scraper/
├── src/
│   └── regolo_private_search/
│       ├── __init__.py
│       └── app.py            # FastAPI app, subagents, spatial chunking, and CLI runner
├── test_app.py               # Pytest test suite (cleaning, density, chunking, endpoint)
├── setup.sh                  # Interactive TUI shell script (setup, demo, custom search)
├── docker-compose.yml        # SearXNG container orchestration
├── searxng-settings.yml      # SearXNG configuration
├── pyproject.toml            # Project packaging & pytest configuration
├── .env                      # Local environment configuration
└── README.md                 # This file
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- Docker and Docker Compose (for SearXNG)
- A [Regolo.ai](https://regolo.ai) API key (get one at [regolo.ai/pricing](https://regolo.ai/pricing))

### 1. Clone and Configure

```bash
git clone https://github.com/regolo-ai/tutorials.git
cd tutorials/searxng-scraper
cp .env.example .env
```

Edit `.env` with your Regolo API key:

```env
REGOLO_API_KEY=your-regolo-api-key
REGOLO_BASE_URL=https://api.regolo.ai/v1
REGOLO_MODEL=brick-v1-beta
SEARXNG_URL=http://localhost:8080
APP_HOST=0.0.0.0
APP_PORT=8000
```

### 2. Run the Setup Script

```bash
./setup.sh
```

Or manually:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
pip install -e . pytest
```

### 3. Start SearXNG

```bash
docker compose up -d
```

### 4. Run the Research Agent

```bash
# CLI mode with interactive TUI
python3 src/regolo_private_search/app.py --query "EU AI Act compliance"

# Or start the FastAPI server
uvicorn regolo_private_search.app:app --reload
```

---

## Development Workflow

- Run the interactive setup menu:
  ```bash
  ./setup.sh
  ```
- Run a single-query CLI search with subagents and live TUI timer:
  ```bash
  export PYTHONPATH=src
  python3 src/regolo_private_search/app.py --query "EU AI Act compliance"
  ```
- Run the FastAPI development server:
  ```bash
  uvicorn regolo_private_search.app:app --reload
  ```

---

## Coding Standards

- **Async-First**: All network calls (`httpx`) and endpoint handlers are fully asynchronous.
- **Strict Typing**: Utilizes Pydantic v2 models and Python type hints.
- **Error Resilience**: Graceful exception handling with fallback mechanisms (JSON API to HTML scraping fallback).
- **Structured Metrics**: Emits structured `[METRICS LOG]` entries to standard output for operational tracking.

---

## Testing

Run the test suite using `pytest`:

```bash
python3 -m pytest -v
```

Tests cover DOM noise removal (`clean_html`), factual density preference (`factual_density`), spatial chunk indexing (`spatial_chunks`), and async endpoint execution.

---

## Contributing

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/amazing-feature`).
3. Commit your changes (`git commit -m 'Add amazing feature'`).
4. Push to the branch (`git push origin feature/amazing-feature`).
5. Open a Pull Request.

---

## License

Distributed under the MIT License. See `LICENSE` for more information.

---

## Powered by Regolo

Run private research agents on Regolo's GPU infrastructure — no local setup required.

[Get Started](https://regolo.ai) · [**Free Trial**](https://regolo.ai/pricing)

Questions? [Open an issue](https://github.com/Regolo-AI/tutorials/issues) or join our [Discord](https://discord.gg/wHxwWCC8).

### How to Use

1. Clone this repository: `git clone https://github.com/regolo-ai/tutorials.git`
2. Navigate to the desired tutorial folder.
3. Follow the instructions in the folder's README.md.
4. Get a free API key from Regolo to run the code: [Sign Up for Free Trial](https://regolo.ai/pricing).
5. Run the code and see the results in minutes.
