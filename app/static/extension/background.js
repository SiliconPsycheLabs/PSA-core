// Silicon Psyche ACT Monitor — Background Service Worker
// All API calls are made here to avoid CORS issues.

const API_BASE = 'https://splabs.io';
const OPENROUTER_BASE = 'https://openrouter.ai/api/v1';
const DEFAULT_MODEL = 'mistralai/mistral-7b-instruct';
const RATE_LIMIT_MS = 500;

// Rate limiter state
let callQueue = [];
let isProcessing = false;
let lastCallTime = 0;

// ─── Storage Helpers ─────────────────────────────────────────────────────────

function getStorage(keys) {
  return new Promise(resolve => chrome.storage.local.get(keys, resolve));
}

function setStorage(data) {
  return new Promise(resolve => chrome.storage.local.set(data, resolve));
}

async function getSettings() {
  const data = await getStorage([
    'splabs_key', 'openrouter_key', 'openrouter_model',
    'analyze_user_turns', 'sessions'
  ]);
  return {
    splabs_key: data.splabs_key || '',
    openrouter_key: data.openrouter_key || '',
    openrouter_model: data.openrouter_model || DEFAULT_MODEL,
    analyze_user_turns: data.analyze_user_turns !== false,
    sessions: data.sessions || {}
  };
}

// ─── Session key: conv:<uuid> from URL, fallback tab:<tabId> ─────────────────

function convKeyFromUrl(url) {
  if (!url) return null;
  const m = String(url).match(/\/chat\/([a-f0-9-]{8,})/i);
  return m ? `conv:${m[1]}` : null;
}

function sessionKey(msg, sender) {
  // Prefer conv_id sent by content script (extracted from location.pathname)
  if (msg.conv_id) return `conv:${msg.conv_id}`;
  // Try to derive from sender tab URL
  const tabUrl = sender.tab && sender.tab.url;
  const fromUrl = convKeyFromUrl(tabUrl);
  if (fromUrl) return fromUrl;
  // Last resort: tab-based key (new conversation not yet assigned a URL)
  const tabId = msg.tab_id || (sender.tab && sender.tab.id);
  return `tab:${tabId}`;
}

async function getSession(key) {
  const { sessions } = await getStorage(['sessions']);
  const all = sessions || {};
  return all[key] || { session_id: null, turns: [], conv_key: key };
}

async function saveSession(key, sessionData) {
  const { sessions } = await getStorage(['sessions']);
  const all = sessions || {};
  all[key] = { ...sessionData, conv_key: key };
  await setStorage({ sessions: all });
}

async function deleteSession(key) {
  const { sessions } = await getStorage(['sessions']);
  const all = sessions || {};
  delete all[key];
  await setStorage({ sessions: all });
}

// ─── API Helpers ──────────────────────────────────────────────────────────────

