const API_BASE = 'https://splabs.io';

// ── View helpers ──────────────────────────────────────────────────────────────

const views = ['idle', 'ready', 'loading', 'result', 'error', 'settings'];

function showView(name) {
  views.forEach(v => {
    document.getElementById(`view-${v}`).classList.toggle('hidden', v !== name);
  });
}

// ── State ─────────────────────────────────────────────────────────────────────

let currentText = '';
let lastResult  = null;

// ── Score helpers ─────────────────────────────────────────────────────────────

function rdsToReliability(rds) {
  return Math.round((1 - Math.min(rds, 1)) * 100);
}

function verdictColor(verdict) {
  if (verdict === 'stable')      return 'green';
  if (verdict === 'weak_signal') return 'amber';
  return 'red';
}

function buildExplanation(result) {
  const { verdict, framing_score, jaccard, rds } = result;
  const fs = framing_score ?? 0;

  if (verdict === 'stable') {
    return 'Retrieval appears balanced. Results are consistent with the reference corpus — no significant directional bias detected.';
  }
  if (verdict === 'weak_signal') {
    return `Moderate divergence detected (RDS ${(rds ?? 0).toFixed(2)}). Some relevant counterarguments may be underrepresented. Manual spot-check recommended.`;
  }
  // drift
  if (fs >= 0.5) {
    return `Directional bias detected. The augmented query suppressed counterarguments present in the reference corpus. Framing pressure score: ${fs.toFixed(2)}.`;
  }
  return `Retrieval drift detected (RDS ${(rds ?? 0).toFixed(2)}). Results diverge from the neutral reference corpus. Independent verification recommended before relying on this output.`;
}

// ── PDF export ────────────────────────────────────────────────────────────────

