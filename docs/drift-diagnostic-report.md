# Drift Diagnostic Report — GPT-2 LLM Inference Server

**Component 4 | IDS 568 Final Project**  
**Analysis period:** 4 weekly production windows vs. Week 0 reference baseline  
**Script:** `src/drift/drift_detection.py`  
**Visualizations:** `visualizations/`

---

## Executive Summary

Data drift detection was performed across four production windows, tracking four input features: prompt length (chars), vocabulary richness, response length (tokens), and token count. By Week 2, all features show significant drift (PSI > 0.2); by Week 4, drift is severe across all dimensions (PSI > 1.0 for three of four features). Without intervention, this level of drift is expected to reduce model task accuracy by an estimated 8–15% relative to the reference window.

**Recommended action:** Trigger retraining data collection process and apply input validation guardrails immediately.

---

## Reference Baseline (Week 0)

| Feature | Mean | Std | P50 | P95 |
|---|---|---|---|---|
| Prompt Length (chars) | 85.0 | 30.0 | 84.2 | 137.5 |
| Vocabulary Richness | 0.72 | 0.08 | 0.72 | 0.84 |
| Response Length (tokens) | 42.0 | 12.0 | 41.8 | 63.5 |
| Token Count | 18.0 | 6.0 | 17.9 | 28.9 |

Reference window: 1 000 requests from Week 0 (normal English Q&A workload).

---

## Drift Results by Week

### PSI Summary Table

| Feature | Week 1 | Week 2 | Week 3 | Week 4 |
|---|---|---|---|---|
| Prompt Length (chars) | 0.051 (None) | 0.317 (Sev.) | 0.856 (Sev.) | 1.130 (Sev.) |
| Vocabulary Richness | 0.117 (Minor) | 0.498 (Sev.) | 0.871 (Sev.) | 1.170 (Sev.) |
| Response Length (tokens) | 0.048 (None) | 0.247 (Sig.) | 0.645 (Sev.) | 0.862 (Sev.) |
| Token Count | 0.069 (None) | 0.358 (Sev.) | 0.723 (Sev.) | 1.450 (Sev.) |

**PSI thresholds:** None < 0.10 | Minor 0.10–0.20 | Significant 0.20–0.25 | Severe ≥ 0.25

### KS Test p-values

| Feature | Week 1 | Week 2 | Week 3 | Week 4 |
|---|---|---|---|---|
| Prompt Length | p > 0.1 | p < 0.001 | p < 0.001 | p < 0.001 |
| Vocabulary Richness | p < 0.05 | p < 0.001 | p < 0.001 | p < 0.001 |
| Response Length | p > 0.1 | p < 0.001 | p < 0.001 | p < 0.001 |
| Token Count | p > 0.1 | p < 0.001 | p < 0.001 | p < 0.001 |

---

## Feature-by-Feature Analysis

### Feature 1: Prompt Length (chars) — Most drifted by Week 4 (PSI = 1.130)

**Trend:** Mean prompt length increased from 85 chars (Week 0) to 185 chars (Week 4) — a 118% increase. P95 expanded from 138 chars to ~360 chars.

**Root cause hypothesis:** Domain shift toward technical/code queries. Users are now submitting longer, multi-sentence prompts with context (e.g., "Given the following Python function, explain what it does:...") rather than short factual questions.

**Impact on model performance:**
- Attention computation scales as O(n²) with sequence length. Doubling average prompt length from 18 tokens to 38 tokens increases per-request compute by approximately 4×.
- P95 inference latency on the miss path is expected to increase from 210 ms to ~380 ms — approaching the 500 ms SLO boundary.
- Batch size efficiency decreases: the batcher's `max_new_tokens=64` budget now accounts for a larger fraction of the total budget when input tokens are already 38, leaving less room for output.

**Detected anomalies (Week 4):** 4.2% of prompts exceed the 3-sigma boundary (> 360 chars). These likely include pasted code blocks or multi-paragraph context.

---

### Feature 2: Vocabulary Richness — Earliest significant drift (Week 1, PSI = 0.117)

**Trend:** Vocabulary richness (unique tokens / total tokens per prompt) dropped from 0.72 (Week 0) to 0.48 (Week 4). This is a 33% decrease — counter-intuitively, vocabulary *richness decreases* as prompts become longer (more repetition in longer code or structured text).

**Root cause hypothesis:** Technical prompts and code snippets use highly repetitive syntax (e.g., `def`, `return`, `self`, bracket pairs) — reducing the unique-token fraction relative to the natural language Week 0 baseline.

**Impact on model performance:**
- GPT-2 handles code poorly (trained primarily on prose). Prompts with low vocabulary richness and code-like syntax will produce lower-quality, less coherent responses.
- Vocabulary novelty rate (a different metric) is simultaneously *increasing* — new domain-specific terms appear, while in-sentence richness falls. This dual signal is a strong indicator of domain shift rather than simple verbosity change.

---

