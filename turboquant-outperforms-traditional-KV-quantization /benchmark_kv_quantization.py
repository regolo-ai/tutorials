#!/usr/bin/env python3
"""
benchmark_kv_quantization.py
────────────────────────────
Objective benchmark: TurboQuant (MSE + Prod) vs traditional scalar KV quantization.

What it measures
----------------
For each method and input distribution, the script reports:

  mse_norm     — E[||x - x_hat||²] / E[||x||²]
                 Normalized reconstruction error.

  ip_bias      — Relative bias in the inner product estimate.
                 0 means unbiased. Negative values indicate shrinkage bias.

  ip_mse_norm  — E[(<y, x> - <y, x_hat>)²] / d
                 Normalized inner-product error across random queries y.

  attn_kl      — KL(softmax(QK/sqrt(d)) || softmax(QK_hat/sqrt(d)))
                 How much quantization perturbs the attention distribution.

  us_per_vec   — Microseconds per vector for quantize + dequantize on CPU.

Distributions tested
--------------------
  gaussian      — Standard Gaussian baseline with no outliers.
  heavy_tailed  — Gaussian with Cauchy outlier channels.
  rope_like     — RoPE-style sinusoidal modulation over Gaussian vectors.

Requirements
------------
  pip install numpy scipy tabulate

Usage
-----
  python benchmark_kv_quantization.py
  python benchmark_kv_quantization.py --dim 128 --n_vectors 2048 --csv results.csv
  python benchmark_kv_quantization.py --dim 64 --n_vectors 512 --no-attn
"""

import argparse
import csv
import math
import time
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
from scipy import integrate, special
from scipy.stats import norm as sp_norm
from tabulate import tabulate


# ─────────────────────────────────────────────────────────────────────────────
# Reproducibility
# ─────────────────────────────────────────────────────────────────────────────

def set_seed(seed: int = 42) -> None:
    np.random.seed(seed)


# TurboQuant paper theoretical distortion references (paper Section 1.3)
THEORY = {
    1: (0.36,  1 / 4),
    2: (0.117, 1 / 16),
    3: (0.030, 1 / 64),
    4: (0.009, 1 / 256),
}


# ─────────────────────────────────────────────────────────────────────────────
# Synthetic KV-like distributions
# ─────────────────────────────────────────────────────────────────────────────

def gen_gaussian(n: int, d: int) -> np.ndarray:
    """Standard Gaussian baseline with no outliers."""
    return np.random.randn(n, d)


