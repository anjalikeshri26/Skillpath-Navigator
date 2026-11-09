const ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };

/** Escape text before putting it in an HTML template. Every dynamic value must go through this. */
export const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ESCAPES[c]);

export const $ = (selector, root = document) => root.querySelector(selector);
export const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

let toastTimer;
export function toast(message) {
  const el = document.getElementById('toast');
  if (!el) return;
  el.textContent = message;
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 3200);
}

export const percent = (fraction) => Math.round((fraction ?? 0) * 100);
export const formatDate = (iso) => new Date(iso + (iso.endsWith('Z') ? '' : 'Z')).toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
export const formatClock = (seconds) => {
  const s = Math.max(0, seconds);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
};

/** A progress bar. `fraction` is 0..1; `tone` picks a colour from how strong the value is. */
export function bar(fraction, { early = false } = {}) {
  const value = Math.max(0, Math.min(1, fraction ?? 0));
  const tone = value < 0.4 ? 'low' : value < 0.65 ? 'warn' : '';
  return `<div class="sp-bar ${tone} ${early ? 'early' : ''}"><i style="width:${Math.round(value * 100)}%"></i></div>`;
}