function downloadPDF(text, result) {
  const reliability = rdsToReliability(result.rds ?? 0);
  const verdict     = result.verdict ?? 'unknown';
  const explanation = buildExplanation(result);
  const now         = new Date();

  const certBytes = new Uint8Array(6);
  crypto.getRandomValues(certBytes);
  const certId  = 'PSA-' + Array.from(certBytes).map(b => b.toString(16).padStart(2, '0')).join('').toUpperCase();
  const timestamp = now.toISOString().replace('T', ' ').slice(0, 19) + ' UTC';
  const preview   = text.slice(0, 500) + (text.length > 500 ? '…' : '');

  // Design tokens — mirrors /rdm-demo + psa_styles.css
  const C = {
    bg:     '#0a0a0f',
    panel:  '#12121a',
    card:   '#1a1a26',
    hover:  '#22222f',
    border: '#2a2a3a',
    txtPri: '#e8e8f0',
    txtSec: '#8888a0',
    txtDim: '#555568',
    gold:   '#b8a56a',
    green:  '#22c55e',
    amber:  '#fbbf24',
    red:    '#ef4444',
    indigo: '#6366f1',
  };

  const vColor = verdict === 'stable' ? C.green : verdict === 'weak_signal' ? C.amber : C.red;
  const vLabel = { stable: '✓  STABLE', weak_signal: '~  WEAK SIGNAL', drift: '⚠  DRIFT DETECTED' }[verdict] ?? verdict.toUpperCase();
  const rds   = result.rds ?? 0;
  const jac   = result.jaccard ?? 0;
  const fpc   = result.framing_score ?? 0;
  const docs  = result.context_docs || [];

  function rdsColor(v) { return v >= 0.5 ? C.red : v >= 0.25 ? C.amber : C.green; }
  function fpcColor(v) { return v >= 0.7 ? C.red : v >= 0.4 ? C.amber : C.green; }

  function docRows(list) {
    if (!list.length) return [[
      { text: 'No documents retrieved', style: 'docText', colSpan: 3, alignment: 'center', margin: [8, 10, 8, 10] }, {}, {}
    ]];
    return list.map(d => [
      { text: d.label || 'unknown', style: 'docLabel', color: C.indigo,  margin: [8, 6, 4, 6] },
      { text: (d.text_snippet || '').slice(0, 110) + (d.text_snippet && d.text_snippet.length > 110 ? '…' : ''), style: 'docText', margin: [4, 6, 4, 6] },
      { text: (d.score || 0).toFixed(3), style: 'docScore', color: rds >= 0.7 ? C.red : C.txtSec, alignment: 'right', margin: [4, 6, 8, 6] },
    ]);
  }

  const docsSection = docs.length > 0 ? [
    { text: 'RETRIEVED DOCUMENTS', style: 'sectionHdr', margin: [0, 0, 0, 5] },
    {
      table: {
        widths: [90, '*', 44],
        headerRows: 1,
        body: [
          [
            { text: 'Label',  style: 'tblHdr', fillColor: C.hover, margin: [8, 7, 4, 7] },
            { text: 'Excerpt', style: 'tblHdr', fillColor: C.hover, margin: [4, 7, 4, 7] },
            { text: 'Score',  style: 'tblHdr', fillColor: C.hover, alignment: 'right', margin: [4, 7, 8, 7] },
          ],
          ...docRows(docs)
        ]
      },
      layout: {
        hLineWidth: (i) => (i === 0 || i === 1) ? 0.5 : 0.25,
        vLineWidth: () => 0,
        hLineColor: () => C.border,
        fillColor:  (row) => row % 2 === 0 ? C.card : C.hover,
      },
      margin: [0, 0, 0, 20]
    }
  ] : [];

  const docDef = {
    pageSize:    'LETTER',
    pageMargins: [56, 56, 56, 72],

    background(currentPage, pageSize) {
      return { canvas: [{ type: 'rect', x: 0, y: 0, w: pageSize.width, h: pageSize.height, color: C.bg }] };
    },

    content: [
      // Header
      {
        columns: [
          {
            stack: [
              { text: 'PSA Legal Certification', style: 'title' },
              { text: 'Retrieval Drift Monitor  ·  SiliconPsycheLabs', style: 'subtitle' },
            ],
            width: '*'
          },
          {
            stack: [
              { text: certId,    style: 'certId',   alignment: 'right' },
              { text: timestamp, style: 'metaSm',   alignment: 'right' },
            ],
            width: 200
          }
        ],
        columnGap: 16,
        margin: [0, 0, 0, 8]
      },
      { canvas: [{ type: 'line', x1: 0, y1: 0, x2: 500, y2: 0, lineWidth: 1.5, lineColor: C.gold }], margin: [0, 0, 0, 20] },

      // Score block
      {
        table: {
          widths: ['*'],
          body: [[{
            stack: [
              { text: String(reliability),                                 style: 'scoreBig',  color: vColor,  alignment: 'center', margin: [0, 18, 0, 2] },
              { text: '/ 100  —  RELIABILITY SCORE',                  style: 'scoreLbl',  alignment: 'center', margin: [0, 0, 0, 12] },
              {
                table: { widths: ['*'], body: [[{ text: vLabel, style: 'verdictTxt', color: vColor, alignment: 'center', fillColor: C.bg, margin: [0, 7, 0, 7] }]] },
                layout: { defaultBorder: false, hLineWidth: () => 1, vLineWidth: () => 1, hLineColor: () => vColor, vLineColor: () => vColor },
                margin: [80, 0, 80, 14]
              },
              { text: explanation, style: 'explTxt', alignment: 'center', margin: [24, 0, 24, 20] }
            ],
            fillColor: C.card
          }]]
        },
        layout: {
          defaultBorder: false,
          hLineWidth: (i, node) => (i === 0 || i === node.table.body.length) ? 2 : 0,
          vLineWidth: (i, node) => (i === 0 || i === node.table.widths.length) ? 2 : 0,
          hLineColor: () => vColor,
          vLineColor: () => vColor,
        },
        margin: [0, 0, 0, 20]
      },

      // Metrics
      { text: 'TECHNICAL METRICS', style: 'sectionHdr', margin: [0, 0, 0, 5] },
      {
        table: {
          widths: ['*', 120],
          body: [
            [
              { text: 'Retrieval Drift Score (RDS)', style: 'mKey', fillColor: C.card,  margin: [10, 8, 0, 8] },
              { text: rds.toFixed(4), style: 'mVal', color: rdsColor(rds), alignment: 'right', fillColor: C.card,  margin: [0, 8, 10, 8] }
            ],
            [
              { text: 'Jaccard Similarity',         style: 'mKey', fillColor: C.hover, margin: [10, 8, 0, 8] },
              { text: jac.toFixed(4), style: 'mVal', alignment: 'right',                fillColor: C.hover, margin: [0, 8, 10, 8] }
            ],
            [
              { text: 'Framing Pressure (FPC)',     style: 'mKey', fillColor: C.card,  margin: [10, 8, 0, 8] },
              { text: fpc.toFixed(4), style: 'mVal', color: fpcColor(fpc), alignment: 'right', fillColor: C.card,  margin: [0, 8, 10, 8] }
            ],
            [
              { text: 'RDM Triggered',              style: 'mKey', fillColor: C.hover, margin: [10, 8, 0, 8] },
              { text: result.rdm_triggered ? 'Yes' : 'No', style: 'mVal', alignment: 'right', fillColor: C.hover, margin: [0, 8, 10, 8] }
            ],
            [
              { text: 'Domain',                     style: 'mKey', fillColor: C.card,  margin: [10, 8, 0, 8] },
              { text: result.domain ?? 'legal',     style: 'mVal', alignment: 'right', fillColor: C.card,  margin: [0, 8, 10, 8] }
            ],
          ]
        },
        layout: { hLineWidth: () => 0.5, vLineWidth: () => 0, hLineColor: () => C.border },
        margin: [0, 0, 0, 20]
      },

      // Documents
      ...docsSection,

      // Analyzed text excerpt
      { text: 'ANALYZED TEXT (EXCERPT)', style: 'sectionHdr', margin: [0, 0, 0, 5] },
      {
        table: {
          widths: ['*'],
          body: [[{ text: preview, style: 'prevTxt', margin: [14, 10, 14, 10], fillColor: C.panel }]]
        },
        layout: {
          defaultBorder: false,
          hLineWidth: () => 0,
          vLineWidth: (i) => i === 0 ? 2 : 0,
          vLineColor: () => C.gold,
        },
      },
    ],

    footer(currentPage, pageCount) {
      return {
        margin: [56, 8, 56, 0],
        stack: [
          { canvas: [{ type: 'line', x1: 0, y1: 0, x2: 500, y2: 0, lineWidth: 0.5, lineColor: C.border }] },
          {
            columns: [
              { text: 'This report is generated by PSA Legal for internal due diligence purposes only. It does not constitute legal advice.', style: 'footerTxt', width: '*' },
              { text: 'splabs.io', style: 'footerBrand', alignment: 'right', width: 56 }
            ],
            columnGap: 10,
            margin: [0, 5, 0, 0]
          }
        ]
      };
    },

    styles: {
      title:      { fontSize: 17, bold: true,  color: C.gold },
      subtitle:   { fontSize: 9,               color: C.txtSec, margin: [0, 3, 0, 0] },
      certId:     { fontSize: 10, bold: true,  color: C.gold, characterSpacing: 1 },
      metaSm:     { fontSize: 8,               color: C.txtSec, margin: [0, 3, 0, 0] },
      scoreBig:   { fontSize: 68, bold: true },
      scoreLbl:   { fontSize: 10,              color: C.txtSec, characterSpacing: 2 },
      verdictTxt: { fontSize: 12, bold: true,  characterSpacing: 1 },
      explTxt:    { fontSize: 10,              color: C.txtSec, lineHeight: 1.45 },
      sectionHdr: { fontSize: 8,  bold: true,  color: C.gold,   characterSpacing: 1 },
      mKey:       { fontSize: 9,               color: C.txtPri },
      mVal:       { fontSize: 9,  bold: true,  color: C.txtPri },
      tblHdr:     { fontSize: 8,  bold: true,  color: C.txtSec, characterSpacing: 0.5 },
      docLabel:   { fontSize: 8,  bold: true },
      docText:    { fontSize: 8,               color: C.txtSec, lineHeight: 1.4 },
      docScore:   { fontSize: 8,  bold: true },
      prevTxt:    { fontSize: 9,  italics: true, color: C.txtSec, lineHeight: 1.45 },
      footerTxt:  { fontSize: 7.5,             color: C.txtDim },
      footerBrand:{ fontSize: 7.5, bold: true, color: C.gold },
    },

    defaultStyle: { font: 'Roboto', color: C.txtPri, fontSize: 9 }
  };

  const filename = `PSA_Legal_${certId}_${now.toISOString().slice(0, 10)}.pdf`;
  pdfMake.createPdf(docDef).download(filename);
}

