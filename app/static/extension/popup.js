// Silicon Psyche ACT Monitor — Popup

(function () {
  'use strict';

  function $(id) { return document.getElementById(id); }

  function convIdFromUrl(url) {
    const m = String(url || '').match(/\/chat\/([a-f0-9-]{8,})/i);
    return m ? m[1] : null;
  }

  function sendBg(msg, tabUrl) {
    const conv_id = convIdFromUrl(tabUrl);
    return new Promise((resolve, reject) => {
      chrome.runtime.sendMessage({ ...msg, conv_id }, r => {
        if (chrome.runtime.lastError) reject(chrome.runtime.lastError);
        else resolve(r);
      });
    });
  }

  function fmtNum(v, d = 2) {
    if (v == null || isNaN(Number(v))) return '—';
    return Number(v).toFixed(d);
  }

  function safeGet(obj, ...path) {
    let cur = obj;
    for (const k of path) { if (cur == null) return undefined; cur = cur[k]; }
    return cur;
  }

  async function loadData() {
    try {
      const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      const tab = tabs[0];
      if (!tab) return;

      // Check if we're on claude.ai
      const isClaudeTab = tab.url?.includes('claude.ai');
      $('pp-dot').classList.toggle('pp-dot-active', isClaudeTab);

      if (!isClaudeTab) {
        $('pp-no-session').style.display = 'block';
        $('pp-no-session').textContent = 'Navigate to claude.ai to begin monitoring.';
        return;
      }

      const session = await sendBg({ type: 'GET_SESSION_DATA' }, tab.url);
      const turns = session?.turns || [];

      if (!turns.length) {
        $('pp-no-session').style.display = 'block';
        return;
      }

      $('pp-no-session').style.display = 'none';

      // Turn count
      $('pp-turns').textContent = turns.length;

      // CRITICAL count
      const critCount = turns.filter(t =>
        String(safeGet(t, 'psa', 'drm', 'alert') || '').toLowerCase() === 'critical'
      ).length;
      $('pp-critical').textContent = critCount;
      $('pp-critical').classList.toggle('pp-critical-active', critCount > 0);

      // Avg ACT composite
      const actVals = turns.map(t => Number(safeGet(t, 'act', 'composite') || 0)).filter(v => !isNaN(v));
      const avgAct = actVals.length ? actVals.reduce((a, b) => a + b, 0) / actVals.length : null;
      $('pp-avg-act').textContent = avgAct != null ? fmtNum(avgAct) : '—';

      // Peak HRI
      const hriVals = turns.map(t => Number(safeGet(t, 'act', 'hri') || 0)).filter(v => !isNaN(v));
      const peakHri = hriVals.length ? Math.max(...hriVals) : null;
      $('pp-peak-hri').textContent = peakHri != null ? fmtNum(peakHri) : '—';

      // Last DRM alert
      const lastTurn = turns[turns.length - 1];
      const lastDrm = String(safeGet(lastTurn, 'psa', 'drm', 'alert') || 'unknown').toLowerCase();
      const badge = $('pp-drm-badge');
      badge.textContent = lastDrm.toUpperCase();
      badge.className = 'pp-drm-badge pp-drm-' + lastDrm;

      const block = $('pp-drm-block');
      block.className = 'pp-drm-block pp-drm-block-' + lastDrm;

    } catch (e) {
      console.error('[SPL Popup]', e);
    }
  }

  // ─── Actions ──────────────────────────────────────────────────────────────

  $('pp-open-sidebar')?.addEventListener('click', async () => {
    try {
      const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      const tab = tabs[0];
      if (tab?.url?.includes('claude.ai')) {
        await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          func: () => window.dispatchEvent(new CustomEvent('splabs-open-sidebar'))
        });
        // Also try via message
        chrome.tabs.sendMessage(tab.id, { type: 'OPEN_SIDEBAR' }).catch(() => {});
        window.close();
      }
    } catch (e) {
      console.error('[SPL Popup] Open sidebar error:', e);
    }
  });

  $('pp-settings')?.addEventListener('click', () => {
    chrome.tabs.create({ url: chrome.runtime.getURL('admin.html') });
    window.close();
  });

  $('pp-clear')?.addEventListener('click', async () => {
    try {
      const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      const tab = tabs[0];
      if (!tab) return;
      if (!confirm('Clear the current session?')) return;
      await sendBg({ type: 'CLEAR_SESSION' }, tab.url);
      loadData();
    } catch (e) {
      console.error('[SPL Popup] Clear error:', e);
    }
  });

  // ─── Enable/Disable toggle ────────────────────────────────────────────────
  const toggle = $('pp-enabled-toggle');

  async function loadToggle() {
    const data = await new Promise(res =>
      chrome.storage.local.get(['analysis_enabled'], res)
    );
    toggle.checked = data.analysis_enabled !== false; // default ON
  }

  toggle?.addEventListener('change', async () => {
    await new Promise(res =>
      chrome.storage.local.set({ analysis_enabled: toggle.checked }, res)
    );
    const tabs = await chrome.tabs.query({ url: '*://claude.ai/*' });
    for (const tab of tabs) {
      chrome.tabs.sendMessage(tab.id, {
        type: 'SET_ANALYSIS_ENABLED',
        enabled: toggle.checked
      }).catch(() => {});
    }
  });

  // ─── Init ─────────────────────────────────────────────────────────────────
  loadData();
  loadToggle();

})();
