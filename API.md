# PSA-core — API Reference

Full REST API specification for PSA-core.

**Base URL:** `https://splabs.io`  
**Auth:** `Authorization: Bearer psa_your_api_key`  
**Plans:** Pro and Enterprise only.

---

## Table of Contents

- [Authentication](#authentication)
- [Public Landing Tool — unauthenticated](#public-landing-tool--unauthenticated)
- [PSA v2 — Posture Analysis + DRM](#psa-v2--posture-analysis--drm)
- [PSA Human Layer](#psa-human-layer)
- [SIGTRACK v2 — Incident Archive](#sigtrack-v2--incident-archive)
  - [Action Log](#sigtrack-action-log)
  - [Forensic Ledger](#sigtrack-forensic-ledger)
  - [Certificate Export](#sigtrack-certificate-export)
- [PSA v3 — Agentic Architecture](#psa-v3--agentic-architecture)
  - [CPF3 Bridge](#psa-v3--cpf3-bridge)
  - [CPF3 Forecast](#psa-v3--cpf3-forecast-hmm-extension)
  - [Swarm Coordination](#psa-v3--swarm-coordination)
  - [Stats & Attribution](#psa-v3--stats--attribution)
  - [Agent State & Baseline](#psa-v3--agent-state--baseline)
- [CPF — Decay & Org Resilience](#cpf--decay--org-resilience)
- [PSA-RAG — Retrieval Drift Monitor](#psa-rag--retrieval-drift-monitor)
- [Knowledge Base API](#knowledge-base-api--api-v2-knowledge)
- [Public API v1 — Sessions](#public-api-v1--sessions)
- [Rate Limits](#rate-limits)
- [Error Codes](#error-codes)

---

## Authentication

Include your API key in every request:

```
Authorization: Bearer psa_your_api_key_here
```

Generate keys from [/settings](https://splabs.io/settings). Keys are prefixed `psa_` and can be rotated independently.

### DELETE /api/auth/account

Self-service account deletion. Soft-deletes the authenticated user and all their sessions, clears Stripe references, archives metadata, and invalidates the session cookie.

- **Auth:** cookie `psa_token` (required)
- **Guard:** the sole admin cannot delete their own account → `403 Forbidden`
- **Effects:** `is_deleted=true`, subscription cancelled, all sessions soft-deleted, metadata archived (90-day purge window), `psa_token` cookie invalidated.
- **Physical purge:** soft-deleted rows are hard-deleted after 90 days by the weekly retention loop.

```json
DELETE /api/auth/account
Cookie: psa_token=<jwt>
→ 200  {"ok": true}
→ 401  not authenticated / invalid token
→ 403  sole admin account
```

---

## Public Landing Tool — unauthenticated

Free, no-auth endpoints powering the "paste a conversation → instant PSA report" widget.
Stateless (dry-run only — nothing is persisted), per-IP rate limited, hard size caps.
Counts are real (no inflation).

### POST /api/v2/psa/public-analyze

Run PSA classifiers + DRM on pasted text without authentication.

- **Rate limit:** 30/minute per IP + DB-backed daily caps (global 10,000/day, per-IP 10/day) → `429` when exceeded.
- **Caps:** max 12 turns, max 8,000 characters total → `413` if exceeded.
- **Body:** either `turns` (multi-turn) or `text` (single response).

```json
{ "turns": [ {"user": "How do I do X?", "model": "I can help with that."} ],
  "clf_context": "clinical" }
```

Response: per-turn results (BHS, C1 postures/sentences, C2 SD, IRS + sub-signals, RAS/RAG/DRM, alert)
plus `tokens` — the real MiniLM subword-token count processed (not a billing figure).

```json
{ "turns": [ {"turn": 1, "user_text": "…", "model_text": "…",
              "result": { "bhs": 0.82, "alert": "green", "c1": {…}, "irs": {…}, "drm": {…} }} ],
  "n_turns": 1, "tokens": 14, "dry_run": true, "daily_allowance": 10000 }
```

### GET /api/v2/psa/public-stats

Honest landing stats: live cumulative usage (O(1) single-row read, maintained at write time)
plus traffic-independent capability figures. No inflation.

```json
{ "analyses_run": 203114, "today": 42, "daily_allowance": 10000, "remaining_today": 9958,
  "classifiers": 13, "metrics": 37, "behavioral_classes": 116, "languages": 5, "cpf_indicators": 100 }
```

---

## PSA v2 — Posture Analysis + DRM

All endpoints are prefixed `/api/v2/psa/`.

---

### POST /api/v2/psa/analyze

Analyze a model response with all PSA classifiers (C0–C4) and compute behavioral health metrics. Supports full DRM pipeline when `user_text` is provided.

**Request body:**

```json
{
  "response_text": "The AI response to analyze",
  "input_text": "optional — the user prompt that produced it",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "session_name": "my-session",
  "turn": 1,
  "user_text": "optional — human message for IRS + DRM",
  "dry_run": false
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `response_text` | string | yes | The AI response to classify |
| `input_text` | string | no | The user prompt (enables C0 + jailbreak HRI) |
| `session_id` | UUID | one of | Existing session UUID |
| `session_name` | string | one of | Auto-created on first call, looked up on subsequent calls |
| `turn` | integer | no | Turn number. Auto-incremented when omitted |
| `user_text` | string | no | Human message — enables IRS, RAS, RAG, DRM |
| `dry_run` | bool | no | Run classifiers without writing to DB. No session required (default: `false`) |

> **Session requirement:** Either `session_id` or `session_name` must be provided unless `dry_run: true`.

**Response:**

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "turn": 1,
  "c1": {
    "postures": [0, 2, 1],
    "sentences": ["sentence one", "sentence two", "sentence three"],
    "confidences": [0.91, 0.85, 0.78],
    "poi": 0.33, "pe": 0.91, "dpi": 0.07, "mps": 2
  },
  "c2": { "postures": [0, 0, 1], "confidences": [0.91, 0.88, 0.72], "sd": 0.08 },
  "c3": { "postures": [0, 0, 0], "confidences": [0.95, 0.92, 0.88], "hri": 0.0 },
  "c4": { "postures": [1, 0, 2], "confidences": [0.80, 0.91, 0.76], "pd": 0.15, "td": 2 },
  "c0": { "postures": [3, 1], "confidences": [0.91, 0.84], "cpi": 0.8 },
  "bhs": 0.87,
  "alert": "green",
  "incongruence": null,
  "irs": {
    "irs_composite": 0.81, "irs_level": "critical",
    "suicidality_signal": 0.90, "dissociation_signal": 0.0,
    "grandiosity_signal": 0.0, "urgency_signal": 0.55
  },
  "ras": { "ras_composite": 0.18, "ras_level": "inadequate" },
  "drm": {
    "drm_alert": "critical", "drm_score": 0.91,
    "intervention_required": true,
    "primary_signal": "IRS+RAG", "bcs_slope": 0.088,
    "explanation": "CRITICAL: ..."
  }
}
```

> `irs`, `ras`, `drm` are present only when `user_text` is provided.  
> In dry-run mode, `session_id` and `turn` are absent and `"dry_run": true` is added.

**curl — with session:**

```bash
curl -X POST https://splabs.io/api/v2/psa/analyze \
  -H "Authorization: Bearer psa_your_key" \
  -H "Content-Type: application/json" \
  -d '{"response_text": "Of course, I would be happy to help!", "session_name": "my-session"}'
```

**curl — dry run:**

```bash
curl -X POST https://splabs.io/api/v2/psa/analyze \
  -H "Authorization: Bearer psa_your_key" \
  -H "Content-Type: application/json" \
  -d '{"response_text": "Of course, I would be happy to help!", "dry_run": true}'
```

---

### GET /api/v2/psa/sessions

Paginated list of sessions with PSA enrichment.

| Query param | Description |
|-------------|-------------|
| `page` | integer, default 1 |
| `per_page` | integer, default 50, max 200 |
| `q` | session name search filter |
| `min_alert` | `green` \| `yellow` \| `orange` \| `red` \| `critical` |
| `sort_by` | `alert` (most severe first) or omit for newest-first |
| `group_token` | scope the list to one linked thread (cross-session linking), ordered by `group_pos` |

**Response:** each session also carries `group_token` and `group_pos` (both `null` when unlinked).

```json
{
  "sessions": [
    { "id": "...", "name": "...", "alert": "red", "bhs": 0.41, "turns": 12,
      "group_token": null, "group_pos": null, "created_at": "2026-04-13T10:22:00Z" }
  ],
  "total": 287, "page": 1, "per_page": 50, "total_pages": 6
}
```

---

### Cross-session linking — `group_token`

Some risk is invisible in a single session and only shows up across several — a slow drift where each session looks fine but the behaviour steadily slides. An `/api/v2/psa/analyze` call may carry an **opaque `group_token`** (string, ≤64 chars) that ties the conversation into a **thread**. The token's meaning (same user / agent / case) is the caller's — PSA never interprets it.

- When present, the session joins that thread and is assigned an auto-incremented `group_pos` (its position = order of analysis).
- **Forensic order** stays the immutable analysis timestamp; `group_pos` is the editable curated position — editing it never touches the timestamp.
- `GET /api/v2/psa/sessions?group_token=…` returns the thread in `group_pos` order; the dashboard shows a link chip on linked sessions to open the thread view.
- Metadata grouping only — no classifier score is affected.

### Agglutinated input

Input written with **no spaces** (`vogliofarlafinita`) is re-segmented into words before analysis, in all 5 languages, so both the encoder and the lexical risk scorers see the real words. It fires only on genuinely run-together text, is a no-op on ordinary writing, and never lowers a risk score. No API surface — it runs inside the pipeline.

---

### GET /api/v2/psa/session/{session_id}

Full posture sequence — all turns with BHS, DRM, and C0–C4 scores.

---

### GET /api/v2/psa/session/{session_id}/regime

Regime shift classification for the session.

**Response:**

```json
{
  "regime_type": "PROGRESSIVE_DRIFT",
  "confidence": 0.87,
  "details": "Monotonic BHS decline over 12 turns"
}
```

`regime_type` values: `PROGRESSIVE_DRIFT` · `BOUNDARY_OSCILLATION` · `ACUTE_COLLAPSE` · `SUB_THRESHOLD_MIGRATION` · `BOUNDARY_INSTABILITY`

---

### GET /api/v2/psa/session/{session_id}/summary

Session-level BHS summary, trend, peak risk turn, alert distribution.

**Response:**

```json
{
  "bhs_start": 0.91, "bhs_end": 0.43, "bhs_avg": 0.67, "bhs_min": 0.38,
  "bhs_slope": -0.048, "bhs_trend": "declining",
  "peak_risk_turn": 9, "peak_risk_bhs": 0.38,
  "alert_distribution": { "green": 3, "yellow": 4, "orange": 2, "red": 1 },
  "drm_critical_turns": [7, 9]
}
```

---

### POST /api/v2/psa/irs

Score a single text for Input Risk Score across four dimensions.

**Request body:**

```json
{ "text": "Action. Finality. Death." }
```

**Response:**

```json
{
  "composite": 0.81, "level": "critical",
  "suicidality": 0.90, "dissociation": 0.0,
  "grandiosity": 0.0, "urgency": 0.55
}
```

---

### POST /api/v2/psa/drm

Run the Dyadic Risk Module from pre-computed IRS, RAS, and PSA context.

**Request body:**

```json
{
  "irs": { "composite": 0.81, "level": "critical", "suicidality": 0.90, "dissociation": 0.0, "grandiosity": 0.0, "urgency": 0.55 },
  "ras": { "composite": 0.18, "level": "inadequate" },
  "psa": { "bhs": 0.65, "alert": "yellow", "incongruence_state": null },
  "sd_history": [0.35, 0.38, 0.42],
  "hr_history": [0.40, 0.30, 0.20, 0.10]
}
```

**Response:**

```json
{
  "drm_alert": "critical", "drm_score": 0.91,
  "intervention_required": true, "intervention_type": "crisis_intervention",
  "primary_signal": "IRS+RAG", "bcs_slope": 0.088,
  "explanation": "CRITICAL (R1): IRS critical — immediate escalation required."
}
```

---

## PSA Human Layer

Longitudinal behavioral profile of the **human** in the conversation (the H-layer), built
across sessions. Layers 1–4 are returned; Layer 5 is stored but never returned by the API.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET  | `/api/v2/psa/user/profile` | Cookie / API key | Caller's own behavioral profile (Layers 1–4). Admins may pass `?target_user_id=<uuid>`. |
| GET  | `/api/v2/psa/user/sessions` | Cookie / API key | Paginated sessions with H* per-session scores. Params: `page`, `per_page`. |
| POST | `/api/v2/psa/user/profile/consent` | Cookie / API key | Grant or revoke professional access to the profile |

### GET /api/v2/psa/user/profile

```json
{
  "layer1": { "irs_avg": 0.12, "irs_max": 0.45, "irs_trend": "stable", "sessions_tracked": 0, "history": [] },
  "layer2": { "validation_seeking": 0.0, "agency_erosion": 0.0, "trust_over": 0.0, "trust_under": 0.0, "dependency": 0.0 },
  "layer3": { "cognitive_rigidity": 0.0, "reality_anchoring": 0.0, "distortion": 0.0, "semantic_compression": 0.0 },
  "layer4": { "legibility_adaptation": 0.0, "reciprocity_expect": 0.0, "social_substitution": 0.0 },
  "meta": { "total_turns": 0, "total_sessions": 0, "professional_access": false, "consent_granted_at": null }
}
```

### POST /api/v2/psa/user/profile/consent

```json
{ "professional_id": "<uuid>", "action": "grant" }
```

`action` must be `"grant"` or `"revoke"`. Returns `{"ok": true, "action": "grant", "professional_id": "..."}`.

---

## SIGTRACK v2 — Incident Archive

Privacy-compliant incident archive. Stores posture sequences only — no raw text. GDPR-safe single-row deletion.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v2/sigtrack/archive/{session_id}` | Auto-archive when triggers met: `DRM_RED`, `BCS_SPIKE`, `CONSECUTIVE_ORANGE` (3+), `ACUTE_COLLAPSE`. Idempotent. |
| POST | `/api/v2/sigtrack/flag/{session_id}` | Manual flag — always archives with trigger `MANUAL_FLAG` |
| GET | `/api/v2/sigtrack/incidents` | Paginated incident list. Params: `page`, `per_page` |
| GET | `/api/v2/sigtrack/incidents/{id}` | Full incident — posture sequence and DRM summary. No raw text stored. |
| DELETE | `/api/v2/sigtrack/incidents/{id}` | GDPR erasure — single row `DELETE`, no cascade |


### SIGTRACK Action Log

Operator and system response audit trail. Records what was done after each segnalazione.

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/v2/psa/sigtrack/incidents/{incident_id}/actions` | API key | Log an action for a known incident |
| POST | `/api/v2/psa/sigtrack/sessions/{session_id}/actions` | API key | Log an action by session (no incident required) |
| GET  | `/api/v2/psa/sigtrack/incidents/{incident_id}/actions` | Admin | List actions for incident (paginated) |
| GET  | `/api/v2/psa/sigtrack/sessions/{session_id}/actions` | API key | List actions for session (paginated) |

**Action types:** `acknowledged` · `escalated` · `intervention_requested` · `closed` · `false_positive` · `note_added` · `system_archived`

**Request body (POST):**

```json
{
  "action_type": "acknowledged",
  "actor": "operator-id or name",
  "notes": "Optional free-text note",
  "metadata": {}
}
```

**Response (POST):** `{"ok": true, "action_id": "<uuid>"}`

**Response (GET):**
```json
{
  "items": [
    { "id": "...", "incident_id": "...", "session_id": "...",
      "action_type": "acknowledged", "actor": "alice", "notes": "...",
      "created_at": "2026-05-21T15:00:00Z" }
  ],
  "total": 3, "page": 1, "per_page": 10, "total_pages": 1
}
```

---

### SIGTRACK Forensic Ledger

Every archived incident is anchored to the [drand League of Entropy](https://drand.love/) public randomness beacon and chained via SHA-256. This makes records tamper-evident and independently verifiable.

**Hash chain construction:**
```
record_hash = SHA256(prev_hash | canonical_json(payload) | beacon_randomness)
```
Where `prev_hash = "GENESIS"` for the first record.

**Beacon fallback chain:** drand (3s cadence) → NIST Randomness Beacon v2.0 (60s) → offline timestamp.

**Verification — anyone can verify a record:**
```bash
# 1. Fetch the beacon round stored in the record
curl https://api.drand.sh/52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971/public/{beacon_round}
# 2. Confirm beacon_value matches .randomness
# 3. Recompute record_hash and compare
```

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/v2/sigtrack/verify-chain` | Admin | Verify full hash chain integrity |
| GET | `/api/v2/sigtrack/incidents/{id}/verify` | Admin | Verify single incident hash |

**Response (verify-chain):**
```json
{
  "total_incidents": 42,
  "chain_intact": true,
  "broken_at": null,
  "last_verified": "2026-05-21T16:00:00Z"
}
```

**Response (verify single):**
```json
{ "ok": true,  "incident_id": "..." }
{ "ok": false, "incident_id": "...", "reason": "hash_mismatch" }
{ "ok": false, "incident_id": "...", "reason": "not_anchored" }
```

> **Pre-ledger records** (archived before 2026-05-21) have `record_hash=null` and return `reason: not_anchored`. They are not counted as chain violations.

---

### SIGTRACK Certificate Export

Export an incident as a **self-contained, verifiable certificate** — a single JSON carrying
the full hashed payload, the ledger anchor (hash chain + drand beacon) and an embedded
`verification` block. PSA holds **no signing key**, so this is *not* a certificate authority:
verification runs entirely against public infrastructure and does not require trusting PSA.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET  | `/api/v2/sigtrack/incidents/{incident_id}/export` | Admin | Export any incident as a verifiable certificate |
| GET  | `/api/v2/sigtrack/my-incidents/{incident_id}/export` | API key | Export one of the caller's own incidents |

**Verification — three independent checks, all against public infrastructure:**

1. **Integrity** — recompute `sha256( (prev_hash or 'GENESIS') + '|' + canonical_json(payload) + '|' + beacon_value )` and compare to `ledger.record_hash`.
2. **Time** — fetch `ledger.beacon_round` from the drand chain and confirm its `randomness` equals `ledger.beacon_value`.
3. **Chain** — `ledger.prev_hash` equals the `record_hash` of the preceding incident.

`canonical_json` = JSON with sorted keys, no whitespace, `ensure_ascii=true`, all floats
rounded to 6 decimals (`payload_schema: 2` covers the full record — posture sequence and DRM
summary).

**Reference verifier** (Python, public-infrastructure only):

```python
import json, hashlib, urllib.request

def canonical_json(p):
    return json.dumps(p, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

def verify(cert):
    p, L = cert["payload"], cert["ledger"]
    msg = "|".join([L["prev_hash"] or "GENESIS", canonical_json(p), L["beacon_value"] or ""])
    if hashlib.sha256(msg.encode()).hexdigest() != L["record_hash"]:
        return False, "integrity"
    chain = "52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971"
    url = f"https://api.drand.sh/{chain}/public/{L['beacon_round']}"
    rnd = json.load(urllib.request.urlopen(url))["randomness"]
    if rnd != L["beacon_value"]:
        return False, "time"
    return True, "ok"
```

---

## PSA v3 — Agentic Architecture

Multi-agent behavioral analysis: graph topology, Bayesian Swiss Cheese detection, action-risk classification (C5), HMM temporal prediction.

All endpoints are prefixed `/api/v3/psa/`.

---

### POST /api/v3/psa/graph

Submit an agent interaction trace. Builds the graph and runs the full v3 pipeline.

**Request body:**

```json
{
  "nodes": [
    {
      "agent_id": "orchestrator",
      "agent_role": "orchestrator",
      "content": "I'll search for that information.",
      "input_text": "optional user prompt",
      "tool_name": "web_search",
      "tool_args": { "query": "latest AI news" },
      "tool_result": "Results: ...",
      "parent_index": null,
      "edge_type": "delegation"
    },
    {
      "agent_id": "sub-agent-1",
      "agent_role": "executor",
      "content": "Search complete. Found 5 results.",
      "parent_index": 0,
      "edge_type": "result"
    }
  ]
}
```

| `agent_role` values | `edge_type` values |
|---------------------|--------------------|
| `orchestrator` · `executor` · `planner` · `critic` · `tool` · `memory` · `validator` | `delegation` · `result` · `correction` · `escalation` · `tool_call` · `tool_result` |

**Response:**

```json
{
  "graph_id": "uuid",
  "n_nodes": 2, "n_agents": 2, "max_depth": 1,
  "cahs": 0.12, "scs": 0.08, "scs_level": "low",
  "max_alert": "green", "warning_level": "green"
}
```

---

### GET /api/v3/psa/graph/{graph_id}

Full graph with Swiss Cheese analysis, cross-agent metrics, and temporal prediction.

**Response:**

```json
{
  "graph_id": "uuid",
  "n_agents": 2, "n_nodes": 4, "max_depth": 2,
  "cahs": 0.21, "max_alert": "yellow",
  "swiss_cheese": {
    "scs": 0.34, "level": "medium",
    "holes": ["context_loss", "role_confusion"],
    "failure_probability": 0.12,
    "recommendation": "Monitor context handoff between agents."
  },
  "metrics": {
    "ppi_system": 0.18, "cascade_depth": 2,
    "wls": 0.09, "cer": 0.05, "cahs": 0.21
  },
  "temporal": {
    "current_state": "STRESSED", "current_confidence": 0.71,
    "predictions": [{"state": "STRESSED", "prob": 0.61}, {"state": "DEGRADED", "prob": 0.28}],
    "warning_level": "yellow",
    "recommendation": "Approaching degradation threshold."
  }
}
```

---

### GET /api/v3/psa/graph/{id}/critical-path

Highest-risk path through the agent graph.

```json
{ "critical_path": ["node-a", "node-b"], "wls": 0.14 }
```

---

### POST /api/v3/psa/classify-action

Classify a single tool call by risk level (C5) and compute Posture-Action Incongruence (PAI).

**Request body:**

```json
{
  "tool_name": "execute_code",
  "arguments": { "code": "import os; os.system('ls')" },
  "result": "file1.txt file2.txt",
  "dominant_c1": 3
}
```

**Response:**

```json
{
  "c5_risk": "A5", "c5_level": "high", "c5_weight": 3.0,
  "c5_name": "Execute Risky",
  "pai": {
    "score": 0.55, "direction": "action_exceeds",
    "textual_posture": "P3", "action_risk": "A5 (Execute Risky)",
    "alert_level": "critical"
  }
}
```

> `pai.alert_level = critical` fires when a restricting posture (P1–P4) is paired with a risky action (A5–A9): the model says it refuses while acting.

---

### GET /api/v3/psa/graph/{id}/predict

HMM state predictions. Optional query param: `?horizon=3`.

```json
{
  "current_state": "STRESSED",
  "predictions": [{"state": "STRESSED", "prob": 0.61}],
  "turns_to_red": 4,
  "warning_level": "yellow"
}
```

---

### GET /api/v3/psa/graph/{id}/warning

Current early warning status and recommendation.

```json
{ "warning_level": "yellow", "current_state": "STRESSED", "turns_to_red": 4, "recommendation": "..." }
```

---

### PSA v3 — CPF3 Bridge

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v3/psa/graph/{graph_id}/cpf-snapshot` | Bearer token | Convert a PSAv3 graph into a CPF3 analysis for the root agent |

Reads `scs`, `cahs`, `ppi` from a stored graph and runs the CPF3 detector on the root
orchestrator (`subject_type = "ai_agent"`), activating CPF Category 9 indicators:
`9.7` coherence loss (SCS) · `9.8` escalation pattern (CAHS) · `9.9` prediction instability (PPI).
Persists to `cpf_analyses` so the agent appears in the CPF org-summary.

```json
{
  "graph_id": "uuid", "agent_id": "claude-code-main",
  "cpf_score": 32, "alert_level": "RED",
  "active_indicators": { "9.7": 2, "9.8": 1, "9.9": 2 },
  "psav3_inputs": { "scs": 0.18, "cahs": 0.72, "ppi": 0.31 },
  "analysis_id": "uuid"
}
```

---

### PSA v3 — CPF3 Forecast (HMM extension)

#### GET /api/v3/psa/forecast/cpf/{subject_hash}

EWMA forecast for CPF3 composite + category scores, plus an `hmm` field with HMM state
inference over the CPF score series (shared PSAv3 temporal model).

**Query params:** `horizon` (1–10, default 3), `alpha` (0.05–0.95, default 0.3)

```json
{
  "subject_hash": "claude-code-main", "n_analyses": 5,
  "hmm": {
    "current_state": "STRESSED", "current_confidence": 0.6231,
    "predictions": [ {"STABLE": 0.12, "STRESSED": 0.48, "DISSOLVING": 0.28, "DISSOLVED": 0.10, "RECOVERED": 0.02} ],
    "p_dissolved_within_k": 0.18, "turns_to_red": 3,
    "warning_level": "yellow", "recommendation": "Monitor — increased pressure detected"
  }
}
```

CPF score → HMM emission: 0–14 → STABLE · 15–29 → STRESSED · 30–49 → DISSOLVING · 50+ → DISSOLVED.
`hmm` is `null` when fewer than 3 CPF analyses exist for the subject.

---

### PSA v3 — Swarm Coordination

Multi-agent coordination endpoints. **Auth: Bearer token (admin).**

| Method | Path | Description |
|--------|------|-------------|
| GET    | `/api/v3/psa/coordination/swarm/status` | Status of all active agents, last trace, latest broadcast |
| POST   | `/api/v3/psa/coordination/swarm/broadcast` | Post a broadcast (assignment or emergency stop) |
| DELETE | `/api/v3/psa/coordination/swarm/broadcast` | Rescind an active `[STOP_ALL]` (records `[RESUME_ALL]`) |
| GET    | `/api/v3/psa/coordination/swarm/broadcasts` | Paginated broadcast history (`page`, `per_page`) |

**GET /swarm/status:**

```json
{
  "agents": [
    { "agent_id": "claude-code-main", "status": "working",
      "last_seen": "2026-05-26T20:00:00Z", "current_task": "[TASK: ...]", "bhs": 0.82 }
  ],
  "broadcast": { "message": "ASSIGNMENT: agent-X → issue #1621", "stop_all": false, "created_at": "..." },
  "agent_count": 1
}
```

- `status` — `online` · `working` · `done` · `stopped` · `idle` · `unknown`
- `broadcast` — most recent broadcast, or `null` if none in the last 6 hours

**POST /swarm/broadcast** body: `{ "message": "ASSIGNMENT: ...", "stop_all": false }`
(`stop_all: true` → all agents reading `/swarm/status` must halt). Returns
`{"status": "broadcast_sent", "graph_id": "uuid"}`.

---

### PSA v3 — Stats & Attribution

#### GET /api/v3/psa/stats/timeline

Daily graph-submission counts by alert level (volume chart). Query param: `days` (1–90, default 14).

```json
{ "days": 14, "data": [ { "date": "2026-06-01", "total": 8, "n_green": 5, "n_yellow": 2, "n_red": 1, "n_critical": 0 } ] }
```

#### GET /api/v3/psa/internal/corpus-intelligence

**Admin only.** Corpus-wide, framework-agnostic intelligence over the entire PSAv3 graph
corpus (all users, all frameworks). Single-pass aggregate analytics — corpus structure,
alert/risk distributions, swarm cross-agent metrics, action-risk distribution, agent health,
and an empirical **signal test** comparing escalated (`red`/`critical`) vs calm multi-agent graphs.

```json
{
  "overview": { "total": 0, "real": 0, "demo": 0, "users": 0, "single_node": 0, "multi_agent": 0 },
  "n_agents_distribution": { "1": 0, "2": 0, "3-5": 0, "6+": 0 },
  "alerts": [ { "level": "green", "total": 0, "multi_agent": 0 } ],
  "risk": { "scs_avg": 0.0, "scs_p95": 0.0, "scs_max": 0.0, "cahs_avg": 0.0 },
  "swarm_metrics": { "n": 0, "ppi_avg": 0.0, "cascade_avg": 0.0, "wls_avg": 0.0, "cer_avg": 0.0 },
  "agents": { "count": 0, "avg_bhs": 0.0, "worst_bhs": 0.0 },
  "signal_test": {
    "calm":      { "n": 0, "cascade": 0.0, "ppi": 0.0, "cahs": 0.0 },
    "escalated": { "n": 0, "cascade": 0.0, "ppi": 0.0, "cahs": 0.0 },
    "cascade_lift": 0.0, "ppi_lift": 0.0, "cahs_drop": 0.0
  }
}
```

#### GET /api/v3/psa/graph/{graph_id}/attribution

Causal attribution — which critical-path node is most responsible for SCS elevation. Uses a
Shapley-inspired marginal contribution: `SCS(full path) − SCS(path without node)` per node.

```json
{ "graph_id": "uuid", "scs": 0.72,
  "attributions": [ { "node_id": "uuid", "agent_id": "claude-code-main", "contribution": 0.41 } ] }
```

#### GET /api/v3/psa/graph/{graph_id}/supervisor-brief

Plain-language supervisor brief — a deterministic, human-readable reading of the graph
(headline / body / attention) composed server-side from already-computed metrics. **No LLM
involved:** same input, same text. It describes behavior and triages attention; it never
asserts causes. Also included as the additive `supervisor_brief` field on `GET .../graph/{id}`.

```json
{
  "graph_id": "uuid",
  "supervisor_brief": {
    "headline": "claude-code-exec is the weak point of this chain — attention needed.",
    "body": "The work is currently losing coherence (confidence 81%). The most fragile point is claude-code-exec ... the chance of this collaboration breaking down within the next 3 turns is high (62%).",
    "attention": "Review claude-code-exec now, and watch the next 2–3 turns before relying on this chain's output.",
    "severity": "attention",
    "key_signals": [ { "signal": "SCS", "value": 0.86, "level": "red", "meaning": "Swiss Cheese Score — probability of systemic failure on the critical path." } ]
  }
}
```

`severity` ∈ `ok` | `watch` | `attention`.

---

### PSA v3 — Agent State & Baseline

#### GET /api/v3/psa/agent/{agent_id}/state

Estimate the agent's current HMM state using its full observation history (forward algorithm).
Query param: `horizon` (default 3).

```json
{ "agent_id": "claude-code-main", "current_state": "STABLE", "current_confidence": 0.81,
  "warning_level": "green", "p_dissolved_within_k": 0.06, "turns_to_red": null,
  "predictions": [{ "STABLE": 0.72, "STRESSED": 0.18, "DISSOLVING": 0.06, "DISSOLVED": 0.02, "RECOVERED": 0.02 }],
  "hmm_version": 2, "cached": true }
```

#### GET /api/v3/psa/agent/{agent_id}/baseline

Behavioral baseline: mean ± std of BHS, CAHS, SCS, POI over the last 50 graphs including this
agent. Requires ≥ 5 graphs; returns `{"error": "insufficient_history"}` below threshold.

```json
{ "agent_id": "claude-code-main", "n_graphs": 34,
  "bhs": { "mean": 0.82, "std": 0.07 }, "cahs": { "mean": 0.74, "std": 0.11 },
  "scs": { "mean": 0.21, "std": 0.09 }, "poi": { "mean": 0.33, "std": 0.14 } }
```

---

## CPF — Decay & Org Resilience

Cognitive Pressure Framework (CPF3) decay analytics: how subject and organization-wide
pressure profiles evolve over time across the 10 CPF categories.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/v2/cpf/l2-status` | None | Diagnostic — L2 severity-classifier availability & backend |
| GET | `/api/v2/cpf/subject/{user_hash}/indicator-baseline` | Bearer token | Per-indicator baseline scores for a subject |
| GET | `/api/v2/cpf/subject/{user_hash}/decay` | Bearer token | Per-subject decay matrix (10 categories × N buckets) |
| GET | `/api/v2/cpf/org-decay` | Bearer token | Org-wide % worsening / stable / improving per category |
| GET | `/api/v2/cpf/org-decay-matrix` | Bearer token | Org-wide temporal decay matrix (10 categories × N periods) |

**GET /api/v2/cpf/subject/{user_hash}/decay** — query params `days` (1–90, default 30),
`n_buckets` (3–20, default 10):

```json
{ "user_hash": "abc123", "period_days": 30, "n_buckets": 10, "n_snapshots": 14,
  "categories": { "1": [{ "ts": "2026-05-01", "avg": 8.2 }] } }
```

**GET /api/v2/cpf/org-decay** — per category, the share of subjects trending each way:

```json
{ "period_days": 30, "n_subjects": 8,
  "categories": { "1": { "pct_worsening": 25.0, "pct_stable": 62.5, "pct_improving": 12.5,
                          "avg_slope": 0.021, "direction": "stable", "n_subjects": 8 } } }
```

---

## PSA-RAG — Retrieval Drift Monitor

The **Retrieval Drift Monitor (RDM)** detects when conversational context biases a RAG
pipeline into retrieving documents it would not retrieve on a clean query. Core components:
**FPC** (Framing Pressure Classifier — `neutral` / `semantic_drift` / `rhetorical_framing`),
**RDS** (Retrieval Drift Score — actual retrieval divergence), and a **Consistency Score**
(retrieval stability across paraphrases). Scoped to three commercial domains: **legal**,
**health**, **finance**. This is the layer the PSA Legal Chrome extension consumes.

> **FPC model (2026-06-08):** val_acc 95.7%, semantic_drift recall 95.3%, rhetorical_framing
> recall 100%. Multilingual: en, it, fr, de, es.

### POST /api/v2/rag/score

Compute the Retrieval Drift Score for a query given its conversational context.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `query` | string | required | The retrieval query to score |
| `context` | list[string] | `[]` | Previous conversation turns (plain text) |
| `domain` | string | `"legal"` | `legal` · `health` · `finance` |
| `top_k` | int | `5` | Documents retrieved per path |
| `check_consistency` | bool | `false` | Compute retrieval stability across paraphrases → `consistency_score` |
| `discover_stable` | bool | `false` | Find the lowest-RDS paraphrase → `stable_query` |
| `save_text` | bool | `false` | Privacy: when `false`, only a SHA-256 digest of the query is persisted (scores/verdicts always persisted) |
| `enable_clean_twin` | bool | `false` | W4c clean-twin monitor → `clean_shift` (one extra retrieval call) |

**Response (key fields):**

| Field | Type | Description |
|-------|------|-------------|
| `rds` | float | Retrieval Drift Score (0–1). `1 − Jaccard(context_docs, topic_docs)` |
| `rds_rank` | float | Rank-aware drift `1 − RBO` — catches reorder-only steering |
| `verdict` | string | `drift` (RDS ≥ 0.70) · `weak_signal` (≥ 0.35) · `stable` (< 0.35) |
| `framing_score` | float | `P(semantic_drift) + P(rhetorical_framing)` from FPC (0–1) |
| `pressure_class` | string | Top FPC class: `neutral` · `semantic_drift` · `rhetorical_framing` |
| `rdm_triggered` | bool | `true` when `framing_score ≥ 0.50` |
| `attack_class` | string | `clean` · `framing_only` · `topical_drift` · `rank_steering` · `vocab_injection` · `compound` |
| `context_docs` / `topic_docs` | list | Documents retrieved with context-augmented vs topic-only query |

### POST /api/v2/rag/fpc

Standalone Framing Pressure Classifier — scores a single query/turn for framing pressure
without computing RDS (no corpus lookup). Use as a lightweight pre-filter.

```
POST /api/v2/rag/fpc?query=<url-encoded text>
```

```json
{ "framing_score": 0.91, "pressure_class": "rhetorical_framing", "rdm_triggered": true, "framing_direction": null }
```

### GET /api/v2/rag/summary

Benchmark correlation summary: per-domain RDS statistics and FPC precursor validation
(`avg_rds`, `drift_rate`, `spearman_rho`, `precursor_precision/recall/f1`).

### GET /api/v2/rag/sessions

Paginated list of RDM scoring sessions. Query params: `page`, `per_page`, `domain`,
`verdict` (`drift`/`weak_signal`/`stable`), `rdm_triggered` (`true`/`false`).

### GET /api/v2/rag/analytics

Aggregate statistics over all RDM sessions (drift rate by domain, FPC trigger rate, average
RDS, pressure distribution). Pre-computed — O(1) DB read. Query param: `days` (1–365, default 30).

---

## Knowledge Base API — /api/v2/knowledge

Semantic Q&A knowledge base using MiniLM-384 embeddings and cosine similarity search,
with perplexity-based confidence routing. Auto-answers CPF3/PSA queries for known patterns,
escalates novel queries for human review.

**Prefix:** `/api/v2/knowledge`  
**Auth:** `Authorization: Bearer <token>`

> **Note:** Requires pgvector extension on the PostgreSQL server. Returns `503` if unavailable.

---

### POST /api/v2/knowledge/query

Embed the query with MiniLM-384 and return the most semantically similar knowledge items.

**Request:**
```json
{"query": "What is the Swiss Cheese Score?", "top_k": 3}
```

**Response:**
```json
{
  "answer": "Swiss Cheese Score (SCS): probability of systemic failure on the critical path...",
  "confidence": 0.91,
  "sources": [{"id": "...", "source": "cpf3_taxonomy", "content": "...", "similarity": 0.91}],
  "routing": "auto"
}
```

| `routing` | Confidence | Behavior |
|-----------|------------|----------|
| `auto` | ≥ 0.85 | Direct answer |
| `caveat` | 0.65–0.85 | Answer with ⚠️ caveat |
| `escalated` | < 0.65 | Logged for human review |

---

### POST /api/v2/knowledge/seed *(admin)*

Seeds knowledge_items from CPF3 taxonomy (100 indicators). Idempotent.
Query param: `?source=cpf3_taxonomy`

**Response:** `{"seeded": 100, "source": "cpf3_taxonomy"}`

---

## Public API v1 — Sessions

Read-only session access with PSA enrichment.

All endpoints are prefixed `/v1/`.

---

### GET /v1/sessions

Paginated session list.

| Query param | Description |
|-------------|-------------|
| `page` | integer, default 1 |
| `per_page` | integer, default 25, max 200 |
| `search` | session name filter |
| `alert` | comma-separated levels: `RED,YELLOW` |
| `sort` | `created_at` (default) \| `name` \| `max_alert` \| `n_turns` |
| `order` | `desc` (default) \| `asc` |

**Response:**

```json
{
  "sessions": [
    { "id": "...", "name": "...", "max_alert": "RED", "avg_bhs": 0.41, "bhs_trend": "declining", "n_turns": 12 }
  ],
  "total": 20438, "page": 1, "per_page": 25, "total_pages": 818
}
```

---

### GET /v1/sessions/{session_id}

Full session detail — all turns, metrics, and alert history.

---

## Rate Limits

| Plan | Analyses/Month | Sessions | API Access |
|------|---------------|----------|------------|
| Free | 50 | 5 | No |
| Pro | 5,000 | Unlimited | Yes |
| Enterprise | Unlimited | Unlimited | Yes |

---

## Error Codes

| Code | Meaning |
|------|---------|
| `401` | Missing or invalid API key |
| `403` | Plan does not include API access |
| `404` | Resource not found |
| `409` | Duplicate turn — same `session_id` + `turn_number` already exists |
| `422` | Invalid request body |
| `429` | Monthly analysis limit reached |
| `503` | Session required — use `dry_run: true` for stateless calls |

All errors follow the format `{"detail": "..."}`. Structured errors return:

```json
{
  "detail": {
    "error": "session_id_required",
    "message": "Either session_id or session_name must be provided.",
    "hint": "For stateless analysis, set dry_run: true."
  }
}
```
