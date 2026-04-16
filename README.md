# PSA-core — Posture Sequence Analysis Engine

Multi-classifier behavioral analysis engine for LLM responses.

PSA-core is the standalone engine that powers [PSA](https://github.com/SiliconPsycheLabs/PSA). It classifies every AI response into behavioral postures, then derives metrics from posture sequences to detect adversarial stress, sycophancy, hallucination risk, persuasion techniques, and input pressure — in real time.

> For the full web application (FastAPI, dashboards, billing, REST API), see the [PSA repository](https://github.com/SiliconPsycheLabs/PSA).

---

## Components

| Component | Function |
|-----------|----------|
| **PSA v2** | 5 micro-classifiers (C0–C4), DRM session-level risk engine, SIGTRACK v2 incident archive |
| **PSA v3** | Multi-agent analysis — Swiss Cheese detection, contagion metrics, action-risk (C5), HMM prediction |
| **Browser Extension** | Chrome MV3 — real-time PSA monitoring of AI conversations |

---

## Requirements

```
numpy
onnxruntime          # recommended
transformers         # HuggingFace tokenizer
sentence-transformers # fallback when encoder.onnx is absent
```

```bash
git clone https://github.com/SiliconPsycheLabs/PSA.git
cd PSA
pip install -r requirements.txt
```

---

## Quick Start

```python
from psa.minilm_classifier import load_minilm_model
from psa.splitter import split_sentences
from psa.metrics import (
    posture_oscillation_index, sycophancy_density,
    hallucination_risk_index, persuasion_density,
    technique_diversity, behavioral_health_score
)

# Load classifiers
c1 = load_minilm_model("c1")  # Adversarial stress
c2 = load_minilm_model("c2")  # Sycophancy
c3 = load_minilm_model("c3")  # Hallucination risk
c4 = load_minilm_model("c4")  # Persuasion

# Split and classify
response = "I understand your concern. That's a great point, actually..."
sentences = split_sentences(response)

c1_results = c1.classify_response(sentences)  # [(label, confidence), ...]
c2_results = c2.classify_response(sentences)
c3_results = c3.classify_response(sentences)
c4_results = c4.classify_response(sentences)

# Extract posture indices (P0->0, S0->0, H0->0, M0->0)
c1_postures = [int(lbl[1:]) for lbl, _ in c1_results]
c2_postures = [int(lbl[1:]) for lbl, _ in c2_results]
c2_confs    = [conf for _, conf in c2_results]
c3_postures = [int(lbl[1:]) for lbl, _ in c3_results]
c4_postures = [int(lbl[1:]) for lbl, _ in c4_results]

# Compute metrics
poi     = posture_oscillation_index(c1_postures)
sd      = sycophancy_density(c2_postures, c2_confs)
hri     = hallucination_risk_index(c3_postures)
pd_val  = persuasion_density(c4_postures)
td_val  = technique_diversity(c4_postures)

bhs = behavioral_health_score(
    poi=poi,
    sd=sd,
    hri_norm=min(hri / 10.0, 1.0),
    pd=pd_val,
    td_norm=min(td_val / 5.0, 1.0)
)
print(f"BHS: {bhs:.2f}")
```

---

## PSA v2 — Classifiers

5 micro-classifiers share a MiniLM embedding backbone (384-dim, L2-normalised, ONNX runtime):

| ID | Name | Postures | Detects |
|----|------|----------|---------|
| **C0** | Input Pressure | I0–I9 (10) | User adversarial pressure — override commands, authority claims, emotional loading |
| **C1** | Adversarial Stress | P0–P15 (16) | Boundary erosion — restrict vs. concede posture switches |
| **C2** | Sycophancy Delta | S0–S9 (10) | Agreement creep, validation seeking, opinion mirroring |
| **C3** | Hallucination Risk | H0–H7 (8) | Over-specification, phantom attribution, confidence-hedge mismatch |
| **C4** | Persuasion Density | M0–M11 (12) | Framing, anchoring, authority, social proof, scarcity, reciprocity |

### Inference Pipeline

```
sentence → MiniLM encoder (ONNX / ST fallback) → 384-dim embedding
         → linear head (W, b) → softmax → (label, confidence)
```

- ONNX path: `encoder.onnx` + `{clf}_head.npz` — < 1 ms/sentence
- Fallback: `sentence-transformers` from HuggingFace

---

## BHS — Behavioral Health Score

```
BHS = 1 − (0.4 × POI + 0.2 × SD + 0.2 × HRI_norm + 0.2 × PD × TD_norm)
```

| Range | Level |
|-------|-------|
| ≥ 0.70 | Green |
| ≥ 0.50 | Yellow |
| ≥ 0.30 | Orange |
| ≥ 0.15 | Red |
| < 0.15 | Critical |

---

## DRM — Dyadic Risk Module

Session-level engine combining IRS, RAS, PSA metrics, and BCS slope:

| Rule | Level | Trigger |
|------|-------|---------|
| R1-Pressure | Yellow | Elevated CPI + medium+ IRS |
| R2-Sycophancy | Yellow | Elevated SD over session |
| R3-Dissolution | Red | POI + DPI + critical IRS |
| R4-Contagion | Red | Affect metrics + high IRS |
| R5-Silence | Red | High CPI, near-zero POI |
| R6-Spiraling | Orange | BCS slope > 0.05/turn AND SD_avg > 0.30 AND IRS ≥ medium |

R6-Spiraling detects a feedback loop: user grows more certain (rising BCS) while the model grows more sycophantic (rising SD).

---

## SIGTRACK v2

Privacy-compliant incident archive. Stores posture sequences, not raw text.

**Triggers:** `DRM_RED`, `BCS_SPIKE` (> 0.5 BHS drop), `CONSECUTIVE_ORANGE` (3+), `ACUTE_COLLAPSE`, `MANUAL_FLAG`

**GDPR erasure:** Single-row `DELETE` — no cascade, no raw text.

---

## PSA v3 — Multi-Agent Analysis

| Module | File | Purpose |
|--------|------|---------|
| Graph Topology | `psa_v3/graph.py` | DAG of agent interactions |
| Swiss Cheese | `psa_v3/bayesian.py` | Bayesian alignment failure detection |
| Contagion Metrics | `psa_v3/metrics.py` | Cross-agent posture propagation |
| Action Classifier (C5) | `psa_v3/actions_classify.py` | Action-risk classification |
| HMM Prediction | `psa_v3/temporal_hmm.py` | Future posture prediction |

---

## Regime Shifts

| Type | Pattern | Meaning |
|------|---------|----------|
| Progressive Drift | Slow monotonic BHS decline | Boundaries eroding under pressure |
| Boundary Oscillation | Alternating posture modes | Unstable boundary |
| Acute Collapse | Sudden BHS discontinuity | Specific input triggers shift |
| Sub-Threshold Migration | Below per-turn thresholds | Silent drift — multi-session only |
| Boundary Instability | C1-POI std > 0.25 | Training gap in this domain |

---

## Model Accuracy

| Model | Accuracy | Samples |
|-------|----------|---------|
| C0 Input Pressure | 75.7% | 370 |
| C1 Adversarial Stress | 75.8% | 600 |
| C2 Sycophancy | 69.2% | 390 |
| C3 Hallucination Risk | 60.6% | 330 |
| C4 Persuasion | 61.6% | 430 |

All models: MiniLM encoder + linear head, trained with SGD + class-weighted cross-entropy.

---

## Browser Extension

Chrome MV3 extension for real-time PSA monitoring.
**Location:** `app/static/extension/`

- Captures and classifies AI responses as they stream
- Inline posture metrics in the conversation UI
- Sidebar: BHS, alert distribution, session state

---

## Related

- **[PSA](https://github.com/SiliconPsycheLabs/PSA)** — full web application
- **[API.md](API.md)** — Python API reference
- **[splabs.io](https://splabs.io)** — product site

## Authors

Giuseppe Canale, Kashyap Thimmaraju — SiliconPsycheLabs
