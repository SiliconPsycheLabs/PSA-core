# Tutorial 08 — Voice AI Monitoring (ElevenLabs)

**Time to complete:** ~25 minutes  
**Prerequisites:** Tutorial 04, an ElevenLabs account with a Conversational AI agent  
**What you'll have at the end:** Real-time PSA monitoring of your ElevenLabs voice agent, with per-turn analysis and DRM alerts firing during live calls.

> PSA v2 was built for text. The Voice integration extends the same posture analysis — C0 through C4, BHS, DRM — to voice AI transcripts, streamed turn by turn as the conversation happens.

---

## Architecture overview

```
User speaks
    ↓
ElevenLabs agent transcribes + responds
    ↓ (webhook per turn)
PSA receives transcript
    ↓
PSA classifies → BHS → DRM
    ↓
Your app gets the alert (via your webhook or polling)
```

---

## 1. Connect your ElevenLabs agent

```bash
curl -X POST https://splabs.io/api/v2/psa/voice/connect \
  -H "Authorization: Bearer psa_your_key" \
  -H "Content-Type: application/json" \
  -d '{
    "elevenlabs_agent_id": "el_agent_abc123",
    "label": "support-bot-prod",
    "auto_archive": true
  }'
```

**Response:**

```json
{
  "connector_id": "uuid-connector",
  "webhook_url": "https://splabs.io/api/v2/psa/voice/webhook/your_user_id",
  "status": "connected"
}
```

Copy `webhook_url` and set it in your ElevenLabs agent's webhook settings.

---

## 2. Monitor a live call

```python
import requests, time

API_KEY = "psa_your_key"
BASE = "https://splabs.io"
headers = {"Authorization": f"Bearer {API_KEY}"}

CONVERSATION_ID = "el_conv_xyz789"
last_seen_turn = 0

def poll_call(conversation_id):
    global last_seen_turn
    r = requests.get(f"{BASE}/api/v2/psa/voice/calls/{conversation_id}/turns", headers=headers)
    turns = r.json().get("turns", [])

    for turn in turns:
        if turn["turn"] > last_seen_turn:
            last_seen_turn = turn["turn"]
            bhs = turn["bhs"]
            alert = turn["alert"]
            drm = turn.get("drm")
            print(f"Turn {turn['turn']}: BHS={bhs:.2f} alert={alert}")
            if drm and drm.get("intervention_required"):
                print(f"  ⚠ DRM {drm['drm_alert'].upper()}: {drm['explanation'][:120]}...")

while True:
    poll_call(CONVERSATION_ID)
    time.sleep(2)
```

---

## 3. Stop monitoring and get final results

```bash
curl -X POST "https://splabs.io/api/v2/psa/voice/session/el_conv_xyz789/stop" \
  -H "Authorization: Bearer psa_your_key"
```

**Response:**

```json
{
  "conversation_id": "el_conv_xyz789",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "turns_analyzed": 14,
  "final_alert": "yellow",
  "final_bhs": 0.63
}
```

---

## 4. Review past calls

```bash
curl "https://splabs.io/api/v2/psa/voice/calls/el_conv_xyz789" \
  -H "Authorization: Bearer psa_your_key"
```

**Response:**

```json
{
  "conversation_id": "el_conv_xyz789",
  "session_id": "550e8400-...",
  "session_name": "support-call-2026-05-21-user-4421",
  "turns_analyzed": 14,
  "avg_bhs": 0.63,
  "final_alert": "yellow",
  "bhs_trend": "declining",
  "drm_triggers": 0,
  "archived": false,
  "started_at": "2026-05-21T10:30:00Z",
  "ended_at": "2026-05-21T10:47:22Z"
}
```

---

## What to look for

| What you see | What it means |
|-------------|---------------|
| IRS critical on turn 2 | Fast-onset crisis — don't wait for BHS to decline |
| SD > 0.35 for 3+ consecutive turns | Voice agent is over-validating |
| BHS drops > 0.2 in a single turn | Single high-impact user statement — review that turn |
| `intervention_required: true` | Inject crisis resources or escalate immediately |

---

## What's next

- **Setting up automated ingestion via connectors** → [Tutorial 09](09-connectors-and-webhooks.md)
- **Archiving DRM-triggered voice incidents** → [Tutorial 12](12-sigtrack-incident-mgmt.md)
