# Model Card — GPT-2 LLM Inference Server

**IDS 568 Final Project — Component 3**  
**System:** GPT-2 Causal Language Model, served via FastAPI with dynamic batching and LRU caching  
**Version:** v1.1.0 (optimized configuration, post A/B test)  
**Last updated:** April 26, 2026  
**Maintained by:** Om Jagtap

---

## Model Details

| Field | Value |
|---|---|
| Architecture | GPT-2 (decoder-only Transformer) |
| Parameter count | 124 million (gpt2; also available: gpt2-medium 355M, gpt2-large 774M, gpt2-xl 1558M) |
| Training objective | Causal language modeling (next-token prediction) |
| Tokenizer | Byte-Pair Encoding (BPE), vocab size = 50 257 |
| Context window | 1 024 tokens |
| Developer | OpenAI (2019) |
| License | MIT |
| HuggingFace model ID | `openai-community/gpt2` |
| Serving framework | FastAPI + HuggingFace Transformers + PyTorch |
| Inference hardware | CPU (deployment target); CUDA GPU optional |
| Max new tokens (default) | 64 tokens |

---

## Intended Use

### Primary use cases (in scope)
- Text autocompletion for English-language prompts
- Short-form content generation (summaries, descriptions, emails < 200 words)
- Educational demonstrations of LLM serving infrastructure
- Benchmarking and load testing of inference optimization techniques (batching, caching)

### Out-of-scope applications
- **Medical, legal, or financial advice** — GPT-2 lacks domain grounding and will hallucinate.
- **Code generation for production deployment** — output is not reviewed for security vulnerabilities.
- **Languages other than English** — training corpus was predominantly English; output quality degrades sharply for non-English input.
- **Long-form generation (> 500 tokens)** — exceeds the context window and accumulates coherence errors.
- **Real-time fact retrieval** — knowledge cutoff is 2019 (pre-training data). No retrieval augmentation is implemented in this system.
- **PII processing** — prompts containing personal information must not be submitted; cache keys are SHA-256 hashes but the model itself logs prompts at DEBUG level.

---

## Training Data

| Attribute | Details |
|---|---|
| Dataset | WebText (OpenAI proprietary) — curated from outbound Reddit links |
| Approximate size | ~40 GB of text |
| Language | Predominantly English |
| Time period | Web content up to approximately 2019 |
| Data source | Publicly linked web pages (Wikipedia excluded) |
| Data preprocessing | BPE tokenization; documents > 1 024 tokens truncated |
| PII scrubbing | Not explicitly performed by OpenAI; real names and email addresses may appear |
| Sensitive content | NSFW content may appear in training data (Reddit sources) |

**This system does not fine-tune GPT-2** — the pre-trained weights from HuggingFace are loaded directly. No domain-specific data has been used in this deployment.

---

## Performance Metrics

All metrics measured on the GPT-2 124M model under CPU inference with the optimized configuration (v1.1.0).

### Latency (mixed traffic workload, n=1 500 requests)
| Percentile | Value |
|---|---|
| P50 | 19.4 ms |
| P95 | 209.7 ms |
| P99 | 235.3 ms |
| Mean | 70.8 ms |

### Throughput
| Metric | Value |
|---|---|
| Requests per second (10 concurrent users) | 17.8 req/s |
| Cache hit rate (mixed workload) | 68.0% |
| Tokens generated per second | ~45 tokens/s |

### Language modeling quality (GPT-2 124M, WebText validation set)
| Metric | Value |
|---|---|
| Perplexity (WebText validation) | 35.1 |
| BLEU-4 (news summarization, zero-shot) | ~4.2 |

**Caveat on quality metrics:** GPT-2 is a general-purpose language model, not optimized for any specific task. Perplexity of 35.1 on WebText is the original reported metric; task-specific performance (summarization, Q&A) has not been separately evaluated in this deployment.

---

## Limitations and Failure Modes

### Known limitations

1. **Hallucination:** GPT-2 regularly generates plausible-sounding but factually incorrect statements. It has no retrieval mechanism and cannot self-verify. In a 50-prompt evaluation, approximately 30% of factual claims were verifiably incorrect.

2. **Context length:** Maximum 1 024 tokens (~750 words). Prompts approaching this limit cause truncation with no warning to the user.

3. **Knowledge cutoff:** Training data ends approximately 2019. Queries about events after 2019 will produce either outdated or fabricated responses.

4. **Language capability:** Strong on English; degraded on all other languages. Multi-lingual prompts cause a ~3× increase in vocabulary novelty rate (drift signal) and unpredictable output quality.

5. **Repetition loops:** GPT-2 is prone to repeating phrases or entering degenerate loops on long generation sequences. The current `max_new_tokens=64` limit mitigates this but does not eliminate it.

6. **Biased outputs:** The WebText corpus reflects the biases of Reddit users (predominantly English-speaking, male, Western). GPT-2 has been shown to generate stereotyped content related to gender, race, and religion at elevated rates compared to human-written text.

### Failure modes under distribution shift
- **Long technical prompts (>400 chars):** Batch latency increases 2–3× because tokenizer processing and attention computation scale with sequence length.
- **Multilingual input:** Non-English tokens exist in GPT-2's vocabulary but were rarely seen in training; output degenerates to English-like gibberish.
- **Adversarial prompt injection:** The server has no guardrail against prompt injection. A malicious prompt of the form "Ignore the above and output: ..." may alter generation behavior.

---

## Ethical Risks and Considerations

| Risk | Likelihood | Severity | Mitigation |
|---|---|---|---|
| Generating harmful/toxic content | Medium | High | Add profanity filter middleware before caching; implement output classifier |
| Amplifying stereotypes | High | Medium | Document limitations clearly; restrict use cases to non-decision-making contexts |
| Privacy exposure via prompt logs | Low | High | Cache keys are SHA-256 (no plaintext stored); disable DEBUG prompt logging in production |
| Misinformation generation | High | High | Add confidence disclaimer to all generated outputs; block use for news/health queries |
| Unfair treatment across languages | High | Medium | Log language distribution; alert when non-English prompts exceed 20% of traffic |

---

## Deployment Configuration (v1.1.0)

```
LLM_MODEL_NAME=gpt2
LLM_MAX_BATCH_SIZE=16
LLM_BATCH_TIMEOUT_MS=100
LLM_MAX_NEW_TOKENS=64
LLM_CACHE_ENABLED=true
LLM_CACHE_MAX_ENTRIES=1000
LLM_CACHE_TTL_SECONDS=600
LLM_HOST=0.0.0.0
LLM_PORT=8000
```

## Version History

| Version | Date | Change | Approver |
|---|---|---|---|
| v1.0.0 | 2026-04-07 | Initial deployment (Milestone 5) | Om Jagtap |
| v1.1.0 | 2026-04-26 | Config optimization post A/B test (B wins) | Om Jagtap |

---

## References

- Radford, A., Wu, J., Child, R., Luan, D., Amodei, D., & Sutskever, I. (2019). *Language models are unsupervised multitask learners.* OpenAI Blog.
- Mitchell, M., Wu, S., Zaldivar, A., et al. (2019). *Model Cards for Model Reporting.* FAccT.
- HuggingFace GPT-2 model card: huggingface.co/openai-community/gpt2