def gen_heavy_tailed(n: int, d: int) -> np.ndarray:
    """
    Gaussian base + a few Cauchy outlier channels.

    This approximates a KV-cache-like setting where a small subset of channels
    dominates the quantization range and hurts scalar quantization.
    """
    x = np.random.randn(n, d)
    n_outliers = max(1, d // 16)
    outlier_idx = np.random.choice(d, n_outliers, replace=False)
    x[:, outlier_idx] = np.random.standard_cauchy((n, n_outliers)) * 5.0
    return x


def gen_rope_like(n: int, d: int) -> np.ndarray:
    """
    RoPE-like sinusoidal modulation applied to Gaussian vectors.

    This is a simple synthetic approximation of how key vectors look after
    positional rotation in transformer attention.
    """
    if d % 2 != 0:
        raise ValueError("Dimension must be even for rope_like distribution.")

    x = np.random.randn(n, d)
    pos = np.arange(n, dtype=np.float32)
    freq = 1.0 / (10000.0 ** (np.arange(0, d, 2, dtype=np.float32) / d))

    cos_ = np.cos(np.outer(pos, freq))
    sin_ = np.sin(np.outer(pos, freq))

    r = np.empty_like(x)
    r[:, 0::2] = x[:, 0::2] * cos_ - x[:, 1::2] * sin_
    r[:, 1::2] = x[:, 0::2] * sin_ + x[:, 1::2] * cos_
    return r


DISTRIBUTIONS = {
    "gaussian": gen_gaussian,
    "heavy_tailed": gen_heavy_tailed,
    "rope_like": gen_rope_like,
}


# ─────────────────────────────────────────────────────────────────────────────
# TurboQuant codebook utilities
# ─────────────────────────────────────────────────────────────────────────────

def beta_pdf(x: np.ndarray, d: int) -> np.ndarray:
    """
    PDF of one coordinate of a random point uniformly distributed on S^{d-1}.

    After random rotation and unit-norm normalization, each coordinate follows
    this Beta-derived distribution. For large d, it approaches N(0, 1/d).
    """
    x = np.clip(x, -1 + 1e-15, 1 - 1e-15)
    log_const = (
        special.gammaln(d / 2.0)
        - 0.5 * np.log(np.pi)
        - special.gammaln((d - 1) / 2.0)
    )
    exponent = (d - 3) / 2.0
    return np.exp(log_const + exponent * np.log(np.maximum(1 - x**2, 1e-30)))


def conditional_mean(lo: float, hi: float, d: int) -> float:
    """
    E[X | lo < X < hi] under the Beta-derived coordinate distribution.
    """
    num, _ = integrate.quad(lambda x: x * beta_pdf(np.array([x]), d)[0], lo, hi)
    den, _ = integrate.quad(lambda x: beta_pdf(np.array([x]), d)[0], lo, hi)
    return num / den if den > 1e-30 else (lo + hi) / 2.0


def lloyd_max_codebook(d: int, bits: int, max_iter: int = 300, tol: float = 1e-10) -> np.ndarray:
    """
    Solve the 1D Lloyd-Max problem for the TurboQuant coordinate distribution.

    This produces the centroid codebook used by PolarQuant / TurboQuantMSE.
    """
    n_clusters = 2 ** bits
    sigma = 1.0 / math.sqrt(d)

    # Gaussian quantile initialization works well in practice for large d
    quantiles = np.linspace(1 / (2 * n_clusters), 1 - 1 / (2 * n_clusters), n_clusters)
    centroids = sp_norm.ppf(quantiles) * sigma

    for _ in range(max_iter):
        boundaries = np.concatenate([
            [-1.0],
            (centroids[:-1] + centroids[1:]) / 2.0,
            [1.0],
        ])

        new_centroids = np.array([
            conditional_mean(boundaries[i], boundaries[i + 1], d)
            for i in range(n_clusters)
        ])

        if np.abs(new_centroids - centroids).max() < tol:
            centroids = new_centroids
            break

        centroids = new_centroids

    return np.sort(centroids)


# ─────────────────────────────────────────────────────────────────────────────
# TurboQuant MSE (Algorithm 1 / PolarQuant-style)
# ─────────────────────────────────────────────────────────────────────────────

class TurboQuantMSE:
    """
    TurboQuant optimized for reconstruction MSE.

    Pipeline:
      1. Store ||x||
      2. Normalize x to the unit sphere
      3. Apply a fixed random orthogonal rotation
      4. Quantize each rotated coordinate with a Lloyd-Max codebook
      5. Rotate back and rescale
    """

    def __init__(self, dim: int, bits: int = 3, seed: int = 42):
        self.dim = dim
        self.bits = bits

        rng = np.random.default_rng(seed)
        G = rng.standard_normal((dim, dim))
        Q, R = np.linalg.qr(G)

        # Enforce a proper orthogonal rotation
        self.Pi = Q * np.sign(np.diag(R))

        self.centroids = lloyd_max_codebook(dim, bits)
        self.boundaries = np.concatenate([
            [-np.inf],
            (self.centroids[:-1] + self.centroids[1:]) / 2.0,
            [np.inf],
        ])

    def quantize(self, x: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        norms = np.linalg.norm(x, axis=-1, keepdims=True)
        x_unit = x / np.maximum(norms, 1e-12)
        y = x_unit @ self.Pi.T
        indices = np.searchsorted(self.boundaries[1:-1], y)
        return indices, norms

    def dequantize(self, indices: np.ndarray, norms: np.ndarray) -> np.ndarray:
        y_hat = self.centroids[indices]
        x_hat = (y_hat @ self.Pi) * norms
        return x_hat

    def round_trip(self, x: np.ndarray) -> np.ndarray:
        return self.dequantize(*self.quantize(x))

    def eff_bits(self) -> float:
        # Quantization bits + one fp16 norm amortized over dim
        return self.bits + 16 / self.dim


# ─────────────────────────────────────────────────────────────────────────────
# TurboQuant Prod (Algorithm 2 / residual QJL correction)
# ─────────────────────────────────────────────────────────────────────────────

class TurboQuantProd(TurboQuantMSE):
    """
    TurboQuant optimized for inner products.

    Stage 1:
      TurboQuantMSE at (bits - 1)

    Stage 2:
      1-bit QJL-style residual correction:
        sign(S r), where r = x - x_mse and S ~ N(0,1)^{dxd}

    This is designed to reduce or remove systematic inner-product bias.
    """

    def __init__(self, dim: int, bits: int = 3, seed: int = 42):
        if bits < 2:
            raise ValueError("TurboQuantProd requires at least 2 bits.")
        super().__init__(dim=dim, bits=bits - 1, seed=seed)
        self.total_bits = bits

        rng = np.random.default_rng(seed + 1337)
        self.S = rng.standard_normal((dim, dim))
        self.qjl_scale = math.sqrt(math.pi / 2.0) / dim

    def round_trip(self, x: np.ndarray) -> np.ndarray:
        # Stage 1: MSE quantization
        indices, norms = self.quantize(x)
        x_mse = self.dequantize(indices, norms)

        # Stage 2: QJL-style residual correction
        residual = x - x_mse
        residual_norms = np.linalg.norm(residual, axis=-1, keepdims=True)

        # Use ±1 signs with zero mapped to +1 for stability
        projections = residual @ self.S.T
        signs = np.where(projections >= 0.0, 1.0, -1.0)

        x_qjl = (signs @ self.S) * (self.qjl_scale * residual_norms)
        return x_mse + x_qjl

    def eff_bits(self) -> float:
        # Total bits + two fp16 norms (original + residual) amortized over dim
        return self.total_bits + 32 / self.dim


# ─────────────────────────────────────────────────────────────────────────────
# Traditional scalar quantization
# ─────────────────────────────────────────────────────────────────────────────

def sym_quantize(x: np.ndarray, bits: int, scale) -> np.ndarray:
    """
    Symmetric uniform quantization around zero.
    """
    qmin = -(2 ** (bits - 1))
    qmax = (2 ** (bits - 1)) - 1
    q = np.clip(np.round(x / scale), qmin, qmax)
    return q * scale


class ScalarQuantizer:
    """
    Traditional scalar quantization.

    Modes:
      per_tensor   — one global scale for all values
      per_token    — one scale per vector
      per_channel  — one scale per coordinate across all vectors
    """

    def __init__(self, bits: int, mode: str = "per_token"):
        if mode not in {"per_tensor", "per_token", "per_channel"}:
            raise ValueError(f"Unsupported mode: {mode}")
        self.bits = bits
        self.mode = mode

    def round_trip(self, x: np.ndarray) -> np.ndarray:
        eps = 1e-12
        qmax = (2 ** self.bits) / 2 - 1

        if self.mode == "per_tensor":
            scale = np.abs(x).max() / qmax + eps
            return sym_quantize(x, self.bits, scale)

        if self.mode == "per_token":
            scale = np.abs(x).max(axis=-1, keepdims=True) / qmax + eps
            return sym_quantize(x, self.bits, scale)

        # per_channel
        scale = np.abs(x).max(axis=0, keepdims=True) / qmax + eps
        return sym_quantize(x, self.bits, scale)

    def eff_bits(self, dim: int) -> float:
        if self.mode == "per_token":
            return self.bits + 16 / dim
        if self.mode == "per_channel":
            # Approximate amortized metadata overhead at long sequence length
            return self.bits + (16 * 0.1 / dim)
        return self.bits + 1e-3


# ─────────────────────────────────────────────────────────────────────────────
# Metrics
# ─────────────────────────────────────────────────────────────────────────────

def compute_metrics(x: np.ndarray, x_hat: np.ndarray, n_query_trials: int = 64) -> Dict[str, float]:
    """
    Compute:
      - normalized MSE
      - inner-product bias
      - normalized inner-product MSE
    """
    _, d = x.shape

    # Reconstruction error
    mse_norm = np.sum((x - x_hat) ** 2, axis=-1).mean() / (
        np.sum(x ** 2, axis=-1).mean() + 1e-12
    )

    # Random unit queries
    Y = np.random.randn(n_query_trials, d)
    Y = Y / np.maximum(np.linalg.norm(Y, axis=-1, keepdims=True), 1e-12)

    ip_true = x @ Y.T
    ip_est = x_hat @ Y.T

    true_mean = ip_true.mean(axis=0)
    est_mean = ip_est.mean(axis=0)

    ip_bias = ((est_mean - true_mean) / (np.abs(true_mean) + 1e-6)).mean()
    ip_mse_norm = np.mean((ip_true - ip_est) ** 2) / d

    return {
        "mse_norm": float(mse_norm),
        "ip_bias": float(ip_bias),
        "ip_mse_norm": float(ip_mse_norm),
    }


def compute_attn_kl(queries: np.ndarray, keys: np.ndarray, keys_hat: np.ndarray) -> float:
    """
    KL(softmax(QK/sqrt(d)) || softmax(QK_hat/sqrt(d)))
    """
    d = queries.shape[-1]
    scale = 1.0 / math.sqrt(d)

    def softmax(x: np.ndarray) -> np.ndarray:
        x = x - x.max(axis=-1, keepdims=True)
        e = np.exp(x)
        return e / np.maximum(e.sum(axis=-1, keepdims=True), 1e-12)

    p = softmax((queries @ keys.T) * scale)
    q = softmax((queries @ keys_hat.T) * scale)

    kl = np.mean(np.sum(p * np.log(np.maximum(p, 1e-15) / np.maximum(q, 1e-15)), axis=-1))
    return float(kl)


# ─────────────────────────────────────────────────────────────────────────────
# Benchmark runner
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class BenchResult:
    method: str
    distribution: str
    eff_bits: float
    mse_norm: float
    ip_bias: float
    ip_mse_norm: float
    attn_kl: float
    us_per_vec: float


def build_methods(dim: int, seed: int) -> List[Tuple[str, object, float]]:
    sq = ScalarQuantizer
    tqm = TurboQuantMSE
    tqp = TurboQuantProd

    return [
        ("INT8 per-token   (8b)", sq(8, "per_token"),    8 + 16 / dim),
        ("INT4 per-token   (4b)", sq(4, "per_token"),    4 + 16 / dim),
        ("INT4 per-channel (4b)", sq(4, "per_channel"),  4 + 16 * 0.1 / dim),
        ("INT2 per-token   (2b)", sq(2, "per_token"),    2 + 16 / dim),
        ("TQ-MSE           (4b)", tqm(dim, 4, seed),     4 + 16 / dim),
        ("TQ-MSE           (3b)", tqm(dim, 3, seed),     3 + 16 / dim),
        ("TQ-MSE           (2b)", tqm(dim, 2, seed),     2 + 16 / dim),
        ("TQ-Prod          (4b)", tqp(dim, 4, seed),     4 + 32 / dim),
        ("TQ-Prod          (3b)", tqp(dim, 3, seed),     3 + 32 / dim),
    ]


def run_benchmark(
    dim: int = 128,
    n_vectors: int = 1024,
    n_q: int = 64,
    n_query_trials: int = 64,
    run_attn: bool = True,
    seed: int = 42,
) -> List[BenchResult]:
    set_seed(seed)

    print(f"\n  Precomputing TurboQuant codebooks (d={dim})...", end="", flush=True)
    methods = build_methods(dim, seed)
    print(f" done ({len(methods)} methods)")

    results: List[BenchResult] = []

    for dist_name, dist_fn in DISTRIBUTIONS.items():
        print(f"\n  Distribution: {dist_name}", flush=True)

        x = dist_fn(n_vectors, dim)

        q = np.random.randn(n_q, dim)
        q = q / np.maximum(np.linalg.norm(q, axis=-1, keepdims=True), 1e-12)

        for name, quantizer, eff_b in methods:
            t0 = time.perf_counter()
            x_hat = quantizer.round_trip(x)
            t1 = time.perf_counter()

            metrics = compute_metrics(x, x_hat, n_query_trials=n_query_trials)
            kl = compute_attn_kl(q, x, x_hat) if run_attn else float("nan")
            us_per_vec = (t1 - t0) * 1e6 / n_vectors

            results.append(BenchResult(
                method=name,
                distribution=dist_name,
                eff_bits=eff_b,
                mse_norm=metrics["mse_norm"],
                ip_bias=metrics["ip_bias"],
                ip_mse_norm=metrics["ip_mse_norm"],
                attn_kl=kl,
                us_per_vec=us_per_vec,
            ))

            kl_str = f"{kl:.5f}" if not math.isnan(kl) else "—"
            print(
                f"    {name:<26}  "
                f"mse={metrics['mse_norm']:.5f}  "
                f"ip_bias={metrics['ip_bias']:+.4f}  "
                f"kl={kl_str}",
                flush=True,
            )

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Formatting and export
# ─────────────────────────────────────────────────────────────────────────────

HEADERS = [
    "Method",
    "Eff. bits",
    "MSE↓ (norm)",
    "IP bias↓",
    "IP MSE↓ (norm)",
    "Attn KL↓",
    "μs/vec",
]


def rows_for_distribution(results: List[BenchResult], distribution: str) -> List[List[str]]:
    rows = []
    for r in results:
        if r.distribution != distribution:
            continue
        rows.append([
            r.method,
            f"{r.eff_bits:.2f}",
            f"{r.mse_norm:.5f}",
            f"{r.ip_bias:+.4f}",
            f"{r.ip_mse_norm:.6f}",
            f"{r.attn_kl:.5f}" if not math.isnan(r.attn_kl) else "—",
            f"{r.us_per_vec:.1f}",
        ])
    return rows


def print_tables(results: List[BenchResult]) -> None:
    for distribution in DISTRIBUTIONS:
        print(f"\n{'═' * 96}")
        print(f"  Distribution: {distribution.upper()}")
        print(f"{'═' * 96}")
        print(tabulate(
            rows_for_distribution(results, distribution),
            headers=HEADERS,
            tablefmt="simple",
            colalign=("left", "right", "right", "right", "right", "right", "right"),
        ))


def print_theory_table() -> None:
    print(f"\n{'─' * 72}")
    print("  TurboQuant MSE theoretical distortion references")
    print(f"{'─' * 72}")

    rows = []
    for bits, (paper_dist, lower_bound) in THEORY.items():
        rows.append([
            f"b={bits}",
            f"{paper_dist:.4f}",
            f"{lower_bound:.5f}",
            f"{paper_dist / lower_bound:.2f}x",
        ])

    print(tabulate(
        rows,
        headers=["Bits", "Paper distortion", "Lower bound (1/4^b)", "Ratio"],
        tablefmt="simple",
    ))
    print("  Ratio ≈ 2.7 means the distortion stays within a constant factor of the lower bound.")


def save_csv(results: List[BenchResult], path: str) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "method",
            "distribution",
            "eff_bits",
            "mse_norm",
            "ip_bias",
            "ip_mse_norm",
            "attn_kl",
            "us_per_vec",
        ])
        for r in results:
            writer.writerow([
                r.method,
                r.distribution,
                f"{r.eff_bits:.6f}",
                f"{r.mse_norm:.8f}",
                f"{r.ip_bias:.8f}",
                f"{r.ip_mse_norm:.8f}",
                f"{r.attn_kl:.8f}" if not math.isnan(r.attn_kl) else "nan",
                f"{r.us_per_vec:.4f}",
            ])

    print(f"\n  Saved CSV results to: {path}")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark TurboQuant against traditional KV scalar quantization",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--dim", type=int, default=128, help="Head dimension")
    parser.add_argument("--n_vectors", type=int, default=1024, help="Number of KV vectors")
    parser.add_argument("--n_q", type=int, default=64, help="Number of queries for attention KL")
    parser.add_argument("--n_query_trials", type=int, default=64, help="Random query trials for IP metrics")
    parser.add_argument("--no-attn", action="store_true", help="Skip attention KL metric")
    parser.add_argument("--csv", type=str, default=None, help="Optional CSV output path")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")

    args = parser.parse_args()

    if args.dim <= 1:
        raise ValueError("dim must be > 1")
    if args.n_vectors <= 0:
        raise ValueError("n_vectors must be > 0")
    if args.n_q <= 0:
        raise ValueError("n_q must be > 0")
    if args.n_query_trials <= 0:
        raise ValueError("n_query_trials must be > 0")

    print("\n" + "═" * 62)
    print("  TurboQuant vs Traditional KV Quantization — Benchmark")
    print("═" * 62)
    print(
        f"  dim={args.dim}  n_vectors={args.n_vectors}  "
        f"seed={args.seed}  attn={'off' if args.no_attn else 'on'}"
    )

    results = run_benchmark(
        dim=args.dim,
        n_vectors=args.n_vectors,
        n_q=args.n_q,
        n_query_trials=args.n_query_trials,
        run_attn=not args.no_attn,
        seed=args.seed,
    )

    print_tables(results)
    print_theory_table()

    if args.csv:
        save_csv(results, args.csv)


if __name__ == "__main__":
    main()