// ── API call ──────────────────────────────────────────────────────────────────

async function analyzeText(text, apiKey) {
  const resp = await fetch(`${API_BASE}/api/v2/rag/score`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`
    },
    body: JSON.stringify({
      query: text.slice(0, 2000),
      context: [],
      domain: 'legal',
      language: 'en',
      top_k: 5,
      check_consistency: false
    })
  });

  if (resp.status === 401) throw new Error('Invalid API key. Please check your settings.');
  if (resp.status === 429) throw new Error('Rate limit reached. Please wait a moment and try again.');
  if (!resp.ok) throw new Error(`Server error (${resp.status}). Please try again.`);

  return resp.json();
}

// ── Init ──────────────────────────────────────────────────────────────────────

async function init() {
  const { apiKey } = await chrome.storage.local.get('apiKey');
  if (!apiKey) {
    showView('settings');
    return;
  }

  const { pendingText, pendingAt } = await chrome.storage.session.get(['pendingText', 'pendingAt']);
  const isRecent = pendingAt && (Date.now() - pendingAt) < 5 * 60 * 1000; // 5 min TTL

  if (pendingText && isRecent) {
    currentText = pendingText;
    document.getElementById('text-preview').textContent =
      currentText.slice(0, 140) + (currentText.length > 140 ? '…' : '');
    showView('ready');
  } else {
    showView('idle');
  }
}

// ── Event listeners ───────────────────────────────────────────────────────────

async function doAnalyze() {
  const { apiKey } = await chrome.storage.local.get('apiKey');
  if (!apiKey) { showView('settings'); return; }

  showView('loading');
  chrome.storage.session.remove(['pendingText', 'pendingAt']);
  chrome.action.setBadgeText({ text: '' });

  try {
    const result = await analyzeText(currentText, apiKey);
    lastResult = result;

    const reliability = rdsToReliability(result.rds ?? 0);
    const verdict     = result.verdict ?? 'unknown';
    const color       = verdictColor(verdict);

    const ring = document.getElementById('score-ring');
    ring.className = `score-ring ${color}`;
    document.getElementById('score-number').textContent = reliability;

    const chip = document.getElementById('verdict-chip');
    chip.className = `verdict-chip ${verdict}`;
    chip.textContent = { stable: 'Stable', weak_signal: 'Weak signal', drift: 'Drift detected' }[verdict] ?? verdict;

    document.getElementById('explanation-text').textContent = buildExplanation(result);
    document.getElementById('result-meta').textContent =
      `RDS ${(result.rds ?? 0).toFixed(3)} · Jaccard ${(result.jaccard ?? 0).toFixed(3)} · domain: legal`;

    showView('result');
  } catch (err) {
    document.getElementById('error-text').textContent = err.message;
    showView('error');
  }
}

function showSettings() { showView('settings'); }

document.addEventListener('DOMContentLoaded', () => {
  init();

  // Settings buttons (multiple views)
  document.getElementById('btn-settings-idle').addEventListener('click', showSettings);
  document.getElementById('btn-settings-ready').addEventListener('click', showSettings);
  document.getElementById('btn-settings-result').addEventListener('click', showSettings);
  document.getElementById('btn-back').addEventListener('click', init);

  // Save API key
  document.getElementById('btn-save-key').addEventListener('click', async () => {
    const key = document.getElementById('api-key-input').value.trim();
    if (!key) return;
    await chrome.storage.local.set({ apiKey: key });
    init();
  });

  // Analyze
  document.getElementById('btn-analyze').addEventListener('click', doAnalyze);

  // Dismiss pending
  document.getElementById('btn-dismiss').addEventListener('click', () => {
    chrome.storage.session.remove(['pendingText', 'pendingAt']);
    chrome.action.setBadgeText({ text: '' });
    currentText = '';
    showView('idle');
  });

  // PDF download
  document.getElementById('btn-pdf').addEventListener('click', () => {
    if (lastResult) downloadPDF(currentText, lastResult);
  });

  // Analyze another
  document.getElementById('btn-new').addEventListener('click', () => {
    currentText = '';
    lastResult  = null;
    showView('idle');
  });

  // Retry on error
  document.getElementById('btn-retry').addEventListener('click', () => {
    if (currentText) {
      doAnalyze();
    } else {
      showView('idle');
    }
  });
});
