"""
Smoke tests — verify core modules load correctly and return plausible results.

These tests are fast, self-contained, and require no external services
(no Docker, Grafana, Prometheus, Redis, or GPT-2 model weights).
"""

import numpy as np
import pytest


# ── A/B simulation ──────────────────────────────────────────────────────────────

def test_ab_simulation_returns_two_arms_with_latencies():
    from src.ab_test.simulation import run_simulation

    arm_a, arm_b = run_simulation(n=200, seed=0)

    assert arm_a.name.startswith("A"), "Arm A name should start with 'A'"
    assert arm_b.name.startswith("B"), "Arm B name should start with 'B'"
    assert len(arm_a.latencies_ms) == 200
    assert len(arm_b.latencies_ms) == 200

    a_clean = arm_a.latencies_ms[~np.isnan(arm_a.latencies_ms)]
    b_clean = arm_b.latencies_ms[~np.isnan(arm_b.latencies_ms)]
    assert len(a_clean) > 0, "Arm A must have at least one valid latency"
    assert len(b_clean) > 0, "Arm B must have at least one valid latency"


def test_ab_evaluate_returns_p95_bootstrap_fields():
    from src.ab_test.simulation import run_simulation, evaluate

    arm_a, arm_b = run_simulation(n=200, seed=0)
    results = evaluate(arm_a, arm_b)

    assert "p95_diff" in results
    assert "p95_bootstrap_ci_95" in results
    assert "p95_improvement_probability" in results

    ci = results["p95_bootstrap_ci_95"]
    assert len(ci) == 2
    assert ci[0] <= ci[1], "CI lower bound must be <= upper bound"

    prob = results["p95_improvement_probability"]
    assert 0.0 <= prob <= 1.0, "Improvement probability must be in [0, 1]"


def test_ab_simulation_b_faster_than_a():
    """Model B (optimized) should have lower P95 than Model A by design."""
    from src.ab_test.simulation import run_simulation, evaluate

    arm_a, arm_b = run_simulation(n=500, seed=42)
    results = evaluate(arm_a, arm_b)

    assert results["arm_b"]["p95"] < results["arm_a"]["p95"], (
        f"B P95 ({results['arm_b']['p95']:.1f} ms) should be < A P95 ({results['arm_a']['p95']:.1f} ms)"
    )


# ── Drift detection ─────────────────────────────────────────────────────────────

def test_drift_detection_returns_four_weekly_windows():
    from src.drift.drift_detection import (
        generate_reference_data,
        generate_production_windows,
        detect_drift,
    )

    reference = generate_reference_data(seed=0)
    windows = generate_production_windows(seed=0)
    results = detect_drift(reference, windows)

    assert len(results) == 4, "Should return exactly 4 weekly windows"
    for week_result in results:
        assert "week" in week_result
        assert "features" in week_result


def test_drift_detection_psi_values_present_and_non_negative():
    from src.drift.drift_detection import (
        generate_reference_data,
        generate_production_windows,
        detect_drift,
    )

    reference = generate_reference_data(seed=0)
    windows = generate_production_windows(seed=0)
    results = detect_drift(reference, windows)

    for week_result in results:
        for feature, data in week_result["features"].items():
            assert "psi" in data, f"Missing PSI for {feature} week {week_result['week']}"
            assert data["psi"] >= 0, f"PSI must be non-negative (got {data['psi']})"
            assert data["drift_severity"] in ("none", "minor", "significant", "severe"), (
                f"Unexpected severity: {data['drift_severity']}"
            )


def test_drift_week4_is_severe():
    """By design, Week 4 should have severe drift on all features (PSI >> 0.25)."""
    from src.drift.drift_detection import (
        generate_reference_data,
        generate_production_windows,
        detect_drift,
    )

    reference = generate_reference_data(seed=0)
    windows = generate_production_windows(seed=0)
    results = detect_drift(reference, windows)

    week4 = results[3]
    for feature, data in week4["features"].items():
        assert data["drift_severity"] == "severe", (
            f"Week 4 {feature} PSI={data['psi']:.3f} should be severe, got {data['drift_severity']}"
        )


# ── Monitoring instrumentation ──────────────────────────────────────────────────

def test_monitoring_instrumentation_attaches_to_fastapi():
    """instrument_app() should add /metrics route without raising."""
    from fastapi import FastAPI
    from src.monitoring.instrumentation import instrument_app

    app = FastAPI()
    instrument_app(app)

    routes = [r.path for r in app.routes]
    assert "/metrics" in routes, "/metrics endpoint must be registered after instrument_app()"


def test_record_inference_does_not_crash():
    """record_inference() should accept valid inputs without raising."""
    from src.monitoring.instrumentation import record_inference

    record_inference(
        prompt="What is machine learning?",
        latency_s=0.12,
        tokens_generated=30,
        cached=False,
        batch_size=4,
    )
