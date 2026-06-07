<div align="center">
  <img src="https://regolo.ai/wp-content/uploads/2026/06/Regolo_logo_positive.png" alt="Regolo.ai Logo" width="300" />
</div>

# OpenClaw vs Hermes Agent Memory Benchmark

<div align="center">
  <img src="https://img.shields.io/badge/build-passing-brightgreen.svg" alt="Build passing" />
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg?logo=python&logoColor=white" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/Code-Runnable_Examples-2ea44f.svg" alt="Code: Runnable Examples" />
  <img src="https://img.shields.io/badge/GPU-100%25_Ready-0078D4.svg" alt="GPU 100% Ready" />
  <img src="https://img.shields.io/badge/API-OpenAI_Compatible-313236.svg" alt="API OpenAI Compatible" />
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT" />
</div>

<br />

This repository contains the code and methodology used to run a live, direct comparison between two of the most discussed AI agent frameworks of 2026: **OpenClaw** and **Hermes Agent**. 

The goal of this benchmark is to measure the performance, speed, and resource consumption of their long-term memory implementations when processing and recalling knowledge from an active session. Instead of running theoretical or mocked scripts, we orchestrated their real CLI interfaces hitting their actual background daemons.

Article: https://regolo.ai/privacy-first-ai-in-europe-zero-retention-sovereignty-and-the-new-risks-we-cannot-ignore/

## What the script does

The entry point is [orchestrator.py](orchestrator.py). It:

- dynamically configures datasets up to hundreds of events via the `NUM_EVENTS` variable.
- hits the live daemons of OpenClaw and Hermes directly through `subprocess`.
- monitors background process RSS usage via `psutil`.
- parses local agent directories (`~/.openclaw` and `~/.hermes`) to track disk size bloating via flat-files vs SQLite.
- records the real latency on information retrieval queries directly from the agents' memory.

## Requirements

To run this benchmark on your own machine, you must have the following installed:
- [Node.js](https://nodejs.org/) (24 or 22.16+)
- [Python 3.12+](https://www.python.org/)
- **Hermes Agent CLI** (`curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash`)
- **OpenClaw CLI** (`npm install -g openclaw@latest`)
- A **Regolo API Key** to ensure a uniform LLM testing ground (we use `minimax-m2.5`).
- The Python dependencies: `pip install psutil rich`

## Setup the Environment

Make sure both frameworks are pointing to the same Regolo endpoint to prevent external API latencies from skewing the results.

### Configure OpenClaw
```bash
cat << 'EOF' > /tmp/regolo.json
{
  "baseUrl": "https://api.regolo.ai/v1",
  "apiKey": "YOUR_REGOLO_API_KEY",
  "api": "openai-completions",
  "models": [
    {
      "id": "minimax-m2.5",
      "name": "minimax-m2.5",
      "reasoning": true,
      "contextWindow": 196608,
      "maxTokens": 196608
    }
  ]
}
EOF

openclaw config set models.providers.regolo --batch-file /tmp/regolo.json --strict-json
openclaw models aliases add minimax-m2.5 regolo/minimax-m2.5
openclaw models set regolo/minimax-m2.5
```

### Configure Hermes
Run `hermes setup` and configure the OpenAI-compatible endpoint with the Regolo URL and your API key.

Ensure both engines are active in the background before running the test:
```bash
openclaw gateway start
hermes gateway start
```

## Run It

From this directory:

```bash
python orchestrator.py
```

## Output

The script prints a console table containing:

- Gateway PID
- RSS Memory Δ
- Disk Usage Δ
- Recall Latency

Example output based on 20 events:

| Metric | OpenClaw | Hermes Agent |
|---|---:|---:|
| **RSS Memory Δ** | 0.00 MB | -2.75 MB |
| **Disk Usage Δ** | 213.41 KB | 0.00 KB |
| **Recall Latency** | 19593.32 ms | 113.14 ms |

## Notes

- **Winner: Hermes Agent**. Hermes bypasses massive LLM context roundtrips entirely using an internal SQLite database (`state.db`) equipped with Full-Text Search (FTS). It performs the recall query locally in 113ms. OpenClaw takes 19.6s by forcing context re-evaluation via flat JSONL files.
- The `NUM_EVENTS` in `orchestrator.py` is defaulted to 300 to show how badly JSONL-based memory approaches scale over time compared to RAG/SQL-based memory.

## Related Article

- [Privacy-First AI in Europe: Zero-Retention, Sovereignty, and the New Risks We Cannot Ignore](https://regolo.ai/privacy-first-ai-in-europe-zero-retention-sovereignty-and-the-new-risks-we-cannot-ignore/)
### How to Use
1. Clone this repository: `git clone https://github.com/regolo-ai/tutorials.git`
2. Navigate to the desired tutorial folder.
3. Follow the instructions in the folder's README.md. 
4. Get a free API key from Regolo to run the code: [Sign Up for Free Trial](https://regolo.ai/pricing).
5. Run the code and see the results in minutes.
