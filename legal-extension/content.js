// Intercepts copy events and detects legal content without touching the host page DOM.
// Passes detected text to the service worker via message passing — no clipboard API polling,
// no DOM scraping, no third-party site dependency.

const LEGAL_CITATION = /\d+\s+(?:U\.S\.|F\.\d[a-z]*|S\.Ct\.|L\.Ed\.|F\.Supp\.|Cal\.|N\.Y\.|Tex\.|Fla\.|Ill\.)\s+\d+/i;

const LEGAL_TERMS = [
  'plaintiff', 'defendant', 'liability', 'statute', 'jurisdiction',
  'holding', 'tort', 'breach', 'contract', 'indemnif', 'negligenc',
  'fiduciar', 'amendment', 'constitutional', 'pursuant', 'wherefore',
  'prima facie', 'res judicata', 'habeas', 'certiorari', 'injunction',
  'deposition', 'affidavit', 'subpoena', 'stipulation', 'damages',
  'malpractice', 'claimant', 'respondent', 'appellant', 'appellee',
  'motion to dismiss', 'summary judgment', 'discovery', 'pleading',
  'counterclaim', 'arbitration', 'settlement', 'litigation'
];

function isLegalContent(text) {
  if (!text || text.trim().length < 80) return false;
  if (LEGAL_CITATION.test(text)) return true;
  const lower = text.toLowerCase();
  return LEGAL_TERMS.some(term => lower.includes(term));
}

document.addEventListener('copy', () => {
  const selected = window.getSelection()?.toString() || '';
  if (!isLegalContent(selected)) return;

  chrome.runtime.sendMessage({
    type: 'LEGAL_COPY_DETECTED',
    text: selected.slice(0, 4000),
    url: window.location.hostname
  }).catch(() => {});
});
