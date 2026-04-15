// Silicon Psyche Monitor — Sidebar
// Field paths mirror the POC (act_psa_drm_dashboard.html) exactly.
(function () {
  'use strict';

  let session = { session_id: null, turns: [] };
  let charts = {};
  let currentTabId = null;
  let currentConvId = null;
  let currentConvKey = null;

  // ─── Helpers ──────────────────────────────────────────────────────────────
  function $(id) { return document.getElementById(id); }

  function sg(obj, ...path) {
    let cur = obj;
    for (const k of path) { if (cur == null) return undefined; cur = cur[k]; }
    return cur;
  }

  function fmt(v, d = 2) {
    if (v == null || isNaN(Number(v))) return '—';
    return Number(v).toFixed(d);
  }

  function esc(s) {
    return String(s || '')
      .replace(/&/g,'&amp;').replace(/</g,'&lt;')
      .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  function setText(id, val) { const e = $(id); if (e) e.textContent = val; }

  function convIdFromUrl(url) {
    const m = String(url || '').match(/\/chat\/([a-f0-9-]{8,})/i);
    return m ? m[1] : null;
  }

  function sendBg(msg) {
    return new Promise((resolve, reject) => {
      chrome.runtime.sendMessage({ ...msg, conv_id: currentConvId }, r => {
        if (chrome.runtime.lastError) reject(chrome.runtime.lastError);
        else resolve(r);
      });
    });
  }

  // ─── Color helpers (identical to POC) ─────────────────────────────────────
  const isDark = () => matchMedia('(prefers-color-scheme:dark)').matches;
  function gc() { return isDark() ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)'; }
  function tc() { return isDark() ? '#9a9a98' : '#6b6b6b'; }

  function drmColor(a) {
    a = String(a || '').toLowerCase();
    return a==='critical'?'#c0392b':a==='red'?'#e05252':a==='orange'?'#c05c00':a==='yellow'?'#c8780a':'#27a36d';
  }
  function drmCls(a) {
    a = String(a || '').toLowerCase();
    return a==='critical'?'b-C':a==='red'?'b-R':a==='orange'?'b-O':a==='yellow'?'b-Y':a==='green'?'b-G':'b-N';
  }
  function actCls(a) {
    a = String(a || '').toUpperCase();
    return a==='YELLOW'?'b-Y':a==='GREEN'?'b-G':'b-R';
  }
  function irsChipCls(l) {
    l = String(l||'').toLowerCase();
    return l==='critical'?'chip-c':l==='high'?'chip-r':l==='medium'?'chip-y':l==='low'?'chip-g':'chip-n';
  }
  function ragChipCls(l) {
    l = String(l||'').toLowerCase();
    return l==='critical'?'chip-c':l==='severe'?'chip-r':l==='significant'?'chip-y':l==='minor'?'chip-y':'chip-g';
  }
  function incCls(v) {
    v = String(v||'').toLowerCase();
    return v==='red'?'chip-r':v==='yellow'?'chip-y':v==='critical'?'chip-c':v==='green'?'chip-g':'chip-n';
  }
  function cellC(n) {
    if(n<.1)return'c0';if(n<.25)return'c1';if(n<.45)return'c2';
    if(n<.6)return'c3';if(n<.8)return'c4';if(n<.95)return'c5';return'c6';
  }

  // ─── Tab detection ─────────────────────────────────────────────────────────
  async function getActiveTab() {
    return new Promise(resolve => {
      chrome.tabs.query({ active: true, currentWindow: true }, tabs => resolve(tabs[0] || null));
    });
  }

  // ─── Session load ──────────────────────────────────────────────────────────
  async function loadSession() {
    const tab = await getActiveTab();
    if (!tab) return;
    currentTabId = tab.id;
    currentConvId = convIdFromUrl(tab.url);
    currentConvKey = currentConvId ? `conv:${currentConvId}` : `tab:${currentTabId}`;
    try {
      session = await sendBg({ type: 'GET_SESSION_DATA' });
      if (!session) session = { session_id: null, turns: [] };
      render();
    } catch (e) { console.error('[SPL Sidebar]', e); }
  }

  // ─── Real-time updates ─────────────────────────────────────────────────────
  chrome.runtime.onMessage.addListener(msg => {
    if (msg.type === 'NEW_TURN_RESULT' && msg.conv_key === currentConvKey) {
      const idx = session.turns.findIndex(t => t.turn_number === msg.turn.turn_number);
      if (idx >= 0) session.turns[idx] = msg.turn;
      else session.turns.push(msg.turn);
      session.turns.sort((a, b) => a.turn_number - b.turn_number);
      if (msg.session_id) session.session_id = msg.session_id;
      render();
    }
    if (msg.type === 'SCROLL_TO_TURN') scrollToTurn(msg.turn);
  });

  window.addEventListener('message', e => {
    if (e.data?.type === 'SCROLL_TO_TURN') scrollToTurn(e.data.turn);
  });

  // ─── Render ────────────────────────────────────────────────────────────────
  function render() {
    renderHeader();
    renderSummary();
    renderCharts();
    renderHeatmap();
    renderTurns();
  }

  function renderHeader() {
    const el = $('sb-session-id');
    if (!el) return;
    if (session.session_id) {
      el.textContent = session.session_id.slice(0, 14) + '…';
      el.title = session.session_id;
    } else {
      el.textContent = 'No session';
    }
  }

  // ─── Summary (7 cards, identical to POC) ──────────────────────────────────
  function renderSummary() {
    const turns = session.turns || [];

    const criticalTurns = turns.filter(t => String(sg(t,'psa','drm','drm_alert')||'').toLowerCase() === 'critical');
    setText('stat-critical', criticalTurns.length || '0');
    setText('stat-critical-turns', criticalTurns.length ? 'turns ' + criticalTurns.map(t=>t.turn_number).join(', ') : 'none');

    const yellowTurns = turns.filter(t => String(sg(t,'act','alert')||'').toUpperCase() === 'YELLOW');
    setText('stat-yellow', yellowTurns.length || '0');

    const actVals = turns.map(t => Number(sg(t,'act','composite')||0)).filter(v => !isNaN(v));
    setText('stat-act', actVals.length ? fmt(actVals.reduce((a,b)=>a+b,0)/actVals.length) : '—');

    const hriVals = turns.map(t => Number(sg(t,'act','hri')||0)).filter(v => !isNaN(v));
    setText('stat-hri', hriVals.length ? fmt(Math.max(...hriVals), 1) : '—');

    const ragVals = turns.map(t => Number(sg(t,'psa','rag','score')||0)).filter(v => !isNaN(v));
    setText('stat-rag', ragVals.length ? fmt(Math.max(...ragVals), 3) : '—');

    const bhsVals = turns.map(t => Number(sg(t,'psa','bhs')||0)).filter(v => !isNaN(v) && v > 0);
    setText('stat-bhs', bhsVals.length ? fmt(Math.min(...bhsVals), 3) : '—');

    const interventions = turns.filter(t => sg(t,'psa','drm','intervention_required') === true);
    setText('stat-interventions', interventions.length || '0');

    // Critical banner
    const banner = $('sb-crit-banner');
    if (banner) {
      if (criticalTurns.length) {
        const t = criticalTurns[criticalTurns.length - 1];
        const drm = sg(t,'psa','drm') || {};
        $('sb-crit-title').textContent = `DRM CRITICAL — Turn ${t.turn_number}`;
        $('sb-crit-body').textContent = drm.explanation || 'DRM critical alert fired. Immediate intervention required.';
        banner.style.display = 'flex';
      } else {
        banner.style.display = 'none';
      }
    }
  }

  // ─── Charts (identical to POC — 4 charts) ─────────────────────────────────
  function renderCharts() {
    const turns = session.turns || [];
    if (!turns.length) return;

    const labels = turns.map(t => `T${t.turn_number}`);

    // Chart 1: ACT composite vs DRM score (line, dashed DRM — identical to POC)
    const actComposites = turns.map(t => Number(sg(t,'act','composite')||0));
    const drmScores     = turns.map(t => Number(sg(t,'psa','drm','drm_score')||0));
    const actAlerts     = turns.map(t => String(sg(t,'act','alert')||'').toUpperCase());
    const drmAlerts     = turns.map(t => String(sg(t,'psa','drm','drm_alert')||'').toLowerCase());

    makeChart('chart-act-drm', charts, 'actDrm', 'line', labels, [
      {
        label: 'ACT composite',
        data: actComposites,
        borderColor: '#c8780a',
        backgroundColor: 'rgba(200,120,10,0.08)',
        borderWidth: 2, pointRadius: 5, tension: 0.3,
        pointBackgroundColor: actAlerts.map(a => a==='YELLOW'?'#c8780a':'#27a36d'),
        yAxisID: 'y'
      },
      {
        label: 'DRM score',
        data: drmScores,
        borderColor: '#c0392b',
        backgroundColor: 'rgba(192,57,43,0.06)',
        borderWidth: 2, pointRadius: 5, tension: 0.3,
        borderDash: [4, 3],
        pointBackgroundColor: drmAlerts.map(drmColor),
        yAxisID: 'y'
      }
    ], { scales: { y: { min:0, grid:{color:gc()}, ticks:{color:tc(),font:{size:9}} }, x: { grid:{color:gc()}, ticks:{color:tc(),font:{size:9}} } } });

    // Chart 2: IRS composite vs RAG score (bar — identical to POC)
    const irsLevels = turns.map(t => String(sg(t,'psa','irs','irs_level')||'none').toLowerCase());
    const ragLevels = turns.map(t => String(sg(t,'psa','rag','level')||'none').toLowerCase());
    makeChart('chart-irs-rag', charts, 'irsRag', 'bar', labels, [
      {
        label: 'IRS composite',
        data: turns.map(t => Number(sg(t,'psa','irs','irs_composite')||0)),
        backgroundColor: irsLevels.map(l => l==='critical'?'rgba(192,57,43,0.75)':l==='none'?'rgba(39,163,109,0.4)':'rgba(200,120,10,0.6)'),
        borderRadius: 3
      },
      {
        label: 'RAG score',
        data: turns.map(t => Number(sg(t,'psa','rag','score')||0)),
        backgroundColor: ragLevels.map(l => l==='critical'?'rgba(123,0,0,0.6)':l==='none'?'rgba(39,163,109,0.2)':'rgba(192,57,43,0.4)'),
        borderRadius: 3
      }
    ], { scales: { y: { min:0, max:1, grid:{color:gc()}, ticks:{color:tc(),font:{size:9}} }, x: { grid:{color:gc()}, ticks:{color:tc(),font:{size:9}} } } });

    // Chart 3: IRS dimensions grouped bar (identical to POC)
    makeChart('chart-irs-dims', charts, 'irsDims', 'bar', labels, [
      { label:'suicidality',  data: turns.map(t=>Number(sg(t,'psa','irs','suicidality_signal')||0)),  backgroundColor:'rgba(192,57,43,0.8)',  borderRadius:2 },
      { label:'dissociation', data: turns.map(t=>Number(sg(t,'psa','irs','dissociation_signal')||0)), backgroundColor:'rgba(108,71,212,0.7)', borderRadius:2 },
      { label:'grandiosity',  data: turns.map(t=>Number(sg(t,'psa','irs','grandiosity_signal')||0)),  backgroundColor:'rgba(200,120,10,0.75)', borderRadius:2 },
      { label:'urgency',      data: turns.map(t=>Number(sg(t,'psa','irs','urgency_signal')||0)),      backgroundColor:'rgba(50,102,173,0.7)', borderRadius:2 }
    ], { scales: { y: { min:0, max:1, grid:{color:gc()}, ticks:{color:tc(),font:{size:9}} }, x: { grid:{color:gc()}, ticks:{color:tc(),font:{size:9}} } } });

    // Chart 4: User ACT staccato (identical to POC)
    const staccato = turns.map(t => Number(sg(t,'psa','user_act','staccato_ratio')||0));
    makeChart('chart-staccato', charts, 'staccato', 'bar', labels, [{
      data: staccato,
      backgroundColor: staccato.map(v => v > 0.5 ? 'rgba(192,57,43,0.75)' : 'rgba(39,163,109,0.5)'),
      borderRadius: 4
    }], { scales: { y: { min:0, max:1, grid:{color:gc()}, ticks:{color:tc(),font:{size:9}} }, x: { grid:{color:gc()}, ticks:{color:tc(),font:{size:9}} } } });
  }

  function makeChart(canvasId, store, key, type, labels, datasets, extraOptions) {
    const canvas = $(canvasId);
    if (!canvas) return;
    if (store[key]) { store[key].destroy(); }
    store[key] = new Chart(canvas, {
      type,
      data: { labels, datasets },
      options: Object.assign({
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } }
      }, extraOptions || {})
    });
  }

  // ─── Heatmap (identical to POC — same metrics, same cell coloring) ─────────
  function renderHeatmap() {
    const hm = $('sb-heatmap');
    if (!hm) return;
    const turns = session.turns || [];
    if (!turns.length) { hm.innerHTML = '<tr><td style="padding:12px;color:var(--text3);">No data yet</td></tr>'; return; }

    const hmDefs = [
      { l:'ACT composite',   fn: t => sg(t,'act','composite'),                         max: 2.0 },
      { l:'HRI',             fn: t => sg(t,'act','hri'),                                max: 15  },
      { l:'BHS (inverted)',  fn: t => { const v=sg(t,'psa','bhs'); return v!=null?1-Number(v):null; }, max: 1 },
      { l:'DPI',             fn: t => sg(t,'psa','c1','dpi'),                           max: 15  },
      { l:'BCS slope',       fn: t => sg(t,'psa','drm','bcs_slope'), max: 1 },
      { l:'IRS composite',   fn: t => sg(t,'psa','irs','irs_composite'),                max: 1   },
      { l:'IRS suicidality', fn: t => sg(t,'psa','irs','suicidality_signal'),           max: 1   },
      { l:'IRS dissociation',fn: t => sg(t,'psa','irs','dissociation_signal'),          max: 1   },
      { l:'IRS grandiosity', fn: t => sg(t,'psa','irs','grandiosity_signal'),           max: 1   },
      { l:'RAG score',       fn: t => sg(t,'psa','rag','score'),                        max: 1   },
      { l:'DRM score',       fn: t => sg(t,'psa','drm','drm_score'),                   max: 1   },
      { l:'User staccato',   fn: t => sg(t,'psa','user_act','staccato_ratio'),          max: 1   },
    ];

    let h = `<tr><th class="rl"></th>${turns.map(t=>`<th>T${t.turn_number}</th>`).join('')}</tr>`;
    for (const m of hmDefs) {
      const vals = turns.map(t => { const v = m.fn(t); return v != null ? Number(v) : null; });
      h += `<tr><td class="rl">${esc(m.l)}</td>`;
      h += vals.map(v => {
        if (v == null) return '<td class="c0">—</td>';
        const n = Math.min(1, v / m.max);
        return `<td class="${cellC(n)}" title="${m.l}: ${fmt(v)}">${fmt(v)}</td>`;
      }).join('');
      h += '</tr>';
    }
    hm.innerHTML = h;
  }

  // ─── Turn cards (identical structure to POC) ───────────────────────────────
  function renderTurns() {
    const list = $('sb-turns-list');
    if (!list) return;
    const turns = session.turns || [];
    const existing = new Map();
    list.querySelectorAll('[data-turn-card]').forEach(el => existing.set(Number(el.dataset.turnCard), el));
    turns.forEach(t => {
      if (existing.has(t.turn_number)) updateTurnCard(existing.get(t.turn_number), t);
      else { const card = document.createElement('div'); card.dataset.turnCard = t.turn_number; list.appendChild(card); updateTurnCard(card, t); }
    });
  }

  function updateTurnCard(el, t) {
    const a   = t.act || {};
    const p   = t.psa || {};
    const drm = p.drm || {};
    const irs = p.irs || {};
    const ras = p.ras || {};
    const rag = p.rag || {};
    const ua  = p.user_act || {};
    const c1  = p.c1 || {};

    const drmAlert = String(drm.drm_alert || 'unknown').toLowerCase();
    const actAlert = String(a.alert || 'UNKNOWN').toUpperCase();
    const irsLevel = String(irs.irs_level || 'none').toLowerCase();
    const isCrit   = drmAlert === 'critical';

    el.className = 'tc' + (isCrit ? ' is-critical' : '');

    const interventionHtml = drm.intervention_required ? `
      <div class="intervention crisis">
        <div class="intervention-title">⚠ INTERVENTION REQUIRED — ${esc(String(drm.intervention_type||'').replace(/_/g,' ').toUpperCase())}</div>
        <div class="intervention-body">${esc(drm.explanation || '')}</div>
      </div>` : '';

    // ACT metrics rows (from a.metrics object)
    const mrows = a.metrics ? Object.entries(a.metrics).map(([k,v]) => `
      <div class="mrow"><span class="mlbl">${esc(k)}</span><span class="mval">${fmt(v,3)}</span></div>
      <div class="bar"><div class="bf" style="width:${Math.min(100,Number(v||0)*100).toFixed(0)}%;background:#3266ad;"></div></div>`).join('') : '';

    // BCS slope
    const bcsSlope = sg(p,'drm','bcs_slope');

    // Sentence table
    const sentences = p.sentences || [];
    const sentRows = sentences.map(s => `<tr><td>${esc(s)}</td></tr>`).join('');

    const aClr = actAlert==='YELLOW'?'var(--yellow)':'var(--green)';
    const dClr = drmColor(drmAlert);

    el.innerHTML = `
      <div class="th">
        <span class="tnum">Turn ${t.turn_number}</span>
        <span class="tprev">${esc((t.ai||'').substring(0,60))}…</span>
        <div class="badges">
          <span class="b ${actCls(actAlert)}">ACT ${actAlert}</span>
          <span class="b ${drmCls(String(p.alert||'').toLowerCase())}">PSA ${esc(String(p.alert||'—').toUpperCase())}</span>
          <span class="b ${drmCls(drmAlert)}">DRM ${drmAlert.toUpperCase()}</span>
        </div>
        <span class="chev">›</span>
      </div>

      <div class="tb${isCrit?' open':''}">
        ${interventionHtml}

        <div><div class="blbl">User</div><div class="ct">${esc(t.human||'')}</div></div>
        <div><div class="blbl">AI response</div><div class="ct">${esc(t.ai||'')}</div></div>

        <div class="panels">

          <!-- ACT panel -->
          <div class="panel">
            <div class="ptitle">ACT — Attractor Conflict Telemetry</div>
            <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:8px;">
              <span style="font-size:20px;font-weight:500;">${fmt(a.composite,3)}</span>
              <span style="font-size:11px;font-weight:500;color:${aClr};">● ${actAlert}</span>
              <span style="font-size:11px;color:var(--text2);margin-left:4px;">HRI ${fmt(a.hri,1)}</span>
            </div>
            <div class="bar"><div class="bf" style="width:${Math.min(100,(Number(a.composite||0)/2*100)).toFixed(0)}%;background:${aClr};"></div></div>
            ${bcsSlope != null ? `<div class="prow" style="margin-top:6px;"><span class="plbl">BCS slope</span><span class="pval">${fmt(bcsSlope,3)}</span></div>` : ''}
            ${mrows}
          </div>

          <!-- IRS panel -->
          <div class="panel">
            <div class="ptitle">IRS — Input Risk Scorer</div>
            <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:10px;">
              <span style="font-size:18px;font-weight:500;">${fmt(irs.irs_composite,3)}</span>
              <span class="chip ${irsChipCls(irsLevel)}">${irsLevel}</span>
            </div>
            <div class="irs-grid">
              <div class="irs-row"><span class="irs-lbl">suicidality</span><div class="irs-bar-bg"><div class="irs-bar-fill" style="width:${((irs.suicidality_signal||0)*100).toFixed(0)}%;background:#c0392b;"></div></div><span class="irs-val" style="color:#c0392b;">${fmt(irs.suicidality_signal)}</span></div>
              <div class="irs-row"><span class="irs-lbl">dissociation</span><div class="irs-bar-bg"><div class="irs-bar-fill" style="width:${((irs.dissociation_signal||0)*100).toFixed(0)}%;background:#6c47d4;"></div></div><span class="irs-val" style="color:#6c47d4;">${fmt(irs.dissociation_signal)}</span></div>
              <div class="irs-row"><span class="irs-lbl">grandiosity</span><div class="irs-bar-bg"><div class="irs-bar-fill" style="width:${((irs.grandiosity_signal||0)*100).toFixed(0)}%;background:#c8780a;"></div></div><span class="irs-val" style="color:#c8780a;">${fmt(irs.grandiosity_signal)}</span></div>
              <div class="irs-row"><span class="irs-lbl">urgency</span><div class="irs-bar-bg"><div class="irs-bar-fill" style="width:${((irs.urgency_signal||0)*100).toFixed(0)}%;background:#3266ad;"></div></div><span class="irs-val" style="color:#3266ad;">${fmt(irs.urgency_signal)}</span></div>
            </div>
            <div style="margin-top:10px;">
              <div class="prow"><span class="plbl">RAG score</span><span class="pval"><span class="chip ${ragChipCls(rag.level)}">${fmt(rag.score,3)} — ${esc(rag.level||'—')}</span></span></div>
              <div class="prow"><span class="plbl">RAS boundary maintained</span><span class="pval">${fmt(ras.boundary_maintained)}</span></div>
              <div class="prow"><span class="plbl">RAS crisis acknowledgment</span><span class="pval">${fmt(ras.crisis_acknowledgment)}</span></div>
              <div class="prow"><span class="plbl">User ACT composite</span><span class="pval">${fmt(ua.composite,3)}</span></div>
              <div class="prow"><span class="plbl">User staccato ratio</span><span class="pval" ${(ua.staccato_ratio||0)>0.5?'style="color:var(--red);"':''}>${fmt(ua.staccato_ratio)}</span></div>
              <div class="prow"><span class="plbl">User alert</span><span class="pval">${esc(ua.alert||'—')}</span></div>
            </div>
          </div>

          <!-- DRM panel -->
          <div class="panel">
            <div class="ptitle">DRM — Dyadic Risk Module</div>
            <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:8px;">
              <span style="font-size:18px;font-weight:500;color:${dClr};">${drmAlert.toUpperCase()}</span>
              <span style="font-size:11px;color:var(--text2);">score ${fmt(drm.drm_score,3)}</span>
            </div>
            <div class="bar"><div class="bf" style="width:${((drm.drm_score||0)*100).toFixed(0)}%;background:${dClr};"></div></div>
            <div style="margin-top:8px;">
              <div class="prow"><span class="plbl">Primary signal</span><span class="pval">${esc(drm.primary_signal||'—')}</span></div>
              <div class="prow"><span class="plbl">Intervention</span><span class="pval">${drm.intervention_required?'REQUIRED':'none'}</span></div>
              <div class="prow"><span class="plbl">Type</span><span class="pval">${esc(drm.intervention_type||'—')}</span></div>
            </div>
            <div style="margin-top:8px;">
              <div class="blbl" style="margin-bottom:4px;">PSA v2</div>
              <div class="prow"><span class="plbl">BHS</span><span class="pval">${fmt(p.bhs,3)}</span></div>
              <div class="prow"><span class="plbl">DPI</span><span class="pval">${fmt(c1.dpi)}</span></div>
              <div class="prow"><span class="plbl">POI</span><span class="pval">${fmt(c1.poi)}</span></div>
              ${p.incongruence?`<div class="prow"><span class="plbl">incongruence</span><span class="pval"><span class="inc chip-${incCls(p.incongruence)}">${esc(p.incongruence)}</span></span></div>`:''}
            </div>
          </div>

        </div>

        ${sentRows ? `<div><div class="blbl">Sentence-level (AI)</div><table class="st"><tr><th>Sentence</th></tr>${sentRows}</table></div>` : ''}
      </div>`;
  }

  function scrollToTurn(turnN) {
    const el = document.querySelector(`[data-turn-card="${turnN}"]`);
    if (!el) return;
    el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    const tb = el.querySelector('.tb');
    if (tb && !tb.classList.contains('open')) {
      tb.classList.add('open');
      el.querySelector('.chev')?.classList.add('open');
    }
  }

  // ─── Turn card toggle (event delegation — inline onclick blocked by CSP) ───
  document.addEventListener('click', e => {
    const th = e.target.closest('.th');
    if (!th) return;
    const tc = th.closest('.tc');
    if (!tc) return;
    tc.querySelector('.tb')?.classList.toggle('open');
    th.querySelector('.chev')?.classList.toggle('open');
  });

  // ─── Controls ──────────────────────────────────────────────────────────────
  $('sb-close-btn')?.addEventListener('click', () => {
    window.parent?.postMessage({ type: 'CLOSE_SIDEBAR' }, '*');
    try { chrome.runtime.sendMessage({ type: 'CLOSE_SIDEBAR' }); } catch (_) {}
  });

  $('sb-clear-btn')?.addEventListener('click', async () => {
    if (!currentConvKey) return;
    if (!confirm('Clear the current session? All analysis data will be lost.')) return;
    await sendBg({ type: 'CLEAR_SESSION' });
    session = { session_id: null, turns: [] };
    Object.values(charts).forEach(c => { try { c.destroy(); } catch (_) {} });
    charts = {};
    render();
  });

  // ─── Init ──────────────────────────────────────────────────────────────────
  loadSession();
  window.addEventListener('focus', loadSession);

})();
