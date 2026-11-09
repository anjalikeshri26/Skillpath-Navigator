import { api } from '../core/api.js';
import { esc, toast, $, $$ } from '../core/dom.js';
import { downloadText, saveShortcut } from '../core/files.js';
import { renderMarkdown } from '../core/markdown.js';
import { setNavigationGuard } from '../core/router.js';
import { mount } from '../core/shell.js';

let draft = null; // { subject, title, markdown, words, model, truncated, saved: note | null, dirty, mode }

export async function loadStudy(params = {}) {
  draft = null;
  let suggestions = [];
  try { suggestions = (await api('/roadmap')).items.filter((i) => !i.completed).slice(0, 5).map((i) => i.topic); } catch { /* suggestions are optional */ }
  mount('study', `
    <div class="page-intro"><div><h2>Study notes</h2>
      <p class="muted">Name a subject and the AI writes structured notes: concepts, worked examples, common mistakes and interview questions. Nothing is stored until you save it, and you can edit the text first. The model can make mistakes, so check anything you will rely on.</p></div></div>
    <section class="panel"><form id="studyForm" class="sp-stack">
      <div class="field-grid"><label>Subject<input id="subject" required minlength="2" maxlength="120" placeholder="e.g. Process scheduling in operating systems" value="${esc(params.subject || '')}"></label>
        <label>Depth<select id="depth"><option>Quick revision</option><option selected>Standard</option><option>In-depth</option></select></label>
        <label>Focus (optional)<input id="focus" maxlength="200" placeholder="e.g. round robin and time quantum"></label></div>
      ${suggestions.length ? `<div><span class="sp-field-note">From your roadmap:</span> ${suggestions.map((s) => `<button type="button" class="sp-filter" data-suggest="${esc(s)}">${esc(s)}</button>`).join('')}</div>` : ''}
      <div class="sp-row"><button class="btn btn-dark" id="generate">Write notes</button><span class="sp-status" id="genStatus" role="status"></span></div>
    </form></section>
    <div id="draftArea"></div>`);

  setNavigationGuard(() => !draft?.dirty || confirm('These notes have not been saved. Leave and lose them?'));
  $$('[data-suggest]').forEach((b) => b.addEventListener('click', () => { $('#subject').value = b.dataset.suggest; $('#subject').focus(); }));
  $('#studyForm').addEventListener('submit', (event) => { event.preventDefault(); generate(); });
}

async function generate() {
  if (draft?.dirty && !confirm('Replace the notes you have not saved?')) return;
  const button = $('#generate');
  const body = { subject: $('#subject').value, depth: $('#depth').value, focus: $('#focus').value };
  button.disabled = true;
  $('#genStatus').textContent = body.depth === 'In-depth' ? 'Writing, this can take up to two minutes…' : 'Writing, this usually takes under a minute…';
  try {
    const result = await api('/study/generate', { method: 'POST', json: body });
    draft = { ...result, saved: null, dirty: true, mode: 'preview' };
    $('#genStatus').textContent = '';
    renderDraft();
    $('#draftArea').scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (error) {
    $('#genStatus').textContent = error.message;
    $('#genStatus').className = 'sp-status error';
  } finally {
    button.disabled = false;
  }
}

function renderDraft() {
  const area = $('#draftArea');
  const saved = draft.saved;
  area.innerHTML = `<section class="panel sp-stack" id="draftPanel">
    <div class="sp-row"><div><h3>Your notes are ready</h3><span class="sp-field-note">${draft.words} words · written by ${esc(draft.model)}</span></div>
      <div class="sp-tabs" role="tablist"><button role="tab" class="${draft.mode === 'preview' ? 'active' : ''}" data-mode="preview">Preview</button><button role="tab" class="${draft.mode === 'edit' ? 'active' : ''}" data-mode="edit">Edit</button></div></div>
    ${draft.truncated ? '<div class="sp-notice">The answer hit the length limit and may end abruptly. Try Quick revision or a narrower subject.</div>' : ''}
    ${draft.mode === 'edit' ? `<textarea id="draftText" class="note-body" aria-label="Edit notes">${esc(draft.markdown)}</textarea>` : `<div class="md note-preview">${renderMarkdown(draft.markdown)}</div>`}
    <label>Save as<input id="draftTitle" maxlength="120" value="${esc(draft.title)}"></label><div class="sp-field-note error" id="titleError" role="alert"></div>
    <div class="sp-row"><span class="sp-status ${saved ? 'ok' : 'warn'}" id="saveStatus" role="status">${saved ? 'Saved to Your notes' : 'Not saved yet'}</span>
      <div class="sp-actions"><button class="btn btn-outline" id="regen">Write again</button><button class="btn btn-outline" id="dl">Download .md</button>
        ${saved ? '<a class="btn btn-outline" href="#/notes?id=' + saved.id + '">Open in Your notes</a>' : ''}
        <button class="btn btn-dark" id="saveDraft">${saved ? 'Save changes' : 'Save to Your notes'}</button></div></div></section>`;

  $$('[data-mode]', area).forEach((b) => b.addEventListener('click', () => { syncFromEditor(); draft.mode = b.dataset.mode; renderDraft(); }));
  $('#draftTitle').addEventListener('input', (e) => { draft.title = e.target.value; draft.dirty = true; });
  $('#draftText')?.addEventListener('input', (e) => { draft.markdown = e.target.value; draft.dirty = true; });
  $('#regen').onclick = generate;
  $('#dl').onclick = () => { syncFromEditor(); downloadText(draft.title, draft.markdown); };
  $('#saveDraft').onclick = saveDraft;
  saveShortcut(area, saveDraft);
}

const syncFromEditor = () => { const text = $('#draftText'); if (text) draft.markdown = text.value; };

async function saveDraft() {
  syncFromEditor();
  const title = $('#draftTitle').value.trim();
  $('#titleError').textContent = '';
  if (!title) { $('#titleError').textContent = 'Give the notes a name first.'; return; }
  const button = $('#saveDraft');
  button.disabled = true;
  try {
    const note = draft.saved
      ? await api(`/notes/${draft.saved.id}`, { method: 'PUT', json: { title, body: draft.markdown, pinned: draft.saved.pinned, revision: draft.saved.revision } })
      : await api('/notes', { method: 'POST', json: { title, body: draft.markdown, source: 'generated', subject: draft.subject } });
    Object.assign(draft, { saved: note, title: note.title, dirty: false });
    renderDraft();
    toast('Saved to Your notes');
  } catch (error) {
    $('#titleError').textContent = error.message;
    button.disabled = false;
    if (error.status === 409) $('#draftTitle').focus();
  }
}
