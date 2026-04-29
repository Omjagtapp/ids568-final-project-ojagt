"""
A/B Test Simulation — GPT-2 Inference Server: Baseline vs. Optimized Configuration

Experiment:
  Model A (Control): batch_timeout_ms=50, cache_ttl=300s, max_batch_size=8
  Model B (Treatment): batch_timeout_ms=100, cache_ttl=600s, max_batch_size=16

Primary metric: P95 request latency (ms)
Secondary metrics: throughput (req/s), cache hit rate, user satisfaction proxy

Run:
  python -m src.ab_test.simulation
  python -m src.ab_test.simulation --n 2000 --output visualizations/
  python -m src.ab_test.simulation --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import random
from pathlib import Path
from typing import NamedTuple

import numpy as np
import scipy.stats as stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# ── Simulation parameters ──────────────────────────────────────────────────────

RANDOM_SEED = 42
N_DEFAULT = 1500  # per arm — power calculation justification in docs/experiment-specification.md

# Model A (control) — Milestone 5 default configuration
A_LATENCY_CACHE_HIT_MS = (18.0, 4.0)    # mean, std
A_LATENCY_CACHE_MISS_MS = (210.0, 35.0)
A_CACHE_HIT_RATE = 0.52
A_THROUGHPUT_RPS = 14.2
A_ERROR_RATE = 0.012

# Model B (treatment) — extended timeout + larger batch + longer TTL
B_LATENCY_CACHE_HIT_MS = (17.0, 3.5)    # slightly faster hit (same path)
B_LATENCY_CACHE_MISS_MS = (185.0, 28.0) # faster due to larger batches
B_CACHE_HIT_RATE = 0.68                  # higher due to 2× TTL
B_THROUGHPUT_RPS = 17.8
B_ERROR_RATE = 0.009


class ArmResult(NamedTuple):
    name: str
    latencies_ms: np.ndarray
    cache_hits: int
    n: int
    errors: int


# ── Simulation core ────────────────────────────────────────────────────────────

def simulate_arm(
    name: str,
    n: int,
    cache_hit_rate: float,
    hit_params: tuple[float, float],
    miss_params: tuple[float, float],
    error_rate: float,
    rng: np.random.Generator,
) -> ArmResult:
    """Simulate n requests for a single arm, drawing from truncated normal distributions."""
    latencies = np.empty(n)
    n_hit = int(n * cache_hit_rate)
    n_miss = n - n_hit

    # Cache hits: faster, lower variance
    hit_latencies = rng.normal(hit_params[0], hit_params[1], n_hit)
    hit_latencies = np.clip(hit_latencies, 5.0, 100.0)

    # Cache misses: slower, higher variance (model inference + batching overhead)
    miss_latencies = rng.normal(miss_params[0], miss_params[1], n_miss)
    miss_latencies = np.clip(miss_latencies, 50.0, 800.0)

    all_latencies = np.concatenate([hit_latencies, miss_latencies])
    rng.shuffle(all_latencies)

    # Simulate errors as NaN (excluded from latency analysis)
    n_errors = int(n * error_rate)
    error_idx = rng.choice(n, size=n_errors, replace=False)
    all_latencies[error_idx] = np.nan

    return ArmResult(
        name=name,
        latencies_ms=all_latencies,
        cache_hits=n_hit,
        n=n,
        errors=n_errors,
    )


def run_simulation(n: int = N_DEFAULT, seed: int = RANDOM_SEED) -> tuple[ArmResult, ArmResult]:
    rng = np.random.default_rng(seed)
    arm_a = simulate_arm(
        "A (Baseline)", n, A_CACHE_HIT_RATE,
        A_LATENCY_CACHE_HIT_MS, A_LATENCY_CACHE_MISS_MS, A_ERROR_RATE, rng,
    )
    arm_b = simulate_arm(
        "B (Optimized)", n, B_CACHE_HIT_RATE,
        B_LATENCY_CACHE_HIT_MS, B_LATENCY_CACHE_MISS_MS, B_ERROR_RATE, rng,
    )
    return arm_a, arm_b


# ── Statistical evaluation ─────────────────────────────────────────────────────

def evaluate(arm_a: ArmResult, arm_b: ArmResult) -> dict:
    """
    Run statistical tests on P95 latency reduction.

    Tests:
      1. Two-sample Welch t-test on mean latency
      2. Mann-Whitney U (non-parametric, more robust for skewed latency data)
      3. 95% bootstrap confidence interval on the mean difference
      4. Effect size (Cohen's d)
    """
    a_clean = arm_a.latencies_ms[~np.isnan(arm_a.latencies_ms)]
    b_clean = arm_b.latencies_ms[~np.isnan(arm_b.latencies_ms)]

    # Descriptive statistics
    def describe(x):
        return {
            "n": len(x),
            "mean": float(np.mean(x)),
            "std": float(np.std(x, ddof=1)),
            "p50": float(np.percentile(x, 50)),
            "p95": float(np.percentile(x, 95)),
            "p99": float(np.percentile(x, 99)),
        }

    stats_a = describe(a_clean)
    stats_b = describe(b_clean)

    # Welch t-test
    t_stat, p_value_t = stats.ttest_ind(a_clean, b_clean, equal_var=False)

    # Mann-Whitney U
    u_stat, p_value_mw = stats.mannwhitneyu(a_clean, b_clean, alternative="greater")

    # Bootstrap 95% CI on mean difference (A - B)
    n_boot = 5000
    rng = np.random.default_rng(0)
    boot_diffs = np.array([
        np.mean(rng.choice(a_clean, len(a_clean))) - np.mean(rng.choice(b_clean, len(b_clean)))
        for _ in range(n_boot)
    ])
    ci_low, ci_high = float(np.percentile(boot_diffs, 2.5)), float(np.percentile(boot_diffs, 97.5))

    # Bootstrap 95% CI on P95 difference (A - B) — primary metric
    rng_p95 = np.random.default_rng(1)
    p95_boot_diffs = np.array([
        np.percentile(rng_p95.choice(a_clean, len(a_clean)), 95)
        - np.percentile(rng_p95.choice(b_clean, len(b_clean)), 95)
        for _ in range(n_boot)
    ])
    p95_ci_low = float(np.percentile(p95_boot_diffs, 2.5))
    p95_ci_high = float(np.percentile(p95_boot_diffs, 97.5))
    p95_improvement_prob = float(np.mean(p95_boot_diffs > 0))

    # Cohen's d
    pooled_std = np.sqrt((np.var(a_clean, ddof=1) + np.var(b_clean, ddof=1)) / 2)
    cohens_d = float((np.mean(a_clean) - np.mean(b_clean)) / pooled_std)

    # P95 reduction
    p95_diff = float(stats_a["p95"] - stats_b["p95"])
    p95_reduction_pct = p95_diff / stats_a["p95"] * 100

    # Cache hit rate delta
    hit_rate_a = arm_a.cache_hits / arm_a.n
    hit_rate_b = arm_b.cache_hits / arm_b.n

    return {
        "arm_a": stats_a,
        "arm_b": stats_b,
        "welch_t_stat": float(t_stat),
        "welch_p_value": float(p_value_t),
        "mannwhitney_u_stat": float(u_stat),
        "mannwhitney_p_value": float(p_value_mw),
        "bootstrap_ci_95": [ci_low, ci_high],
        "cohens_d": cohens_d,
        "p95_diff": p95_diff,
        "p95_reduction_pct": float(p95_reduction_pct),
        "p95_bootstrap_ci_95": [p95_ci_low, p95_ci_high],
        "p95_improvement_probability": p95_improvement_prob,
        "cache_hit_rate_a": float(hit_rate_a),
        "cache_hit_rate_b": float(hit_rate_b),
        "statistically_significant": float(p_value_t) < 0.05,
        "practical_significance": abs(cohens_d) > 0.2,
    }


# ── Visualizations ─────────────────────────────────────────────────────────────

def make_plots(arm_a: ArmResult, arm_b: ArmResult, results: dict, output_dir: str = "visualizations") -> None:
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    a_clean = arm_a.latencies_ms[~np.isnan(arm_a.latencies_ms)]
    b_clean = arm_b.latencies_ms[~np.isnan(arm_b.latencies_ms)]

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("A/B Test Results: Baseline vs. Optimized GPT-2 Inference Server",
                 fontsize=14, fontweight="bold", y=0.98)

    # 1. Latency distribution (KDE + histogram)
    ax = axes[0, 0]
    ax.hist(a_clean, bins=60, alpha=0.5, color="#2196F3", density=True, label="A: Baseline")
    ax.hist(b_clean, bins=60, alpha=0.5, color="#4CAF50", density=True, label="B: Optimized")
    ax.axvline(np.percentile(a_clean, 95), color="#1565C0", linestyle="--", linewidth=1.5,
               label=f"A P95 = {np.percentile(a_clean,95):.1f} ms")
    ax.axvline(np.percentile(b_clean, 95), color="#2E7D32", linestyle="--", linewidth=1.5,
               label=f"B P95 = {np.percentile(b_clean,95):.1f} ms")
    ax.set_xlabel("Latency (ms)")
    ax.set_ylabel("Density")
    ax.set_title("Latency Distribution")
    ax.legend(fontsize=8)
    ax.set_xlim(0, 600)

    # 2. Boxplot comparison
    ax = axes[0, 1]
    bp = ax.boxplot([a_clean, b_clean], labels=["A: Baseline", "B: Optimized"],
                    patch_artist=True, notch=True)
    colors = ["#2196F3", "#4CAF50"]
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)
    ax.set_ylabel("Latency (ms)")
    ax.set_title("Latency Boxplot (with notch = 95% CI on median)")
    ax.set_ylim(0, 500)

    # 3. Percentile comparison
    ax = axes[1, 0]
    percentiles = [50, 75, 90, 95, 99]
    p_a = [np.percentile(a_clean, p) for p in percentiles]
    p_b = [np.percentile(b_clean, p) for p in percentiles]
    x = np.arange(len(percentiles))
    width = 0.35
    bars_a = ax.bar(x - width/2, p_a, width, label="A: Baseline", color="#2196F3", alpha=0.8)
    bars_b = ax.bar(x + width/2, p_b, width, label="B: Optimized", color="#4CAF50", alpha=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels([f"P{p}" for p in percentiles])
    ax.set_ylabel("Latency (ms)")
    ax.set_title("Latency Percentile Comparison")
    ax.legend()
    for bar in bars_a:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2,
                f"{bar.get_height():.0f}", ha="center", va="bottom", fontsize=7)
    for bar in bars_b:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2,
                f"{bar.get_height():.0f}", ha="center", va="bottom", fontsize=7)

    # 4. Bootstrap CI plot
    ax = axes[1, 1]
    rng = np.random.default_rng(0)
    boot_diffs = np.array([
        np.mean(rng.choice(a_clean, len(a_clean))) - np.mean(rng.choice(b_clean, len(b_clean)))
        for _ in range(2000)
    ])
    ax.hist(boot_diffs, bins=50, color="#9C27B0", alpha=0.7, edgecolor="white")
    ci_lo, ci_hi = np.percentile(boot_diffs, [2.5, 97.5])
    ax.axvline(ci_lo, color="#4A148C", linestyle="--", label=f"95% CI low: {ci_lo:.1f} ms")
    ax.axvline(ci_hi, color="#4A148C", linestyle="--", label=f"95% CI high: {ci_hi:.1f} ms")
    ax.axvline(0, color="red", linestyle="-", linewidth=1.5, label="No effect (0)")
    ax.axvline(np.mean(boot_diffs), color="black", linestyle="-",
               label=f"Mean diff: {np.mean(boot_diffs):.1f} ms")
    ax.set_xlabel("Mean Latency Difference A−B (ms)")
    ax.set_ylabel("Bootstrap samples")
    ax.set_title("Bootstrap Distribution of Mean Difference (5 000 resamples)")
    ax.legend(fontsize=8)

    plt.tight_layout()
    out_path = os.path.join(output_dir, "ab_test_results.png")
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved: {out_path}")


# ── CLI entrypoint ─────────────────────────────────────────────────────────────

def _print_results(results: dict) -> None:
    print("\n" + "="*60)
    print("  A/B TEST STATISTICAL RESULTS")
    print("="*60)
    a, b = results["arm_a"], results["arm_b"]
    print(f"\n{'Metric':<30} {'Arm A':>12} {'Arm B':>12}")
    print("-"*56)
    print(f"{'N (valid)':<30} {a['n']:>12,} {b['n']:>12,}")
    print(f"{'Mean latency (ms)':<30} {a['mean']:>12.1f} {b['mean']:>12.1f}")
    print(f"{'Std (ms)':<30} {a['std']:>12.1f} {b['std']:>12.1f}")
    print(f"{'P50 (ms)':<30} {a['p50']:>12.1f} {b['p50']:>12.1f}")
    print(f"{'P95 (ms)':<30} {a['p95']:>12.1f} {b['p95']:>12.1f}")
    print(f"{'P99 (ms)':<30} {a['p99']:>12.1f} {b['p99']:>12.1f}")
    print(f"{'Cache hit rate':<30} {results['cache_hit_rate_a']:>11.1%} {results['cache_hit_rate_b']:>11.1%}")
    print()
    print(f"--- Primary metric: P95 latency ---")
    print(f"P95 difference A-B:          {results['p95_diff']:.1f} ms  ({results['p95_reduction_pct']:.1f}% reduction)")
    print(f"P95 bootstrap 95% CI (A-B):  [{results['p95_bootstrap_ci_95'][0]:.1f}, {results['p95_bootstrap_ci_95'][1]:.1f}] ms")
    print(f"P95 improvement probability: {results['p95_improvement_probability']:.1%}")
    print(f"--- Supporting: mean latency ---")
    print(f"Welch t-test:  t={results['welch_t_stat']:.3f}, p={results['welch_p_value']:.4f}")
    print(f"Mann-Whitney:  U={results['mannwhitney_u_stat']:.0f}, p={results['mannwhitney_p_value']:.4f}")
    print(f"Cohen's d:     {results['cohens_d']:.3f}")
    print(f"Bootstrap 95% CI on mean diff (A-B): [{results['bootstrap_ci_95'][0]:.1f}, {results['bootstrap_ci_95'][1]:.1f}] ms")
    print()
    sig = "YES" if results["statistically_significant"] else "NO"
    prac = "YES" if results["practical_significance"] else "NO"
    print(f"Statistically significant (p<0.05): {sig}")
    print(f"Practically significant (|d|>0.2):  {prac}")
    print("="*60)

    if results["statistically_significant"] and results["practical_significance"]:
        print("\nRECOMMENDATION: Ship Model B (Optimized)")
    elif results["statistically_significant"]:
        print("\nRECOMMENDATION: Ship Model B (statistically significant but small effect)")
    else:
        print("\nRECOMMENDATION: Collect more data (insufficient evidence)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run A/B test simulation")
    parser.add_argument("--n", type=int, default=N_DEFAULT, help="Requests per arm")
    parser.add_argument("--seed", type=int, default=RANDOM_SEED)
    parser.add_argument("--output", default="visualizations", help="Output directory for plots")
    parser.add_argument("--dry-run", action="store_true", help="Run without saving output")
    parser.add_argument("--json", dest="json_out", metavar="FILE", help="Save results as JSON")
    args = parser.parse_args()

    print(f"Running A/B simulation: n={args.n} per arm, seed={args.seed}")
    arm_a, arm_b = run_simulation(n=args.n, seed=args.seed)
    results = evaluate(arm_a, arm_b)
    _print_results(results)

    if not args.dry_run:
        make_plots(arm_a, arm_b, results, output_dir=args.output)

    if args.json_out:
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        with open(args.json_out, "w") as f:
            json.dump(results, f, indent=2)
        print(f"Results saved to {args.json_out}")
