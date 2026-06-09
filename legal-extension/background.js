// Service worker: receives legal content from content script,
// stores it and updates the badge so the user knows something is ready to analyze.

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type !== 'LEGAL_COPY_DETECTED') return;

  chrome.storage.session.set({
    pendingText: msg.text,
    pendingUrl: msg.url,
    pendingAt: Date.now()
  });

  chrome.action.setBadgeText({ text: '!' });
  chrome.action.setBadgeBackgroundColor({ color: '#c0a43a' });

  sendResponse({ ok: true });
});

chrome.action.onClicked.addListener(() => {
  chrome.action.setBadgeText({ text: '' });
});
