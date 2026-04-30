

# TurboQuant KV Benchmark

Official benchmark to compare TurboQuant against traditional scalar key/value (KV) quantization methods for LLMs.

**Reference article:**
👉 [TurboQuant Benchmark: what to measure, what matters, and how to read the results](https://regolo.ai/turboquant-benchmark-what-to-measure-what-matters-and-how-to-read-the-results/)

This repository provides a lightweight, reproducible script to evaluate:
- reconstruction accuracy
- bias and MSE on inner product
- attention KL divergence
- CPU time per vector

TurboQuant is an optimized quantization technique for LLM KV caches, designed to maximize quality while maintaining efficiency and speed, as described in the article.

---


## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```


Alternatively:

```bash
pip install .
```


## Run

```bash
python benchmark_kv_quantization.py
```


Example with custom parameters:

```bash
python benchmark_kv_quantization.py --dim 128 --n_vectors 2048 --csv results.csv
```


## Metrics evaluated

The script reports:

- Normalized reconstruction MSE
- Inner product bias
- Normalized inner product MSE
- Attention KL divergence
- CPU time per vector


## Dependencies

- NumPy
- SciPy
- tabulate