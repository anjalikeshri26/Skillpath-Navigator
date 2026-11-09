import { api } from '../core/api.js';
import { bar, esc, toast, $ } from '../core/dom.js';
import { mount } from '../core/shell.js';
import { session } from '../core/state.js';

export async function loadResume() {
  const latest = await api('/resume/latest');
  const page = mount('resume', `
    <div class="page-intro"><div><h2>Resume studio</h2>
      <p class="muted">Feedback is measured against the skills expected for <b>${esc(session.user?.target_role || 'your role')}</b>. Nothing is rewritten for you, so your achievements stay yours.</p></div></div>
    <section class="panel"><div class="sp-stack">
      <div><label class="btn btn-dark file-button">Choose resume<input id="resumeFile" type="file" accept=".pdf,.docx" hidden></label>
        <span class="muted" id="fileName"> PDF or DOCX, up to 8 MB, text-based</span></div>
      <label>Job description (optional)<textarea class="sp-textarea" id="jd" maxlength="6000" placeholder="Paste a job posting to see which of its skills your resume covers"></textarea></label>
      <div><button class="btn btn-dark" id="analyse" disabled>Analyse resume</button></div>
    </div></section>
    <div id="resumeResult">${latest ? render(latest) : ''}</div>
    <div class="notice"><b>About the score</b><p>It is a transparent checklist, not an ATS simulation: every point below is explained. Scanned PDFs need OCR first. Add a skill only if it matches your real experience.</p></div>`);

  const fileInput = $('#resumeFile', page);
  fileInput.addEventListener('change', () => {
    $('#fileName', page).textContent = fileInput.files[0]?.name ?? '';
    $('#analyse', page).disabled = !fileInput.files[0];
  });
  $('#analyse', page).addEventListener('click', async (event) => {
    const form = new FormData();
    form.append('file', fileInput.files[0]);
    form.append('job_description', $('#jd', page).value);
    event.target.disabled = true;
    $('#resumeResult', page).innerHTML = '<p class="muted">Reading your resume…</p>';
    try {
      $('#resumeResult', page).innerHTML = render(await api('/resume/analyze', { method: 'POST', form }));
      wireDelete(page);
    } catch (error) {
      $('#resumeResult', page).innerHTML = `<p class="error">${esc(error.message)}</p>`;
    } finally {
      event.target.disabled = false;
    }
  });
  wireDelete(page);
}

function wireDelete(page) {
  const button = $('#deleteResume', page);
  if (!button) return;
  button.addEventListener('click', async () => {
    if (!confirm('Delete this resume and its analysis?')) return;
    try {
      await api(`/resume/${button.dataset.id}`, { method: 'DELETE' });
      $('#resumeResult', page).innerHTML = '';
      toast('Resume deleted');
    } catch (error) { toast(error.message); }
  });
}

function render(record) {
  const a = record.analysis;
  const chips = a.skills.map((s) => `<span class="sp-chip ${s.evidence}" title="${s.evidence === 'demonstrated' ? 'Shown in a project or experience' : 'Only listed'}">${esc(s.name)}</span>`).join('');
  const missing = a.missing_skills.map((s) => `<span class="sp-chip missing">${esc(s.name)}</span>`).join('');
  const jd = a.jd_match;
  return `<section class="panel sp-stack">
    <div class="sp-row"><div><div class="sp-score-ring">${a.score}<small>/100</small></div><small class="muted">${esc(record.filename)} · scored for ${esc(a.role)}</small></div>
      <button class="sp-link-button" id="deleteResume" data-id="${record.id}">Delete this resume</button></div>
    <div class="sp-breakdown">${a.breakdown.map((b) => `<div class="sp-bar-row"><div class="label">${esc(b.label)}<small>${esc(b.detail)}</small></div>${bar(b.points / b.max)}<b>${b.points}/${b.max}</b></div>`).join('')}</div>
    <div><h4>Skills found</h4>${chips || '<p class="sp-empty">None of the tracked skills were recognised.</p>'}
      <p class="sp-field-note">Green: shown in a project or experience. Beige: only listed.</p></div>
    ${a.missing_skills.length ? `<div><h4>Expected for this role but not found</h4>${missing}</div>` : ''}
    ${jd ? `<div><h4>Match against the job description</h4>${jd.skill_coverage === null ? '' : `<p><b>${Math.round(jd.skill_coverage * 100)}%</b> of its recognised skills appear on your resume.</p>`}
      ${jd.missing.length ? `<p>Not found: ${jd.missing.map((m) => `<span class="sp-chip missing">${esc(m)}</span>`).join('')}</p>` : ''}<p class="sp-field-note">${esc(jd.note)}</p></div>` : ''}
    ${a.recommendations.length ? `<div><h4>What to improve</h4><ul class="sp-list">${a.recommendations.map((r) => `<li>${esc(r)}</li>`).join('')}</ul></div>` : ''}
    <p class="muted">${esc(a.disclaimer)}</p></section>`;
}
