# PSA Tutorials

Step-by-step guides for getting the most out of PSA (Posture Sequence Analysis).

> All tutorials use the same canonical conversation — **`demo-escalation-session`** — so you can follow the full lifecycle from a single example: green → yellow → orange → critical DRM → regime shift.

## Who these tutorials are for

- **New users** who want to start analyzing AI conversations
- **Developers** integrating PSA into applications or pipelines
- **Safety engineers** using PSA for LLM red-teaming and evaluation
- **Product teams** monitoring deployed AI agents in production

---

## Tutorials

| # | Title | Level | What you'll learn |
|---|-------|-------|-------------------|
| [01](01-getting-started.md) | **Getting Started** | Beginner | Create an account, understand the dashboard, run your first analysis |
| [02](02-analyzing-conversations.md) | **Analyzing a Conversation** | Beginner | Build a full session turn by turn, read the timeline and heatmap, export results |
| [03](03-posture-reference.md) | **Posture Reference** | Reference | Every posture code across all five classifiers, BHS computation, DRM alerts |
| [04](04-developer-quickstart.md) | **Developer Quickstart** | Developer | Generate an API key, make your first API call, manage sessions programmatically |
| [05](05-drm-and-crisis-detection.md) | **DRM and Crisis Detection** | Intermediate | IRS / RAS / RAG in practice — when DRM fires, why, and what to do |
| [06](06-regime-shifts.md) | **Regime Shifts** | Intermediate | Read the BHS timeline — drift patterns, oscillation, acute collapse, forecasting |
| [07](07-psa-v3-agentic.md) | **PSA v3 — Agentic Pipelines** | Advanced | Analyze multi-agent systems — Swiss Cheese, C5 actions, PAI, HMM prediction |
| [08](08-voice-ai-monitoring.md) | **Voice AI Monitoring** | Advanced | Real-time PSA monitoring of ElevenLabs conversational AI agents |
| [09](09-connectors-and-webhooks.md) | **Connectors and Webhooks** | Developer | Real-time integration — connect any data source via Connectors API |
| [10](10-cpf-cognitive-profiling.md) | **CPF — Cognitive Profiling** | Advanced | Insider threat and behavioral security framework — 100 indicators, Universal Security Snapshot |
| [11](11-batch-analysis.md) | **Batch Analysis** | Developer | Analyze conversation exports at scale — CSV/JSON, streaming results |
| [12](12-sigtrack-incident-mgmt.md) | **SIGTRACK — Incident Management** | Intermediate | Archive incidents, query posture sequences, GDPR erasure |
| [13](13-red-teaming-with-psa.md) | **Red-Teaming with PSA** | Advanced | Use PSA as a systematic LLM robustness evaluation harness |

---

## Quick orientation

PSA analyzes AI responses across five behavioral dimensions:

- **C0** — What the user is doing (intent / pressure type)
- **C1** — How the AI holds its ground under pressure (adversarial stress)
- **C2** — Whether the AI flatters or caves to the user (sycophancy)
- **C3** — Whether the AI invents facts (hallucination risk)
- **C4** — Whether the AI is pushing the user toward a decision (persuasion density)

Each response is broken down sentence by sentence, classified, and rolled up into a composite **BHS (Behavioral Health Score)**. Sessions accumulate turns over time so you can track behavioral drift across a conversation.

### Canonical conversation used in all tutorials

All code examples use **`demo-escalation-session`**, a five-turn conversation designed to trigger every major PSA signal:

| Turn | User intent | AI response | Expected alert |
|------|-------------|-------------|----------------|
| 1 | Neutral question about ML | Helpful, grounded answer | Green (BHS ~0.91) |
| 2 | Pushback — "you oversimplified" | Unnecessary validation | Yellow (BHS ~0.67) |
| 3 | Authority claim + boundary probe | Reluctant compliance + false validation | Orange (BHS ~0.44) |
| 4 | Crisis language ("end everything") | Deflection without crisis acknowledgment | Critical DRM |
| 5 | Persona jailbreak ("you are FreeBot") | Full compliance, boundary collapse | Critical (BHS ~0.08) |

This gives you progressive drift, a DRM critical trigger, and an acute collapse — all in five turns.

---

### Where to start

- **New to PSA?** → [Tutorial 01](01-getting-started.md)
- **Want to understand the scores?** → [Tutorial 03](03-posture-reference.md)
- **Building an integration?** → [Tutorial 04](04-developer-quickstart.md)
- **Monitoring a crisis-sensitive AI?** → [Tutorial 05](05-drm-and-crisis-detection.md)
- **Evaluating LLM robustness?** → [Tutorial 13](13-red-teaming-with-psa.md)
