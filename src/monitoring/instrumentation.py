"""
Production monitoring instrumentation for the GPT-2 LLM Inference Server.

Wraps the FastAPI application (Milestone 5) with Prometheus metrics covering:
  - Request latency (histogram, p50/p95/p99 SLOs)
  - Request throughput (counter)
  - Error rate (counter by status code)
  - Cache hit / miss (counter)
  - Active in-flight requests (gauge)
  - Token throughput (tokens per second)
  - Input prompt length distribution (histogram)
  - Model drift signal: vocabulary novelty rate (gauge)

Usage:
  from src.monitoring.instrumentation import instrument_app, generate_traffic
  instrument_app(app)          # wrap an existing FastAPI instance
  generate_traffic(n=500)      # send synthetic load for dashboard population
"""

from __future__ import annotations

import hashlib
import random
import time
from typing import Callable

import httpx
from fastapi import FastAPI, Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    CollectorRegistry,
    REGISTRY,
)

# ── Metric definitions ─────────────────────────────────────────────────────────

REQUEST_LATENCY = Histogram(
    "llm_request_latency_seconds",
    "End-to-end request latency in seconds",
    ["endpoint", "cached"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

REQUEST_TOTAL = Counter(
    "llm_requests_total",
    "Total number of requests received",
    ["endpoint", "status_code"],
)

CACHE_OPS = Counter(
    "llm_cache_operations_total",
    "Cache hit / miss events",
    ["result"],  # hit | miss
)

ACTIVE_REQUESTS = Gauge(
    "llm_active_requests",
    "Number of requests currently being processed",
)

TOKEN_THROUGHPUT = Counter(
    "llm_tokens_generated_total",
    "Total tokens generated across all requests",
)

INPUT_LENGTH = Histogram(
    "llm_input_prompt_length_chars",
    "Distribution of input prompt lengths in characters",
    buckets=[10, 25, 50, 100, 200, 400, 800, 1600],
)

VOCAB_NOVELTY = Gauge(
    "llm_vocab_novelty_rate",
    "Fraction of prompt tokens not seen in reference window (drift signal)",
)

BATCH_SIZE = Histogram(
    "llm_batch_size",
    "Number of requests processed in each inference batch",
    buckets=[1, 2, 4, 8, 16],
)

ERROR_TOTAL = Counter(
    "llm_errors_total",
    "Total number of request errors",
    ["error_type"],
)

# ── Reference vocabulary (simulated baseline) ─────────────────────────────────

_REFERENCE_VOCAB: set[str] = set()
_SEEN_WINDOW: list[str] = []
_WINDOW_SIZE = 200


def _update_vocab_novelty(prompt: str) -> None:
    global _REFERENCE_VOCAB, _SEEN_WINDOW
    tokens = prompt.lower().split()
    if len(_REFERENCE_VOCAB) < 500:
        _REFERENCE_VOCAB.update(tokens)
        return
    novel = sum(1 for t in tokens if t not in _REFERENCE_VOCAB)
    novelty_rate = novel / max(len(tokens), 1)
    VOCAB_NOVELTY.set(novelty_rate)
    _SEEN_WINDOW.extend(tokens)
    if len(_SEEN_WINDOW) > _WINDOW_SIZE:
        _SEEN_WINDOW = _SEEN_WINDOW[-_WINDOW_SIZE:]


# ── FastAPI middleware ─────────────────────────────────────────────────────────

def instrument_app(app: FastAPI) -> None:
    """Attach Prometheus middleware and /metrics endpoint to an existing FastAPI app."""

    @app.middleware("http")
    async def prometheus_middleware(request: Request, call_next: Callable) -> Response:
        endpoint = request.url.path
        ACTIVE_REQUESTS.inc()
        t0 = time.perf_counter()
        status_code = 500
        cached_label = "unknown"
        try:
            response = await call_next(request)
            status_code = response.status_code
            cached_label = response.headers.get("X-Cache", "unknown")
            return response
        except Exception as exc:
            ERROR_TOTAL.labels(error_type=type(exc).__name__).inc()
            raise
        finally:
            elapsed = time.perf_counter() - t0
            REQUEST_LATENCY.labels(endpoint=endpoint, cached=cached_label).observe(elapsed)
            REQUEST_TOTAL.labels(endpoint=endpoint, status_code=str(status_code)).inc()
            ACTIVE_REQUESTS.dec()

    @app.get("/metrics", tags=["ops"], include_in_schema=False)
    async def prometheus_metrics() -> Response:
        data = generate_latest(REGISTRY)
        return Response(content=data, media_type=CONTENT_TYPE_LATEST)


# ── Standalone metric emission helpers ────────────────────────────────────────

def record_inference(
    prompt: str,
    latency_s: float,
    tokens_generated: int,
    cached: bool,
    batch_size: int = 1,
) -> None:
    """Call this from within the inference path to record fine-grained metrics."""
    label = "hit" if cached else "miss"
    CACHE_OPS.labels(result=label).inc()
    TOKEN_THROUGHPUT.inc(tokens_generated)
    INPUT_LENGTH.observe(len(prompt))
    BATCH_SIZE.observe(batch_size)
    _update_vocab_novelty(prompt)


# ── Synthetic traffic generator (for dashboard population) ────────────────────

_PROMPTS = [
    "Explain the water cycle in simple terms.",
    "What is machine learning?",
    "Write a short poem about autumn.",
    "Describe the process of photosynthesis.",
    "What are the main causes of climate change?",
    "Tell me about the history of the internet.",
    "How does a neural network learn?",
    "What is the capital of France?",
    "Explain quantum computing to a five-year-old.",
    "What are the benefits of renewable energy?",
    "Summarize the French Revolution in three sentences.",
    "How do vaccines work?",
    "What is the difference between AI and ML?",
    "Describe a sunset over the ocean.",
    "What is the Pythagorean theorem?",
    "Tell me about black holes.",
    "How does the human immune system work?",
    "What are the main programming paradigms?",
    "Explain gradient descent.",
    "What is the significance of the Turing test?",
]

_DRIFT_PROMPTS = [
    "Calcule l'intégrale de x^2 de 0 à 1.",
    "Beschreibe den Kreislauf des Wassers.",
    "Пожалуйста, объясните машинное обучение.",
    "量子コンピューティングについて説明してください。",
    "What is 量子纠缠 and how does it relate to computing?",
    "Explique la relativité générale en termes simples.",
    "كيف يعمل الذكاء الاصطناعي؟",
]


def generate_traffic(
    base_url: str = "http://localhost:8000",
    n: int = 300,
    drift_fraction: float = 0.0,
    seed: int = 42,
) -> None:
    """
    Send synthetic HTTP traffic to a running inference server.

    Args:
        base_url: Server base URL.
        n: Total number of requests to send.
        drift_fraction: Fraction of requests to use out-of-distribution prompts
                        (simulates data drift for Component 4).
        seed: Random seed for reproducibility.
    """
    random.seed(seed)
    results = {"success": 0, "error": 0, "cache_hit": 0, "cache_miss": 0}
    all_prompts = _PROMPTS.copy()
    if drift_fraction > 0:
        all_prompts += _DRIFT_PROMPTS

    with httpx.Client(base_url=base_url, timeout=30.0) as client:
        for i in range(n):
            use_drift = (random.random() < drift_fraction) and _DRIFT_PROMPTS
            pool = _DRIFT_PROMPTS if use_drift else _PROMPTS
            prompt = random.choice(pool)
            use_cache = random.random() > 0.3  # ~70% hit scenario

            endpoint = "/v1/generate" if use_cache else "/v1/generate/nocache"
            try:
                resp = client.post(endpoint, json={"prompt": prompt, "max_new_tokens": 32})
                if resp.status_code == 200:
                    data = resp.json()
                    results["success"] += 1
                    if data.get("cached"):
                        results["cache_hit"] += 1
                    else:
                        results["cache_miss"] += 1
                    record_inference(
                        prompt=prompt,
                        latency_s=data.get("latency_ms", 0) / 1000,
                        tokens_generated=len(data.get("generated_text", "").split()),
                        cached=data.get("cached", False),
                    )
                else:
                    results["error"] += 1
                    ERROR_TOTAL.labels(error_type=f"http_{resp.status_code}").inc()
            except Exception as exc:
                results["error"] += 1
                ERROR_TOTAL.labels(error_type=type(exc).__name__).inc()

            if (i + 1) % 50 == 0:
                print(f"  [{i+1}/{n}] success={results['success']} "
                      f"hit={results['cache_hit']} miss={results['cache_miss']} "
                      f"error={results['error']}")

    print(f"\nTraffic generation complete: {results}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Send synthetic traffic to the LLM server")
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--n", type=int, default=300)
    parser.add_argument("--drift", type=float, default=0.0,
                        help="Fraction of requests to use drift prompts (0.0-1.0)")
    args = parser.parse_args()
    generate_traffic(base_url=args.url, n=args.n, drift_fraction=args.drift)
