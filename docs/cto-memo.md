# Memorandum: AI Governance and Risk Assessment Findings

**To:** Chief Technology Officer  
**From:** Om Jagtap, MLOps Engineering  
**Date:** April 26, 2026  
**Subject:** GPT-2 LLM Inference Server — Governance Review and Action Plan  
**Classification:** Internal — Engineering Leadership

---

## Purpose

This memo summarizes the findings of a comprehensive governance and risk review of the GPT-2 LLM Inference Server currently operating in our environment. The review covers operational safety, data compliance, risk classification, and recommended actions.

---

## What We Built and Why It Matters

The GPT-2 LLM Inference Server (first deployed as Milestone 5) is a text generation API serving the 124-million-parameter GPT-2 model via FastAPI. It processes approximately 14–18 requests per second under current load and incorporates two key optimizations: dynamic request batching (reducing per-request compute overhead) and SHA-256-keyed LRU caching (achieving 68% cache hit rate in the optimized configuration).

This system is currently used for educational demonstrations and infrastructure benchmarking. Its architecture directly mirrors the patterns used in production LLM deployments at scale.

---

## Key Findings

### 1. The system is operationally sound, with two yellow-zone signals

Our Prometheus/Grafana monitoring dashboard (Component 1) shows:
- **P95 latency: 210 ms** — well within the 500 ms SLO, but 59% of margin is consumed at current load. A 2× traffic increase without horizontal scaling would breach the SLO.
- **Error rate: 0.9%** — 10% below the 1% alert threshold. A traffic spike of ~50% would likely trigger alert conditions due to batcher queue saturation.

**Recommended action:** Add HTTP 429 back-pressure to the batcher and deploy the Redis cache backend to support horizontal scaling before traffic increases.

### 2. Data drift is already measurable and will accelerate

Drift analysis (Component 4) across four production windows reveals that prompt length and vocabulary richness are both shifting significantly by Week 2. By Week 4, all features show severe drift (PSI > 0.25), with estimated model accuracy degradation of 13–18%.

The monitoring dashboard includes a real-time vocabulary novelty signal that triggers at 15% — this provides 1–2 weeks of advance warning before drift reaches critical levels.

**Recommended action:** Activate the vocabulary novelty alert today. Schedule monthly PSI analysis runs and define a retraining trigger (PSI > 0.25 sustained for 2 weeks).

### 3. Five critical risks require immediate mitigation plans

Our risk assessment (Component 5) identified five risks rated Critical (score ≥ 15):

| Risk | Score | Required Action | Timeline |
|---|---|---|---|
| Silent distribution drift (R-06) | 20 | Activate drift alerts + PSI cron job | **Immediate** |
| Bias/toxic content (R-01) | 16 | Integrate Detoxify classifier | 2 weeks |
| Knowledge cutoff misinformation (R-03) | 15 | Add knowledge-cutoff disclaimer middleware | 1 week |
| PII exposure in prompts (R-09) | 15 | Integrate Presidio PII detector | 2 weeks |
| Medical/legal advice generation (R-11) | 15 | Add topic classifier + statutory disclaimer | 2 weeks |

All five mitigations are software changes to the existing FastAPI middleware stack — no infrastructure changes required.

### 4. The A/B test validates the optimized configuration

A statistically rigorous experiment (Component 2, n=1 500/arm) comparing the baseline server configuration against an optimized one found that the optimized configuration (longer batch timeout, larger batch size, 2× cache TTL) delivers:
- **17.7% P95 latency reduction** (255 ms → 210 ms)
- **30.8% increase in cache hit rate** (52% → 68%)
- **25% reduction in error rate** (1.2% → 0.9%)

These results are statistically significant (p < 0.0001, Cohen's d = 0.44). **The optimized configuration has been deployed as v1.1.0.**

### 5. Compliance posture is adequate for current scope, fragile for expansion

For the current use case (educational demonstrations, internal benchmarking):
- No HIPAA obligations (medical use explicitly blocked)
- GDPR compliance: cache TTL=600 s satisfies right-to-erasure with 10-minute lag; no PII stored in cache
- CCPA: no user-facing data collection; privacy policy not required for internal use

**Risk:** If the system scope expands to external users or consequential decisions, five compliance gaps become critical: PII detection, GDPR data residency, bias audit, statutory disclaimers, and model version pinning.

---

## Recommended Action Items (Priority Order)

1. **[Immediate]** Activate Prometheus alert: vocabulary novelty > 15% → PagerDuty notification
2. **[1 week]** Deploy knowledge-cutoff disclaimer middleware
3. **[2 weeks]** Integrate Detoxify output classifier and Presidio PII detector
4. **[2 weeks]** Add HTTP 429 back-pressure to DynamicBatcher; set `max_queue_depth=50`
5. **[1 month]** Pin GPT-2 model revision SHA; verify at startup; log in audit trail
6. **[1 month]** Deploy Redis cache backend to support horizontal scaling
7. **[Quarterly]** Run PSI drift analysis; evaluate retraining need; update model card

---

## Conclusion

The GPT-2 Inference Server is a well-instrumented, operationally stable system for its current scope. The governance and monitoring framework built in this project provides the observability and accountability needed to operate AI systems responsibly. The five critical risks are all addressable through middleware additions with no model changes required.

I recommend approving the five immediate action items listed above and scheduling a follow-up governance review in 90 days.

---

*Om Jagtap  
MLOps Engineering | IDS 568 Final Project*
