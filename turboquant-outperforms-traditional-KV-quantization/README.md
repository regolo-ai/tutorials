# TurboQuant KV benchmark

This repository contains a lightweight benchmark to compare TurboQuant against traditional scalar KV quantization methods.

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

## What it measures

The benchmark reports:

- normalized reconstruction MSE
- inner-product bias
- normalized inner-product MSE
- attention KL divergence
- CPU time per vector

## Dependencies

- NumPy
- SciPy
- tabulate