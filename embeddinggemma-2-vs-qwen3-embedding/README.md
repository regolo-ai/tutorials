# EmbeddingGemma 2 vs Qwen3-Embedding (0.6B & 8B) + Reranker-4B Benchmark

Reproducible retrieval, Matryoshka Representation Learning (MRL) dimension truncation, and two-stage cross-encoder reranking benchmark comparing:

- `embeddinggemma-2:270m-bf16-text` (Google EmbeddingGemma 2 text tower, 270M parameters, 768d, local Apple M1 Ultra MLX)
- `embeddinggemma:latest` (Google EmbeddingGemma 1 baseline, 308M parameters, 768d, local Apple M1 Ultra)
- `qwen3-embedding:0.6b` (Alibaba Qwen3-Embedding-0.6B, 595M parameters, 1024d, local Apple M1 Ultra)
- `Qwen3-Embedding-8B` (Alibaba Qwen3-Embedding-8B, 4096d + native MRL `dimensions` pass-through on Regolo Sovereign EU API)
- `Qwen3-Reranker-4B` (4B cross-encoder on Regolo `/v1/rerank`)

## Quick Start

1. Start Ollama (`>= 0.40.4` required for EmbeddingGemma 2 / Gemma 4 architecture) and pull the local checkpoints:

```bash
ollama pull embeddinggemma-2:270m-bf16-text
ollama pull embeddinggemma:latest
ollama pull qwen3-embedding:0.6b
```

2. Configure your Regolo API key in `.env`:

```bash
cp .env.example .env
```

3. Run the unit tests and the full benchmark suite:

```bash
python3 -c "import test_metrics as t; t.test_mrl_truncate_and_normalize(); t.test_ranking_metrics(); t.test_instruction_formatting(); print('OK')"
python3 benchmark.py
```

Full JSON metrics are written to `results/benchmark_results.json`.
