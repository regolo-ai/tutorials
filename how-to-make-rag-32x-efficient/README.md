# fastest-rag-crewai

A minimal, tested reference implementation showing how to combine **CrewAI** with
**binary quantization** to build a memory-efficient RAG system.

## What this demonstrates

- Converting float32 embeddings into packed binary vectors (1 bit/dim) with FAISS.
- A `BinaryVectorStore` that runs Hamming-distance search and optionally reranks
  top candidates using float32 cosine similarity for accuracy recovery.
- A two-agent CrewAI pipeline: a **Retrieval Specialist** agent (binary index tool)
  and an **Answer Synthesizer** agent that grounds its answer in retrieved context.
- A reproducible benchmark comparing float32 exact search vs binary search
  (with/without rerank) on memory footprint, latency, and recall@10.

## Architecture

```
Documents -> Embedding Model -> float32 vectors
                                     |
                          binary_quantize() [1 bit/dim]
                                     |
                        FAISS IndexBinaryFlat (Hamming)
                                     |
                 Retrieval Specialist Agent (CrewAI tool)
                                     |
                    Answer Synthesizer Agent (CrewAI LLM)
                                     |
                              Grounded answer
```

## Project structure

```
fastest-rag-crewai/
├── crew.py                     # CrewAI pipeline entrypoint
├── requirements.txt
├── src/
│   ├── quantization.py         # binary_quantize, hamming_topk, memory_footprint
│   └── vectorstore.py          # BinaryVectorStore (FAISS binary index + rerank)
├── benchmarks/
│   └── run_benchmark.py        # reproducible benchmark script
└── data/
    └── corpus.txt              # sample corpus for quick testing
```

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Set your LLM provider key for CrewAI (e.g. `OPENAI_API_KEY`, `GROQ_API_KEY`) as
required by the model you plug into `build_crew(..., llm=...)`.

## Run the RAG pipeline

```bash
python crew.py "What are common diabetes treatment approaches?"
```

This loads `data/corpus.txt`, embeds it with `sentence-transformers`
(`BAAI/bge-small-en-v1.5`), builds a binary-quantized FAISS index, and runs the
CrewAI crew (retrieval agent -> answering agent).

## Run the benchmark

```bash
python benchmarks/run_benchmark.py
```

### Results (8,000 synthetic documents, 384-dim embeddings, 200 queries, k=10)

| Method | Memory | Reduction | Avg latency | Recall@10 |
|---|---|---|---|---|
| Float32 Flat (exact) | 12,288,000 bytes | 1x | 0.21 ms | 100% |
| Binary Quantized (no rerank) | 384,000 bytes | 32x | 0.03 ms | 10.6% |
| Binary + Rerank (oversample=100) | 384,000 bytes | 32x | 0.10 ms | 14.8% |
| Binary + Rerank (oversample=500) | 384,000 bytes | 32x | ~0.20 ms | 27.4% |
| Binary + Rerank (oversample=1000) | 384,000 bytes | 32x | ~0.35 ms | 37.6% |

**Key takeaway:** binary quantization delivers the theoretical 32x memory
reduction exactly as expected, and search is ~8x faster than float32 exact
search at k=10. Raw binary-only recall is low on this embedding distribution;
in production, always pair binary search with a float32 rerank stage over an
oversampled candidate set, and tune the oversample size against your recall
target. Recall depends heavily on the embedding model's separability under a
zero-threshold sign quantization — production embedding models (e.g. BGE,
OpenAI, Cohere) trained with quantization-aware objectives will recall
meaningfully better than the generic TF-IDF+SVD vectors used in this synthetic
benchmark.

## Notes on production use

- Real embedding models (BGE, Cohere embed v3, OpenAI text-embedding-3) are
  better suited to sign-based binary quantization than generic TF-IDF/SVD
  vectors used here for a fast, dependency-light benchmark.
- For very large corpora, keep only the oversampled candidate float32 vectors
  in memory (e.g. memory-mapped), not the full float32 corpus.
- Milvus, Azure AI Search, and Qdrant all support native binary vector types
  and Hamming-distance indexes for this pattern in production.
