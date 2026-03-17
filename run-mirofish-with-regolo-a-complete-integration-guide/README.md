# MiroFish × regolo.ai — Starter Kit

Companion code for the step-by-step integration guide:  
**→ URL_BLOG_POST**

Three scripts that let you verify, explore, and configure a [regolo.ai](https://regolo.ai) endpoint for [MiroFish](https://github.com/666ghj/MiroFish) — a multi-agent swarm intelligence engine for social simulation and prediction.

---

## What's inside

| File | Purpose |
|------|---------|
| `demo_simulation.py` | Standalone practical demo: 3-round multi-agent policy debate with persistent memory and a final report |
| `verify_connection.py` | Smoke-test the regolo.ai API — confirms auth, runs a chat completion, prints token usage |
| `verify_memory.py` | End-to-end test for the Mem0 memory layer using regolo.ai for both LLM + embeddings |
| `list_models.py` | Lists all models on your account with recommended use cases for MiroFish workloads |
| `generate_mirofish_env.py` | Generates a ready-to-use `.env` file for the MiroFish repo root |

---

## Quick start

### 1. Clone this repo and enter the directory

```bash
git clone <this-repo-url>
cd mirofish-regolo-starter
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Add your credentials

```bash
cp .env.example .env
```

Edit `.env` and fill in:

```env
REGOLO_API_KEY=your_regolo_api_key_here   # from dashboard.regolo.ai
LLM_MODEL_NAME=Llama-3.3-70B-Instruct    # or any model from list_models.py
MEM0_LLM_MODEL=Llama-3.3-70B-Instruct    # model used by Mem0 for reasoning
MEM0_EMBEDDER_MODEL=Qwen3-Embedding-8B   # embedding model (4096 dims, on regolo.ai)
```

> Get your regolo.ai API key at [dashboard.regolo.ai](https://dashboard.regolo.ai/) — 30-day free trial, no credit card required.  
> **No memory service account needed** — Mem0 runs locally and uses regolo.ai for embeddings.

### 4. Verify the connection

```bash
python verify_connection.py
```

Expected output:

```
✓ API key loaded
✓ Chat completion succeeded
  Model reply: The connection is working properly...
  Model used:  Llama-3.3-70B-Instruct
  Tokens used: 80 total (prompt=57, completion=23)

✓ All checks passed — regolo.ai is ready for MiroFish
```

### 4. Run the practical demo (no MiroFish install needed)

```bash
python demo_simulation.py
```

Three AI agents — a policy analyst, a startup CTO, and an ethics researcher — debate EU AI regulation across 3 rounds. Each agent has persistent memory (Mem0 + regolo.ai embeddings). A ReportAgent summarises the emergent dynamics at the end.

This is the same LLM + memory pattern MiroFish uses internally. Use it to validate your setup before running a full simulation.

### 5. Test the memory layer

```bash
python verify_memory.py
```

Expected output:

```
✓ Mem0 initialized (LLM: Llama-3.3-70B-Instruct, Embedder: Qwen3-Embedding-8B)
✓ Memory stored  — id: <uuid>
✓ Memory retrieved: I am running a social simulation about climate policy.
✓ Memory layer is ready for MiroFish
```

Mem0 runs entirely locally using an in-memory Qdrant vector store. All LLM reasoning and embedding calls are routed through your regolo.ai key — no external memory service needed.

### 6. Browse available models

```bash
python list_models.py
```

Output annotates each model with its recommended role in a MiroFish simulation pipeline.

### 7. Generate the MiroFish `.env`

```bash
python generate_mirofish_env.py
```

This writes `mirofish.env` in the current directory. Copy it to the root of your MiroFish clone:

```bash
cp mirofish.env /path/to/MiroFish/.env
```

From there, follow the full installation guide in the blog post (**URL_BLOG_POST**) to install dependencies and start the simulation.

---

## Memory layer: Mem0 (open source, no account needed)

Instead of Zep Cloud, this starter kit uses **[Mem0](https://github.com/mem0ai/mem0)** — a fully open-source agent memory library (Apache 2.0, 26k+ stars).

Mem0 runs locally without any external service. It uses:
- **Qdrant in-memory** as the vector store (no server needed by default)
- **regolo.ai** for both the LLM reasoning layer and the embedding model

Embedding dimensions on regolo.ai:

| Model | Dims |
|-------|------|
| `gte-Qwen2` | 3584 |
| `Qwen3-Embedding-8B` | 4096 |

For persistence across restarts, configure a local Qdrant instance in `verify_memory.py` (see the commented-out `vector_store` section).

---

## Model recommendations for MiroFish

| Model | Best for |
|-------|---------|
| `Llama-3.1-8B-Instruct` | Dev/test runs — fast and low cost |
| `Llama-3.3-70B-Instruct` | Most production simulations — best quality/speed balance |
| `gpt-oss-20b` | Structured JSON agent calls, compact reasoning |
| `gpt-oss-120b` | Maximum reasoning quality for final simulation runs |
| `qwen3.5-122b` | Large MoE, top-tier quality, higher token cost |
| `qwen3-8b` | Non-English seed documents |
| `gte-Qwen2` / `Qwen3-Embedding-8B` | Vector search in the GraphRAG layer |

---

## Why regolo.ai for MiroFish

MiroFish burns 1–5M tokens per simulation run. The LLM tier needs to be fast, affordable, and — especially for sensitive seed documents — **private**.

- **Zero data retention** — prompts and completions are never stored or used for training
- **EU infrastructure** — Italian data centers, GDPR-compliant by design
- **No execution time limits** — long-running simulations won't be killed mid-run
- **OpenAI-compatible API** — `LLM_BASE_URL` is the only change MiroFish needs
- **Green compute** — 100% carbon-free energy
- **Full-stack open source** — regolo.ai for inference + Mem0 for memory, no proprietary services

---

## Requirements

- Python 3.11–3.12
- `openai >= 1.0.0`
- `python-dotenv >= 1.0.0`
- `mem0ai >= 0.1.0`

---

## License

MIT — see [LICENSE](LICENSE).
