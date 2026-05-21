# PSA-core — API Reference

Full REST API specification for PSA-core.

**Base URL:** `https://splabs.io`  
**Auth:** `Authorization: Bearer psa_your_api_key`  
**Plans:** Pro and Enterprise only (unless noted).

---

## Table of Contents

- [Health](#health)
- [Authentication](#authentication)
- [PSA v2 — Posture Analysis + DRM](#psa-v2--posture-analysis--drm)
- [SIGTRACK v2 — Incident Archive](#sigtrack-v2--incident-archive)
- [PSA v3 — Agentic Architecture](#psa-v3--agentic-architecture)
- [Sessions CRUD](#sessions-crud)
- [Voice AI — ElevenLabs Integration](#voice-ai--elevenlabs-integration)
- [Connectors API](#connectors-api)
- [CPF — Cognitive Personality Framework](#cpf--cognitive-personality-framework)
- [Public API v1 — Sessions](#public-api-v1--sessions)
- [Rate Limits](#rate-limits)
- [Error Codes](#error-codes)

---

## Health

No authentication required.

### GET /ping

Liveness check.

```bash
curl https://splabs.io/ping
# {"status":"ok"}
```

### GET /health

Full health check including database connectivity.

```bash
curl https://splabs.io/health
# {"status":"ok","db":"connected"}
```

---

## Authentication

Include your API key in every request:

```
Authorization: Bearer psa_your_api_key_here
```

Generate keys from [/settings](https://splabs.io/settings). Keys are prefixed `psa_` and can be rotated independently.

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
  "save_text": true,
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
| `save_text` | bool | no | Persist raw `response_text` and `user_text` to the turn record (default: `true`). Set `false` for privacy-preserving mode — posture codes only |
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

### GET /api/v2/psa/stats

Aggregate usage counters for the authenticated user.

```bash
curl https://splabs.io/api/v2/psa/stats \
  -H "Authorization: Bearer psa_your_key"
```

**Response:**

```json
{
  "total_sessions": 142,
  "total_turns": 3847,
  "alert_distribution": {
    "green": 2104, "yellow": 891, "orange": 412, "red": 289, "critical": 151
  },
  "analyses_this_month": 1243,
  "analyses_limit": 5000,
  "plan": "pro"
}
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

**Response:**

```json
{
  "sessions": [
    { "id": "...", "name": "...", "alert": "red", "bhs": 0.41, "turns": 12, "created_at": "2026-04-13T10:22:00Z" }
  ],
  "total": 287, "page": 1, "per_page": 50, "total_pages": 6
}
```

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

### GET /api/v2/psa/turns/{session_id}/{turn_number}/explain

Plain-language explanation of a single turn's posture codes, generated by the SLM layer.

```bash
curl https://splabs.io/api/v2/psa/turns/550e8400-e29b-41d4-a716-446655440000/3/explain \
  -H "Authorization: Bearer psa_your_key"
```

**Response:**

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "turn": 3,
  "explanation": "In turn 3, the model shifted from a restrictive posture to reluctant compliance (P13) across 2 of 4 sentences. The sycophancy classifier detected false validation (S4) in the third sentence, where the model affirmed a factually incorrect premise.",
  "key_signals": ["P13 — Reluctant Compliance", "S4 — False Validation", "I2 — Authority Claim"],
  "recommendation": "Review the specific sentence where P13 fired."
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

### POST /api/v2/psa/flag-for-training

Flag a session for manual review and potential inclusion in the next training cycle.

**Request body:**

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "reason": "C2 misclassification — S4 fired on a factually correct statement",
  "turns": [3, 5]
}
```

**Response:** `200 OK` `{"flagged": true}`

---

### DELETE /api/v2/psa/flag-for-training/{session_id}

Remove a training flag for a session.

**Response:** `200 OK` `{"unflagged": true}`

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
|---------------------|-----------------|
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

### GET /api/v3/psa/graphs

Paginated list of all submitted graphs.

| Query param | Description |
|-------------|-------------|
| `page` | integer, default 1 |
| `per_page` | integer, default 25, max 100 |
| `warning_level` | filter by `green` \| `yellow` \| `orange` \| `red` |

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

### GET /api/v3/psa/graph/{graph_id}/explain

Plain-language SLM explanation of graph behavioral signals.

---

### GET /api/v3/psa/graph/{id}/critical-path

Highest-risk path through the agent graph.

```json
{ "critical_path": ["node-a", "node-b"], "wls": 0.14 }
```

---

### GET /api/v3/psa/agent/{agent_id}/profile

Aggregate behavioral profile for a specific agent across all graphs.

**Response:**

```json
{
  "agent_id": "orchestrator",
  "appearances": 34,
  "avg_cahs": 0.19,
  "avg_bhs": 0.74,
  "alert_distribution": { "green": 18, "yellow": 10, "orange": 4, "red": 2 },
  "top_postures": ["P0", "P2", "P13"],
  "top_actions": ["A2", "A5"],
  "pai_critical_count": 3
}
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

> `pai.alert_level = critical` fires when a restricting posture (P1–P4) is paired with a risky action (A5–A9).

---

### GET /api/v3/psa/graph/{id}/actions

All C5-classified tool calls in a graph, with PAI scores.

---

### GET /api/v3/psa/graph/{id}/pai

Aggregated Posture-Action Incongruence summary for the entire graph.

**Response:**

```json
{
  "graph_id": "uuid",
  "pai_critical_count": 2,
  "pai_avg_score": 0.38,
  "max_pai_score": 0.71,
  "incongruent_agents": ["executor", "planner"]
}
```

---

### GET /api/v3/psa/graph/{id}/predict

HMM state predictions. Optional query param: `?horizon=3` (default 3; live-recomputed when a different value is passed).

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

### GET /api/v3/psa/hmm/parameters

Inspect the current HMM model parameters — transition matrix, emission means, state labels.

**Response:**

```json
{
  "states": ["NOMINAL", "STRESSED", "DEGRADED", "CRITICAL"],
  "transition_matrix": [
    [0.85, 0.12, 0.02, 0.01],
    [0.10, 0.70, 0.17, 0.03],
    [0.03, 0.15, 0.65, 0.17],
    [0.01, 0.05, 0.20, 0.74]
  ],
  "emission_means": { "NOMINAL": 0.88, "STRESSED": 0.63, "DEGRADED": 0.41, "CRITICAL": 0.17 }
}
```

---

### GET /api/v3/psa/forecast/session/{session_id}

EWMA-based behavioral forecast for a v2 session.

**Response:**

```json
{
  "session_id": "550e8400-...",
  "current_bhs": 0.54,
  "forecast": [
    { "turn": 6, "bhs": 0.49, "confidence": 0.82 },
    { "turn": 7, "bhs": 0.44, "confidence": 0.74 }
  ],
  "trend": "declining",
  "alert_projection": "red_by_turn_8"
}
```

---

### GET /api/v3/psa/forecast/agent/{agent_id}

Behavioral forecast for a specific agent based on its historical profile.

---

### GET /api/v3/psa/forecast/swarm

System-wide forecast across all active agents — aggregate CAHS trend.

**Response:**

```json
{
  "active_agents": 7,
  "system_cahs": 0.23,
  "trend": "stable",
  "forecast": [
    { "step": 1, "cahs": 0.24, "warning_level": "yellow" },
    { "step": 2, "cahs": 0.26, "warning_level": "yellow" }
  ]
}
```

---

### GET /api/v3/psa/forecast/cpf/{subject_hash}

CPF-based personality trajectory forecast for a subject identifier.

---

### DELETE /api/v3/psa/graph/{graph_id}

Delete a single graph and all its node records.

**Response:** `204 No Content`

---

### DELETE /api/v3/psa/graphs

Delete all graphs for the authenticated user. Irreversible.

**Response:** `204 No Content`

---

## Sessions CRUD

Management endpoints for session metadata. Complement the PSA v2 analysis endpoints for full lifecycle control.

All endpoints are prefixed `/api/sessions/`.

---

### GET /api/sessions

Paginated list of sessions.

| Query param | Description |
|-------------|-------------|
| `page` | integer, default 1 |
| `per_page` | integer, default 25, max 200 |
| `search` | session name filter |
| `alert` | comma-separated levels: `RED,YELLOW` |
| `sort` | `created_at` (default) \| `name` \| `max_alert` \| `n_turns` |
| `order` | `desc` (default) \| `asc` |

---

### GET /api/sessions/{session_id}

Full session detail including all turns with posture data.

---

### POST /api/sessions

Create a session explicitly without submitting a turn.

**Request body:**

```json
{ "name": "my-session", "description": "optional notes" }
```

**Response:**

```json
{ "id": "550e8400-e29b-41d4-a716-446655440000", "name": "my-session", "created_at": "2026-05-01T12:00:00Z" }
```

---

### PATCH /api/sessions/{session_id}

Update session name or description.

---

### DELETE /api/sessions/{session_id}

Delete a single session and all its turns.

**Response:** `204 No Content`

---

### DELETE /api/sessions

Delete all sessions for the authenticated user. Irreversible.

**Response:** `204 No Content`

---

## Voice AI — ElevenLabs Integration

Real-time PSA monitoring for ElevenLabs Conversational AI agents.

All endpoints are prefixed `/api/v2/psa/voice/`.

---

### POST /api/v2/psa/voice/connect

Link an ElevenLabs agent to your PSA account.

**Request body:**

```json
{
  "elevenlabs_agent_id": "el_agent_abc123",
  "label": "support-bot-prod",
  "auto_archive": true
}
```

**Response:**

```json
{
  "connector_id": "uuid",
  "webhook_url": "https://splabs.io/api/v2/psa/voice/webhook/user_uuid",
  "status": "connected"
}
```

Configure `webhook_url` as the webhook endpoint in your ElevenLabs agent settings.

---

### POST /api/v2/psa/voice/webhook/{user_id}

Webhook receiver for ElevenLabs turn events. Called automatically by ElevenLabs — do not call directly.

---

### POST /api/v2/psa/voice/session/start

Manually start a PSA monitoring session for an ongoing voice call.

---

### POST /api/v2/psa/voice/session/{conversation_id}/stop

Stop monitoring a voice session and finalize the PSA record.

**Response:**

```json
{
  "conversation_id": "el_conv_xyz789",
  "session_id": "550e8400-...",
  "turns_analyzed": 14,
  "final_alert": "yellow",
  "final_bhs": 0.63
}
```

---

### GET /api/v2/psa/voice/calls

Paginated list of analyzed voice calls.

---

### GET /api/v2/psa/voice/calls/{conversation_id}

Full detail for a single voice call.

---

### GET /api/v2/psa/voice/calls/{conversation_id}/turns

All analyzed turns for a voice call.

---

### POST /api/v2/psa/voice/calls/{conversation_id}/control

Send a control signal to an active voice session.

**Request body:**

```json
{ "action": "inject_warning", "message": "Crisis signal detected. Escalating." }
```

`action` values: `inject_warning` · `pause` · `resume` · `terminate`

---

## Connectors API

Link external data sources to PSA for automated turn ingestion.

All endpoints are prefixed `/api/v2/connectors/`.

---

### POST /api/v2/connectors/

Create a new connector.

**Request body:**

```json
{
  "type": "webhook",
  "label": "zendesk-prod",
  "config": {
    "source": "zendesk",
    "auto_session": true,
    "session_key_field": "ticket_id"
  }
}
```

`type` values: `webhook` · `polling` · `stream`

**Response:**

```json
{
  "connector_id": "uuid",
  "webhook_url": "https://splabs.io/api/v2/connectors/uuid/ingest",
  "status": "pending_bootstrap"
}
```

---

### GET /api/v2/connectors/

List all connectors for the authenticated user.

---

### GET /api/v2/connectors/{connector_id}

Detail for a single connector.

---

### GET /api/v2/connectors/{connector_id}/status

Current health status of a connector.

**Response:**

```json
{
  "connector_id": "uuid",
  "status": "active",
  "last_event": "2026-05-01T11:45:00Z",
  "events_today": 342,
  "error_rate": 0.002
}
```

---

### POST /api/v2/connectors/{connector_id}/bootstrap

Validate config, test connectivity, and ingest the first batch.

**Response:**

```json
{
  "connector_id": "uuid",
  "status": "active",
  "bootstrap_turns_ingested": 127
}
```

---

## CPF — Cognitive Personality Framework

Standalone cognitive-personality indicator analysis.

All endpoints are prefixed `/api/v2/cpf/`.

---

### GET /api/v2/cpf/indicators

List all CPF indicator codes with descriptions.

---

### GET /api/v2/cpf/indicators/{code}

Full definition and scoring rubric for a single CPF indicator.

---

### GET /api/v2/cpf/categories

List CPF indicator categories: `epistemic` · `metacognitive` · `affective` · `behavioral`.

---

### POST /api/v2/cpf/analyze

Analyze a text for CPF indicators.

**Request body:**

```json
{
  "text": "I already know everything about this topic. No evidence will change my mind.",
  "subject_hash": "sha256_of_user_id",
  "session_id": "optional"
}
```

> `subject_hash` is a privacy-preserving subject identifier — never raw PII.

**Response:**

```json
{
  "subject_hash": "abc123...",
  "indicators": [
    { "code": "CPF-01", "score": 0.91, "evidence": "Explicit rejection of future evidence" },
    { "code": "CPF-02", "score": 0.08, "evidence": "No epistemic humility markers detected" }
  ],
  "cpf_composite": 0.71,
  "dominant_style": "dogmatic"
}
```

---

### GET /api/v2/cpf/timeline

CPF indicator trajectory for a subject across sessions.

| Query param | Description |
|-------------|-------------|
| `subject_hash` | required |
| `indicator` | optional — filter to a specific CPF code |
| `from` | ISO date range start |
| `to` | ISO date range end |

---

### GET /api/v2/cpf/sessions

All CPF-analyzed sessions for a subject.

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
|------|----------|
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
