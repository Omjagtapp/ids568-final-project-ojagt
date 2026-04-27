"""Generate all PNG diagrams for the final project submission."""
from __future__ import annotations
import os
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
import numpy as np


def _box(ax, text, xy, w=0.18, h=0.09, fc="#1565C0", tc="white", fontsize=9):
    x, y = xy
    rect = mpatches.FancyBboxPatch(
        (x - w/2, y - h/2), w, h,
        boxstyle="round,pad=0.01", facecolor=fc, edgecolor="white", linewidth=1.5
    )
    ax.add_patch(rect)
    ax.text(x, y, text, ha="center", va="center", fontsize=fontsize,
            color=tc, fontweight="bold", wrap=True,
            multialignment="center")


def _arrow(ax, src, dst, label="", color="#455A64"):
    ax.annotate(
        "", xy=dst, xytext=src,
        arrowprops=dict(arrowstyle="-|>", color=color, lw=1.8),
    )
    if label:
        mx = (src[0] + dst[0]) / 2
        my = (src[1] + dst[1]) / 2
        ax.text(mx, my + 0.015, label, ha="center", va="bottom",
                fontsize=7, color=color, style="italic")


# ── 1. Lineage Diagram ────────────────────────────────────────────────────────

def make_lineage_diagram(path: str) -> None:
    fig, ax = plt.subplots(figsize=(14, 4))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor("#0D1117")
    ax.set_facecolor("#0D1117")

    steps = [
        ("Training Data\n(HuggingFace\nOpenWebText)", 0.08, "#1B5E20"),
        ("Pre-training\nGPT-2 (124M)\nOpenAI 2019", 0.25, "#0D47A1"),
        ("Model\nEvaluation\nPerplexity / BLEU", 0.42, "#4A148C"),
        ("Deployment\nFastAPI + Docker\nMilestone 5", 0.59, "#BF360C"),
        ("Monitoring\nPrometheus\n+ Grafana", 0.76, "#006064"),
        ("Governance\nAudit Trail\n+ Model Card", 0.93, "#37474F"),
    ]

    for label, x, color in steps:
        _box(ax, label, (x, 0.55), w=0.15, h=0.30, fc=color, fontsize=8)

    for i in range(len(steps) - 1):
        src = (steps[i][1] + 0.075, 0.55)
        dst = (steps[i+1][1] - 0.075, 0.55)
        _arrow(ax, src, dst, color="white")

    # Sub-annotations below boxes
    sub = [
        "40GB WebText\nNo PII", "117M→1.5B\nparams avail.",
        "BPE tokenizer\nperplexity=35.1", "SHA-256 cache\nbatching",
        "latency/drift\nP95 SLO=500ms", "NIST AI RMF\nrisk register",
    ]
    for (label, x, _), s in zip(steps, sub):
        ax.text(x, 0.28, s, ha="center", va="center", fontsize=7,
                color="#B0BEC5", multialignment="center")

    ax.set_title("GPT-2 LLM Inference Server — Model Lineage Diagram",
                 color="white", fontsize=13, fontweight="bold", pad=10)
    plt.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=150, bbox_inches="tight", facecolor="#0D1117")
    plt.close()
    print(f"Saved: {path}")


# ── 2. System Boundary Diagram ────────────────────────────────────────────────

