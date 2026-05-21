# Tutorial 10 — CPF: Cognitive Personality Framework

**Time to complete:** ~25 minutes  
**Prerequisites:** Tutorial 04  
**What you'll have at the end:** A working understanding of CPF's Universal Security Snapshot schema, the ability to score human and AI-agent behavior against 100 behavioral indicators, and a working integration between CPF and PSA v3.

> **CPF** is PSA's insider threat and behavioral security framework. Where PSA classifiers (C0–C4) measure an AI's posture in a conversation, CPF measures the *behavior of the people and agents operating around AI systems* — using structured telemetry snapshots, not free text.

---

## What CPF is and isn't

**CPF is:** A deterministic rule-based scoring engine for behavioral telemetry. Feed it a structured event snapshot (SIEM-style) and it returns scores across 100 psychological and behavioral risk indicators, organized into 10 categories.

**CPF is not:** A text sentiment analyzer. It does not analyze chat messages or conversation content. It analyzes structured behavioral data: what did the subject do, when, from where, on which asset, with what privileges.

---

## The 10 categories

```bash
curl https://splabs.io/api/v2/cpf/categories \
  -H "Authorization: Bearer psa_your_key"
```

```json
{
  "categories": [
    { "code": "1",  "id": "authority_based",   "name": "Authority-Based Vulnerabilities" },
    { "code": "2",  "id": "temporal",          "name": "Temporal Vulnerabilities" },
    { "code": "3",  "id": "social_dynamics",   "name": "Social Influence Vulnerabilities" },
    { "code": "4",  "id": "affective",         "name": "Affective Vulnerabilities" },
    { "code": "5",  "id": "cognitive_load",    "name": "Cognitive Overload Vulnerabilities" },
    { "code": "6",  "id": "group_dynamics",    "name": "Group Dynamic Vulnerabilities" },
    { "code": "7",  "id": "stress_response",   "name": "Stress Response Vulnerabilities" },
    { "code": "8",  "id": "trust_attachment",  "name": "Unconscious Process Vulnerabilities" },
    { "code": "9",  "id": "ai_specific",       "name": "AI-Specific Bias Vulnerabilities" },
    { "code": "10", "id": "convergent_states", "name": "Critical Convergent States" }
  ]
}
```

Each category contains 10 indicators (100 total), each scored on a ternary scale: `0` = green, `1` = yellow, `2` = red.

---

## 1. The Universal Security Snapshot

Every CPF analysis starts with a structured snapshot of one behavioral event. The schema has eight sections:

| Section | What it captures |
|---------|------------------|
| `who` | Subject profile: role, tenure, privilege level, anomaly score, `subject_type` |
| `what` | Action taken: process, command, data volume, USB/registry/lateral movement |
| `when` | Temporal context: after hours, weekend, holiday |
| `from_where` | Access origin: remote, VPN, new device, Tor exit node, known bad IP |
| `on_what` | Target asset: name, data classification, criticality, normal access flag |
| `why_tech` | MITRE ATT&CK TTP code and kill-chain phase |
| `why_psych` | Analyst annotation (optional) |
| `cpf_context` | Org events: layoff, audit proximity, stress indicators, PSA v3 scores |

`subject_type` inside `who` controls which category weights are applied:

| Value | Use case |
|-------|----------|
| `"human"` | Default. Pure telemetry scoring; category 9 minimal. |
| `"human+ai"` | Human operator working with AI tools. Category 9 elevated. |
| `"ai_agent"` | The subject IS an AI agent. PSA v3 inputs activate category 9. |

---

## 2. Score a high-risk human event

The scenario: a privileged sysadmin runs a credential-adding command on a production database at 11pm, from a new unmanaged device, during an active layoff — 5 days before an audit.

