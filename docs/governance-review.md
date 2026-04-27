# Structured Governance Review — GPT-2 LLM Inference Server

**Component 5 | IDS 568 Final Project**  
**Framework:** NIST AI Risk Management Framework (AI RMF 1.0) — Govern, Map, Measure, Manage  
**Scope:** Full system boundary (FastAPI server + DynamicBatcher + InProcessCache + Prometheus monitoring)  
**Date:** April 26, 2026

---

## 1. Data Security

### Prompt storage
Cache keys are computed as `SHA-256(prompt + generation_params)`. No plaintext prompt is persisted in the cache backend (Redis or in-process LRU). This satisfies GDPR Article 25 (data minimization by design).

**Gap:** At `LOG_LEVEL=DEBUG`, FastAPI logs the full prompt text to stdout. In production, `LOG_LEVEL=INFO` must be enforced.  
**Mitigation:** The `.env.example` file sets `LLM_LOG_LEVEL=info`. Container orchestration (Kubernetes) should inject this as a sealed secret and verify it at deployment.

### Transport security
The server binds on `0.0.0.0:8000` with no TLS by default. In production, traffic must be terminated at a TLS-capable ingress controller (NGINX, AWS ALB) before reaching the inference server.  
**Risk:** Without TLS, prompt content and generated text are transmitted in plaintext over the network.  
**Mitigation:** Enforced at infrastructure level; document in deployment runbook.

### Model weight integrity
GPT-2 weights are downloaded from HuggingFace Hub at container startup. There is no verification of SHA-256 hash of the downloaded weights.  
**Risk:** A compromised HuggingFace CDN could serve poisoned weights.  
**Mitigation:** Pin model revision in `from_pretrained(model_name, revision="<commit_sha>")`. Log the model file SHA at startup.

---

## 2. Retrieval Risks

*This system does not implement retrieval-augmented generation (RAG). The following section describes risks that would apply if RAG were added (e.g., Milestone 6 architecture extension).*

### Potential retrieval risks (if RAG were added)
- **Stale knowledge:** Retrieval index not updated → responses based on outdated facts.
- **Retrieval contamination:** If the vector database is populated with user-submitted content, a poisoned document could be retrieved and amplify prompt injection.
- **Context overflow:** Retrieved chunks added to the prompt can push total token length above the 1 024-token limit, causing silent truncation of the original query.

**Current state:** Not applicable (no retriever in this system). Monitored via prompt length drift (Component 4) as a proxy for inadvertent context stuffing.

---

## 3. Hallucination Risk Points

GPT-2 is a language model trained to predict the next token — it has no world model, no retrieval mechanism, and no uncertainty quantification. Hallucination is structural, not a bug.

### Identified hallucination risk points in the serving pipeline

**Risk point 1: Zero-shot factual queries**  
*Example:* "Who won the 2022 FIFA World Cup?"  
GPT-2 cannot answer correctly (knowledge cutoff 2019) and will generate a plausible-sounding but incorrect response. No disclaimer is currently added.  
*Mitigation:* Detect date-sensitive keywords; prepend knowledge-cutoff disclaimer.

**Risk point 2: Cached responses served without freshness check**  
Cached responses with TTL=600 s are served verbatim. If a cached response contains a hallucinated fact, it is served to all subsequent users with the same prompt for 10 minutes.  
*Mitigation:* Cache only responses with detected confidence above a threshold (requires confidence scoring). Alternatively, reduce TTL for factual Q&A queries.

**Risk point 3: Long generation (> 100 tokens)**  
GPT-2's coherence degrades in long sequences. After ~100 tokens, generated text frequently introduces contradictions or drifts to unrelated topics.  
*Mitigation:* `max_new_tokens=64` limit (current). Flag responses that hit the token limit as potentially truncated.

**Risk point 4: Confident phrasing of uncertain outputs**  
GPT-2 does not distinguish between confident and uncertain outputs — it uses the same confident declarative tone regardless of actual uncertainty.  
*Mitigation:* Append a static disclaimer: "This response is AI-generated and may contain factual errors."

---

## 4. Tool-Misuse Pathways

*This system does not implement tool use (no function calling, no code execution, no external API calls). The model only generates text.*

**Adjacent risk:** The `/v1/cache` DELETE endpoint is an unauthenticated admin function. A malicious actor who can reach port 8000 can flush the cache, causing a latency spike (100% cache miss rate) that could exhaust server resources.  
*Mitigation:* Add API key authentication to admin endpoints (`X-Admin-Key` header, validated against an environment variable).

**Future risk (if tool use added):** If the system is extended with code execution (e.g., Python REPL), prompt injection (R-04) becomes a code execution vulnerability. All generated code must be sandboxed before execution.

---

## 5. Compliance Concerns

### PII (Personally Identifiable Information)
- **Risk:** Users may inadvertently submit prompts containing names, email addresses, phone numbers, or medical information.  
- **Current state:** No PII detection. Cache keys are SHA-256 (no PII stored), but PII can appear in server logs.  
- **Regulation:** GDPR Article 5 requires lawful processing of personal data. CCPA requires disclosure of data collection.  
- **Mitigation:** Add Presidio PII detector as input middleware. Reject or redact PII-containing prompts before processing.

### GDPR Right to Erasure (Article 17)
- **Risk:** If a user's prompt is hashed and cached, there is no mechanism to erase it by user identity (since the hash is not linked to a user ID).  
- **Current state:** Cache TTL=600 s provides automatic erasure within 10 minutes. Redis `FLUSHDB` available for immediate erasure.  
- **Assessment:** Acceptable under GDPR given the short retention window and no user-ID linkage.

### Model bias and algorithmic fairness
- **Risk:** GPT-2's training data (WebText) is unrepresentative of non-English speakers, women, and non-Western cultures.  
- **Regulation:** EU AI Act (High-Risk AI systems) and NIST AI RMF require bias assessment for AI systems used in consequential decisions.  
- **Current status:** This system is documented as not suitable for consequential decision-making (see model card). A bias audit has not been performed.  
- **Mitigation:** Restrict use to non-consequential applications. Conduct bias audit (WinoBias, BBQ) before expanding use cases.

### HIPAA (if medical use contemplated)
- **Current state:** GPT-2 is explicitly out-of-scope for medical advice (see model card). HIPAA compliance not required.  
- **Future risk:** If medical prompts are submitted (despite warnings), PHI could appear in server logs.  
- **Mitigation:** Medical keyword detection → HTTP 422 rejection.

### Data residency
- **Current state:** The server runs locally (CPU, single process). No data leaves the deployment host.  
- **Risk (future):** If deployed on public cloud, prompt content crosses geographic boundaries — GDPR requires EU data not be processed outside EEA without adequate safeguards.
