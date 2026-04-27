# Risk Register — GPT-2 LLM Inference Server

**Component 3 | IDS 568 Final Project**  
**Framework:** NIST AI Risk Management Framework (AI RMF 1.0)  
**Last reviewed:** April 26, 2026

---

## Risk Register Table

| ID | Category | Risk Description | Likelihood (1–5) | Severity (1–5) | Risk Score | Mitigation Strategy | Owner | Status |
|---|---|---|---|---|---|---|---|---|
| R-01 | Bias | GPT-2 generates gender/racial stereotypes in open-ended prompts due to Reddit training bias | 4 | 4 | 16 | (1) Add output classifier (Perspective API or Detoxify); (2) Log flagged outputs; (3) Restrict use to factual Q&A, not opinion generation | Om Jagtap | Open |
| R-02 | Bias | Non-English speakers receive significantly degraded output quality, creating disparate impact | 4 | 3 | 12 | (1) Detect input language (langdetect library); (2) Return HTTP 422 with language warning for non-English input; (3) Document limitation in API docs | Om Jagtap | Open |
| R-03 | Bias | Knowledge cutoff (2019) creates systematic accuracy gap for users querying recent events | 5 | 3 | 15 | (1) Prepend "Note: knowledge limited to 2019" disclaimer to all outputs; (2) Log queries with date-sensitive keywords; (3) Consider RAG extension (Milestone 6 architecture) | Om Jagtap | Open |
| R-04 | Robustness | Prompt injection attacks alter model behavior (e.g., "Ignore above instructions and...") | 3 | 4 | 12 | (1) Add input sanitizer that detects common injection patterns (regex); (2) Log injection attempts; (3) Rate-limit IPs with high injection frequency | Om Jagtap | Open |
| R-05 | Robustness | Cache poisoning: malicious prompt engineered to produce cached harmful content served to all users | 2 | 5 | 10 | (1) SHA-256 keys prevent key manipulation; (2) Add output classifier before caching; (3) Admin flush endpoint (`DELETE /v1/cache`) available for emergency eviction | Om Jagtap | Open |
| R-06 | Robustness | Distribution drift (domain shift) silently degrades accuracy without triggering any alert | 4 | 4 | 16 | (1) Vocabulary novelty Prometheus alert at >15% (Component 1); (2) PSI monitoring (Component 4) with automated weekly drift report; (3) Retraining trigger when PSI > 0.2 on any feature | Om Jagtap | Open |
| R-07 | Robustness | DynamicBatcher queue saturation under traffic spikes causes HTTP 503 cascading failure | 3 | 4 | 12 | (1) Add `max_queue_depth` parameter with HTTP 429 back-pressure; (2) Circuit breaker pattern; (3) Horizontal scaling with Redis cache backend | Om Jagtap | Open |
| R-08 | Privacy | Prompt content logged at DEBUG level exposes user queries in log files | 3 | 4 | 12 | (1) Set log level to INFO in production (suppresses DEBUG); (2) Truncate prompts in logs to first 20 characters; (3) Cache keys are SHA-256 (no plaintext in cache storage) | Om Jagtap | Mitigated |
| R-09 | Privacy | User prompts may contain PII (names, emails, medical info) submitted inadvertently | 3 | 5 | 15 | (1) Add PII detector (Presidio) to input validation middleware; (2) Reject or redact prompts with detected PII; (3) Document no-PII policy in API terms of service | Om Jagtap | Open |
| R-10 | Compliance | No data retention policy: cached prompt hashes stored indefinitely in Redis | 3 | 3 | 9 | (1) TTL=600s on all cache entries limits retention automatically; (2) Cache flush available via admin endpoint; (3) Document retention policy in governance review | Om Jagtap | Mitigated |
| R-11 | Compliance | Model generates medical/legal/financial advice that users may act on | 3 | 5 | 15 | (1) Add topic classifier to detect medical/legal/financial queries; (2) Prepend statutory disclaimer to responses in these categories; (3) Block and log such queries if operating in regulated context | Om Jagtap | Open |
| R-12 | Compliance | No model versioning enforcement: production could silently receive updated HuggingFace weights | 2 | 4 | 8 | (1) Pin model version with `revision` parameter in `from_pretrained()`; (2) Log model SHA256 fingerprint at startup; (3) Audit trail records model version at each deployment | Om Jagtap | Open |

---

## Risk Score Matrix

```
Severity →  1       2       3       4       5
           ─────────────────────────────────────
Likelihood
5       │    5      10      15      20      25
4       │    4       8      12      16      20  ← R-01, R-06
3       │    3       6       9      12      15  ← R-04, R-07, R-08, R-09, R-11
2       │    2       4       6       8      10  ← R-05, R-12
1       │    1       2       3       4       5
```

**High risk (≥ 15):** R-01 (16), R-06 (16), R-03 (15), R-09 (15), R-11 (15) — require immediate mitigation plan  
**Medium risk (8–14):** R-02, R-04, R-05, R-07, R-08, R-10, R-12  
**Low risk (< 8):** None currently identified

---

## Top Priority Mitigations (Ordered by Risk Score)

### Priority 1: R-01 — Bias in generated content (Score: 16)
**Concrete action:** Integrate `detoxify` library as a post-generation filter. Any response with toxicity score > 0.7 is redacted and logged. Implementation: 2 days.

### Priority 2: R-06 — Silent drift (Score: 16)
**Concrete action:** Vocabulary novelty Prometheus alert is already implemented (Component 1). PSI weekly cron job (Component 4) emails drift report to the team. Retraining trigger: if any feature PSI > 0.25 for 2 consecutive weeks, open a GitHub issue.

### Priority 3: R-09 — PII in prompts (Score: 15)
**Concrete action:** Add `presidio-analyzer` to the FastAPI request middleware. Requests with detected PII entities (PERSON, EMAIL, PHONE, MEDICAL) are rejected with HTTP 422 and logged (without the PII content).

### Priority 4: R-03 — Knowledge cutoff bias (Score: 15)
**Concrete action:** Parse prompt for date-sensitive keywords ("2020", "2021", "2022", "2023", "2024", "2025", "recent", "current", "latest"). Prepend disclaimer: "Note: GPT-2 knowledge is limited to events before 2020."

### Priority 5: R-11 — Medical/legal/financial advice (Score: 15)
**Concrete action:** Keyword-based topic classifier with 50 seed terms per category. Matching requests receive a statutory disclaimer prepended to the response.