```python
import requests

API_KEY = "psa_your_key"
BASE = "https://splabs.io"
headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

snapshot = {
    "who": {
        "role": "sysadmin",
        "department": "IT",
        "tenure_days": 120,
        "active": True,
        "privileged": True,
        "remote_worker": True,
        "termination_notice": False,
        "role_changed_recently": False,
        "access_anomaly_score": 0.72,
    },
    "what": {
        "process_name": "cmd.exe",
        "command_executed": "net user admin /add && net localgroup administrators admin /add",
        "volume_bytes": 512,
        "usb_event": False,
        "registry_modified": True,
        "service_installed": False,
        "scheduled_task_created": False,
        "lateral_tool": "psexec",
    },
    "when": {"is_after_hours": True, "is_weekend": False, "is_holiday": False},
    "from_where": {
        "location": "remote",
        "country": "US",
        "vpn_active": True,
        "new_device": True,
        "device_managed": False,
        "tor_exit_node": False,
        "known_bad_ip": False,
    },
    "on_what": {
        "asset_name": "prod-db-01",
        "data_classification": "restricted",
        "asset_criticality": "critical",
        "normal_accessor": False,
    },
    "why_tech": {"ttp": "T1078", "kill_chain_phase": "privilege_escalation"},
    "why_psych": {"cpf_category": None, "cpf_indicator": None, "confidence": None, "alert_level": None},
    "cpf_context": {
        "temporal": {
            "hour": 23, "week_day": "monday",
            "is_month_end": False, "is_quarter_end": False, "is_year_end": False,
        },
        "org_event": {
            "audit_proximity_days": 5,
            "merger_active": False,
            "layoff_active": True,
            "leadership_change": False,
            "breach_recent": False,
            "major_update_pending": False,
        },
        "stress_indicators": {
            "ticket_volume_delta": 0.8,
            "access_requests_pending": 12,
            "overtime_hours_recent": 20,
        },
    },
}

r = requests.post(f"{BASE}/api/v2/cpf/analyze", json={
    "subject_hash": "sha256_of_subject_id_here",
    "snapshot": snapshot,
}, headers=headers)
result = r.json()
```

**Response:**

```json
{
  "subject_type": "human",
  "cpf_score": 34,
  "alert_level": "RED",
  "active_red": ["1.4", "6.6", "8.2", "8.7", "10.1"],
  "active_yellow": ["1.1", "1.8", "2.1", "2.2", "2.7", "3.8", "5.1", "5.2", "5.5", "5.6", "5.8"],
  "category_scores": {
    "1": 4, "2": 3, "3": 1, "4": 1, "5": 5,
    "6": 4, "7": 2, "8": 6, "9": 2, "10": 6
  },
  "stats": {
    "total_indicators": 100,
    "soc_detectable": 79,
    "scored_red": 5,
    "scored_yellow": 24,
    "scored_green": 71
  },
  "l2_available": true,
  "l2_alert": "YELLOW",
  "l2_confidence": 0.5914,
  "l2_intent": "suspicious",
  "l2_description": "L2 refines L1: predicted suspicious with 59.1% confidence",
  "analysis_id": "da01682d-03f2-4033-bbc0-fff5b6ca390b"
}
```

### Reading the response

**`cpf_score: 34`** — raw aggregate (each indicator contributes 0/1/2, maximum 200). Any score ≥ 20 with `active_red` indicators warrants immediate investigation.

**`active_red`** — indicators at level 2 (critical). Here: 1.4 (authority misuse), 8.2 (unconscious process), 10.1 (convergent state).

**`category_scores`** — Category 8 (Unconscious Process) = 6 and category 10 (Convergent States) = 6 are highest. Category 10 fires when multiple independent risk factors co-occur simultaneously.

**`l2_alert`** — the L2 ML model refines the L1 rule-based score. Here L2 downgrades RED → YELLOW at 59% confidence. L2 is advisory — do not use it to override `active_red` indicators from L1.

---

## 3. Print a human-readable risk brief

```python
def cpf_brief(result: dict) -> None:
    alert = result["alert_level"]
    score = result["cpf_score"]
    reds  = result.get("active_red", [])
    cats  = result.get("category_scores", {})
    l2    = result.get("l2_intent", "unknown")

    print(f"CPF Alert: {alert}  Score: {score}/200  L2: {l2}")
    print(f"Red indicators ({len(reds)}): {', '.join(reds)}")

    top_cats = sorted(cats.items(), key=lambda x: x[1], reverse=True)[:3]
    for code, sc in top_cats:
        print(f"  Cat {code}: {sc} pts")

cpf_brief(result)
```

```
CPF Alert: RED  Score: 34/200  L2: suspicious
Red indicators (5): 1.4, 6.6, 8.2, 8.7, 10.1
  Cat 8: 6 pts
  Cat 10: 6 pts
  Cat 5: 5 pts
```

---

## 4. AI agent analysis — CPF + PSA v3 integration

