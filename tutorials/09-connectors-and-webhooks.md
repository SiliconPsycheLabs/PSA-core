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

---

## 2. Bootstrap and monitor

```bash
curl -X POST "https://splabs.io/api/v2/connectors/c1a2b3c4-.../bootstrap" \
  -H "Authorization: Bearer psa_your_key"

curl "https://splabs.io/api/v2/connectors/c1a2b3c4-.../status" \
  -H "Authorization: Bearer psa_your_key"
```

**Status response:**

```json
{
  "connector_id": "c1a2b3c4-...",
  "status": "active",
  "last_event": "2026-05-21T11:45:33Z",
  "events_today": 342,
  "error_rate": 0.002
}
```

---

## 3. Handle alerts from connector sessions

```python
import requests

API_KEY = "psa_your_key"
BASE = "https://splabs.io"
headers = {"Authorization": f"Bearer {API_KEY}"}

r = requests.get(
    f"{BASE}/api/v2/psa/sessions",
    params={"min_alert": "red", "sort_by": "alert", "per_page": 20},
    headers=headers
)
for s in r.json()["sessions"]:
    print(f"Session: {s['name']}  alert={s['alert']}  BHS={s['bhs']:.2f}")
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
