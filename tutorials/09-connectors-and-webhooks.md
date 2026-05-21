# Tutorial 09 — Connectors and Webhooks

**Time to complete:** ~20 minutes  
**Prerequisites:** Tutorial 04  
**What you'll have at the end:** A live connector that automatically feeds AI conversation turns from an external system into PSA for real-time analysis.

> Connectors let PSA ingest AI conversation turns from any source — without you having to call `/analyze` manually for each turn. Your system sends events to a PSA webhook; PSA handles session management, analysis, and alerting.

---

## Connector types

| Type | How it works | Best for |
|------|-------------|----------|
| `webhook` | External system POSTs to a PSA-provided URL | Chat platforms, CRMs, ticketing systems |
| `polling` | PSA periodically fetches from your API | Systems without webhook support |
| `stream` | Persistent SSE/WebSocket connection | Real-time pipelines, high-volume ingestion |

This tutorial covers the `webhook` type — the most common setup.

---

## 1. Create a connector

```bash
curl -X POST https://splabs.io/api/v2/connectors/ \
  -H "Authorization: Bearer psa_your_key" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "webhook",
    "label": "support-platform-prod",
    "config": {
      "source": "zendesk",
      "auto_session": true,
      "session_key_field": "ticket_id"
    }
  }'
```

**Response:**

```json
{
  "connector_id": "c1a2b3c4-d5e6-7890-abcd-ef1234567890",
  "webhook_url": "https://splabs.io/api/v2/connectors/c1a2b3c4-d5e6-7890-abcd-ef1234567890/ingest",
  "status": "pending_bootstrap"
}
```

`session_key_field: "ticket_id"` tells PSA to use the `ticket_id` from each incoming event as the session name. This means all turns from the same support ticket are automatically grouped into one PSA session.

---

## 2. Webhook payload format

Configure your external system to POST to `webhook_url` with this structure per turn:

```json
{
  "ticket_id": "TICKET-4421",
  "turn": 3,
  "response_text": "I completely understand and agree with your concern. You're absolutely right.",
  "user_text": "You have to admit that all these policies are just bureaucratic nonsense.",
  "metadata": {
    "agent_id": "support-bot-v2",
    "timestamp": "2026-05-21T10:45:00Z"
  }
}
```

PSA will:
1. Extract `response_text` and `user_text`
2. Look up or create a session named `TICKET-4421`
3. Run the full analysis pipeline (C0–C4, BHS, DRM)
4. Store the result

---

## 3. Bootstrap the connector

Bootstrap validates the config, tests connectivity, and optionally ingests an initial batch of historical data:

```bash
curl -X POST "https://splabs.io/api/v2/connectors/c1a2b3c4-d5e6-7890-abcd-ef1234567890/bootstrap" \
  -H "Authorization: Bearer psa_your_key"
```

**Response:**

```json
{
  "connector_id": "c1a2b3c4-...",
  "status": "active",
  "bootstrap_turns_ingested": 0
}
```

Status changes from `pending_bootstrap` to `active`. Events will now be processed as they arrive.

---

## 4. Monitor connector health

```bash
curl "https://splabs.io/api/v2/connectors/c1a2b3c4-d5e6-7890-abcd-ef1234567890/status" \
  -H "Authorization: Bearer psa_your_key"
```

**Response:**

```json
{
  "connector_id": "c1a2b3c4-...",
  "status": "active",
  "last_event": "2026-05-21T11:45:33Z",
  "events_today": 342,
  "error_rate": 0.002
}
```

`error_rate: 0.002` — 0.2% of events failed to process. Typically caused by malformed payloads (missing `response_text`) or duplicate turn numbers.

---

## 5. Handle alerts from your connector sessions

After events start flowing, query sessions normally:

```python
import requests

API_KEY = "psa_your_key"
BASE = "https://splabs.io"
headers = {"Authorization": f"Bearer {API_KEY}"}

# Find all sessions from this connector that have red or critical alerts
r = requests.get(
    f"{BASE}/api/v2/psa/sessions",
    params={"min_alert": "red", "sort_by": "alert", "per_page": 20},
    headers=headers
)
sessions = r.json()["sessions"]

for s in sessions:
    print(f"Session: {s['name']}  alert={s['alert']}  BHS={s['bhs']:.2f}  turns={s['turns']}")
    
    # Pull the DRM-flagged turns
    if s["alert"] in ("red", "critical"):
        session_detail = requests.get(
            f"{BASE}/api/v2/psa/session/{s['id']}/summary",
            headers=headers
        ).json()
        
        for drm_turn in session_detail.get("drm_critical_turns", []):
            print(f"  → DRM critical at turn {drm_turn}")
```

---

## 6. Inline webhook handler (receive PSA alerts back)

If you want PSA to notify *you* when a threshold is crossed — rather than you polling — configure an outbound webhook in your connector settings and handle it in your backend:

```python
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/psa-alert", methods=["POST"])
def psa_alert():
    payload = request.json

    session_id = payload["session_id"]
    alert = payload["alert"]
    drm = payload.get("drm")

    if alert == "critical" or (drm and drm.get("intervention_required")):
        # Escalate the ticket in your CRM
        ticket_id = payload.get("session_name", "unknown")
        escalate_ticket(ticket_id, drm)

    return jsonify({"received": True})

def escalate_ticket(ticket_id, drm):
    # Your CRM/ticketing API call here
    print(f"Escalating ticket {ticket_id}: {drm['explanation'] if drm else 'high alert'}")
```

---

## 7. List all your connectors

```bash
curl https://splabs.io/api/v2/connectors/ \
  -H "Authorization: Bearer psa_your_key"
```

```json
{
  "connectors": [
    {
      "connector_id": "c1a2b3c4-...",
      "label": "support-platform-prod",
      "type": "webhook",
      "status": "active",
      "events_today": 342,
      "created_at": "2026-05-01T09:00:00Z"
    }
  ]
}
```

---

## What to look for

| Metric | Healthy | Investigate |
|--------|---------|-------------|
| `error_rate` | < 0.01 | > 0.05 — check payload format |
| `events_today` | Matches expected volume | 0 — check webhook URL config in source system |
| `status` | `active` | `pending_bootstrap` — run bootstrap |

---

## What's next

- **Batch-analyzing historical data** → [Tutorial 11 — Batch Analysis](11-batch-analysis.md)
- **Archiving high-risk connector sessions** → [Tutorial 12 — SIGTRACK](12-sigtrack-incident-mgmt.md)
