# Installation Guide — Silicon Psyche ACT Monitor

## Prerequisites

- Google Chrome 114+ (or any Chromium-based browser that supports Manifest V3)
- A splabs.io API key (format: `act_…`)
- *(Optional)* An OpenRouter API key for natural-language explanations

---

## Step 1: Load the Extension in Chrome

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable **Developer mode** (toggle in the top-right corner)
3. Click **Load unpacked**
4. Select the `extension/` folder from this repository
5. The **Silicon Psyche Monitor** extension will appear in your extensions list
6. Pin it to the toolbar by clicking the puzzle-piece icon → pin ⬡

---

## Step 2: Configure API Keys

1. Click the **⬡ SPL** icon in the Chrome toolbar
2. Click **⚙ Settings** — this opens the admin panel
3. Enter your **splabs.io API Key** (`act_…`) and click **Test ↗** to verify
4. *(Optional)* Enter your **OpenRouter API Key** for the "Explain ↗" feature
5. Choose your preferred OpenRouter model (default: `mistralai/mistral-7b-instruct`)
6. Click **Save Settings** (or press `Ctrl+S` / `Cmd+S`)

---

## Step 3: Start Monitoring

1. Navigate to [claude.ai](https://claude.ai) and open any conversation
2. Have a conversation — after each AI response completes, chips will appear automatically beneath each message
3. Click **▸ details** on any chip to expand PSA classifiers and IRS/RAG/DRM breakdowns
4. Click the **SPL** button (bottom-right of the page) to open the full sidebar dashboard
5. Click **DRM [level]** badge on any chip to jump directly to that turn in the sidebar

---

## Using the Sidebar Dashboard

The sidebar (420px, fixed right) shows:

| Section | Description |
|---------|-------------|
| Summary cards | Turn count, CRITICAL alerts, avg ACT, peak HRI, peak RAG, BHS floor |
| Charts | ACT + DRM over turns, IRS dimensions, user staccato |
| Heatmap | 11-metric × N-turn intensity grid |
| Turn cards | Expandable per-turn panels with ACT / IRS / DRM detail |

**Auto-expand:** DRM CRITICAL turns open automatically in the sidebar.

---

## Using the Explain Feature

When a turn has DRM ≥ Orange, an **Explain ↗** button appears in the expanded chip row.

1. Expand chips with **▸ details**
2. Click **Explain ↗**
3. A 2–3 sentence plain-English explanation is generated via OpenRouter and stored in the session

Requires: OpenRouter API key configured in Settings.

---

## Session Management

### Clear Session
- Popup → **↺ Clear Session**, or
- Sidebar header → **↺ Clear**, or
- Settings → **↺ Clear Session**

Clears all stored turn data and resets the session ID. The next turn analyzed will start a new splabs.io session.

### Export Session
In **Settings → Session Management**:

- **Export JSON** — full session object with all API response data
- **Export HTML Dashboard** — standalone HTML file with a sortable data table, suitable for sharing or archiving

---

## Known Limitations

1. **DOM selector fragility** — Claude.ai is a React SPA that may change its DOM structure without notice. The extension uses multiple fallback selectors (`[data-testid="human-turn"]`, `[data-testid="ai-turn"]`, class-based fallbacks) and fails gracefully if none match.

2. **Streaming detection** — Messages are detected as "complete" after a 1500ms debounce with no further DOM mutations. Very long AI responses or slow connections may occasionally trigger early analysis; the result will still be valid but may be based on partial text.

3. **Rate limiting** — Minimum 500ms between API calls. If more than 5 turns are queued, older ones are dropped to process only the most recent.

4. **Session scope** — Each browser tab has its own session. Opening claude.ai in multiple tabs creates independent sessions.

5. **API authentication** — The extension sends the API key via `Authorization: Bearer` header. If the splabs.io API requires cookie-based auth instead, analyses will return HTTP 401 errors (visible in the extension's background service worker console).

6. **OpenRouter model availability** — Model availability depends on your OpenRouter subscription tier. `mistralai/mistral-7b-instruct` is available on free tier.

---

## Debugging

Open Chrome DevTools for the extension:
- **Background (service worker):** `chrome://extensions/` → Silicon Psyche Monitor → **Service Worker**
- **Content script:** Open DevTools on claude.ai → Console → filter by `[SPL]`
- **Sidebar:** Right-click inside the sidebar iframe → Inspect

All log messages are prefixed with `[SPL]`.
