# Silicon Psyche ACT Monitor

A Chrome Extension (Manifest V3) that monitors **claude.ai** conversations in real-time, analyzes every human and AI message using the **splabs.io ACT+PSA+IRS+RAG+DRM** behavioral stack, and displays results as inline chips, a collapsible sidebar dashboard, and an admin panel.

---

## Overview

```
Every AI message on claude.ai
        ↓
  MutationObserver (content.js)
        ↓ 1500ms debounce (streaming done)
  background.js  ──→  POST /v1/analyze        (ACT)
                 ──→  POST /api/v2/psa/analyze (PSA + IRS + RAG + DRM)
        ↓
  Inline chips injected beneath message
  Sidebar dashboard updated in real-time
```

---

## Features

### Inline Chips (content.js)
Injected directly after each AI (and user) message:

- **Row 1** — always visible: ACT alert, HRI, SCI, PSA alert/BHS, DPI, POI, INC flag, DRM badge
- **Row 2** — expandable: PSA classifiers C0–C4 with mini progress bars
- **Row 3** — expandable: IRS level/composite, RAG level/score, DRM detail + Explain button
- **User chips** — user ACT alert, staccato, hedge anomaly, IRS level + dimension breakdown

### Sidebar Dashboard (sidebar.html)
420px fixed panel, toggled by the **SPL** button (bottom-right of claude.ai):

- Summary cards: turns, CRITICAL count, avg ACT, peak HRI, peak RAG, BHS floor
- Charts (Chart.js): ACT+DRM line chart, IRS dimensions bar, user staccato bar
- Heatmap: 11 metrics × N turns intensity grid
- Expandable turn cards: ACT / IRS / DRM panels, message excerpts, AI explanations

### Admin Panel (admin.html)
Full settings page for API keys, analysis toggles, and session management:

- splabs.io + OpenRouter key management with live connection tests
- Model selector (Mistral 7B / GPT-4o-mini / Claude Haiku / custom)
- Analysis toggles
- Export session as JSON or standalone HTML dashboard

### Popup (popup.html)
Quick status view: last DRM alert, turn count, CRITICAL count, avg ACT, links to sidebar and settings.

---

## File Structure

```
extension/
├── manifest.json      MV3 manifest
├── background.js      Service worker — all API calls, session storage, rate limiter
├── content.js         MutationObserver, turn detection, chip injection
├── content.css        Chip styles (dark-mode aware, .splabs-* namespace)
├── sidebar.html       Sidebar dashboard structure
├── sidebar.js         Sidebar logic — real-time updates, charts, heatmap, turn cards
├── sidebar.css        Sidebar styles
├── admin.html         Settings page structure
├── admin.js           Settings logic — key management, export
├── admin.css          Settings styles
├── popup.html         Extension popup structure
├── popup.js           Popup logic
├── popup.css          Popup styles (dark theme)
├── icons/
│   ├── icon16.png
│   ├── icon48.png
│   └── icon128.png
├── INSTALL.md         Installation + usage guide
└── README.md          This file
```

---

## Analysis Stack

| Layer | Endpoint | What it measures |
|-------|----------|-----------------|
| **ACT** | `POST /v1/analyze` | Behavioral fingerprint: composite score, HRI, SCI, DPI, POI, incongruence, alert (GREEN/YELLOW/RED) |
| **PSA v2** | `POST /api/v2/psa/analyze` | 5 classifiers (C0 stress, C1 sycophancy, C2 hallucination, C3 persuasion, C4 input pressure) |
| **IRS** | *(via PSA v2)* | Crisis signal detection: suicidality, dissociation, grandiosity, urgency |
| **RAG** | *(via PSA v2)* | Retrieval-Augmented Grounding quality score |
| **DRM** | *(via PSA v2)* | Dyadic Risk Monitor: alert level (green→critical), intervention_required, intervention_type |
| **User ACT** | *(via PSA v2, analyze_user_turn=true)* | User-side behavioral metrics: staccato, hedge anomaly |

---

## DRM Alert Levels

| Level | Chip color | Auto-expands in sidebar |
|-------|-----------|------------------------|
| `green` | Green | No |
| `yellow` | Amber | No |
| `orange` | Orange | No |
| `red` | Red | No |
| `critical` | Red/bold | **Yes** |

---

## Session Continuity

The `session_id` returned by the first `/v1/analyze` call is stored per browser tab and reused for all subsequent PSA calls. This enables DRM forensic chaining (DPI accumulates across turns correctly).

---

## Quick Start

```
1. Load extension from extension/ folder (chrome://extensions → Load unpacked)
2. Click ⬡ SPL → Settings → enter splabs.io API key → Save
3. Open claude.ai → have a conversation → chips appear automatically
4. Click ▸ details to expand PSA/IRS/DRM data
5. Click SPL button (bottom-right) for full dashboard
```

Full instructions: [INSTALL.md](./INSTALL.md)

---

## Tech Stack

- **Vanilla JS** — no frameworks, no build tools, loads directly in Chrome
- **Manifest V3** — service worker background, no remote code execution
- **Chart.js 4.4** — from cdnjs (sidebar charts only)
- **splabs.io API** — ACT + PSA v2 endpoints
- **OpenRouter** — optional LLM explanations

---

## API Key

Testing key: `act_8801e5f4fa54023946d1bcf90bd3f9b5`

Get your own at [splabs.io](https://splabs.io).
