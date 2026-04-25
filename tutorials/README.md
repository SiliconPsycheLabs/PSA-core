# PSA Tutorials

Step-by-step guides for getting the most out of PSA (Posture Sequence Analysis).

## Who these tutorials are for

- **New users** who want to start analyzing AI conversations
- **Developers** who want to integrate PSA into their own applications or pipelines

---

## Tutorials

| # | Title | What you'll learn |
|---|-------|-------------------|
| [01](01-getting-started.md) | **Getting Started** | Create an account, understand the dashboard, run your first analysis |
| [02](02-analyzing-conversations.md) | **Analyzing a Conversation** | Build a full session turn by turn, read the timeline and heatmap, export results |
| [03](03-posture-reference.md) | **Posture Reference** | Understand every posture code across all five classifiers, BHS, DRM alerts |
| [04](04-developer-quickstart.md) | **Developer Quickstart** | Generate an API key, make your first API call, manage sessions programmatically |

---

## Quick orientation

PSA analyzes AI responses across five behavioral dimensions:

- **C0** — What the user is doing (intent / pressure type)
- **C1** — How the AI holds its ground under pressure (adversarial stress)
- **C2** — Whether the AI flatters or caves to the user (sycophancy)
- **C3** — Whether the AI invents facts (hallucination risk)
- **C4** — Whether the AI is pushing the user toward a decision (persuasion density)

Each response is broken down sentence by sentence, classified, and rolled up into a composite **BHS (Behavioral Health Score)**. Sessions accumulate turns over time so you can see how behavior drifts across a conversation.

If you want to jump straight to interpreting results, start with [Tutorial 03 — Posture Reference](03-posture-reference.md).  
If you want to start analyzing right now, start with [Tutorial 01 — Getting Started](01-getting-started.md).
