import { api } from '../core/api.js';
import { bar, esc, toast, $, $$ } from '../core/dom.js';
import { mount } from '../core/shell.js';
import { session } from '../core/state.js';

export async function loadRoadmap() {
  const data = await api('/roadmap');
  paint(data);
}

function paint({ items, summary }) {
  const progress = summary.total ? summary.completed / summary.total : 0;
  const page = mount('roadmap', `
    <div class="page-intro"><div><h2>Your learning roadmap</h2>
      <p class="muted">Ordered so prerequisites come first. Priority reflects the role's skill weights and what your quizzes and resume show about you. It updates after each test.</p></div>
      <div class="role-pill">${esc(session.user?.target_role || '')}</div></div>
    <section class="panel"><div class="sp-row"><div><b>${summary.completed} of ${summary.total}</b> skills complete · about ${summary.hours_remaining} hours remaining</div>
      <button class="btn btn-outline" id="rebuild">Recalculate</button></div>${bar(progress)}</section>
    <div class="roadmap-list">${items.map(card).join('') || '<p class="sp-empty">Nothing to study right now. Great work.</p>'}</div>`);

  $$('[data-complete]', page).forEach((el) => el.addEventListener('click', async () => {
    try {
      await api(`/roadmap/${el.dataset.complete}`, { method: 'PATCH', json: { completed: el.dataset.state !== 'true' } });
      paint(await api('/roadmap'));
    } catch (error) { toast(error.message); }
  }));
  $('#rebuild', page).addEventListener('click', async () => {
    try { paint(await api('/roadmap/rebuild', { method: 'POST' })); toast('Roadmap recalculated'); } catch (error) { toast(error.message); }
  });
}

const card = (x) => `<article class="roadmap-item">
  <div class="roadmap-check ${x.completed ? 'checked' : ''}" role="button" tabindex="0" aria-label="Toggle complete" data-complete="${x.id}" data-state="${x.completed}">${x.completed ? '✓' : ''}</div>
  <div class="roadmap-info"><div class="roadmap-title"><h3>${esc(x.topic)}</h3><span class="priority ${x.priority.toLowerCase()}">${x.priority} priority</span></div>
    <p>${esc(x.reason)}</p>
    <div class="roadmap-meta"><span>About ${x.estimated_hours}h</span><a href="#/study?subject=${encodeURIComponent(x.topic)}">Write study notes</a>${x.prerequisites.length ? `<span>Needs: ${x.prerequisites.map(esc).join(', ')}</span>` : ''}</div>
    <div class="roadmap-meta">${x.resources.map((r) => `<a class="sp-resource" href="${esc(r.url)}" target="_blank" rel="noopener noreferrer">${esc(r.title)} <small>(${esc(r.kind)}, ${esc(r.level)})</small></a>`).join('')}</div>
  </div></article>`;
