# Recommendation Memo: A/B Test — Ship Model B

**To:** Engineering Lead, IDS 568 Final Project  
**From:** Om Jagtap  
**Date:** April 26, 2026  
**Re:** GPT-2 Inference Server Configuration A/B Test — Ship Decision

---

## Recommendation: Ship Model B (Optimized Configuration)

### Evidence Summary

The A/B experiment ran 1 500 requests per arm under the `mixed` traffic scenario (50% repeated prompts, 50% novel prompts). All statistical and guardrail criteria were met.

| Metric | Model A (Baseline) | Model B (Optimized) | Δ |
|---|---|---|---|
| Mean Latency | 110.0 ms | 70.8 ms | **−35.6% ↓** |
| P95 Latency | 254.7 ms | 209.7 ms | **−17.7% ↓** |
| P99 Latency | 278.9 ms | 235.3 ms | **−15.6% ↓** |
| Cache Hit Rate | 52.0% | 68.0% | **+30.8% ↑** |
| Error Rate | 1.2% | 0.9% | **−25.0% ↓** |

**Statistical significance:** Welch t-test p < 0.0001; Mann-Whitney U p < 0.0001.  
**Effect size:** Cohen's d = 0.44 (medium practical significance, exceeds the d > 0.20 threshold).  
**Bootstrap 95% CI on mean difference (A − B):** [32.8 ms, 45.6 ms] — the entire interval is positive (B is faster), confirming the direction of effect.

### Why These Results Make Physical Sense

The 16-percentage-point increase in cache hit rate (52% → 68%) is directly caused by the 2× longer TTL (300 s → 600 s). With a longer cache lifetime, repeated prompts — which constitute ~50% of the `mixed` workload — are served from memory more frequently, bypassing the 180–220 ms model inference path entirely. This collapses the mean latency from 110 ms to 71 ms and narrows the P95 from 255 ms to 210 ms.

The larger batch size (8 → 16) reduces per-request overhead during the miss path: each model forward pass amortizes the CUDA/CPU initialization cost across more requests. Under CPU inference, this benefit is moderate (~15 ms per request), but it becomes dominant on GPU (where batch efficiency directly maps to throughput).

### Guardrails Assessment

All guardrails passed:
- Error rate: 0.9% in Model B vs. 1.2% in Model A (improved, not worse).
- Response length: mean response length unchanged (both arms: ~42 tokens).
- No arm exhibited cache fragmentation artifacts.

### Action Items

1. **Deploy Model B configuration** (`BATCH_TIMEOUT_MS=100`, `MAX_BATCH_SIZE=16`, `CACHE_TTL=600`) to the production server.
2. **Monitor for 48 hours** post-deployment: watch P95 latency and error rate in Grafana.
3. **Re-run experiment on GPU hardware** once available: the batch size effect will be more pronounced on GPU, and the optimal `BATCH_TIMEOUT_MS` may differ.
4. **Update model card** (Component 3) to reflect the new default configuration.
5. **Log configuration change** in the audit trail (`logs/audit-trail.json`).