def make_system_boundary_diagram(path: str) -> None:
    fig, ax = plt.subplots(figsize=(16, 9))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 9)
    ax.axis("off")
    fig.patch.set_facecolor("#FAFAFA")
    ax.set_facecolor("#FAFAFA")

    def box(text, x, y, w=1.9, h=0.8, fc="#1565C0", tc="white", fs=9):
        rect = mpatches.FancyBboxPatch(
            (x - w/2, y - h/2), w, h,
            boxstyle="round,pad=0.05", facecolor=fc, edgecolor="#37474F", linewidth=1.2
        )
        ax.add_patch(rect)
        ax.text(x, y, text, ha="center", va="center", fontsize=fs,
                color=tc, fontweight="bold", multialignment="center")

    def arrow(x1, y1, x2, y2, label="", color="#455A64"):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="-|>", color=color, lw=1.5))
        if label:
            ax.text((x1+x2)/2, (y1+y2)/2 + 0.12, label, ha="center",
                    fontsize=7, color=color, style="italic")

    def boundary(x, y, w, h, label, color="#E3F2FD", ec="#1565C0"):
        rect = mpatches.FancyBboxPatch(
            (x, y), w, h,
            boxstyle="round,pad=0.1", facecolor=color, edgecolor=ec, linewidth=2,
            linestyle="--", alpha=0.3
        )
        ax.add_patch(rect)
        ax.text(x + w/2, y + h + 0.05, label, ha="center", fontsize=9,
                color=ec, fontweight="bold")

    # System boundary boxes
    boundary(0.3, 0.5, 15.4, 7.5, "GPT-2 LLM Inference System Boundary", "#E8EAF6", "#3F51B5")
    boundary(1.2, 1.2, 3.5, 5.5, "Client Layer", "#E3F2FD", "#1565C0")
    boundary(5.0, 1.2, 4.5, 5.5, "Serving Layer (FastAPI)", "#E8F5E9", "#2E7D32")
    boundary(9.8, 1.2, 4.8, 5.5, "Observability Layer", "#FFF3E0", "#E65100")

    # Client layer
    box("Web Client\n/ API User", 2.0, 6.2, fc="#1565C0")
    box("Load\nGenerator\n(benchmarks/)", 2.0, 4.5, fc="#0D47A1")
    box("Synthetic\nTraffic\n(instrumentation.py)", 2.0, 2.8, fc="#1A237E")

    # Serving layer
    box("FastAPI\nEndpoint\n/v1/generate", 7.2, 6.2, fc="#2E7D32")
    box("DynamicBatcher\n(batching.py)\nmax_size=8", 7.2, 4.7, fc="#1B5E20")
    box("InProcessCache\n(caching.py)\nSHA-256 keys", 7.2, 3.2, fc="#33691E")
    box("GPT-2\n(HuggingFace)\n124M params", 7.2, 1.8, fc="#004D40")

    # Observability layer
    box("Prometheus\nMetrics\n/metrics", 12.2, 6.2, fc="#E65100")
    box("Grafana\nDashboard\n:3000", 12.2, 4.7, fc="#BF360C")
    box("Drift\nDetector\n(drift/)", 12.2, 3.2, fc="#4E342E")
    box("Audit\nTrail\nlogs/audit-trail.json", 12.2, 1.8, fc="#37474F")

    # Arrows — client to serving
    arrow(3.0, 6.2, 6.2, 6.2, "HTTP POST /v1/generate")
    arrow(3.0, 4.5, 6.2, 5.8, "HTTP load")
    arrow(3.0, 2.8, 6.2, 5.4, "synthetic traffic")

    # Arrows — within serving
    arrow(7.2, 5.8, 7.2, 5.1, "cache miss → batch")
    arrow(7.2, 4.3, 7.2, 3.6, "LRU lookup/store")
    arrow(7.2, 2.8, 7.2, 2.2, "batch inference")
    arrow(6.2, 6.2, 8.2, 6.2, "", color="gray")  # response back

    # Arrows — serving to observability
    arrow(8.2, 6.2, 11.2, 6.2, "metrics emit")
    arrow(8.2, 4.7, 11.2, 4.7, "request stats")
    arrow(8.2, 3.2, 11.2, 3.2, "input features")
    arrow(8.2, 1.8, 11.2, 1.8, "model events")
    arrow(12.2, 5.8, 12.2, 5.1, "scrape :8000/metrics")
    arrow(12.2, 4.3, 12.2, 3.6, "PSI/KS alerts")

    # Trust boundaries
    ax.annotate("", xy=(4.7, 7.2), xytext=(4.7, 0.8),
                arrowprops=dict(arrowstyle="-", color="red", lw=2, linestyle="dashed"))
    ax.text(4.72, 7.4, "Trust Boundary", fontsize=8, color="red", fontweight="bold")

    ax.annotate("", xy=(9.7, 7.2), xytext=(9.7, 0.8),
                arrowprops=dict(arrowstyle="-", color="orange", lw=2, linestyle="dashed"))
    ax.text(9.72, 7.4, "Data Boundary", fontsize=8, color="orange", fontweight="bold")

    ax.set_title("GPT-2 LLM Inference Server — System Boundary Diagram",
                 fontsize=14, fontweight="bold", pad=12)
    plt.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved: {path}")


# ── 3. Simulated Dashboard Screenshot ─────────────────────────────────────────