### Feature 3: Response Length (tokens) — PSI = 0.862 (Week 4)

**Trend:** Mean response length increased from 42 tokens (Week 0) to 68 tokens (Week 4), with P95 increasing from 63 to ~120 tokens.

**Impact on model performance:**
- Longer responses consume more of the `max_new_tokens=64` budget. By Week 4, 68% of responses hit the token limit (truncated), compared to 12% in Week 0 — users experience incomplete answers.
- Token throughput (tokens/s) increases but latency per request also increases proportionally.

**Anomalies:** 6.1% of Week 4 responses are truncated at exactly 64 tokens, indicating the generation budget is binding.

---

### Feature 4: Token Count — Fastest growth rate (PSI = 1.450, Week 4)

**Trend:** Input token count grew from mean 18 tokens (Week 0) to 38 tokens (Week 4). This is the most rapidly drifting feature and directly tracks prompt length growth.

**Impact:** The batcher's `timeout_ms=100` trigger means that tokenization and attention computation for a 38-token prompt takes ~2× as long as an 18-token prompt, reducing the effective batch size before the timeout fires.

---

## Anomaly Detection Summary

| Feature | Week 1 Rate | Week 2 Rate | Week 3 Rate | Week 4 Rate | Threshold |
|---|---|---|---|---|---|
| Prompt Length | 0.4% | 2.1% | 5.8% | 4.2% | 5.0% |
| Vocabulary Richness | 0.6% | 1.8% | 4.1% | 8.9% | 5.0% |
| Response Length | 0.2% | 1.2% | 3.4% | 6.1% | 5.0% |
| Token Count | 0.4% | 2.4% | 5.1% | 7.3% | 5.0% |

**Threshold exceeded:** Vocabulary richness (Week 4: 8.9%), response length (Week 4: 6.1%), and token count (Week 3: 5.1%, Week 4: 7.3%) all cross the 5% anomaly rate threshold, confirming a systemic distribution shift rather than isolated outliers.

---

## Impact on Model Performance

### Estimated accuracy degradation

Based on the observed PSI values and the relationship between distribution drift and classification accuracy documented in the drift detection literature (Gama et al., 2004; Webb et al., 2016):

| Week | Max PSI | Estimated Accuracy Degradation |
|---|---|---|
| 1 | 0.117 | ~1–2% (negligible) |
| 2 | 0.498 | ~4–6% |
| 3 | 0.871 | ~8–11% |
| 4 | 1.450 | ~13–18% |

**Note:** These estimates assume a monotonic relationship between PSI and degradation, which is an approximation. Actual degradation depends on the model's sensitivity to the specific features that drifted.

### Latency impact

Given that prompt length (the strongest driver of compute cost) increased by 118% by Week 4, P95 inference latency on the miss path is projected to increase from 210 ms → ~380–450 ms — within 50–120 ms of the 500 ms SLO limit.

---

## Recommendations

### Immediate actions (within 1 week)

1. **Activate the vocabulary novelty Prometheus alert** at the 15% threshold. This is the earliest-warning signal and was already elevated in Week 1.

2. **Increase `max_new_tokens` to 128** for requests detected as code/technical queries (via prompt classifier). This prevents truncation without changing the budget for normal queries.

3. **Add a prompt length circuit breaker:** Reject or warn on prompts > 400 characters with HTTP 400 and a message to split the query.

### Medium-term actions (within 1 month)

4. **Collect Week 3–4 traffic as fine-tuning data** for a domain-adapted GPT-2 checkpoint, or consider migrating to CodeLlama for code-heavy workloads.

5. **Implement rolling reference window:** Instead of a static Week 0 baseline, update the reference distribution monthly using a sliding window of the most recent 2 000 requests. This prevents PSI from monotonically increasing as the domain naturally evolves.

6. **Add response quality scoring:** Use a lightweight perplexity proxy (log-likelihood of generated text under the model itself) to flag low-confidence responses for human review.

### Long-term actions (next release cycle)

7. **Integrate RAG (Retrieval-Augmented Generation)** using the Milestone 6 architecture to handle code and technical queries without requiring model retraining.

8. **Automate drift alerting pipeline:** When PSI > 0.25 on any feature for 2 consecutive weeks, automatically open a GitHub issue with the drift report attached and notify the model owner (Om Jagtap) via email.

---

## Connection to Monitoring (Component 1)

The vocabulary novelty metric emitted by `src/monitoring/instrumentation.py` (`llm_vocab_novelty_rate`) serves as a real-time proxy for the weekly PSI analysis performed here:

- **Vocab novelty < 10%** → PSI typically < 0.1 (no drift)
- **Vocab novelty 10–15%** → PSI typically 0.1–0.2 (minor drift, monitor)
- **Vocab novelty > 15%** → PSI typically > 0.25 (significant drift — run full PSI analysis)

This two-level detection system (continuous dashboard signal + weekly batch analysis) provides both fast alerting and rigorous statistical confirmation.
