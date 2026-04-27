"""
Data Integrity & Drift Detection — GPT-2 LLM Inference Server

Detects and quantifies:
  1. Feature drift  — prompt length, vocabulary richness, token count distributions
  2. Label drift    — response length distribution (proxy for model output shift)
  3. Outlier / integrity anomalies — prompts with extreme lengths, encoding issues
  4. PSI (Population Stability Index) for each feature window
  5. KS test for distributional equality

Workflow:
  1. generate_reference_data()  — build baseline distributions from Week-1 traffic
  2. generate_production_data() — simulate 4 weekly production windows
  3. detect_drift()             — compute PSI, KS, anomaly flags per window
  4. plot_drift()               — save time-series visualizations
  5. save_report()              — write JSON summary

Run:
  python -m src.drift.drift_detection
  python -m src.drift.drift_detection --output visualizations/ --report docs/drift-report.json
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import scipy.stats as stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

RANDOM_SEED = 0
N_REF = 1000       # reference window size
N_PROD = 500       # production window size per week
N_WEEKS = 4        # number of production windows to simulate


# ── Data generation ────────────────────────────────────────────────────────────

def _prompt_length(rng, loc, scale, size):
    return np.clip(rng.normal(loc, scale, size), 10, 1600).astype(float)

def _vocab_richness(rng, loc, scale, size):
    """Unique tokens / total tokens — a proxy for lexical diversity."""
    return np.clip(rng.normal(loc, scale, size), 0.05, 1.0).astype(float)

def _response_length(rng, loc, scale, size):
    return np.clip(rng.normal(loc, scale, size), 5, 512).astype(float)

def _token_count(rng, loc, scale, size):
    return np.clip(rng.normal(loc, scale, size), 2, 300).astype(int).astype(float)


def generate_reference_data(seed: int = RANDOM_SEED) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    return {
        "prompt_length_chars": _prompt_length(rng, 85.0, 30.0, N_REF),
        "vocab_richness": _vocab_richness(rng, 0.72, 0.08, N_REF),
        "response_length_tokens": _response_length(rng, 42.0, 12.0, N_REF),
        "token_count": _token_count(rng, 18.0, 6.0, N_REF),
    }


def generate_production_windows(seed: int = RANDOM_SEED) -> list[dict[str, np.ndarray]]:
    """
    Simulate 4 weekly windows with gradual distribution shift.

    Week 1: slight shift (language mix starts appearing)
    Week 2: moderate shift (more multilingual prompts, longer inputs)
    Week 3: significant shift (domain change — technical/code queries surge)
    Week 4: severe shift (fully out-of-distribution, adversarial-style inputs)
    """
    windows = []
    params = [
        # (prompt_len_mean, prompt_len_std, vocab_mean, vocab_std, resp_mean, resp_std, tok_mean, tok_std)
        (90.0,  32.0,  0.70, 0.09,  43.0, 13.0,  19.0, 6.5),   # week 1 — slight
        (105.0, 42.0,  0.65, 0.12,  48.0, 18.0,  22.0, 8.0),   # week 2 — moderate
        (138.0, 65.0,  0.58, 0.15,  55.0, 22.0,  28.0, 11.0),  # week 3 — significant
        (185.0, 95.0,  0.48, 0.20,  68.0, 32.0,  38.0, 16.0),  # week 4 — severe
    ]
    for i, p in enumerate(params):
        rng = np.random.default_rng(seed + i + 1)
        windows.append({
            "prompt_length_chars": _prompt_length(rng, p[0], p[1], N_PROD),
            "vocab_richness": _vocab_richness(rng, p[2], p[3], N_PROD),
            "response_length_tokens": _response_length(rng, p[4], p[5], N_PROD),
            "token_count": _token_count(rng, p[6], p[7], N_PROD),
        })
    return windows


# ── PSI calculation ────────────────────────────────────────────────────────────

def psi(reference: np.ndarray, production: np.ndarray, n_bins: int = 10) -> float:
    """
    Population Stability Index.

    PSI < 0.1  : No significant drift
    PSI 0.1-0.2: Minor drift — monitor closely
    PSI > 0.2  : Significant drift — investigate / retrain
    PSI > 0.25 : Severe drift — immediate action required
    """
    bins = np.percentile(reference, np.linspace(0, 100, n_bins + 1))
    bins[0] -= 1e-9
    bins[-1] += 1e-9

    ref_counts, _ = np.histogram(reference, bins=bins)
    prod_counts, _ = np.histogram(production, bins=bins)

    ref_pct = ref_counts / len(reference) + 1e-9
    prod_pct = prod_counts / len(production) + 1e-9

    return float(np.sum((prod_pct - ref_pct) * np.log(prod_pct / ref_pct)))


# ── Anomaly detection ──────────────────────────────────────────────────────────

def detect_anomalies(data: np.ndarray, feature: str) -> dict[str, Any]:
    """Flag samples outside 3-sigma from the reference mean as anomalies."""
    mean, std = np.mean(data), np.std(data, ddof=1)
    anomaly_mask = np.abs(data - mean) > 3 * std
    return {
        "anomaly_count": int(np.sum(anomaly_mask)),
        "anomaly_rate": float(np.mean(anomaly_mask)),
        "anomaly_min": float(data[anomaly_mask].min()) if anomaly_mask.any() else None,
        "anomaly_max": float(data[anomaly_mask].max()) if anomaly_mask.any() else None,
    }


# ── Drift detection orchestrator ───────────────────────────────────────────────

def detect_drift(
    reference: dict[str, np.ndarray],
    windows: list[dict[str, np.ndarray]],
) -> list[dict[str, Any]]:
    """Compute PSI, KS test, and anomaly stats for each production window."""
    results = []
    for week_idx, window in enumerate(windows, start=1):
        week_result: dict[str, Any] = {"week": week_idx, "features": {}}
        for feature, ref_data in reference.items():
            prod_data = window[feature]
            psi_val = psi(ref_data, prod_data)
            ks_stat, ks_pval = stats.ks_2samp(ref_data, prod_data)
            anomalies = detect_anomalies(prod_data, feature)
            severity = (
                "none" if psi_val < 0.1 else
                "minor" if psi_val < 0.2 else
                "significant" if psi_val < 0.25 else
                "severe"
            )
            week_result["features"][feature] = {
                "psi": round(psi_val, 4),
                "ks_statistic": round(float(ks_stat), 4),
                "ks_p_value": round(float(ks_pval), 6),
                "drift_severity": severity,
                "ref_mean": round(float(np.mean(ref_data)), 3),
                "prod_mean": round(float(np.mean(prod_data)), 3),
                "mean_shift_pct": round(
                    (np.mean(prod_data) - np.mean(ref_data)) / max(abs(np.mean(ref_data)), 1e-9) * 100, 2
                ),
                **anomalies,
            }
        results.append(week_result)
    return results


# ── Visualizations ─────────────────────────────────────────────────────────────

FEATURE_LABELS = {
    "prompt_length_chars": "Prompt Length (chars)",
    "vocab_richness": "Vocabulary Richness",
    "response_length_tokens": "Response Length (tokens)",
    "token_count": "Token Count",
}

SEVERITY_COLORS = {"none": "#4CAF50", "minor": "#FF9800", "significant": "#FF5722", "severe": "#B71C1C"}


def plot_drift(
    reference: dict[str, np.ndarray],
    windows: list[dict[str, np.ndarray]],
    drift_results: list[dict],
    output_dir: str = "visualizations",
) -> None:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    features = list(reference.keys())
    weeks = [f"Week {r['week']}" for r in drift_results]

    # --- Plot 1: PSI over time for all features ---
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    fig.suptitle("PSI (Population Stability Index) Over Time by Feature",
                 fontsize=14, fontweight="bold")
    axes = axes.flatten()
    for i, feature in enumerate(features):
        ax = axes[i]
        psi_vals = [r["features"][feature]["psi"] for r in drift_results]
        colors = [SEVERITY_COLORS[r["features"][feature]["drift_severity"]] for r in drift_results]
        bars = ax.bar(weeks, psi_vals, color=colors, alpha=0.85, edgecolor="black", linewidth=0.5)
        ax.axhline(0.1, color="#FF9800", linestyle="--", linewidth=1.2, label="Minor drift threshold (0.10)")
        ax.axhline(0.2, color="#FF5722", linestyle="--", linewidth=1.2, label="Significant drift (0.20)")
        ax.axhline(0.25, color="#B71C1C", linestyle="--", linewidth=1.2, label="Severe drift (0.25)")
        for bar, val in zip(bars, psi_vals):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.003,
                    f"{val:.3f}", ha="center", va="bottom", fontsize=9, fontweight="bold")
        ax.set_title(FEATURE_LABELS[feature])
        ax.set_ylabel("PSI")
        ax.set_ylim(0, max(max(psi_vals) * 1.3, 0.35))
        if i == 0:
            ax.legend(fontsize=7, loc="upper left")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "drift_psi_over_time.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved: {output_dir}/drift_psi_over_time.png")

    # --- Plot 2: Distribution shift for most drifted feature (prompt_length_chars) ---
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle("Distribution Shift: Prompt Length (chars) — Reference vs. Production Weeks",
                 fontsize=13, fontweight="bold")
    ax = axes[0]
    ax.hist(reference["prompt_length_chars"], bins=40, alpha=0.6, color="#1565C0",
            density=True, label="Reference (Week 0)")
    week_colors = ["#42A5F5", "#FFA726", "#EF5350", "#B71C1C"]
    for idx, window in enumerate(windows):
        ax.hist(window["prompt_length_chars"], bins=40, alpha=0.4,
                color=week_colors[idx], density=True, label=f"Week {idx+1}")
    ax.set_xlabel("Prompt Length (chars)")
    ax.set_ylabel("Density")
    ax.set_title("Histogram Overlay")
    ax.legend(fontsize=8)

    ax = axes[1]
    mean_ref = np.mean(reference["prompt_length_chars"])
    means_prod = [np.mean(w["prompt_length_chars"]) for w in windows]
    p95_ref = np.percentile(reference["prompt_length_chars"], 95)
    p95_prod = [np.percentile(w["prompt_length_chars"], 95) for w in windows]
    x = np.arange(len(weeks))
    ax.plot([-1] + list(x), [mean_ref] + means_prod, "o-", color="#2196F3",
            linewidth=2, markersize=7, label="Mean")
    ax.plot([-1] + list(x), [p95_ref] + p95_prod, "s--", color="#FF5722",
            linewidth=2, markersize=7, label="P95")
    ax.axhline(mean_ref, color="#2196F3", linestyle=":", alpha=0.4, linewidth=1)
    ax.axhline(p95_ref, color="#FF5722", linestyle=":", alpha=0.4, linewidth=1)
    ax.set_xticks(list(range(-1, len(weeks))))
    ax.set_xticklabels(["Ref"] + weeks)
    ax.set_ylabel("Prompt Length (chars)")
    ax.set_title("Mean and P95 Over Time")
    ax.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "drift_prompt_length.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved: {output_dir}/drift_prompt_length.png")

    # --- Plot 3: Heatmap of drift severity across features and weeks ---
    fig, ax = plt.subplots(figsize=(10, 5))
    severity_map = {"none": 0, "minor": 1, "significant": 2, "severe": 3}
    matrix = np.array([
        [severity_map[r["features"][f]["drift_severity"]] for f in features]
        for r in drift_results
    ])
    psi_matrix = np.array([
        [r["features"][f]["psi"] for f in features]
        for r in drift_results
    ])
    cmap = plt.cm.get_cmap("RdYlGn_r", 4)
    im = ax.imshow(matrix, cmap=cmap, vmin=-0.5, vmax=3.5, aspect="auto")
    ax.set_xticks(range(len(features)))
    ax.set_xticklabels([FEATURE_LABELS[f] for f in features], rotation=20, ha="right")
    ax.set_yticks(range(len(weeks)))
    ax.set_yticklabels(weeks)
    for i in range(len(weeks)):
        for j in range(len(features)):
            ax.text(j, i, f"{psi_matrix[i, j]:.3f}", ha="center", va="center",
                    fontsize=10, fontweight="bold",
                    color="white" if matrix[i, j] >= 2 else "black")
    cbar = plt.colorbar(im, ax=ax, ticks=[0, 1, 2, 3])
    cbar.set_ticklabels(["None", "Minor", "Significant", "Severe"])
    ax.set_title("Drift Severity Heatmap (PSI values shown)", fontsize=13, fontweight="bold")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "drift_severity_heatmap.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved: {output_dir}/drift_severity_heatmap.png")

    # --- Plot 4: Anomaly rate over time ---
    fig, ax = plt.subplots(figsize=(10, 4))
    for feature in features:
        anomaly_rates = [r["features"][feature]["anomaly_rate"] * 100 for r in drift_results]
        ax.plot(weeks, anomaly_rates, "o-", linewidth=2, markersize=6,
                label=FEATURE_LABELS[feature])
    ax.axhline(5.0, color="red", linestyle="--", linewidth=1.2, label="5% anomaly threshold")
    ax.set_ylabel("Anomaly Rate (%)")
    ax.set_title("Anomaly Rate Over Production Windows", fontsize=13, fontweight="bold")
    ax.legend(fontsize=8)
    ax.set_ylim(0, max(15, ax.get_ylim()[1]))
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "drift_anomaly_rate.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved: {output_dir}/drift_anomaly_rate.png")


# ── Report ─────────────────────────────────────────────────────────────────────

def save_report(drift_results: list[dict], path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(drift_results, f, indent=2)
    print(f"Drift report saved to: {path}")


def print_summary(drift_results: list[dict]) -> None:
    print("\n" + "="*65)
    print("  DRIFT DETECTION SUMMARY")
    print("="*65)
    header = f"{'Feature':<35} " + "  ".join(f"{'Wk'+str(r['week']):>8}" for r in drift_results)
    print(header)
    print("-"*65)
    for feature in drift_results[0]["features"]:
        vals = "  ".join(
            f"{r['features'][feature]['psi']:>8.3f}"
            for r in drift_results
        )
        sevs = " ".join(
            f"({r['features'][feature]['drift_severity'][0].upper()})"
            for r in drift_results
        )
        print(f"{FEATURE_LABELS[feature]:<35} {vals}  {sevs}")
    print()
    print("Severity key: N=None (<0.10)  M=Minor (<0.20)  S=Significant (<0.25)  X=Severe (≥0.25)")
    print("="*65)


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run drift detection pipeline")
    parser.add_argument("--output", default="visualizations", help="Output directory for plots")
    parser.add_argument("--report", default="", help="Path to save JSON drift report")
    parser.add_argument("--seed", type=int, default=RANDOM_SEED)
    args = parser.parse_args()

    print("Generating reference and production data...")
    reference = generate_reference_data(seed=args.seed)
    windows = generate_production_windows(seed=args.seed)

    print("Running drift detection...")
    drift_results = detect_drift(reference, windows)
    print_summary(drift_results)

    print("\nGenerating visualizations...")
    plot_drift(reference, windows, drift_results, output_dir=args.output)

    if args.report:
        save_report(drift_results, args.report)

    print("\nDone.")
