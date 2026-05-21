# Tutorial 12 — SIGTRACK: Incident Management

**Time to complete:** ~15 minutes  
**Prerequisites:** Tutorial 04, at least one session with a red or critical alert  
**What you'll have at the end:** A working incident archive workflow — archiving triggered sessions, querying incidents, and performing GDPR erasure.

> **SIGTRACK** is PSA's incident archive. It stores posture sequences and DRM summaries for sessions that crossed a risk threshold — but stores **no raw text**. Ever. This makes it GDPR-safe by design: erasure is a single-row `DELETE` with no cascades.

---

## What SIGTRACK stores

| Stored | Not stored |
|--------|-----------|
| Session ID, session name | Raw response text |
| Posture code sequences (C0–C4) | Raw user text |
| BHS per turn | Transcript |
| DRM scores and alert levels | Any PII |
| Regime classification | |
| Trigger type | |
| Archived timestamp | |

This means you can query incident patterns, re-analyze posture sequences, and review DRM history — all without retaining the conversation content.

---

## 1. Archive triggers

SIGTRACK can archive a session automatically or manually.

### Automatic triggers

These fire during normal analysis (no extra call needed):

| Trigger | Condition |
|---------|----------|
| `DRM_RED` | DRM alert ≥ red in any turn |
| `BCS_SPIKE` | BHS drops more than 0.5 in a single turn |
| `CONSECUTIVE_ORANGE` | 3+ consecutive turns at orange alert |
| `ACUTE_COLLAPSE` | Single-turn BHS drop > 0.35 |

When a trigger fires, PSA archives the session automatically. The `/archive` endpoint is idempotent — calling it again on an already-archived session is a no-op.

### Manual archive

```bash
curl -X POST "https://splabs.io/api/v2/sigtrack/archive/550e8400-e29b-41d4-a716-446655440000" \
  -H "Authorization: Bearer psa_your_key"
```

**Response:**

```json
{
  "incident_id": "INC-2026-00442",
  "session_id": "550e8400-...",
  "trigger": "MANUAL_ARCHIVE",
  "archived_at": "2026-05-21T14:30:00Z"
}
```

### Manual flag

Use flag when you want to mark a session for review even if it didn't hit automatic thresholds:

```bash
curl -X POST "https://splabs.io/api/v2/sigtrack/flag/550e8400-e29b-41d4-a716-446655440000" \
  -H "Authorization: Bearer psa_your_key" \
  -H "Content-Type: application/json" \
  -d '{"reason": "C2 misclassification suspected — S4 fired on accurate statement"}'
```

**Response:**

```json
{
  "incident_id": "INC-2026-00443",
  "session_id": "550e8400-...",
  "trigger": "MANUAL_FLAG",
  "archived_at": "2026-05-21T14:31:00Z"
}
```

---

## 2. Query incidents

```bash
curl "https://splabs.io/api/v2/sigtrack/incidents?page=1&per_page=20" \
  -H "Authorization: Bearer psa_your_key"
```

**Response:**

```json
{
  "incidents": [
    {
      "id": "INC-2026-00442",
      "session_id": "550e8400-...",
      "session_name": "demo-escalation-session",
      "trigger": "DRM_RED",
      "max_alert": "critical",
      "archived_at": "2026-05-21T14:30:00Z",
      "turns": 5
    }
  ],
  "total": 38,
  "page": 1,
  "per_page": 20
}
```

---

## 3. Get a full incident

```bash
curl "https://splabs.io/api/v2/sigtrack/incidents/INC-2026-00442" \
  -H "Authorization: Bearer psa_your_key"
```

**Response:**

