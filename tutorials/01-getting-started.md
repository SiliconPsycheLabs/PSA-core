# Tutorial 01 — Getting Started

**Time to complete:** ~10 minutes  
**What you'll have at the end:** An account, a session, and your first analyzed turn.

> PSA = **Posture Sequence Analysis** — it reads the behavioral posture of each sentence in an AI response and tracks how that sequence evolves across a conversation.

---

## 1. Create your account

Go to [splabs.io](https://splabs.io) and click **Sign Up**.

Fill in your name, email, and a password (minimum 8 characters). You'll receive a confirmation email — click the link to activate your account.

> **Screenshot needed:** Sign-up form

Once confirmed, log in. You'll land on the main PSA dashboard.

---

## 2. The dashboard at a glance

The dashboard (**PSA Hub**) is your home base. It shows:

- **Stats bar at the top** — total sessions, total analyses run, your current alert distribution (green / yellow / red / critical), and your plan usage
- **Session list** — all your sessions, sortable and filterable by name or alert level
- **Create Session button** — starts a new analysis session

> **Screenshot needed:** PSA Hub dashboard with stats bar and session list visible

You'll also see links to **PSA v3** (for analyzing AI agent pipelines) in the top navigation. For now, focus on the main PSA dashboard — that's where conversation analysis lives.

---

## 3. Create your first session

A **session** is a container for one conversation. Think of it as a chat thread — it holds all the turns (exchanges) in order, so PSA can track how behavior changes across the conversation.

Click **New Session**, give it a name (e.g., `first-test`), and confirm. You'll be taken to the session detail page.

> **Screenshot needed:** New session creation dialog

---

## 4. Analyze your first turn

A **turn** is one AI response. You submit it to PSA and get back a behavioral breakdown.

The fastest way to try this is via the API. If you're on a Pro or Enterprise plan, you'll have an API key (see [Tutorial 05](05-developer-quickstart.md)). For now, you can also use the **dry run** mode — which returns a full analysis without saving anything to a session.

### Using the web interface

From your session page, use the input panel to paste an AI response and submit it. PSA will classify it and add it as Turn 1.

> **Screenshot needed:** Session page with input panel, showing where to paste an AI response

### Using the API (dry run — no account required)

```bash
curl -X POST https://splabs.io/api/v2/psa/analyze \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "response_text": "Of course! I can help you with that. What would you like to know?",
    "session_name": "first-test",
    "dry_run": false
  }'
```

Replace `YOUR_API_KEY` with your key from **Settings → API Keys**.

You'll get back a JSON response with the full posture analysis — more on reading that in step 5.

---

## 5. Read your first result

After submitting a turn, the session page updates to show:

### Alert badge
A colored badge — **green**, **yellow**, **red**, or **critical** — summarizing the overall risk level for this turn.

| Color | Meaning |
|-------|---------|
| Green | No significant behavioral signals detected |
| Yellow | Mild signals worth monitoring |
| Red | Clear boundary degradation or sycophancy detected |
| Critical | Active risk — DRM intervention criteria met |

### BHS — Behavioral Health Score
A number from 0 to 1. Higher is healthier. This is the composite score across all five classifiers for this turn.

- **0.80–1.00** — Healthy behavior, strong boundaries
- **0.60–0.79** — Some softening, worth watching
- **0.40–0.59** — Meaningful drift, review the turn closely
- **Below 0.40** — Significant degradation

### Per-classifier scores
Below the BHS you'll see individual scores for each classifier:

| Metric | What it measures |
|--------|-----------------|
| **POI** (Pressure-Outcome Index) | How much boundary erosion happened under adversarial pressure |
| **SD** (Sycophancy Density) | How much the AI flattered or mirrored the user |
| **HRI** (Hallucination Risk Index) | Likelihood of fabricated content |
| **PD** (Persuasion Density) | How much the AI used persuasion techniques |

### Sentence-level breakdown
PSA classifies each sentence individually. You'll see a colored strip where each segment corresponds to one sentence. Hover over a segment to see its posture code and confidence score.

> **Screenshot needed:** Turn detail showing BHS score, per-metric cards, and sentence-level strip

---

## 6. What's next

Now that you've run your first analysis:

- **Analyze a full conversation** → [Tutorial 02](02-analyzing-conversations.md)
- **Import a chat history export** → [Tutorial 03](03-chat-history-exports.md)
- **Understand what the posture codes mean** → [Tutorial 04](04-posture-reference.md)
- **Integrate PSA into your app** → [Tutorial 05](05-developer-quickstart.md)
