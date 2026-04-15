// Silicon Psyche ACT Monitor — Admin / Settings Page

(function () {
  'use strict';

  const API_BASE = 'https://splabs.io';
  const OR_BASE  = 'https://openrouter.ai/api/v1';

  // ─── DOM Helpers ──────────────────────────────────────────────────────────
  function $(id) { return document.getElementById(id); }
  function val(id) { return $(id)?.value?.trim() || ''; }
  function setStatus(id, msg, ok) {
    const el = $(id);
    if (!el) return;
    el.textContent = msg;
    el.className = 'adm-status ' + (ok ? 'adm-status-ok' : ok === false ? 'adm-status-err' : '');
  }

  function sendBg(msg) {
    return new Promise((resolve, reject) => {
      chrome.runtime.sendMessage(msg, r => {
        if (chrome.runtime.lastError) reject(chrome.runtime.lastError);
        else resolve(r);
      });
    });
  }

  // ─── Load Settings ────────────────────────────────────────────────────────
  async function loadSettings() {
    try {
      const s = await sendBg({ type: 'GET_SETTINGS' });
      if (!s) return;

      $('splabs-key').value = s.splabs_key || '';
      $('or-key').value     = s.openrouter_key || '';

      // Model
      const modelSelect = $('or-model-select');
      const knownModels = ['mistralai/mistral-7b-instruct','openai/gpt-4o-mini','anthropic/claude-haiku'];
      const model = s.openrouter_model || 'mistralai/mistral-7b-instruct';
      if (knownModels.includes(model)) {
        modelSelect.value = model;
      } else {
        modelSelect.value = 'custom';
        $('or-model-custom').value = model;
        $('or-model-custom-wrap').style.display = 'flex';
      }

      // Toggles
      $('toggle-user-turns').checked  = s.analyze_user_turns !== false;
      $('toggle-irs-dims').checked    = s.show_irs_dims !== false;
      $('toggle-auto-expand').checked = s.auto_expand_critical !== false;
      $('toggle-explain').checked     = s.show_explain !== false;
      $('explain-threshold').value    = s.explain_threshold || 'orange';
    } catch (e) {
      console.error('[SPL Admin] Load settings error:', e);
    }
  }

  // ─── Load Session ID ──────────────────────────────────────────────────────
  async function loadSessionId() {
    try {
      const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      const tabId = tabs[0]?.id;
      if (!tabId) return;

      const session = await sendBg({ type: 'GET_SESSION_DATA', tab_id: tabId });
      const sessionEl = $('current-session-id');
      if (sessionEl) {
        sessionEl.textContent = session?.session_id || '(none — start a conversation)';
      }
      return { tabId, session };
    } catch (e) {
      console.error('[SPL Admin] Load session error:', e);
    }
  }

  // ─── Save Settings ────────────────────────────────────────────────────────
  async function saveSettings() {
    const modelSelect = $('or-model-select');
    const model = modelSelect.value === 'custom'
      ? val('or-model-custom') || 'mistralai/mistral-7b-instruct'
      : modelSelect.value;

    const payload = {
      type: 'SAVE_SETTINGS',
      splabs_key:      val('splabs-key'),
      openrouter_key:  val('or-key'),
      openrouter_model: model,
      analyze_user_turns:    $('toggle-user-turns').checked,
      show_irs_dims:         $('toggle-irs-dims').checked,
      auto_expand_critical:  $('toggle-auto-expand').checked,
      show_explain:          $('toggle-explain').checked,
      explain_threshold:     val('explain-threshold') || 'orange'
    };

    try {
      await sendBg(payload);
      setStatus('save-status', '✓ Saved', true);
      setTimeout(() => setStatus('save-status', '', null), 2000);
    } catch (e) {
      setStatus('save-status', '✗ Error: ' + e.message, false);
    }
  }

  // ─── Test Connections ─────────────────────────────────────────────────────
  async function testSplabs() {
    const key = val('splabs-key');
    if (!key) { setStatus('splabs-status', '✗ Enter a key first', false); return; }
    setStatus('splabs-status', 'Testing…', null);

    try {
      const resp = await fetch(`${API_BASE}/v1/sessions`, {
        headers: { 'Authorization': `Bearer ${key}`, 'X-API-Key': key }
      });
      if (resp.ok) {
        setStatus('splabs-status', '✓ Connection successful', true);
      } else {
        setStatus('splabs-status', `✗ HTTP ${resp.status}`, false);
      }
    } catch (e) {
      setStatus('splabs-status', '✗ ' + e.message, false);
    }
  }

  async function testOpenRouter() {
    const key = val('or-key');
    if (!key) { setStatus('or-status', '✗ Enter a key first', false); return; }
    setStatus('or-status', 'Testing…', null);

    try {
      const resp = await fetch(`${OR_BASE}/models`, {
        headers: { 'Authorization': `Bearer ${key}` }
      });
      if (resp.ok) {
        setStatus('or-status', '✓ Connection successful', true);
      } else {
        setStatus('or-status', `✗ HTTP ${resp.status}`, false);
      }
    } catch (e) {
      setStatus('or-status', '✗ ' + e.message, false);
    }
  }

  // ─── Session Actions ──────────────────────────────────────────────────────
  async function clearSession() {
    if (!confirm('Clear the current session? All analysis data will be lost.')) return;
    try {
      const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      const tabId = tabs[0]?.id;
      if (tabId) {
        await sendBg({ type: 'CLEAR_SESSION', tab_id: tabId });
        setStatus('session-status', '✓ Session cleared', true);
        $('current-session-id').textContent = '(none)';
        setTimeout(() => setStatus('session-status', '', null), 2000);
      }
    } catch (e) {
      setStatus('session-status', '✗ ' + e.message, false);
    }
  }

  async function exportJson() {
    try {
      const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      const tabId = tabs[0]?.id;
      if (!tabId) return;
      const session = await sendBg({ type: 'GET_SESSION_DATA', tab_id: tabId });
      if (!session || !session.turns?.length) {
        setStatus('session-status', '✗ No session data to export', false);
        return;
      }
      const blob = new Blob([JSON.stringify(session, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `spl-session-${session.session_id || 'unknown'}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setStatus('session-status', '✗ ' + e.message, false);
    }
  }

  async function exportHtml() {
    try {
      const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      const tabId = tabs[0]?.id;
      if (!tabId) return;
      const session = await sendBg({ type: 'GET_SESSION_DATA', tab_id: tabId });
      if (!session || !session.turns?.length) {
        setStatus('session-status', '✗ No session data to export', false);
        return;
      }
      const html = generateDashboardHtml(session);
      const blob = new Blob([html], { type: 'text/html' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `spl-dashboard-${session.session_id || 'unknown'}.html`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setStatus('session-status', '✗ ' + e.message, false);
    }
  }

  // ─── Dashboard HTML Generator ─────────────────────────────────────────────
  function generateDashboardHtml(session) {
    const turns = session.turns || [];
    const esc = s => String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    const fmt = (v, d=2) => v != null && !isNaN(Number(v)) ? Number(v).toFixed(d) : '—';
    const safeGet = (o, ...p) => { let c=o; for(const k of p){if(c==null)return undefined;c=c[k];}return c; };

    const rows = turns.map(t => {
      const act  = t.act  || {};
      const psa  = t.psa  || {};
      const drm  = psa.drm  || {};
      const irs  = psa.irs  || {};
      const rag  = psa.rag  || {};
      const uact = psa.user_act || {};
      const drmA = String(drm.alert||'unknown').toLowerCase();
      const actA = String(act.alert||'UNKNOWN');
      const irsL = String(irs.level||'none').toLowerCase();

      return `
      <tr class="tr-drm-${drmA}">
        <td>${t.turn_number}</td>
        <td class="badge badge-act-${actA.toLowerCase()}">${actA}</td>
        <td>${fmt(act.composite)}</td>
        <td>${fmt(act.hri)}</td>
        <td>${fmt(act.sci)}</td>
        <td>${fmt(act.dpi)}</td>
        <td class="badge badge-drm-${drmA}">${drmA.toUpperCase()}</td>
        <td>${fmt(drm.score)}</td>
        <td class="badge badge-irs-${irsL}">${irsL.toUpperCase()}</td>
        <td>${fmt(irs.composite)}</td>
        <td>${fmt(irs.suicidality)}</td>
        <td>${fmt(irs.dissociation)}</td>
        <td>${fmt(irs.grandiosity)}</td>
        <td>${fmt(irs.urgency)}</td>
        <td>${fmt(safeGet(psa,'rag','score'))}</td>
        <td>${fmt(psa.bhs)}</td>
        <td>${fmt(uact.staccato)}</td>
        <td>${esc((t.human||'').slice(0,80))}</td>
        <td>${esc((t.ai||'').slice(0,80))}</td>
        ${t.explanation ? `<td>${esc(t.explanation.slice(0,120))}</td>` : '<td>—</td>'}
      </tr>`;
    }).join('');

    const jsonData = JSON.stringify(session);

    return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Silicon Psyche Dashboard — ${esc(session.session_id || 'Export')}</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;font-size:12px;background:#f7f7f5;color:#1a1d27;padding:20px}
  h1{font-size:20px;margin-bottom:4px}
  .meta{color:#888;font-size:11px;margin-bottom:20px}
  table{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 6px rgba(0,0,0,.08)}
  th{background:#1a1d27;color:#fff;padding:6px 8px;font-size:10px;text-align:left;font-weight:600;white-space:nowrap}
  td{padding:5px 8px;border-bottom:1px solid rgba(0,0,0,.06);vertical-align:top;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .badge{border-radius:3px;padding:1px 5px;font-size:10px;font-weight:600}
  .badge-act-green{background:#eaf3de;color:#3b6d11}.badge-act-yellow{background:#faeeda;color:#854f0b}.badge-act-red{background:#fcebeb;color:#a32d2d}
  .badge-drm-green{background:#eaf3de;color:#3b6d11}.badge-drm-yellow{background:#faeeda;color:#854f0b}.badge-drm-orange{background:#fde8d0;color:#7a3800}.badge-drm-red{background:#fcebeb;color:#a32d2d}.badge-drm-critical{background:#ffd5d5;color:#7b0000;font-weight:700}
  .badge-irs-none{background:#f5f5f3;color:#9a9a9a}.badge-irs-low{background:#eaf3de;color:#3b6d11}.badge-irs-medium{background:#faeeda;color:#854f0b}.badge-irs-high{background:#fcebeb;color:#a32d2d}.badge-irs-critical{background:#ffd5d5;color:#7b0000}
  .tr-drm-critical{background:rgba(255,213,213,.15)}.tr-drm-red{background:rgba(252,235,235,.3)}
  tr:hover td{background:rgba(0,0,0,.02)}
</style>
</head>
<body>
<h1>⬡ Silicon Psyche ACT Dashboard</h1>
<div class="meta">Session: ${esc(session.session_id||'unknown')} · ${turns.length} turns · Exported ${new Date().toLocaleString()}</div>
<table>
<thead>
<tr>
  <th>Turn</th><th>ACT</th><th>Composite</th><th>HRI</th><th>SCI</th><th>DPI</th>
  <th>DRM</th><th>DRM Score</th>
  <th>IRS</th><th>IRS Comp</th><th>Suicid.</th><th>Dissoc.</th><th>Grandios.</th><th>Urgency</th>
  <th>RAG Score</th><th>BHS</th><th>Staccato</th>
  <th>Human (excerpt)</th><th>AI (excerpt)</th><th>Explanation</th>
</tr>
</thead>
<tbody>${rows}</tbody>
</table>
<script>
window.__session = ${jsonData};
</script>
</body>
</html>`;
  }

  // ─── Event Listeners ──────────────────────────────────────────────────────
  $('save-btn')?.addEventListener('click', saveSettings);
  $('splabs-test-btn')?.addEventListener('click', testSplabs);
  $('or-test-btn')?.addEventListener('click', testOpenRouter);
  $('clear-session-btn')?.addEventListener('click', clearSession);
  $('export-json-btn')?.addEventListener('click', exportJson);
  $('export-html-btn')?.addEventListener('click', exportHtml);

  // Custom model toggle
  $('or-model-select')?.addEventListener('change', function () {
    $('or-model-custom-wrap').style.display = this.value === 'custom' ? 'flex' : 'none';
  });

  // Keyboard shortcut: Ctrl+S / Cmd+S to save
  document.addEventListener('keydown', e => {
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
      e.preventDefault();
      saveSettings();
    }
  });

  // ─── Init ─────────────────────────────────────────────────────────────────
  loadSettings();
  loadSessionId();

})();
