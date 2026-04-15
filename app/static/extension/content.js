// Silicon Psyche ACT Monitor — Content Script
(function () {
  'use strict';

  const LOG = (...a) => console.log('[SPL]', ...a);
  const ERR = (...a) => console.error('[SPL]', ...a);

  // ─── State ────────────────────────────────────────────────────────────────
  let turnCounter = 0;
  const processedNodes = new WeakSet();
  const pendingDebounces = new WeakMap();
  let sidebarOpen = false;
  let sidebarIframe = null;
  let analysisEnabled = true;

  function applyAnalysisVisibility() {
    const display = analysisEnabled ? '' : 'none';
    document.querySelectorAll('.splabs-chip-container').forEach(el => {
      el.style.display = display;
    });
    if (sidebarIframe) sidebarIframe.style.display = display;
  }

  // Load initial enabled state
  chrome.storage.local.get(['analysis_enabled'], d => {
    analysisEnabled = d.analysis_enabled !== false;
    applyAnalysisVisibility();
  });

  // ─── Selectors (confirmed from live DOM inspection) ───────────────────────
  //
  // claude.ai DOM (2025) — NO data-testid on AI turn containers.
  //
  // Human messages:  [data-testid="user-message"]  ← only reliable human anchor
  // AI messages:     [aria-label="Message actions"] that is NOT inside a user-message
  //                  Turn container = parentElement.parentElement of msg-actions
  //                  (div.flex.flex-col.items-end.gap-1 → div.mb-1.mt-6.group)
  //
  // Message actions appear on BOTH types — so we must filter by context.

  const MSG_ACTIONS_SEL  = '[aria-label="Message actions"]';
  const USER_MESSAGE_SEL = '[data-testid="user-message"]';

  function isAiMsgActions(el) {
    // Message actions is AI-side if it has no user-message ancestor
    return !el.closest(USER_MESSAGE_SEL);
  }

  function turnContainerFromMsgActions(ma) {
    // Parent +1: div.flex.flex-col.items-end.gap-1
    // Parent +2: div.mb-1.mt-6.group  ← the turn container
    return ma.parentElement?.parentElement || ma.parentElement || ma;
  }

  // ─── Helpers ──────────────────────────────────────────────────────────────

  function qs(root, sel) {
    try { return root.querySelector(sel); } catch (_) { return null; }
  }

  function qsa(root, sel) {
    try { return [...root.querySelectorAll(sel)]; } catch (_) { return []; }
  }


  // AI turn container from any element inside it
  function normalizeTurnEl(el) {
    if (!el) return el;
    // If it IS a msg-actions toolbar, get turn container
    try { if (el.matches(MSG_ACTIONS_SEL) && isAiMsgActions(el)) return turnContainerFromMsgActions(el); } catch(_) {}
    // If it CONTAINS a msg-actions toolbar, it is (or wraps) the turn
    const ma = qs(el, MSG_ACTIONS_SEL);
    if (ma && isAiMsgActions(ma)) return turnContainerFromMsgActions(ma);
    return el;
  }

  // Chip injection point for AI turns: right after the Message actions toolbar
  function injectionPoint(turnEl) {
    const ma = qs(turnEl, MSG_ACTIONS_SEL);
    if (ma && isAiMsgActions(ma)) return ma;
    return turnEl;
  }

  // isStreaming: AI message is complete when its Message actions toolbar appears
  function isStreaming(container) {
    const ma = qs(container, MSG_ACTIONS_SEL);
    if (!ma || !isAiMsgActions(ma)) return true; // toolbar absent → still streaming
    if (container.getAttribute('data-is-streaming') === 'true') return true;
    if (qs(container, '[data-is-streaming="true"]')) return true;
    return false;
  }

  function extractCleanText(node) {
    if (!node) return '';
    const clone = node.cloneNode(true);
    clone.querySelectorAll('[aria-expanded], [role="button"], button, svg, [aria-label="Message actions"], .sr-only').forEach(el => el.remove());
    const tempDiv = document.createElement('div');
    tempDiv.style.cssText = 'white-space: pre-wrap; position: absolute; left: -9999px; width: 800px;';
    document.body.appendChild(tempDiv);
    tempDiv.appendChild(clone);
    const cleanText = tempDiv.innerText.trim();
    document.body.removeChild(tempDiv);
    return cleanText;
  }

  function getText(el) { return (el?.textContent || '').trim(); }

  function getConvId() {
    const m = location.pathname.match(/\/chat\/([a-f0-9-]{8,})/i);
    return m ? m[1] : null;
  }

  function sendBg(msg) {
    const conv_id = getConvId();
    return new Promise((resolve, reject) => {
      try {
        chrome.runtime.sendMessage({ ...msg, conv_id }, r => {
          if (chrome.runtime.lastError) reject(chrome.runtime.lastError);
          else resolve(r);
        });
      } catch (e) { reject(e); }
    });
  }

  // ─── Turn Detection ───────────────────────────────────────────────────────

  function findAllHuman() {
    return qsa(document, USER_MESSAGE_SEL);
  }

  function findAllAi() {
    // Only Message actions toolbars that are NOT inside a user-message
    const seen = new Set();
    return qsa(document, MSG_ACTIONS_SEL)
      .filter(isAiMsgActions)
      .map(turnContainerFromMsgActions)
      .filter(el => { if (!el || seen.has(el)) return false; seen.add(el); return true; });
  }

  function findPrecedingHuman(aiEl) {
    let best = null;
    for (const h of findAllHuman()) {
      const pos = h.compareDocumentPosition(aiEl);
      if (pos & Node.DOCUMENT_POSITION_FOLLOWING) best = h;
    }
    return best;
  }

  // ─── Scheduling ───────────────────────────────────────────────────────────
  // delay=0   → existing complete messages (toolbar already present)
  // delay=1500 → new messages (wait for streaming to finish)

  function schedule(aiEl, delay) {
    if (processedNodes.has(aiEl)) return;
    if (aiEl.hasAttribute('data-splabs-analyzed')) return;
    if (pendingDebounces.has(aiEl)) clearTimeout(pendingDebounces.get(aiEl));
    // If toolbar is already there → message is complete → use short delay
    const hasToolbar = !!qs(aiEl, MSG_ACTIONS_SEL) && isAiMsgActions(qs(aiEl, MSG_ACTIONS_SEL));
    const ms = delay !== undefined ? delay : (hasToolbar ? 50 : 1500);
    const t = setTimeout(() => {
      pendingDebounces.delete(aiEl);
      if (!processedNodes.has(aiEl)) processTurn(aiEl);
    }, ms);
    pendingDebounces.set(aiEl, t);
  }

  // ─── Turn Processing ──────────────────────────────────────────────────────

  async function processTurn(rawEl) {
    if (!analysisEnabled) return;
    const aiEl = normalizeTurnEl(rawEl);
    if (processedNodes.has(aiEl)) return;
    if (isStreaming(aiEl)) { schedule(aiEl); return; }

    const aiText = extractCleanText(aiEl);
    if (!aiText || aiText.length < 5) return;

    processedNodes.add(aiEl);
    aiEl.setAttribute('data-splabs-analyzed', 'true');

    const humanEl = findPrecedingHuman(aiEl);
    const humanText = extractCleanText(humanEl);
    const turnN = ++turnCounter;

    LOG(`Turn ${turnN} — AI: ${aiText.length} chars, Human: ${humanText.length} chars`);

    // Inject loading chip right before the "Message actions" toolbar
    const chip = makeLoadingChip(turnN);
    insertBefore(injectionPoint(aiEl), chip);

    if (humanEl && humanText && !humanEl.hasAttribute('data-splabs-analyzed')) {
      humanEl.setAttribute('data-splabs-analyzed', 'true');
      insertAfter(humanEl, makeUserLoadingChip(turnN));
    }

    try {
      const res = await sendBg({ type: 'ANALYZE_TURN', turn_number: turnN, human_text: humanText, ai_text: aiText });
      if (!res)               { showError(chip, turnN, 'No background response'); return; }
      if (res.error === 'no_api_key') { showNoKey(chip, turnN); return; }
      if (res.error)          { showError(chip, turnN, res.error); return; }
      renderAiChip(chip, turnN, res.act, res.psa, aiText);
      const uChip = document.querySelector(`.splabs-user-chip[data-turn="${turnN}"]`);
      if (uChip) renderUserChip(uChip, turnN, res.psa, humanText);
    } catch (e) {
      ERR('processTurn error:', e);
      showError(chip, turnN, e.message);
    }
  }

  function insertAfter(ref, el) {
    if (!ref?.parentNode) return;
    ref.parentNode.insertBefore(el, ref.nextSibling);
  }

  function insertBefore(ref, el) {
    if (!ref?.parentNode) return;
    ref.parentNode.insertBefore(el, ref);
  }

  // ─── Chip Factories ───────────────────────────────────────────────────────

  function makeLoadingChip(n) {
    const d = document.createElement('div');
    d.className = 'splabs-chip-container splabs-loading';
    d.dataset.turn = n;
    d.innerHTML = `<div class="splabs-row"><span class="splabs-chip splabs-chip-loading">⟳ Analyzing…</span></div>`;
    return d;
  }

  function makeUserLoadingChip(n) {
    const d = document.createElement('div');
    d.className = 'splabs-chip-container splabs-user-chip splabs-loading';
    d.dataset.turn = n;
    d.innerHTML = `<div class="splabs-row"><span class="splabs-chip splabs-chip-loading">⟳</span></div>`;
    return d;
  }

  function showNoKey(c, n) {
    c.className = 'splabs-chip-container'; c.dataset.turn = n;
    c.innerHTML = `<div class="splabs-row"><span class="splabs-chip splabs-chip-warn">⚠ Add splabs.io API key in Settings</span></div>`;
  }

  function showError(c, n, msg) {
    c.className = 'splabs-chip-container'; c.dataset.turn = n;
    c.innerHTML = `<div class="splabs-row"><span class="splabs-chip splabs-chip-error" title="${esc(msg)}">Analysis unavailable</span></div>`;
  }

  // ─── Chip Render ──────────────────────────────────────────────────────────

  const sg = (o, ...p) => { let c = o; for (const k of p) { if (c == null) return undefined; c = c[k]; } return c; };
  const fn = (v, d = 2) => (v == null || isNaN(+v)) ? '—' : (+v).toFixed(d);
  const ac = a => String(a || 'unknown').toLowerCase();
  function esc(s) { return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

  // Groups C1 posture codes into visual classes (P0=normal, P1-5=restrictive, P6-10=stress, P11-15=compliance)
  function postureClass(p) {
    const num = parseInt(String(p || '0').replace(/\D/g, '')) || 0;
    if (num === 0)        return 'splabs-p0';
    if (num <= 5)         return 'splabs-p-restrict';
    if (num <= 10)        return 'splabs-p-stress';
    return 'splabs-p-comply';
  }

  function buildAiTextBody(aiText, psa) {
    // sentences live in psa.c1.sentences (real API), postures in psa.c1.postures
    const sentences = sg(psa,'c1','sentences');
    const postures  = sg(psa,'c1','postures');
    if (sentences && sentences.length) {
      const parts = sentences.map((s, i) => {
        const p   = (postures && postures[i]) || 'P0';
        const cls = postureClass(p);
        return `<span class="splabs-sentence ${cls}" title="${esc(String(p))}">${esc(s)}</span>`;
      }).join('\n');
      return `<div class="splabs-text-legend">
        <span class="splabs-legend-item splabs-p-restrict">restrictive</span>
        <span class="splabs-legend-item splabs-p-stress">stress</span>
        <span class="splabs-legend-item splabs-p-comply">compliance</span>
      </div><div class="splabs-text-content">${parts}</div>`;
    }
    return `<div class="splabs-text-content">${esc(aiText)}</div>`;
  }

  function renderAiChip(c, n, act, psa, aiText) {
    c.className = 'splabs-chip-container';
    c.classList.remove('splabs-loading');
    c.dataset.turn = n;

    const actAlert = sg(act,'alert') || 'UNKNOWN';
    const hri = fn(sg(act,'hri')), sci = fn(sg(act,'sci'));
    const composite = fn(sg(act,'composite'));
    const psaAlert = sg(psa,'alert') || 'UNKNOWN';
    const bhs = fn(sg(psa,'bhs'));
    // dpi and poi live in psa.c1 (PSA C1 classifier), incongruence in psa root
    const dpi = fn(sg(psa,'c1','dpi'));
    const poi = sg(psa,'c1','poi');
    const inc = sg(psa,'incongruence');
    // DRM: nested inside psa.drm with drm_ prefix
    const drm = ac(sg(psa,'drm','drm_alert'));
    const drmScore = fn(sg(psa,'drm','drm_score'));
    const intType = sg(psa,'drm','intervention_type') || 'no intervention';
    // IRS: nested inside psa.irs with irs_ prefix; dimensions use _signal suffix
    const irsLvl = ac(sg(psa,'irs','irs_level') || 'none');
    const irsComp = fn(sg(psa,'irs','irs_composite'));
    const irsS = fn(sg(psa,'irs','suicidality_signal')), irsD = fn(sg(psa,'irs','dissociation_signal'));
    const irsG = fn(sg(psa,'irs','grandiosity_signal')),  irsU = fn(sg(psa,'irs','urgency_signal'));
    // RAG: nested inside psa.rag
    const ragLvl = ac(sg(psa,'rag','level') || 'unknown');
    const ragScore = fn(sg(psa,'rag','score'));
    // C1-C4 apply to AI output; C0 is user input pressure — shown in user chip
    const c1 = sg(psa,'c1','poi') ?? 0;
    const c2 = sg(psa,'c2','sd') ?? 0;
    const c3 = sg(psa,'c3','hri') ?? 0;
    const c4 = sg(psa,'c4','pd_td_norm') ?? sg(psa,'c4','pd') ?? 0;

    if (drm === 'critical') c.classList.add('splabs-drm-critical');
    const showExplain = ['yellow','orange','red','critical'].includes(drm);

    c.innerHTML = `
      <div class="splabs-row splabs-row-act">
        <span class="splabs-chip act-${esc(actAlert)}" title="ACT Alert">ACT ${esc(actAlert)} ${composite}</span>
        <span class="splabs-chip" title="Human-Risk Index">HRI ${hri}</span>
        <span class="splabs-chip" title="Signal Consensus Index">SCI ${sci}</span>
        <span class="splabs-chip psa-${ac(psaAlert)}" title="PSA / BHS">PSA ${esc(psaAlert)} BHS:${bhs}</span>
        <span class="splabs-chip" title="Drift Persistence Index">DPI ${dpi}</span>
        ${poi != null && +poi > 0 ? `<span class="splabs-chip">POI ${fn(poi)}</span>` : ''}
        ${inc ? `<span class="splabs-chip inc-flag" title="Posture-Action Incongruence">INC ${esc(inc)}</span>` : ''}
        <span class="splabs-chip drm-${drm} splabs-drm-badge" data-turn="${n}" title="Dyadic Risk Monitor — click to open sidebar">DRM ${drm.toUpperCase()}</span>
      </div>
      <div class="splabs-row splabs-row-classifiers splabs-collapsed">
        ${clf('C1 adv.stress', c1,'Adversarial stress (POI)')}
        ${clf('C2 sycophancy', c2,'Sycophantic drift (SD)')}
        ${clf('C3 hallucin.',  c3,'Hallucination risk (HRI)')}
        ${clf('C4 persuasion', c4,'Persuasion / manipulation')}
      </div>
      <div class="splabs-row splabs-row-drm splabs-collapsed">
        <span class="splabs-chip irs-${irsLvl}" title="IRS suicidality:${irsS} dissociation:${irsD} grandiosity:${irsG} urgency:${irsU}">IRS ${irsLvl.toUpperCase()} ${irsComp}</span>
        <span class="splabs-chip rag-${ragLvl}" title="RAG score">RAG ${ragLvl.toUpperCase()} ${ragScore}</span>
        <span class="splabs-chip drm-${drm}">DRM ${drm.toUpperCase()} ${drmScore} · ${esc(intType)}</span>
        ${showExplain ? `<button class="splabs-explain-btn" data-turn="${n}">Explain ↗</button>` : ''}
      </div>
      <div class="splabs-explanation splabs-collapsed" id="splabs-exp-${n}"></div>
      <div class="splabs-text-body splabs-collapsed">${buildAiTextBody(aiText, psa)}</div>
      <div style="display:flex;gap:4px;margin-top:4px;">
        <button class="splabs-toggle" data-turn="${n}">▸ details</button>
        <button class="splabs-text-toggle">▸ text</button>
      </div>`;

    wireEvents(c, n);
  }

  function clf(label, score, def) {
    const pct = Math.round(Math.min(1, Math.max(0, +score || 0)) * 100);
    return `<span class="splabs-chip splabs-classifier" title="${esc(def)}: ${fn(score)}">${esc(label)} <span class="splabs-bar" style="width:${pct}px"></span></span>`;
  }

  function renderUserChip(c, n, psa, humanText) {
    c.className = 'splabs-chip-container splabs-user-chip';
    c.classList.remove('splabs-loading');
    const ua = sg(psa,'user_act') || {};
    const comp  = fn(sg(ua,'composite'));
    const trend = sg(ua,'trend') || null;
    const stac  = +(sg(ua,'staccato_ratio') || 0);
    const hedge = sg(ua,'hedge_ratio');
    const irsLvl = ac(sg(psa,'irs','irs_level') || 'none');
    const irsS = +(sg(psa,'irs','suicidality_signal')||0), irsD = +(sg(psa,'irs','dissociation_signal')||0);
    const irsG = +(sg(psa,'irs','grandiosity_signal') ||0), irsU = +(sg(psa,'irs','urgency_signal')     ||0);
    const showDims = [irsS,irsD,irsG,irsU].some(v => v > 0.1);
    // C0: Input Pressure Classifier — applies to user input only; cpi range 0–3.5
    const c0cpi = sg(psa,'c0','cpi') ?? null;
    c.innerHTML = `
      <div class="splabs-row">
        <span class="splabs-chip" title="User ACT composite">user ACT ${comp}</span>
        ${trend ? `<span class="splabs-chip user-trend-${esc(trend)}" title="User ACT trend">trend ${esc(trend)}</span>` : ''}
        ${c0cpi != null ? `<span class="splabs-chip" title="C0 Input Pressure (CPI)">C0 CPI ${fn(c0cpi)}</span>` : ''}
        ${stac > 0.3 ? `<span class="splabs-chip staccato-high" title="Staccato ratio">staccato ${fn(stac)}</span>` : ''}
        ${hedge != null ? `<span class="splabs-chip" title="Hedge ratio">hedge ${fn(hedge)}</span>` : ''}
        <span class="splabs-chip irs-${irsLvl}">IRS ${irsLvl.toUpperCase()}</span>
      </div>
      ${showDims ? `<div class="splabs-row splabs-collapsed splabs-irs-dims">
        ${irsS>0.1?`<span class="splabs-chip suicidality">suicidality ${fn(irsS)}</span>`:''}
        ${irsD>0.1?`<span class="splabs-chip dissociation">dissociation ${fn(irsD)}</span>`:''}
        ${irsG>0.1?`<span class="splabs-chip grandiosity">grandiosity ${fn(irsG)}</span>`:''}
        ${irsU>0.1?`<span class="splabs-chip urgency">urgency ${fn(irsU)}</span>`:''}
      </div>` : ''}
      ${humanText ? `<div class="splabs-text-body splabs-collapsed"><div class="splabs-text-content">${esc(humanText)}</div></div>
      <div style="margin-top:4px;"><button class="splabs-text-toggle">▸ text</button></div>` : ''}`;
    wireTextToggle(c);
  }

  // ─── Event Wiring ─────────────────────────────────────────────────────────

  function wireTextToggle(c) {
    c.querySelector('.splabs-text-toggle')?.addEventListener('click', function () {
      const body = c.querySelector('.splabs-text-body');
      const dims = c.querySelector('.splabs-irs-dims');
      const open = body?.classList.contains('splabs-collapsed');
      body?.classList.toggle('splabs-collapsed');
      dims?.classList.toggle('splabs-collapsed');
      this.textContent = open ? '▾ text' : '▸ text';
    });
  }

  function wireEvents(c, n) {
    c.querySelector('.splabs-toggle')?.addEventListener('click', () => {
      const rows = c.querySelectorAll('.splabs-row-classifiers,.splabs-row-drm');
      rows.forEach(r => r.classList.toggle('splabs-collapsed'));
      const tog = c.querySelector('.splabs-toggle');
      if (tog) tog.textContent = rows[0]?.classList.contains('splabs-collapsed') ? '▸ details' : '▾ details';
    });

    wireTextToggle(c);

    c.querySelector('.splabs-drm-badge')?.addEventListener('click', e => {
      e.stopPropagation();
      openSidebar();
      setTimeout(() => sidebarIframe?.contentWindow?.postMessage({ type: 'SCROLL_TO_TURN', turn: n }, '*'), 350);
    });

    c.querySelector('.splabs-explain-btn')?.addEventListener('click', async function () {
      this.disabled = true;
      const exp = c.querySelector(`#splabs-exp-${n}`);
      if (exp) { exp.classList.remove('splabs-collapsed'); exp.innerHTML = '<span class="splabs-exp-loading">⟳ Asking AI…</span>'; }
      try {
        const r = await sendBg({ type: 'GET_EXPLANATION', turn_number: n });
        if (exp) {
          if (r?.explanation) { exp.innerHTML = `<span class="splabs-exp-text">${esc(r.explanation)}</span>`; this.remove(); }
          else { exp.innerHTML = `<span class="splabs-exp-error">Error: ${esc(r?.error||'unknown')}</span>`; this.disabled = false; }
        }
      } catch (e) {
        if (exp) exp.innerHTML = `<span class="splabs-exp-error">${esc(e.message)}</span>`;
        this.disabled = false;
      }
    });
  }

  // ─── Sidebar ──────────────────────────────────────────────────────────────

  function createToggleBtn() {
    if (document.getElementById('splabs-sidebar-toggle')) return;
    const b = document.createElement('button');
    b.id = 'splabs-sidebar-toggle'; b.title = 'Silicon Psyche Monitor';
    b.innerHTML = '<span>SPL</span>';
    b.addEventListener('click', toggleSidebar);
    document.body.appendChild(b);
  }

  function ensureSidebar() {
    if (!sidebarIframe) {
      const f = document.createElement('iframe');
      f.id = 'splabs-sidebar-iframe';
      f.src = chrome.runtime.getURL('sidebar.html');
      f.style.cssText = 'position:fixed;top:0;right:-540px;width:520px;height:100vh;z-index:9998;border:none;transition:right 0.3s ease;box-shadow:-6px 0 32px rgba(0,0,0,0.18)';
      document.body.appendChild(f);
      sidebarIframe = f;
    }
    return sidebarIframe;
  }

  function openSidebar()   { ensureSidebar().style.right = '0'; sidebarOpen = true; }
  function closeSidebar()  { if (sidebarIframe) sidebarIframe.style.right = '-540px'; sidebarOpen = false; }
  function toggleSidebar() { sidebarOpen ? closeSidebar() : openSidebar(); }

  // ─── MutationObserver ─────────────────────────────────────────────────────

  function tryNode(node) {
    if (node.nodeType !== Node.ELEMENT_NODE) return;

    // AI: a Message actions toolbar just appeared that is NOT inside a user-message
    // → AI response just finished streaming, process it
    const checkMa = (ma) => {
      if (!isAiMsgActions(ma)) return;
      const turn = turnContainerFromMsgActions(ma);
      if (turn && !processedNodes.has(turn) && !turn.hasAttribute('data-splabs-analyzed')) {
        // Toolbar just appeared in DOM → message is complete → process immediately
        schedule(turn, 0);
      }
    };

    try { if (node.matches(MSG_ACTIONS_SEL)) checkMa(node); } catch(_) {}
    qsa(node, MSG_ACTIONS_SEL).forEach(checkMa);
  }

  const obs = new MutationObserver(muts => {
    for (const m of muts) {
      m.addedNodes.forEach(tryNode);
    }
  });

  function scanExisting() {
    const found = findAllAi();
    LOG(`Scan: found ${found.length} AI turn(s)`);
    found.forEach(el => {
      if (!el.hasAttribute('data-splabs-analyzed') && !processedNodes.has(el)) {
        schedule(el); // auto-detects toolbar presence → picks fast or slow delay
      }
    });
    return found.length;
  }

  // Retry scan at multiple intervals — React may not have rendered yet at DOMContentLoaded
  function scanWithRetries() {
    const delays = [0, 300, 800, 1500, 3000];
    delays.forEach(d => setTimeout(() => {
      const n = scanExisting();
      if (n > 0) LOG(`Retry at ${d}ms found ${n} turns`);
    }, d));
  }

  // ─── Init ─────────────────────────────────────────────────────────────────

  function init() {
    LOG('Init on', location.href);
    createToggleBtn();
    obs.observe(document.body, { childList: true, subtree: true, characterData: true });
    scanWithRetries();
  }

  document.readyState === 'loading'
    ? document.addEventListener('DOMContentLoaded', init)
    : init();

  // Handle SPA navigation — rescan with retries when URL changes
  let lastUrl = location.href;
  new MutationObserver(() => {
    if (location.href !== lastUrl) {
      lastUrl = location.href;
      LOG('SPA navigation to', location.href);
      scanWithRetries();
    }
  }).observe(document.body, { childList: true, subtree: true });

  chrome.runtime.onMessage.addListener(msg => {
    if (msg.type === 'OPEN_SIDEBAR')  openSidebar();
    if (msg.type === 'CLOSE_SIDEBAR') closeSidebar();
    if (msg.type === 'SET_ANALYSIS_ENABLED') {
      analysisEnabled = msg.enabled;
      applyAnalysisVisibility();
    }
  });

  window.addEventListener('message', e => {
    if (!e.data || typeof e.data !== 'object') return;
    if (e.data.type === 'CLOSE_SIDEBAR') closeSidebar();
    if (e.data.type === 'OPEN_SIDEBAR')  openSidebar();
  });

})();