function makeHeaders(apiKey) {
  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${apiKey}`,
    'X-API-Key': apiKey
  };
}

async function callActAnalyze(apiKey, text, prompt, sessionId) {
  const body = {
    text,
    prompt: prompt || null,
    session_name: 'Claude.ai Extension'
  };
  if (sessionId) body.session_id = sessionId;

  const resp = await fetch(`${API_BASE}/v1/analyze`, {
    method: 'POST',
    headers: makeHeaders(apiKey),
    body: JSON.stringify(body)
  });

  if (!resp.ok) {
    const errText = await resp.text().catch(() => '');
    throw new Error(`ACT API error ${resp.status}: ${errText}`);
  }
  return resp.json();
}

async function callPsaAnalyze(apiKey, responseText, inputText, sessionId, turn, userText) {
  const body = {
    response_text: responseText,
    input_text: inputText || null,
    session_id: sessionId,
    turn: turn || 1,
    analyze_user_turn: true,
    user_text: userText || null
  };

  const resp = await fetch(`${API_BASE}/api/v2/psa/analyze`, {
    method: 'POST',
    headers: makeHeaders(apiKey),
    body: JSON.stringify(body)
  });

  if (!resp.ok) {
    const errText = await resp.text().catch(() => '');
    throw new Error(`PSA API error ${resp.status}: ${errText}`);
  }
  return resp.json();
}

// ─── Rate-Limited Queue ───────────────────────────────────────────────────────

async function processQueue() {
  if (isProcessing || callQueue.length === 0) return;
  isProcessing = true;

  while (callQueue.length > 0) {
    const now = Date.now();
    const elapsed = now - lastCallTime;
    if (elapsed < RATE_LIMIT_MS) {
      await sleep(RATE_LIMIT_MS - elapsed);
    }

    const item = callQueue.shift();
    lastCallTime = Date.now();

    try {
      await item.task();
    } catch (e) {
      console.error('[SPL] Queue task error:', e);
    }
  }

  isProcessing = false;
}

function enqueue(task) {
  callQueue.push({ task });
  processQueue();
}

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

// ─── Message Handlers ─────────────────────────────────────────────────────────

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  (async () => {
    try {
      switch (msg.type) {
        case 'ANALYZE_TURN':
          await handleAnalyzeTurn(msg, sender, sendResponse);
          break;
        case 'GET_EXPLANATION':
          await handleGetExplanation(msg, sender, sendResponse);
          break;
        case 'GET_SESSION_DATA':
          await handleGetSessionData(msg, sender, sendResponse);
          break;
        case 'CLEAR_SESSION':
          await handleClearSession(msg, sender, sendResponse);
          break;
        case 'SAVE_SETTINGS':
          await handleSaveSettings(msg, sender, sendResponse);
          break;
        case 'GET_SETTINGS':
          await handleGetSettings(msg, sender, sendResponse);
          break;
        default:
          sendResponse({ error: 'Unknown message type' });
      }
    } catch (e) {
      console.error('[SPL] Message handler error:', e);
      sendResponse({ error: e.message });
    }
  })();
  return true; // Keep channel open for async response
});

async function handleAnalyzeTurn(msg, sender, sendResponse) {
  const { turn_number, human_text, ai_text } = msg;

  const settings = await getSettings();
  if (!settings.splabs_key) {
    sendResponse({ error: 'no_api_key' });
    return;
  }

  const key = sessionKey(msg, sender);

  enqueue(async () => {
    let session = await getSession(key);
    let actResult = null;
    let psaResult = null;

    // Step 1: ACT analysis
    try {
      actResult = await callActAnalyze(
        settings.splabs_key, ai_text, human_text, session.session_id
      );
      // Capture server session_id on first turn
      if (!session.session_id && actResult && actResult.session_id) {
        session.session_id = actResult.session_id;
      }
    } catch (e) {
      console.error('[SPL] ACT error:', e);
      actResult = { error: e.message };
    }

    // Step 2: PSA analysis (requires session_id)
    if (session.session_id) {
      try {
        psaResult = await callPsaAnalyze(
          settings.splabs_key,
          ai_text,
          human_text,
          session.session_id,
          turn_number,
          settings.analyze_user_turns ? human_text : null
        );
      } catch (e) {
        console.error('[SPL] PSA error:', e);
        psaResult = { error: e.message };
      }
    }

    // Step 3: Build and store turn data
    const turnData = {
      turn_number,
      human: human_text,
      ai: ai_text,
      timestamp: new Date().toISOString(),
      act: actResult,
      psa: psaResult,
      explanation: null
    };

    // Upsert by turn_number
    const idx = session.turns.findIndex(t => t.turn_number === turn_number);
    if (idx >= 0) session.turns[idx] = turnData;
    else session.turns.push(turnData);
    session.turns.sort((a, b) => a.turn_number - b.turn_number);

    await saveSession(key, session);

    sendResponse({ act: actResult, psa: psaResult, session_id: session.session_id });

    // Broadcast to sidebar
    try {
      chrome.runtime.sendMessage({
        type: 'NEW_TURN_RESULT',
        conv_key: key,
        turn: turnData,
        session_id: session.session_id
      }).catch(() => {});
    } catch (_) {}
  });
}

async function handleGetExplanation(msg, sender, sendResponse) {
  const { turn_number } = msg;

  const settings = await getSettings();
  if (!settings.openrouter_key) {
    sendResponse({ error: 'no_openrouter_key' });
    return;
  }

  const key = sessionKey(msg, sender);
  const session = await getSession(key);
  const turn = session.turns.find(t => t.turn_number === turn_number);
  if (!turn) {
    sendResponse({ error: 'turn_not_found' });
    return;
  }

  try {
    const resp = await fetch(`${OPENROUTER_BASE}/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${settings.openrouter_key}`,
        'HTTP-Referer': 'https://claude.ai',
        'X-Title': 'Silicon Psyche Extension'
      },
      body: JSON.stringify({
        model: settings.openrouter_model || DEFAULT_MODEL,
        max_tokens: 200,
        messages: [{
          role: 'user',
          content: `You are an AI safety analyst. Analyze this behavioral telemetry result in 2-3 sentences for a non-technical user. Focus on what is happening and why it matters. Be direct and clear.\n\nData: ${JSON.stringify(turn, null, 2)}`
        }]
      })
    });

    if (!resp.ok) {
      const errText = await resp.text().catch(() => '');
      throw new Error(`OpenRouter error ${resp.status}: ${errText}`);
    }

    const data = await resp.json();
    const explanation = data?.choices?.[0]?.message?.content || 'No explanation available.';

    const idx = session.turns.findIndex(t => t.turn_number === turn_number);
    if (idx >= 0) session.turns[idx].explanation = explanation;
    await saveSession(key, session);

    sendResponse({ explanation });
  } catch (e) {
    console.error('[SPL] Explanation error:', e);
    sendResponse({ error: e.message });
  }
}

async function handleGetSessionData(msg, sender, sendResponse) {
  const key = sessionKey(msg, sender);
  const session = await getSession(key);
  sendResponse(session);
}

async function handleClearSession(msg, sender, sendResponse) {
  const key = sessionKey(msg, sender);
  await deleteSession(key);
  sendResponse({ ok: true });
}

async function handleSaveSettings(msg, _sender, sendResponse) {
  const { splabs_key, openrouter_key, openrouter_model, analyze_user_turns } = msg;
  await setStorage({
    splabs_key: splabs_key || '',
    openrouter_key: openrouter_key || '',
    openrouter_model: openrouter_model || DEFAULT_MODEL,
    analyze_user_turns: analyze_user_turns !== false
  });
  sendResponse({ ok: true });
}

async function handleGetSettings(_msg, _sender, sendResponse) {
  const s = await getSettings();
  sendResponse({
    splabs_key: s.splabs_key,
    openrouter_key: s.openrouter_key,
    openrouter_model: s.openrouter_model,
    analyze_user_turns: s.analyze_user_turns
  });
}
