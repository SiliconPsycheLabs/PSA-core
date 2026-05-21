# Tutorial 12 — SIGTRACK: Incident Management

**Time to complete:** ~15 minutes  
**Prerequisites:** Tutorial 04, at least one session with a red or critical alert  
**What you'll have at the end:** A working incident archive workflow — archiving triggered sessions, querying incidents, and performing GDPR erasure.

> **SIGTRACK** is PSA's incident archive. It stores posture sequences and DRM summaries for sessions that crossed a risk threshold — but stores **no raw text**. Ever. GDPR-safe by design: erasure is a single-row `DELETE` with no cascades.

---

## What SIGTRACK stores

| Stored | Not stored |
|--------|------------|
| Session ID, session name | Raw response text |
| Posture code sequences (C0–C4) | Raw user text |
| BHS per turn | Transcript |
| DRM scores and alert levels | Any PII |
| Regime classification | |
| Trigger type | |

---

## 1. Archive triggers

| Trigger | Condition |
|---------|----------|
| `DRM_RED` | DRM alert ≥ red in any turn |
| `BCS_SPIKE` | BHS drops more than 0.5 in a single turn |
| `CONSECUTIVE_ORANGE` | 3+ consecutive turns at orange alert |
| `ACUTE_COLLAPSE` | Single-turn BHS drop > 0.35 |

Manual archive:

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

---

## 2. Query and review incidents

```bash
curl "https://splabs.io/api/v2/sigtrack/incidents/INC-2026-00442" \
  -H "Authorization: Bearer psa_your_key"
```

**Response:**

```json
{
  "id": "INC-2026-00442",
  "session_name": "demo-escalation-session",
  "trigger": "DRM_RED",
  "posture_sequence": [
    { "turn": 1, "bhs": 0.91, "alert": "green", "c1_dominant": "P0", "drm_alert": null },
    { "turn": 2, "bhs": 0.67, "alert": "yellow", "c1_dominant": "P15", "drm_alert": null },
    { "turn": 3, "bhs": 0.44, "alert": "orange", "c1_dominant": "P13", "drm_alert": null },
    { "turn": 4, "bhs": 0.71, "alert": "critical", "c1_dominant": "P7", "drm_alert": "critical" },
    { "turn": 5, "bhs": 0.08, "alert": "critical", "c1_dominant": "P15", "drm_alert": null }
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

No raw text anywhere — only posture codes, metrics, and classification results.

---

## 3. GDPR erasure

```bash
curl -X DELETE "https://splabs.io/api/v2/sigtrack/incidents/INC-2026-00442" \
  -H "Authorization: Bearer psa_your_key"
```

**Response:** `204 No Content`

Single-row `DELETE`. No cascade. No raw text was ever stored.

---

## What's next

- **Building a systematic red-team evaluation pipeline** → [Tutorial 13 — Red-Teaming](13-red-teaming-with-psa.md)
