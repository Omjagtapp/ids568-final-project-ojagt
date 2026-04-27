# Dashboard Interpretation — GPT-2 LLM Inference Server

**Component 1 | IDS 568 Final Project**

---

## System Overview

The Grafana dashboard (see `dashboards/grafana-export.json` and `screenshots/dashboard-overview.png`) monitors the GPT-2 LLM Inference Server built in Milestone 5. The server is a FastAPI application combining dynamic request batching and SHA-256-keyed LRU caching, serving GPT-2 (124M parameter) via HuggingFace Transformers.

Dashboard datasource: Prometheus scraping `/metrics` at `localhost:8000/metrics` every 10 seconds.

---

## Panel-by-Panel Interpretation

### 1. Request Latency — P50 / P95 / P99 (ms)

**What it shows:** End-to-end request latency split across three quantiles, giving a complete picture of the tail distribution.

**Healthy range:**
- P50: 20–50 ms (cache hits dominate)
- P95: 150–300 ms (mix of hits and batched inferences)
- P99: < 500 ms (hard SLO boundary)

**What the dashboard reveals:** Under simulated 300-request traffic, P50 hovers at ~25 ms (cache hits) while P95 sits at ~255 ms. The separation between P50 and P95 — approximately 10× — is the signature of a bimodal latency distribution: fast cache hits vs. slower batched model inferences. This bimodality is expected and healthy.

**Bottleneck signal:** When P95 approaches 400 ms, the batcher's `timeout_ms` trigger is firing before the batch fills, meaning arrival rate has dropped below the batch efficiency threshold. P99 > 500 ms signals an SLO breach.

**Diagnostic reasoning:** The gap between P95 (~255 ms) and P99 (~279 ms) is narrow (24 ms), indicating a sharp tail cutoff — this confirms that extreme latency outliers are rare and the system is not experiencing pathological queueing.

---

### 2. P95 Latency Stat Panel (SLO: 500 ms)

**What it shows:** Single-value gauge with red/yellow/green thresholds.

**Healthy range:** Green < 200 ms, yellow 200–500 ms, red > 500 ms.

**Current value:** ~255 ms (yellow). This is acceptable for a GPT-2 CPU-based inference server but leaves a 245 ms margin before SLO breach — insufficient headroom for a traffic spike.

**Action:** Deploy to GPU hardware or increase `LLM_MAX_BATCH_SIZE` to 16 to improve batch efficiency and reduce miss-path latency.

---

### 3. Throughput (req/s)

**What it shows:** Request rate across all endpoints, instantaneous and rolling 1-minute average.

**Healthy range:** > 10 req/s under nominal load; should scale linearly with concurrency up to the batcher's throughput ceiling.

**Observed:** ~14 req/s under 10-concurrent-user synthetic load. This is consistent with Milestone 5 benchmark results showing 14.2 req/s for the `mixed` scenario.

**Bottleneck:** Throughput is CPU-bound (GPT-2 inference on CPU). Moving to GPU or ONNX quantization would unlock 5–20× throughput improvement.

---

### 4. Cache Hit Rate

**What it shows:** Rolling 2-minute ratio of cache hits to total requests.

**Healthy range:** > 50% under production traffic patterns with repeated query workloads. Below 30% means the cache provides minimal latency benefit and should be evaluated for correctness.

**Observed:** ~52% with the default TTL (300 s). This aligns with the Milestone 5 `mixed` benchmark scenario. The Model B configuration (TTL = 600 s, Component 2 A/B test) raises this to ~68%.

**Drift correlation:** A sustained *drop* in cache hit rate — without a corresponding increase in unique user count — indicates vocabulary or topic drift: users are querying about new subjects the cache has never seen. This is a leading drift indicator (see Component 4).

---

### 5. Error Rate (alert > 1%)

**What it shows:** Fraction of requests returning HTTP 5xx or timing out, as a percentage of total traffic.

**Healthy range:** < 0.5% under normal conditions. Values above 1% trigger an alert.

**Observed:** ~0.8–1.2% under synthetic load. Errors are predominantly `http_503` from the batcher when the queue exceeds capacity during traffic bursts.

**Bottleneck identified:** The batcher queue has no back-pressure mechanism; under sudden load spikes, requests that time out before a batch flushes will fail. The fix is to add a circuit breaker or queue depth limit with graceful HTTP 429 responses instead of 503.

---

### 6. Active In-Flight Requests (Gauge)

**What it shows:** Gauge of requests currently inside the FastAPI middleware, bounded [0, 12+].

**Healthy range:** 0–5 at steady state; spikes to 8–12 during batching windows.

**Observed:** Oscillates between 2 and 9 with the 10-concurrent-user load, reflecting the 50 ms batcher timeout cycle. Values above 12 indicate queue saturation — the system is taking on more work than it can complete within SLO.

---

### 7. Vocabulary Novelty Rate — Drift Signal (alert > 15%)

