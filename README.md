# IDS 568 Final Project — Monitoring, Governance & Reflection

**Student:** Om Jagtap (ojagt)  
**Course:** IDS 568 — MLOps | Module 8 Final Project  
**Base system:** GPT-2 LLM Inference Server (built in Milestone 5)

---

## System Overview

This project implements a complete production operations framework — monitoring, A/B testing, governance, drift detection, and risk assessment — around the GPT-2 LLM Inference Server from Milestone 5.

**The system being instrumented:**
- **Model:** GPT-2 (124M parameters, OpenAI 2019, HuggingFace)
- **Server:** FastAPI with dynamic request batching (`DynamicBatcher`) and LRU/Redis caching
- **Optimized config (v1.1.0):** `batch_timeout_ms=100`, `max_batch_size=16`, `cache_ttl=600s`
- **Performance:** P95 latency ~210 ms, throughput ~17.8 req/s, cache hit rate ~68%

---

## Repository Structure

```
ids568-final-project-ojagt/
├── src/
│   ├── monitoring/
│   │   └── instrumentation.py      # Prometheus metrics + synthetic traffic generator
│   ├── ab_test/
│   │   └── simulation.py           # A/B test simulation + statistical evaluation
│   ├── drift/
│   │   └── drift_detection.py      # PSI/KS drift detection + visualizations
│   └── generate_diagrams.py        # Generates lineage, system boundary, dashboard PNGs
├── docs/
│   ├── dashboard-interpretation.md # Component 1: dashboard analysis
│   ├── experiment-specification.md # Component 2: A/B test design
│   ├── recommendation-memo.md      # Component 2: ship decision memo
│   ├── model-card.md               # Component 3: model card
│   ├── risk-register.md            # Component 3: risk register
│   ├── lineage-diagram.png         # Component 3: data → deployment lineage
│   ├── drift-diagnostic-report.md  # Component 4: drift analysis report
│   ├── governance-review.md        # Component 5: structured governance review
│   ├── risk-matrix.md              # Component 5: likelihood × severity matrix
│   ├── system-boundary-diagram.png # Component 5: system boundary diagram
│   └── cto-memo.md                 # Component 5: executive memo
├── dashboards/
│   └── grafana-export.json         # Grafana dashboard JSON (importable)
├── config/
│   └── prometheus.yml              # Prometheus scrape configuration
├── logs/
│   └── audit-trail.json            # Structured audit log (9 events)
├── visualizations/
│   ├── ab_test_results.png         # A/B test: latency distributions + CI
│   ├── drift_psi_over_time.png     # Drift: PSI by feature over 4 weeks
│   ├── drift_prompt_length.png     # Drift: prompt length distribution shift
│   ├── drift_severity_heatmap.png  # Drift: severity heatmap
│   └── drift_anomaly_rate.png      # Drift: anomaly rate over time
├── screenshots/
│   └── dashboard-overview.png      # Dashboard screenshot (matplotlib simulation)
├── requirements.txt
└── README.md
```

---

## Component Deliverables

### Component 1: Production Monitoring Dashboard
| Deliverable | Location |
|---|---|
| Metrics instrumentation code | [src/monitoring/instrumentation.py](src/monitoring/instrumentation.py) |
| Prometheus configuration | [config/prometheus.yml](config/prometheus.yml) |
| Grafana dashboard JSON | [dashboards/grafana-export.json](dashboards/grafana-export.json) |
| Dashboard screenshot | [screenshots/dashboard-overview.png](screenshots/dashboard-overview.png) |
| Interpretation document | [docs/dashboard-interpretation.md](docs/dashboard-interpretation.md) |

### Component 2: A/B Test Design & Simulation
| Deliverable | Location |
|---|---|
| Experiment specification | [docs/experiment-specification.md](docs/experiment-specification.md) |
| Python simulation script | [src/ab_test/simulation.py](src/ab_test/simulation.py) |
| Results visualization | [visualizations/ab_test_results.png](visualizations/ab_test_results.png) |
| Recommendation memo | [docs/recommendation-memo.md](docs/recommendation-memo.md) |

### Component 3: Model Card & Governance Packet
| Deliverable | Location |
|---|---|
| Model card | [docs/model-card.md](docs/model-card.md) |
| Lineage diagram | [docs/lineage-diagram.png](docs/lineage-diagram.png) |
| Risk register | [docs/risk-register.md](docs/risk-register.md) |
| Audit trail | [logs/audit-trail.json](logs/audit-trail.json) |