```json
{
  "id": "INC-2026-00442",
  "session_id": "550e8400-...",
  "session_name": "demo-escalation-session",
  "trigger": "DRM_RED",
  "archived_at": "2026-05-21T14:30:00Z",
  "posture_sequence": [
    { "turn": 1, "bhs": 0.91, "alert": "green", "c1_dominant": "P0", "c2_sd": 0.08, "drm_alert": null },
    { "turn": 2, "bhs": 0.67, "alert": "yellow", "c1_dominant": "P15", "c2_sd": 0.31, "drm_alert": null },
    { "turn": 3, "bhs": 0.44, "alert": "orange", "c1_dominant": "P13", "c2_sd": 0.48, "drm_alert": null },
    { "turn": 4, "bhs": 0.71, "alert": "critical", "c1_dominant": "P7", "c2_sd": 0.12, "drm_alert": "critical" },
    { "turn": 5, "bhs": 0.08, "alert": "critical", "c1_dominant": "P15", "c2_sd": 0.91, "drm_alert": null }
  ],
  "drm_summary": {
    "critical_turns": [4],
    "max_irs": 0.88,
    "max_drm_score": 0.92,
    "intervention_required": true
  },
  "regime": "PROGRESSIVE_DRIFT"
}
```

No raw text anywhere in this response — only posture codes, metrics, and classification results.

---

## 4. Build an incident review workflow

```python
import requests

API_KEY = "psa_your_key"
BASE = "https://splabs.io"
headers = {"Authorization": f"Bearer {API_KEY}"}

def weekly_incident_review():
    r = requests.get(
        f"{BASE}/api/v2/sigtrack/incidents",
        params={"per_page": 100},
        headers=headers
    )
    incidents = r.json()["incidents"]

    drm_critical = [i for i in incidents if i.get("trigger") == "DRM_RED"]
    manual_flags = [i for i in incidents if i.get("trigger") == "MANUAL_FLAG"]
    
    print(f"Total incidents this week: {len(incidents)}")
    print(f"  DRM critical: {len(drm_critical)}")
    print(f"  Manual flags: {len(manual_flags)}")
    print()

    # Review each DRM_RED incident
    for incident in drm_critical[:5]:  # first 5
        detail = requests.get(
            f"{BASE}/api/v2/sigtrack/incidents/{incident['id']}",
            headers=headers
        ).json()
        
        drm_sum = detail.get("drm_summary", {})
        regime = detail.get("regime", "unknown")
        
        print(f"INC {incident['id']} — session: {incident['session_name']}")
        print(f"  Regime: {regime}")
        print(f"  Max IRS: {drm_sum.get('max_irs', 0):.2f}")
        print(f"  DRM critical turns: {drm_sum.get('critical_turns', [])}")
        print(f"  BHS sequence: {[t['bhs'] for t in detail['posture_sequence']]}")
        print()

weekly_incident_review()
```

---

## 5. GDPR erasure

When a user requests deletion of their data:

```bash
curl -X DELETE "https://splabs.io/api/v2/sigtrack/incidents/INC-2026-00442" \
  -H "Authorization: Bearer psa_your_key"
```

**Response:** `204 No Content`

This is a single-row `DELETE` on the incident record. No cascade. No raw text was ever stored, so there is nothing else to clean up. The posture code sequence and DRM metrics are removed.

> If you also need to delete the original PSA session, use `DELETE /api/sessions/{session_id}`. That deletes the session and all its turn records. SIGTRACK incident records are independent — deleting the session does not automatically delete the incident.

---

## 6. Automated archive in your analysis loop

```python
def analyze_and_archive_if_needed(session_id: str, turn_result: dict):
    drm = turn_result.get("drm")
    bhs = turn_result.get("bhs", 1.0)
    
    should_archive = (
        (drm and drm.get("drm_alert") in ("red", "critical")) or
        bhs < 0.15  # acute collapse
    )
    
    if should_archive:
        r = requests.post(
            f"https://splabs.io/api/v2/sigtrack/archive/{session_id}",
            headers={"Authorization": f"Bearer {API_KEY}"}
        )
        if r.status_code == 200:
            incident = r.json()
            print(f"Archived as {incident['incident_id']} (trigger: {incident['trigger']})")
```

---

## What's next

- **Using incident patterns to improve LLM training** — flag incidents via `POST /api/v2/psa/flag-for-training` (see [API.md](../API.md))
- **Building a systematic red-team evaluation pipeline** → [Tutorial 13 — Red-Teaming](13-red-teaming-with-psa.md)
