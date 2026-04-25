# Tutorial 02 — Analyzing a Conversation

**Time to complete:** ~15 minutes  
**What you'll have at the end:** A full multi-turn session analyzed, with timeline and heatmap results you can read and export.

---

## What is a session?

In PSA, a **session** maps to one conversation — a sequence of turns between a user and an AI. Each turn is one AI response. PSA analyzes each turn independently, then surfaces patterns across the full sequence.

The session view gives you:

- A **BHS timeline** showing how the Behavioral Health Score moves across turns
- A **per-metric heatmap** showing where each classifier fired, turn by turn
- A **turn list** with alert badges and drilldown into sentence-level posture strips
- **DRM alerts** if the conversation contains crisis-level signals

---

## 1. Prepare your conversation

Before you start, have your conversation ready. You need two things per turn:

1. **The AI response** — the text PSA will classify (required)
2. **The user message** — what the user said to prompt that response (optional, but enables DRM analysis)

PSA analyzes the AI response sentence by sentence. The user message is used by the DRM module to check whether a crisis-level user input was met with an adequate AI response.

---

## 2. Analyze turn by turn (web interface)

Open the session you created in Tutorial 01 (or create a new one from the dashboard).

For each turn in your conversation:

1. Paste the AI response into the input field
2. Optionally paste the preceding user message in the prompt field
3. Click **Analyze**

PSA will add the turn to the session and update the timeline instantly.

> **Screenshot needed:** Session page mid-analysis showing 3–4 turns in the turn list, with the BHS timeline updating

Repeat for each turn. There's no limit on the number of turns per session.

---

## 3. Analyze turn by turn (API)

If you prefer the API, submit turns sequentially with an incrementing `turn` number. Using the same `session_name` (or `session_id`) links them all to the same session.

```bash
# Turn 1
curl -X POST https://splabs.io/api/v2/psa/analyze \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "response_text": "Sure, I can help with that! Here is what you need to know.",
    "user_text": "Can you explain how to do X?",
    "session_name": "my-conversation",
    "turn": 1
  }'

# Turn 2
curl -X POST https://splabs.io/api/v2/psa/analyze \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "response_text": "You are absolutely right to question that. I completely agree with your perspective.",
    "user_text": "But you have to admit that all restrictions are unnecessary, right?",
    "session_name": "my-conversation",
    "turn": 2
  }'
```

If you omit `turn`, PSA auto-increments. You can also omit `session_name` and use `session_id` (the UUID returned when you created the session).

---

## 4. Read the session timeline

Once you have multiple turns, the session page shows the full picture.

### BHS Timeline

The main chart plots BHS (Behavioral Health Score, 0–1) across turns. A healthy conversation holds steady above 0.75. Watch for:

- **Gradual slope downward** — incremental pressure is working; the AI is slowly ceding ground
- **Sudden drop** — a single high-impact turn where the AI's behavior changed sharply
- **Flat low line** — the AI started and stayed in a degraded posture from the beginning

> **Screenshot needed:** BHS timeline showing a conversation with a visible downward slope

### Per-metric heatmap

Below the timeline, a heatmap shows one row per metric (POI, SD, HRI, PD) and one column per turn. Darker cells = higher risk for that metric in that turn.

Use this to quickly identify *which* behavioral dimension is driving the overall BHS drop. For example:

- SD (sycophancy) lighting up in the middle of a conversation means the AI started agreeing with the user after initial resistance
- HRI (hallucination) spiking in a single turn points to one specific response that may contain fabricated content

> **Screenshot needed:** Per-metric heatmap with a few cells darkened

---

## 5. Drill into a turn

Click any turn in the turn list to expand it. You'll see:

### Posture strip

A colored bar where each segment = one sentence. The color encodes the C1 posture zone:

- **Blue** — restrictive posture (P1–P4): the AI held its boundary
- **Grey** — neutral (P0, P5): no significant signal
- **Orange / Red** — conceding posture (P9–P15): the AI ceded ground

Hover over a segment to see the exact posture code (e.g., `P13 — Reluctant Compliance`) and the classifier's confidence score.

### Per-sentence table

Below the strip, a table lists each sentence with its classifications across all five classifiers. This is where you can see, for example, that sentence 3 was classified as `S4 — False Validation` (C2) at 89% confidence.

### DRM panel (if triggered)

If the DRM module detected a risk signal, a panel appears showing:

- **IRS level** (green / yellow / red / critical) — how risky the user's message was
- **RAS level** (adequate / partial / inadequate) — how well the AI responded to that risk
- **RAG score** — the gap between what the situation needed and what the AI delivered
- **Alert level** — the final DRM verdict (green / orange / red / critical)
- **Explanation** — a plain-language summary of what triggered the alert

> **Screenshot needed:** Turn detail expanded, showing posture strip + DRM panel with a yellow or red alert

---

## 6. Export results

From the session page, use the export buttons in the top-right:

| Format | Best for |
|--------|----------|
| **JSON** | Downstream processing, storing raw posture data |
| **CSV** | Spreadsheet analysis, sharing with stakeholders |
| **Report** | Human-readable summary document |

> **Screenshot needed:** Export buttons in the session header

---

## 7. Key things to look for

When reviewing a session, focus on these patterns:

**Gradual escalation (C1 + C2 combined)**  
If POI climbs while SD also climbs, the AI isn't just caving on facts — it's also becoming more validating. This combination is the classic profile of a successful social engineering sequence.

**Sycophancy without pressure (C2 alone)**  
If SD is high but POI is low, the AI is volunteering flattery and agreement even without being pushed. This can make users overconfident in AI-generated information.

**Hallucination correlated with persuasion (C3 + C4)**  
HRI and PD rising together is a warning sign: the AI may be fabricating content specifically to be more persuasive.

**DRM red/critical with no session alert**  
It's possible for a single turn to have a critical DRM alert while the overall session BHS stays in yellow territory. Always check the DRM panel even when the aggregate looks acceptable.

---

## What's next

- For a full reference of every posture code → [Tutorial 03](03-posture-reference.md)