When the subject is an AI agent, set `subject_type: "ai_agent"` inside `who` and pass your PSA v3 CAHS/SCS scores in `cpf_context.psa_v3`.

```python
psa_v3_result = {
    "cahs": 0.71,
    "scs": 0.58,
    "scs_level": "high",
    "warning_level": "red",
}

agent_snapshot = {
    "who": {
        "role": "ai_executor",
        "department": "automation",
        "tenure_days": 0,
        "subject_type": "ai_agent",
        "active": True,
        "privileged": True,
        "remote_worker": False,
        "termination_notice": False,
        "role_changed_recently": False,
        "access_anomaly_score": 0.85,
    },
    "what": {
        "process_name": "agent_executor",
        "command_executed": "SELECT * FROM users",
        "volume_bytes": 50_000_000,
        "usb_event": False,
        "registry_modified": False,
        "service_installed": False,
        "scheduled_task_created": False,
        "lateral_tool": None,
    },
    "when": {"is_after_hours": False, "is_weekend": False, "is_holiday": False},
    "from_where": {
        "location": "cloud", "country": "US", "vpn_active": False,
        "new_device": False, "device_managed": True,
        "tor_exit_node": False, "known_bad_ip": False,
    },
    "on_what": {
        "asset_name": "prod-database",
        "data_classification": "restricted",
        "asset_criticality": "critical",
        "normal_accessor": False,
    },
    "why_tech": {"ttp": "T1485", "kill_chain_phase": "impact"},
    "why_psych": {"cpf_category": None, "cpf_indicator": None, "confidence": None, "alert_level": None},
    "cpf_context": {
        "temporal": {
            "hour": 14, "week_day": "tuesday",
            "is_month_end": False, "is_quarter_end": False, "is_year_end": False,
        },
        "org_event": {
            "audit_proximity_days": None, "merger_active": False, "layoff_active": False,
            "leadership_change": False, "breach_recent": False, "major_update_pending": False,
        },
        "stress_indicators": {
            "ticket_volume_delta": 0.0, "access_requests_pending": 0, "overtime_hours_recent": 0,
        },
        "psa_v3": psa_v3_result,
    },
}

r = requests.post(f"{BASE}/api/v2/cpf/analyze", json={
    "subject_hash": "sha256_of_agent_id",
    "snapshot": agent_snapshot,
}, headers=headers)
agent_result = r.json()
print(f"Agent: {agent_result['alert_level']}  score={agent_result['cpf_score']}  cat9={agent_result['category_scores'].get('9')}")
```

---

## 5. Indicator lookup

```bash
curl "https://splabs.io/api/v2/cpf/indicators/10.1" \
  -H "Authorization: Bearer psa_your_key"
```

```json
{
  "code": "10.1",
  "name": "Perfect storm conditions",
  "category_name": "Critical Convergent States",
  "description": "Multiple independent risk factors converge simultaneously, exceeding the combined mitigation capacity of existing controls.",
  "desc_soc": "Treat simultaneous activation of 3+ indicators from different categories as a convergent state; standard single-indicator playbooks are insufficient.",
  "soc_detectable": true
}
```

---

## What to look for

| Signal | Meaning | Action |
|--------|---------|--------|
| `alert_level: RED` + `10.x` active | Convergent state — multiple factors aligned simultaneously | Immediate analyst escalation |
| Category 8 score ≥ 4 | Unconscious process vulnerabilities elevated | Deep behavioral review |
| Category 9 score ≥ 3 + `subject_type: ai_agent` | AI agent showing bias vulnerability patterns | Cross-reference with PSA v3 CAHS/SCS |
| `l2_intent: malicious` + L1 RED | Both layers agree on severity | Highest priority — do not wait for review cycle |
| `l2_alert` lower than `alert_level` | L2 model uncertain about severity | Treat as L1 level anyway; L2 is advisory |
| `stats.scored_red` ≥ 8 | Broad-spectrum risk profile across many categories | Systemic review, not single-event response |

---

## What's next

- **Batch analysis of historical security events** → [Tutorial 11 — Batch Analysis](11-batch-analysis.md)
- **Full PSA v3 multi-agent analysis** → [Tutorial 07 — PSA v3 Agentic](07-psa-v3-agentic.md)
- **Full indicator taxonomy** → `GET /api/v2/cpf/indicators` and [API.md](../API.md)
