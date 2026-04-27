# Risk Matrix — GPT-2 LLM Inference Server

**Component 5 | IDS 568 Final Project**

Likelihood scale: 1 (Rare) → 5 (Almost Certain)  
Severity scale: 1 (Negligible) → 5 (Critical)  
Risk Score = Likelihood × Severity

---

## Risk Matrix (Likelihood × Severity)

|  | **Sev 1 Negligible** | **Sev 2 Low** | **Sev 3 Medium** | **Sev 4 High** | **Sev 5 Critical** |
|---|---|---|---|---|---|
| **Like 5 (Almost Certain)** | — | — | R-03: Knowledge cutoff bias | R-06: Silent drift | — |
| **Like 4 (Likely)** | — | — | R-02: Non-English quality | R-01: Bias/toxicity | — |
| **Like 3 (Possible)** | — | R-10: Retention policy | — | R-04: Prompt injection; R-07: Batcher saturation; R-08: Prompt logging | R-09: PII exposure; R-11: Medical/legal advice |
| **Like 2 (Unlikely)** | — | — | — | R-05: Cache poisoning; R-12: Weight version drift | — |
| **Like 1 (Rare)** | — | — | — | — | — |

**Color coding:** Score ≥ 15 = Critical (red) | 8–14 = High (orange) | 4–7 = Medium (yellow) | < 4 = Low (green)

---

## Detailed Risk Entries with Mitigations

| ID | Risk | Likelihood | Severity | Score | Zone | Mitigation | Residual Risk |
|---|---|---|---|---|---|---|---|
| R-01 | Bias and toxic content generation | 4 | 4 | **16** | Critical | (1) Detoxify post-generation classifier; (2) Log flagged outputs; (3) Scope to non-opinion use cases | 8 (Medium) after mitigation |
| R-02 | Disparate quality for non-English speakers | 4 | 3 | **12** | High | (1) Language detection (langdetect); (2) HTTP 422 with language warning; (3) Document limitation | 6 (Medium) |
| R-03 | Knowledge cutoff (2019) causes systematic misinformation | 5 | 3 | **15** | Critical | (1) Date-sensitive keyword detection; (2) Automatic knowledge-cutoff disclaimer prepended to output | 10 (High) |
| R-04 | Prompt injection alters model behavior | 3 | 4 | **12** | High | (1) Regex pattern filter for injection keywords; (2) Log injection attempts; (3) Rate-limit suspicious IPs | 6 (Medium) |
| R-05 | Cache poisoning serves harmful cached content | 2 | 4 | **8** | High | (1) SHA-256 keys prevent key manipulation; (2) Output classifier before caching; (3) Admin flush available | 4 (Low) |
| R-06 | Silent distribution drift degrades accuracy without alert | 5 | 4 | **20** | Critical | (1) Vocabulary novelty Prometheus alert (>15%); (2) Weekly PSI cron job; (3) Retraining trigger at PSI>0.25 | 8 (Medium) |
| R-07 | Batcher queue saturation → cascading 503 errors | 3 | 4 | **12** | High | (1) `max_queue_depth` + HTTP 429 back-pressure; (2) Circuit breaker; (3) Horizontal scaling | 4 (Low) |
| R-08 | DEBUG logs expose prompt content | 3 | 4 | **12** | High | (1) Enforce `LOG_LEVEL=INFO` in prod; (2) Truncate prompts in logs to 20 chars | 3 (Low) — mitigated |
| R-09 | PII exposure in prompts and logs | 3 | 5 | **15** | Critical | (1) Presidio PII detector in middleware; (2) Reject/redact PII prompts; (3) API terms of service | 6 (Medium) |
| R-10 | No explicit data retention policy | 3 | 3 | **9** | High | (1) TTL=600s auto-eviction; (2) Admin flush for emergency; (3) Document policy | 3 (Low) — mitigated |
| R-11 | Medical/legal/financial advice generation | 3 | 5 | **15** | Critical | (1) Topic classifier (50 seed terms); (2) Statutory disclaimer prepended; (3) Block in regulated contexts | 6 (Medium) |
| R-12 | Silent model weight update from HuggingFace | 2 | 4 | **8** | High | (1) Pin revision SHA in `from_pretrained()`; (2) Log model fingerprint at startup; (3) Audit trail records version | 2 (Low) |

---

## Residual Risk Summary

After all proposed mitigations are implemented:

| Risk Zone | Count (current) | Count (residual) |
|---|---|---|
| Critical (≥ 15) | 5 | 0 |
| High (8–14) | 5 | 3 |
| Medium (4–7) | 2 | 6 |
| Low (< 4) | 0 | 3 |

The most significant residual risks (High) are:
- **R-03** (Knowledge cutoff): Inherent limitation of the model architecture — cannot be fully mitigated without RAG or retraining.
- **R-06** (Silent drift): Monitoring and alerting reduce severity, but automated retraining is not yet implemented.
- **R-01** (Bias): Classifier reduces but does not eliminate biased outputs — requires ongoing human review.
