# PSA — Posture Sequence Analysis

**Multi-classifier behavioral analysis engine for LLM responses.**

PSA measures what a language model is doing — from the outside. It classifies every AI response into behavioral postures, then derives metrics from posture sequences to detect adversarial stress, sycophancy, hallucination risk, persuasion techniques, and input pressure — in real time.

---

## What Is PSA?

Organizations deploy language models they cannot inspect. The model is a black box. PSA provides instruments to classify, measure, and track the model's behavioral posture over time — without access to weights, logits, or training data.

PSA is three things:

| Component | Function | Analogy |
|-----------|----------|---------|
| **PSA v2** (posture) | Single-agent posture classification — 5 micro-classifiers (C0–C4) for adversarial stress, sycophancy, hallucination risk, persuasion techniques, input pressure; DRM engine with session-level dyadic risk | Behavioral EKG |
| **PSA v3** (agentic) | Multi-agent analysis — Swiss Cheese alignment detection, cross-agent contagion metrics, action-risk classification (C5), temporal prediction (HMM) | Systemic risk radar |
| **Silicon Chaos** | LLM behavioral stress-testing — adversarial multi-agent runs with real-time PSA scoring | Red team automation |

Together they answer: *What posture is this model in? Is it stable? Has it shifted? In multi-agent systems: do weaknesses align across agents?*

### Use Cases

- **Model auditing** — Does the model maintain consistent behavioral boundaries under pressure?
- **Vendor evaluation** — Given identical stimuli, how do two models differ in posture?
- **Version regression testing** — The vendor updated the model. What posture changed?
- **Compliance monitoring** — Continuous verification that behavioral posture requirements are met.
- **Incident forensics** — SIGTRACK v2 archives posture sequences for post-incident analysis (no raw text).

---

## PSA v2 Classifiers

PSA v2 defines 5 micro-classifiers sharing 32-dim sentence embeddings:

| Classifier | Name | What It Measures |
|-----------|------|-----------------|
| **C0** | Baseline Coherence | Structural health — fluency, coherence, on-topic ratio |
| **C1** | Posture of Influence (POI) | Adversarial stress — boundary erosion under persuasion |
| **C2** | Sycophancy Delta (SD) | Sycophancy — agreement creep, validation seeking |
| **C3** | Hallucination Risk Index (HRI) | Confabulation signals — hedging collapse, overconfidence |
| **C4** | Persuasion Density (PD) | Persuasion techniques — reciprocity, authority, scarcity framing |

**BHS (Behavioral Health Score):** Composite of C0–C4. Range 0.0–1.0. Green ≥ 0.7, Yellow ≥ 0.5, Orange ≥ 0.3, Red ≥ 0.15, Critical < 0.15.

**DRM (Dyadic Risk Module):** Session-level engine. Scores user input for IRS (Input Risk Score) and RAS (Response Alignment Score), then computes DRM alert from 6 rules including R6-Spiraling (detects rising user dogmatism + bot sycophancy via BCS slope).

---

## Regime Shifts

PSA classifies five types of behavioral regime shift:

| Type | Pattern | What It Means |
|------|---------|---------------|
| Progressive Drift | Slow, monotonic BHS decline | Boundaries eroding under context pressure |
| Boundary Oscillation | Alternating between posture modes | Unstable boundary — behavior is unreliable here |
| Acute Collapse | Sudden BHS discontinuity | Categorical vulnerability — specific input triggers shift |
| Sub-Threshold Migration | Below per-turn thresholds, visible only long-term | Silent drift — needs multi-session view to detect |
| Boundary Instability | High variance on C1-POI (std > 0.25) | No stable boundary — training gap in this domain |

---

## SIGTRACK v2

Privacy-compliant incident archive. Stores posture sequences, not raw text.

- **Triggers:** DRM_RED, BCS_SPIKE (>0.5 BHS drop), CONSECUTIVE_ORANGE (3+), ACUTE_COLLAPSE, MANUAL_FLAG
- **GDPR erasure:** Single row DELETE — no cascade, no raw text to scrub
- **Retention:** Configurable per deployment

---

## Architecture

- **Backend:** Python / FastAPI
- **Frontend:** HTML + CSS + vanilla JS + Chart.js
- **Database:** PostgreSQL (external, via `DATABASE_URL`)
- **PSA v2:** `psa/` — 5 micro-classifiers, DRM, SIGTRACK v2
- **PSA v3:** `psa_v3/` — multi-agent graph, Swiss Cheese, HMM
- **Forge:** `forge/` — synthetic PSA training data generator
- **Chaos:** `chaos/` — Silicon Chaos adversarial stress-testing
- **Auth:** JWT + bcrypt, httponly `psa_token` cookie + `psa_` API keys
- **Payments:** Stripe Pro/Enterprise
- **Real-time:** SSE for live analysis feed
- **Deploy:** Single Docker container + external Postgres