**What it shows:** Fraction of unique tokens in recent prompts that were never seen in the reference vocabulary window (first 500 unique tokens).

**Why it matters:** A rising novelty rate means users are querying about topics outside the model's primary training distribution — a leading indicator of accuracy degradation and hallucination increase.

**Healthy range:** < 10% for stable production traffic. 10–15% warrants investigation. > 15% triggers an alert.

**Observed:** ~5–7% under normal English-language prompts. In drift simulation experiments (Component 4), multilingual and technical-domain prompts push this to 18–35%.

---

### 8. Input Prompt Length Distribution

**What it shows:** P50 and P95 of input prompt length in characters, using a histogram quantile.

**Healthy range:** P50 ≈ 85 chars (reference baseline), P95 ≈ 220 chars.

**Drift signal:** When P95 prompt length climbs above 400 chars, it signals a domain shift toward longer technical or code-generation queries — which carry higher batch latency and greater hallucination risk.

---

## System Health Summary

| Metric | Current | Healthy Threshold | Status |
|---|---|---|---|
| P95 Latency | ~255 ms | < 500 ms | YELLOW |
| P99 Latency | ~279 ms | < 500 ms | GREEN |
| Throughput | ~14 req/s | > 10 req/s | GREEN |
| Error Rate | ~0.9% | < 1% | YELLOW |
| Cache Hit Rate | ~52% | > 50% | GREEN |
| Active Requests | 2–9 | < 12 | GREEN |
| Vocab Novelty | ~6% | < 15% | GREEN |

**Overall assessment:** The system is healthy under current load. Two yellow signals warrant attention:
1. P95 latency at 255 ms leaves only 245 ms margin before SLO breach — acceptable today but not after a 2× traffic increase.
2. Error rate at 0.9% is dangerously close to the 1% alert threshold — the batcher needs back-pressure.

---

## Identified Bottlenecks and Risks

### Bottleneck 1: CPU-bound inference
GPT-2 on CPU yields ~180–220 ms per cache-miss request. Migrating to GPU would reduce this to ~15–30 ms, collapsing P95 to ~50 ms.

### Bottleneck 2: No batcher back-pressure
Under sudden load spikes (>20 req/s), the batcher queue overflows and requests fail with HTTP 503. Adding a `max_queue_depth` parameter and returning HTTP 429 (Too Many Requests) would improve resilience.

### Bottleneck 3: In-process cache limits horizontal scaling
The `InProcessCache` is local to each process. Horizontal scaling (multiple replicas) creates cache fragmentation and lowers effective hit rate. Migrating to the Redis backend resolves this.

### Risk: Silent accuracy degradation via vocabulary drift
A rising novelty rate indicates domain shift, but the system has no mechanism to automatically flag individual responses as low-confidence. Adding a perplexity-based confidence score to the API response would enable downstream filtering.

---

## Alert Conditions for Production

```yaml
# Prometheus alerting rules (reference for alertmanager)
groups:
  - name: llm_inference_alerts
    rules:
      - alert: HighP95Latency
        expr: histogram_quantile(0.95, sum(rate(llm_request_latency_seconds_bucket[5m])) by (le)) > 0.5
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "P95 latency exceeds 500ms SLO"
          runbook: "Scale horizontally or increase batch size"

      - alert: HighErrorRate
        expr: rate(llm_errors_total[5m]) / (rate(llm_requests_total[5m]) + 1e-9) > 0.01
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Error rate exceeds 1% — check batcher queue depth"

      - alert: LowCacheHitRate
        expr: rate(llm_cache_operations_total{result="hit"}[10m]) / (rate(llm_cache_operations_total[10m]) + 1e-9) < 0.3
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Cache hit rate dropped below 30% — possible drift or cache invalidation"

      - alert: VocabDriftDetected
        expr: llm_vocab_novelty_rate > 0.15
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Vocabulary novelty rate > 15% — possible input distribution drift"
```

---

## Design Justification

**Why Prometheus + Grafana over OpenTelemetry?**  
The Milestone 5 server uses FastAPI with a custom `/metrics` endpoint — Prometheus pull-model requires zero SDK code changes in the serving path, while OpenTelemetry push-model would require modifying the lifespan hook. Prometheus also has native Grafana integration and mature Python client libraries (`prometheus_client`).

**Why histogram metrics instead of gauges for latency?**  
Gauges only show instantaneous values. Histograms enable quantile calculation over rolling windows, which is the correct way to reason about SLOs. The bucket boundaries (5 ms – 10 s) cover both sub-millisecond cache hits and worst-case cold-start inference.

**Why vocabulary novelty as a drift signal?**  
Embedding-based drift (e.g., cosine distance of BERT embeddings) is more accurate but requires a second model inference per request, doubling latency. Vocabulary novelty is a lightweight O(n) proxy that can run synchronously in the metric middleware without impacting the serving path.