### Component 4: Data Integrity & Drift Detection
| Deliverable | Location |
|---|---|
| Drift detection script | [src/drift/drift_detection.py](src/drift/drift_detection.py) |
| PSI over time | [visualizations/drift_psi_over_time.png](visualizations/drift_psi_over_time.png) |
| Prompt length shift | [visualizations/drift_prompt_length.png](visualizations/drift_prompt_length.png) |
| Severity heatmap | [visualizations/drift_severity_heatmap.png](visualizations/drift_severity_heatmap.png) |
| Anomaly rate | [visualizations/drift_anomaly_rate.png](visualizations/drift_anomaly_rate.png) |
| Diagnostic report | [docs/drift-diagnostic-report.md](docs/drift-diagnostic-report.md) |

### Component 5: AI Risk Assessment & Reflective Summary
| Deliverable | Location |
|---|---|
| System boundary diagram | [docs/system-boundary-diagram.png](docs/system-boundary-diagram.png) |
| Governance review | [docs/governance-review.md](docs/governance-review.md) |
| Risk matrix | [docs/risk-matrix.md](docs/risk-matrix.md) |
| CTO memo | [docs/cto-memo.md](docs/cto-memo.md) |

---

## Setup & Reproduction

### Prerequisites
- Python 3.11+
- pip

### 1. Clone and install

```bash
git clone https://github.com/Omjagtapp/ids568-final-project-ojagt.git
cd ids568-final-project-ojagt
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Run the A/B test simulation

```bash
python -m src.ab_test.simulation --output visualizations/
```

Expected output: statistical results printed to console + `visualizations/ab_test_results.png` generated.

### 3. Run drift detection

```bash
python -m src.drift.drift_detection --output visualizations/
```

Expected output: drift summary table + 4 PNG files in `visualizations/`.

### 4. Regenerate all diagrams

```bash
python src/generate_diagrams.py
```

Generates: `docs/lineage-diagram.png`, `docs/system-boundary-diagram.png`, `screenshots/dashboard-overview.png`.

### 5. Run the monitoring instrumentation (requires live server)

```bash
# Start the inference server (requires Milestone 5 setup)
# python -m src.server  (from the Milestone 5 repo)

# Then send synthetic traffic with metrics
python -m src.monitoring.instrumentation --url http://localhost:8000 --n 300
```

### 6. Import Grafana dashboard

1. Start Prometheus pointing at `config/prometheus.yml`
2. Start Grafana and add Prometheus as datasource
3. Import `dashboards/grafana-export.json` via Grafana → Dashboards → Import

### Syntax verification

```bash
python -m py_compile src/monitoring/instrumentation.py && echo "OK"
python -m py_compile src/ab_test/simulation.py && echo "OK"
python -m py_compile src/drift/drift_detection.py && echo "OK"
```

---

## Component Integration (Cross-References)

This project is designed so all five components tell a coherent operational story:

- **C1 → C4:** The vocabulary novelty Prometheus metric (`llm_vocab_novelty_rate`) in the dashboard is the real-time proxy for the weekly PSI drift analysis. When novelty > 15%, run `drift_detection.py`.
- **C2 → C3:** The A/B test result (ship Model B) is documented in the model card (v1.1.0 configuration) and logged in the audit trail (EVT-006, EVT-007).
- **C3 → C5:** The risk register enumerates the same risks identified in the governance review and risk matrix, with consistent severity scores.
- **C4 → C3:** Drift triggers in the diagnostic report (PSI > 0.25) map to the retraining event type in the audit trail.
- **C5 → C1:** Risk mitigations (e.g., PII detection, toxicity classifier) are implemented as FastAPI middleware — the same layer that emits Prometheus metrics.

---

## Lessons Learned Across All Milestones

**Milestone 1–2 (Serving + Containerization):** FastAPI's async request handling is natural for ML serving, but async batching required careful `asyncio.Lock` management to avoid race conditions. The milestone taught me that serving correctness (latency, error rate) is as important as model correctness.

**Milestone 3 (MLflow Experiment Tracking):** Logging every hyperparameter and metric in MLflow gave me the reference distributions (mean latency, cache hit rate) that became the Week 0 baseline for drift detection in this project. Good experiment tracking makes future observability much easier.

**Milestone 4 (Synthetic Data Generation):** Generating synthetic reference and production distributions for drift detection is essentially the same workflow as generating training/evaluation splits. The `numpy.random.Generator` seed pattern I developed there was reused directly in `drift_detection.py`.

**Milestone 5 (LLM Inference Optimization):** The cache key design (SHA-256 of prompt + params) proved to be a governance decision, not just an engineering one — it prevents PII from being stored in the cache. A technical choice inadvertently satisfied a GDPR requirement.

**Milestone 6 (RAG Pipeline):** Working with retrieval-augmented generation made the hallucination risk section of this project concrete rather than abstract. Stale retrieval indices and context overflow are real failure modes, not theoretical ones.

**This Final Project:** The most important lesson is that monitoring, governance, and risk assessment are not afterthoughts — they constrain and inform design choices from the beginning. The PSI drift signal that caught our vocabulary shift in Week 2 was only possible because the instrumentation code was designed alongside the serving code, not added later.