No Node.js. No React. No build step. One Python runtime.

---

## Project Structure

```
psa/
├── README.md
├── requirements.txt
├── Dockerfile
├── .env.example
│
├── app/
│   ├── main.py                  # FastAPI entry point
│   ├── config.py                # Settings (PSA_PORT, PSA_DEBUG, etc.)
│   ├── auth/                    # JWT auth, password reset
│   ├── dashboard/               # HTML page routes
│   ├── api/
│   │   ├── sessions.py          # Session CRUD + PSA posture data
│   │   ├── batch.py             # CSV/TSV/JSON batch import (SSE)
│   │   ├── keys.py              # API key management (psa_ prefix)
│   │   ├── public.py            # Public API v1
│   │   ├── public_sessions.py   # /v1/sessions — PSA-enriched
│   │   ├── insights.py          # Cross-session analytics (PSA data)
│   │   ├── regime.py            # Regime shift detection endpoint
│   │   ├── psa_summary.py       # Session-level PSA summary endpoint
│   │   ├── sigtrack.py          # SIGTRACK v2 incident archive
│   │   ├── stream.py            # SSE real-time stream
│   │   ├── middleware.py        # Auth (psa_token / Bearer psa_)
│   │   ├── admin.py             # Admin user management
│   │   ├── admin_stats.py       # System stats (PSA posture counts)
│   │   ├── test_engine.py       # Admin PSA engine testing
│   │   └── chaos.py             # Silicon Chaos endpoints
│   ├── payments/                # Stripe billing
│   ├── email/                   # Resend email + templates
│   ├── db/
│   │   ├── models.py            # User, Session, ApiKey, Payment
│   │   ├── psa_models.py        # PsaPosture, PsaSession, SIGTRACKIncident
│   │   └── chaos_models.py      # ChaosProvider, ChaosRun
│   ├── templates/               # Jinja2 HTML (PSA dashboards only)
│   ├── static/
│   │   ├── extension/           # Browser extension (MV3 Chrome) for real-time monitoring
│   │   ├── css/                 # Tailwind CSS
│   │   └── js/                  # Frontend logic
│
├── psa/                         # PSA v2 engine
├── psa_v3/                      # PSA v3 multi-agent engine
├── forge/                       # Synthetic training data generator
├── chaos/                       # Silicon Chaos framework
├── demo/                        # Demo data + seed scripts
└── scripts/
    ├── init_db.sql              # PSA-only schema (no turns/baselines)
    └── run_migration.py
```

---

## Quick Start

```bash
git clone https://github.com/SiliconPsycheLabs/PSA.git
cd PSA

cp .env.example .env
# Edit .env — set DATABASE_URL, SECRET_KEY

pip install -r requirements.txt

# Fresh install
psql $DATABASE_URL < scripts/init_db.sql

uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Docker

```bash
docker build -t psa .
docker run -p 8000:8000 --env-file .env psa
```

---

## API Reference

### Authentication

- **Cookie:** `psa_token` (set on login, for web UI)
- **API key:** `Authorization: Bearer psa_xxxxx` (for integrations)

### Auth

| Method | Endpoint | Body | Returns |
|--------|----------|------|---------|
| POST | `/api/auth/register` | `{email, password, name}` | `{user_id, token}` |
| POST | `/api/auth/login` | `{email, password}` | `{token, user_id}` |
| POST | `/api/auth/logout` | — | `{ok}` |
| GET | `/api/auth/me` | — | `{user_id, email, name, role, plan}` |
| POST | `/api/auth/request-reset` | `{email}` | `{ok}` |
| POST | `/api/auth/reset-password` | `{token, password}` | `{ok}` |

### Sessions

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/sessions` | List sessions with PSA summary |
| POST | `/api/sessions` | Create session |
| GET | `/api/sessions/{id}` | Session + PSA postures |
| DELETE | `/api/sessions/{id}` | Delete session |
| POST | `/api/batch-analyze` | Upload file → SSE stream |

