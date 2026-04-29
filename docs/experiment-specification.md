# A/B Experiment Specification — GPT-2 Inference Server Configuration Optimization

**Component 2 | IDS 568 Final Project**

---

## 1. Hypothesis

**Null hypothesis (H₀):** There is no difference in P95 request latency between the baseline server configuration (Model A) and the optimized configuration (Model B).

**Alternative hypothesis (H₁):** The optimized configuration (Model B — extended batch timeout + larger batch size + longer cache TTL) reduces P95 latency by at least 10% compared to baseline.

**Rationale:** Milestone 5 benchmark results showed that increasing `batch_timeout_ms` from 50 ms to 100 ms allows the batcher to accumulate larger batches, improving GPU utilization and reducing per-request model latency on cache-miss paths. Simultaneously, doubling the cache TTL (300 s → 600 s) and maximum batch size (8 → 16) should increase cache hit rate and throughput. This experiment formalizes those observations into a statistically rigorous comparison.

---

## 2. Configuration Definitions

| Parameter | Model A (Control) | Model B (Treatment) |
|---|---|---|
| `LLM_BATCH_TIMEOUT_MS` | 50 ms | 100 ms |
| `LLM_MAX_BATCH_SIZE` | 8 | 16 |
| `LLM_CACHE_TTL_SECONDS` | 300 s | 600 s |
| `LLM_CACHE_MAX_ENTRIES` | 1 000 | 1 000 |
| `LLM_MODEL_NAME` | `gpt2` | `gpt2` |
| Deployment environment | CPU, single process | CPU, single process |

---

## 3. Success Metrics

### Primary metric
- **P95 request latency (ms)** — the 95th percentile of end-to-end request latency. Target: ≥ 10% reduction in Model B vs. Model A.

### Secondary metrics
| Metric | Direction | Guardrail |
|---|---|---|
| Cache hit rate | Higher is better | Must not decrease in Model B |
| Throughput (req/s) | Higher is better | Must not decrease by > 5% |
| Error rate | Lower is better | Must remain < 2% in both arms |
| P99 latency | Lower is better | Monitor for regression |

### Guardrail metrics
- **Error rate** must stay below 2%. If Model B's error rate exceeds Model A's by > 0.5%, the experiment must be stopped.
- **Response quality proxy** (response length): if mean response length drops by > 15%, it may indicate the model is returning truncated outputs due to batch overflow — experiment must be paused.

---

## 4. Randomization Method

**Unit of randomization:** Individual HTTP request, assigned to arm using a deterministic hash of `(request_id % 2)`.

**Rationale for request-level randomization:** Since the GPT-2 server is stateless (no user session), randomizing at the request level is appropriate and simpler than user-level randomization. Cache state is arm-specific — each arm maintains its own cache instance — preventing cross-contamination.

**Traffic split:** 50 / 50 (equal allocation, optimal statistical power for detecting symmetric effect sizes).

**Novelty effect control:** The first 10% of each arm's traffic is discarded as warm-up to allow the cache to reach steady-state hit rates.

---

## 5. Sample Size Justification (Power Analysis)

**Statistical test:** Two-sample Welch t-test (unequal variance, non-parametric robustness confirmed via Mann-Whitney U).

**Parameters:**
- **Minimum Detectable Effect (MDE):** 10% reduction in P95 latency from baseline (~255 ms → ~230 ms), corresponding to an absolute difference of ~25 ms.
- **Baseline P95 latency:** 255 ms (from Milestone 5 benchmarks, `mixed` scenario)
- **Estimated standard deviation:** ~95 ms (estimated from M5 latency distribution; heavy right tail)
- **Standardized effect size (Cohen's d):** |Δμ| / σ = 25 / 95 ≈ 0.26 (small-to-medium)
- **Significance level (α):** 0.05 (two-tailed)
- **Statistical power (1-β):** 0.80

**Formula (two-sample t-test):**

n ≈ 2 × (z_{α/2} + z_β)² × σ² / δ²

Where z_{0.025} = 1.96, z_{0.20} = 0.84, σ = 95 ms, δ = 25 ms:

n ≈ 2 × (1.96 + 0.84)² × 95² / 25² ≈ 2 × 7.84 × 9025 / 625 ≈ **226 requests per arm**

**Safety margin (3× for non-normality and multiple metrics):** 226 × 3 = **678 requests per arm minimum**.

**Selected sample size:** **1 500 requests per arm** (≈ 6.6× the minimum). This provides > 99% power to detect the 10% MDE and accommodates multiple secondary metric comparisons without requiring Bonferroni correction (conservative family-wise error rate).

**Estimated duration:** At 14 req/s throughput with 50% arm split, 1 500 requests per arm accumulates in ~214 seconds (~3.6 minutes) of synthetic load. For production deployment with real-user traffic (~200 daily active users), this corresponds to approximately **7.5 hours** of runtime.

---

## 6. Statistical Analysis Plan

**Primary decision metric: P95 latency reduction**

1. **Primary analysis:** 95% bootstrap CI on the P95 latency difference A − B (5 000 resamples). If the entire CI is positive (i.e., A's P95 > B's P95 at both bounds) and the P95 improvement probability ≥ 95%, the primary criterion is met.
2. **Supporting analysis — mean latency:** Two-sample Welch t-test on mean latency (handles unequal variances). Provides a conventional p-value as corroborating evidence; it is *not* the primary decision driver because P95 (not mean) is the user-facing SLO metric.
3. **Non-parametric validation:** Mann-Whitney U test (robust to heavy-tailed latency distributions).
4. **Effect size:** Cohen's d on mean latency (|d| > 0.2 = practical significance threshold for mean shift).
5. **Mean bootstrap CI:** 95% bootstrap CI on the mean difference A − B (5 000 resamples).
6. **Multiple comparison correction:** Benjamini-Hochberg procedure applied to the 4 secondary metrics.

**Decision rule:**
- If P95 bootstrap CI entirely positive AND P95 improvement probability ≥ 95% AND all guardrails pass: **Ship Model B**
- If Welch p < 0.05 AND |d| ≤ 0.2 but P95 criterion not met: **Ship Model B with caveat** (mean benefit detectable but P95 improvement unconfirmed)
- If neither criterion met: **Run more data** (or stop if practical significance is clearly unachievable)

---

## 7. Execution Timeline

| Phase | Duration | Action |
|---|---|---|
| Warm-up | 10% of samples | Discard; allow cache to reach steady state |
| Data collection | Until n=1 500/arm | Monitor guardrails every 100 requests |
| Analysis | After collection | Run `src/ab_test/simulation.py` |
| Decision | Within 24h of analysis | Publish recommendation memo |