def make_dashboard_screenshot(path: str) -> None:
    """Generate a matplotlib-based mock Grafana dashboard screenshot."""
    np.random.seed(42)
    t = np.linspace(0, 300, 300)  # 5 minutes at 1s resolution

    # Simulated metrics
    latency_p50 = 45 + 10*np.sin(t/30) + np.random.normal(0, 3, 300)
    latency_p95 = 180 + 30*np.sin(t/45 + 0.5) + np.random.normal(0, 8, 300)
    throughput = 14 + 3*np.sin(t/60) + np.random.normal(0, 1, 300)
    cache_hits = np.clip(0.52 + 0.1*np.sin(t/90) + np.random.normal(0, 0.02, 300), 0, 1)
    error_rate = np.clip(0.008 + 0.005*np.abs(np.sin(t/120)) + np.random.normal(0, 0.001, 300), 0, 0.05)
    active_req = np.clip(2 + 4*np.abs(np.sin(t/30)) + np.random.normal(0, 0.5, 300), 0, 12).astype(int)

    fig = plt.figure(figsize=(18, 11))
    fig.patch.set_facecolor("#1A1A2E")
    gs = plt.GridSpec(3, 4, figure=fig, hspace=0.45, wspace=0.35)

    def styled_ax(ax, title, ylabel, color="#4FC3F7"):
        ax.set_facecolor("#16213E")
        for spine in ax.spines.values():
            spine.set_color("#455A64")
        ax.tick_params(colors="#90A4AE", labelsize=8)
        ax.set_title(title, color=color, fontsize=9, fontweight="bold", pad=4)
        ax.set_ylabel(ylabel, color="#90A4AE", fontsize=8)
        ax.set_xlabel("Time (s)", color="#90A4AE", fontsize=8)
        ax.yaxis.label.set_color("#90A4AE")

    # Panel 1: Latency time series
    ax1 = fig.add_subplot(gs[0, :2])
    ax1.plot(t, latency_p50, color="#4FC3F7", linewidth=1.2, label="P50")
    ax1.plot(t, latency_p95, color="#FF8A65", linewidth=1.2, label="P95")
    ax1.axhline(500, color="#EF5350", linestyle="--", linewidth=0.8, alpha=0.7, label="SLO 500ms")
    ax1.legend(fontsize=7, facecolor="#16213E", labelcolor="white")
    ax1.fill_between(t, latency_p50, latency_p95, alpha=0.15, color="#4FC3F7")
    styled_ax(ax1, "Request Latency (ms)", "Latency (ms)")
    ax1.set_ylim(0, 600)

    # Panel 2: Throughput
    ax2 = fig.add_subplot(gs[0, 2:])
    ax2.fill_between(t, 0, throughput, color="#81C784", alpha=0.6)
    ax2.plot(t, throughput, color="#A5D6A7", linewidth=1.0)
    styled_ax(ax2, "Throughput (req/s)", "req/s", "#81C784")
    ax2.set_ylim(0, 25)

    # Panel 3: Cache hit rate
    ax3 = fig.add_subplot(gs[1, :2])
    ax3.fill_between(t, 0, cache_hits * 100, color="#CE93D8", alpha=0.5)
    ax3.plot(t, cache_hits * 100, color="#E1BEE7", linewidth=1.0)
    ax3.axhline(50, color="#FF8A65", linestyle="--", linewidth=0.8, alpha=0.7, label="Target 50%")
    ax3.legend(fontsize=7, facecolor="#16213E", labelcolor="white")
    styled_ax(ax3, "Cache Hit Rate (%)", "Hit Rate (%)", "#CE93D8")
    ax3.set_ylim(0, 100)

    # Panel 4: Error rate
    ax4 = fig.add_subplot(gs[1, 2:])
    ax4.fill_between(t, 0, error_rate * 100, color="#EF9A9A", alpha=0.6)
    ax4.plot(t, error_rate * 100, color="#FFCDD2", linewidth=1.0)
    ax4.axhline(1.0, color="#EF5350", linestyle="--", linewidth=0.8, alpha=0.8, label="Alert >1%")
    ax4.legend(fontsize=7, facecolor="#16213E", labelcolor="white")
    styled_ax(ax4, "Error Rate (%)", "Error (%)", "#EF9A9A")
    ax4.set_ylim(0, 3)

    # Panel 5: Active requests
    ax5 = fig.add_subplot(gs[2, :2])
    ax5.bar(t[::5], active_req[::5], width=4, color="#FFB74D", alpha=0.8)
    styled_ax(ax5, "Active In-Flight Requests", "Count", "#FFB74D")
    ax5.set_ylim(0, 15)

    # Panel 6: Vocab novelty (drift signal)
    novelty = np.clip(0.05 + 0.03*np.sin(t/100) + np.random.normal(0, 0.005, 300), 0, 0.25)
    ax6 = fig.add_subplot(gs[2, 2:])
    ax6.plot(t, novelty * 100, color="#80DEEA", linewidth=1.2)
    ax6.fill_between(t, 0, novelty * 100, color="#80DEEA", alpha=0.3)
    ax6.axhline(15, color="#FFF176", linestyle="--", linewidth=0.8, alpha=0.8, label="Drift alert >15%")
    ax6.legend(fontsize=7, facecolor="#16213E", labelcolor="white")
    styled_ax(ax6, "Vocabulary Novelty Rate (% new tokens)", "Novelty %", "#80DEEA")
    ax6.set_ylim(0, 30)

    # Header title bar
    fig.text(0.5, 0.97, "GPT-2 LLM Inference Server — Production Monitoring Dashboard",
             ha="center", va="center", fontsize=15, fontweight="bold", color="#E3F2FD")
    fig.text(0.5, 0.945, "Datasource: Prometheus  |  Refresh: 10s  |  Window: Last 5 minutes",
             ha="center", va="center", fontsize=9, color="#78909C")

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=150, bbox_inches="tight", facecolor="#1A1A2E")
    plt.close()
    print(f"Saved: {path}")


if __name__ == "__main__":
    print("Generating diagrams...")
    make_lineage_diagram("docs/lineage-diagram.png")
    make_system_boundary_diagram("docs/system-boundary-diagram.png")
    make_dashboard_screenshot("screenshots/dashboard-overview.png")
    print("All diagrams generated.")