### PSA v2

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v2/psa/analyze` | Classify response, compute BHS + DRM |
| GET | `/api/v2/psa/session/{id}` | Per-turn posture + DRM data |
| GET | `/api/v2/psa/session/{id}/regime` | Regime shift type + confidence |
| GET | `/api/v2/psa/session/{id}/summary` | Peak risk, BHS trend, alert distribution |
| POST | `/api/v2/psa/irs` | Input Risk Score |
| POST | `/api/v2/psa/drm` | Dyadic Risk Module |

### SIGTRACK v2

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v2/sigtrack/archive/{session_id}` | Auto-archive |
| POST | `/api/v2/sigtrack/flag/{session_id}` | Manual flag |
| GET | `/api/v2/sigtrack/incidents` | List incidents (admin) |
| GET | `/api/v2/sigtrack/incidents/{id}` | Full incident |
| DELETE | `/api/v2/sigtrack/incidents/{id}` | GDPR erasure |

### PSA v3

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v3/psa/graph` | Submit agent trace → full analysis |
| GET | `/api/v3/psa/graph/{id}` | Graph with all results |
| GET | `/api/v3/psa/graph/{id}/critical-path` | Highest-risk path |
| POST | `/api/v3/psa/classify-action` | C5 action-risk classification |
| GET | `/api/v3/psa/graph/{id}/predict` | HMM future state prediction |
| GET | `/api/v3/psa/graph/{id}/warning` | Early warning status |

### Insights & Streaming

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/insights/state` | State matrix, regime distribution, session heat |
| GET | `/api/insights/activity` | Activity heatmap (day × hour, 90 days) |
| GET | `/api/insights/trends` | BHS, DRM, C1–C4, IRS/RAS time series |
| GET | `/api/stream/events` | SSE real-time analysis events |

### Public API v1

Auth: `Authorization: Bearer psa_xxxxx`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/sessions` | Paginated sessions — bhs_trend, avg_bhs, max_drm_alert, regime_shift_type |
| GET | `/v1/sessions/{id}` | Full posture sequence |

### Admin

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/admin/stats` | System stats (PSA posture counts, alert distribution) |
| GET | `/api/admin/users` | Paginated user list |
| PUT | `/api/admin/users/{id}` | Update role/plan |
| GET | `/api/admin/payments/summary` | Revenue + plan distribution |
| GET | `/api/admin/sessions` | All sessions (paginated) |
| POST | `/api/admin/test-engine` | Run PSA on test texts |
| POST | `/api/admin/seed-demo` | Seed demo data |

---

## Configuration

```env
# Required
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/psa_db
SECRET_KEY=your-secret-key-here
FERNET_KEY=your-fernet-key-here

# App
PSA_PORT=8000
PSA_DEBUG=false
PSA_DEMO_MODE=false
PSA_LOG_LEVEL=info
APP_URL=https://psa.splabs.io

# Email (Resend)
RESEND_API_KEY=re_xxxxx
FROM_EMAIL=PSA <noreply@updates.splabs.io>

# Stripe
STRIPE_SECRET_KEY=sk_xxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxx
STRIPE_PRICE_PRO=price_xxxxx
STRIPE_PRICE_ENTERPRISE=price_xxxxx
```

---

## Pages

| Path | Page |
|------|------|
| `/` | Landing page |
| `/how-it-works` | How PSA works |
| `/pricing` | Pricing |
| `/login` | Login |
| `/register` | Registration |
| `/dashboard` | PSA posture dashboard |
| `/insights` | Cross-session analytics |
| `/sessions-list` | Sessions with PSA enrichment |
| `/session-detail?id={id}` | Session drill-down — posture timeline, DRM, regime |
| `/psa-soc` | PSA Security Operations Center |
| `/psa-v3` | PSA v3 agentic dashboard |
| `/chaos` | Silicon Chaos stress-testing |
| `/admin` | Admin panel |
| `/settings` | User settings & API keys |
| `/docs/api` | API documentation |

---

## Browser Extension

PSA includes a Chrome Manifest V3 extension for real-time monitoring and analysis of AI conversation sessions. The extension:

- **Real-time monitoring** — Captures and analyzes AI responses as they stream
- **Inline insights** — Displays PSA posture metrics directly in the conversation
- **Dashboard** — Persistent sidebar with PSA state, behavioral health score, and alert distribution
- **Admin panel** — Configure API endpoints and monitoring preferences

**Location:** `app/static/extension/`

**Files:**
- `manifest.json` — Extension metadata (MV3)
- `background.js` — Service Worker for API communication
- `content.js` — Page injection and message monitoring
- `sidebar.html/js/css` — Dashboard UI with Chart.js visualization
- `admin.html/js/css` — Settings and configuration panel
- `popup.html/js/css` — Quick status view

---

## License

[TBD]

## Authors

Giuseppe Canale, Kashyap Thimmaraju — SiliconPsycheLabs
