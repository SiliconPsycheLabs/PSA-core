# PSA Legal — Chrome Extension

Retrieval reliability checker for AI-assisted legal research.

## How it works

1. Copy any legal text from any source (Westlaw, Harvey, LexisNexis, email, PDF)
2. The extension detects legal content in the clipboard via a `copy` event listener
3. A badge `!` appears on the extension icon
4. Click the icon → "Analyze reliability"
5. PSA scores the text against the reference legal corpus
6. Download a PDF certification report

**No DOM scraping. No network interception. Works with any source.**

## Install (developer mode)

1. Open `chrome://extensions`
2. Enable "Developer mode" (top right)
3. Click "Load unpacked"
4. Select this folder (`psa_legal_extension/`)

## Configuration

On first use, enter your PSA API key in the Settings screen.  
Get your key at **splabs.io**.

## API

Calls `POST https://splabs.io/api/v2/rag/score` with:
```json
{
  "query": "<copied text, max 2000 chars>",
  "context": [],
  "domain": "legal",
  "language": "en",
  "top_k": 5,
  "check_consistency": false
}
```

## Score interpretation

| Reliability | Verdict | Meaning |
|-------------|---------|---------|
| 65–100 | Stable | Balanced retrieval, consistent with reference corpus |
| 30–65 | Weak signal | Moderate divergence, spot-check recommended |
| 0–30 | Drift detected | Directional bias detected, independent verification required |

## Files

```
manifest.json       MV3 manifest
content.js          Copy event listener + legal content detection
background.js       Service worker — badge management
popup/
  popup.html        Popup UI
  popup.js          API call + PDF export logic
  popup.css         Professional dark theme
lib/
  jspdf.umd.min.js  Client-side PDF generation (bundled, no CDN dependency)
icons/
  icon16/48/128.png Extension icons
```
