

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

## Run

```bash
python benchmark_kv_quantization.py
```


Example with custom parameters:

```bash
python benchmark_kv_quantization.py --dim 128 --n_vectors 2048 --csv results.csv
```

To see all available options (e.g., `--no-attn` to skip the attention KL metric or `--seed` for reproducible runs):

```bash
python benchmark_kv_quantization.py --help
```

## Data

The benchmark relies entirely on **synthetic data distributions** generated on the fly, so no external dataset download is required. The tested distributions include:
- **Gaussian**: Standard Gaussian baseline with no outliers.
- **Heavy-tailed**: Gaussian with Cauchy outlier channels.
- **RoPE-like**: RoPE-style sinusoidal modulation over Gaussian vectors.

## Metrics evaluated

The script reports:

- **Normalized reconstruction MSE**
- **Inner product bias**
- **Normalized inner product MSE**
- **Attention KL divergence**
- **CPU time per vector**


## Dependencies

- NumPy
- SciPy
- tabulate

---

### 🎁 Get Started Free of Use for 30 Days

Sign up for Regolo and get **30 days free and 70% off for next 3 months:**

[Get Started](https://regolo.ai) · [**REGOLO FREE TRIAL**](https://regolo.ai/pricing)

[Regolo Platform](https://regolo.ai)

[Models Library](https://regolo.ai/models-library/)

[Documentation & Guides](https://regolo.ai/docs)

[YouTube Channel](https://www.youtube.com/@regoloai)

[Discord & Support](https://discord.gg/wHxwWCC8)