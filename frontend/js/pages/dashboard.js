import { api } from '../core/api.js';
import { bar, esc, formatDate, percent } from '../core/dom.js';
import { mount } from '../core/shell.js';
import { session } from '../core/state.js';

export async function loadDashboard() {
  const d = await api('/dashboard');
  const s = d.stats;
  const first = esc((session.user?.name || 'there').split(' ')[0]);
  const today = new Date().toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long' });
  const next = d.next_step;
  const progress = s.total ? s.completed / s.total : 0;

  mount('dashboard', `
    <div class="welcome-row"><div><div class="section-kicker">${esc(today)}</div><h2>Hello, ${first}.</h2></div></div>
    <div class="sp-next"><div><h3>${esc(next.title)}</h3><p>${esc(next.detail)}</p></div>
      <a class="btn btn-light" href="#/${next.view}${next.topic ? `?topic=${encodeURIComponent(next.topic)}` : ''}">Open</a></div>
    <div class="metric-grid">
      <div class="metric-card"><span>Roadmap progress</span><b>${percent(progress)}<small>%</small></b>${bar(progress)}<em>${s.completed} of ${s.total} skills done, about ${s.hours_remaining}h left</em></div>
      <div class="metric-card"><span>Tests taken</span><b>${s.tests_taken}</b><em>${s.questions_answered} questions answered</em></div>
      <div class="metric-card"><span>Recent average</span><b>${s.recent_average ?? '–'}${s.recent_average === null ? '' : '<small>%</small>'}</b><em>${s.recent_average === null ? 'Take a test to see this' : 'Across your last 10 tests'}</em></div>
      <div class="metric-card"><span>Active days</span><b>${s.active_days_14}</b><em>Days with a test in the last 14</em></div>
    </div>
    <div class="sp-grid-2">
      <section class="panel"><div class="panel-heading"><h3>Topic mastery</h3><a class="inline-link" href="#/tests">Practise</a></div>
        ${d.mastery.length ? d.mastery.map(masteryRow).join('') : '<p class="sp-empty">Mastery appears after your first test. Faded bars mean few answers so far.</p>'}</section>
      <section class="panel"><div class="panel-heading"><h3>Next on your roadmap</h3><a class="inline-link" href="#/roadmap">View all</a></div>
        ${d.roadmap_preview.map((x) => `<div class="roadmap-row"><div class="check-circle"></div><div><b>${esc(x.topic)}</b><small>${esc(x.reason)}</small></div><span class="priority ${x.priority.toLowerCase()}">${x.priority}</span></div>`).join('') || '<p class="sp-empty">Nothing outstanding.</p>'}</section>
    </div>
    <section class="panel history-panel"><div class="panel-heading"><h3>Recent tests</h3></div>
      ${d.recent_attempts.map((a) => `<div class="history-row"><span><b>${esc(a.topic)}</b><small>${formatDate(a.date)} · ${esc(a.difficulty)} · ${a.correct}/${a.total}</small></span><strong>${a.score}%</strong></div>`).join('') || '<p class="sp-empty">No tests yet.</p>'}</section>`);
}

const masteryRow = (m) => `<div class="sp-bar-row"><div class="label">${esc(m.topic)}<small>next: ${esc(m.recommended_difficulty)}</small></div>${bar(m.mastery, { early: !m.reliable })}<b>${percent(m.mastery)}%</b></div>`;
