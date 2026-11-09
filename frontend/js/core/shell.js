import { api } from './api.js';
import { esc, $ } from './dom.js';
import { session } from './state.js';

const NAV = [
  ['dashboard', '◫', 'Overview'],
  ['roadmap', '⌁', 'My roadmap'],
  ['resume', '▤', 'Resume studio'],
  ['tests', '◷', 'Mock tests'],
  ['study', '▦', 'Study notes'],
  ['notes', '✎', 'Your notes'],
  ['assistant', '✳', 'AI assistant'],
  ['interview', '◎', 'Interview lab'],
];
const TITLES = { dashboard: 'Your preparation at a glance', roadmap: 'Roadmap', resume: 'Resume studio', tests: 'Mock tests', study: 'Study notes', notes: 'Your notes', assistant: 'AI assistant', interview: 'Interview lab', profile: 'Profile settings' };

/** Draw the signed-in layout and return the element pages render into. */
export function mount(active, contentHtml) {
  const app = document.getElementById('app');
  document.body.classList.add('in-app');
  const user = session.user || {};
  const link = ([view, icon, label]) => `<a class="side-link ${view === active ? 'active' : ''}" href="#/${view}">${icon} <span>${label}</span></a>`;
  app.innerHTML = `<div class="workspace"><aside class="sidebar">
    <a class="brand" href="#/dashboard"><span class="brand-mark">S</span><span>skillpath<span class="brand-light"> navigator</span></span></a>
    <div class="side-label">WORKSPACE</div>${NAV.map(link).join('')}
    <div class="sidebar-bottom"><div class="side-label">ACCOUNT</div>
      <a class="side-link ${active === 'profile' ? 'active' : ''}" href="#/profile">⚙ <span>Profile settings</span></a>
      <button class="side-link" data-action="logout">↪ <span>Sign out</span></button>
      <div class="mini-user"><div class="user-avatar">${esc((user.name || 'S')[0].toUpperCase())}</div><span><b>${esc(user.name || 'Student')}</b><small>${esc(user.target_role || 'Placement candidate')}</small></span></div>
    </div></aside>
    <section class="workspace-main"><header class="workspace-top"><div><span class="breadcrumb">Student workspace</span><h1>${esc(TITLES[active] || '')}</h1></div>
      <div class="top-user"><span class="status-dot" id="aiDot"></span><span id="aiLabel">Checking AI…</span><div class="user-avatar">${esc((user.name || 'S')[0].toUpperCase())}</div></div></header>
      <div class="page-content" id="page">${contentHtml}</div></section></div>`;
  window.scrollTo(0, 0);
  refreshAiStatus();
  return $('#page');
}

async function refreshAiStatus() {
  try {
    const health = await api('/health');
    const on = health.ai.configured;
    $('#aiLabel').textContent = on ? 'Groq connected' : 'AI features off';
    $('#aiLabel').title = on ? `Model: ${health.ai.model}` : 'Add GROQ_API_KEY to backend/.env to enable interviews, the tutor and question generation';
    $('#aiDot').style.background = on ? '' : '#c9a24b';
  } catch { /* the status indicator is informational only */ }
}

export function leaveApp() {
  document.body.classList.remove('in-app');
}
