import { api } from '../core/api.js';
import { esc, formatDate, toast, $, $$ } from '../core/dom.js';
import { renderMarkdown } from '../core/markdown.js';
import { setNavigationGuard } from '../core/router.js';
import { mount } from '../core/shell.js';
import { downloadText, saveShortcut } from '../core/files.js';

const FILTERS = [['', 'All'], ['written', 'Written by me'], ['generated', 'From Study']];
let state;

const freshState = () => ({ items: [], total: 0, query: '', source: '', note: null, title: '', body: '', pinned: false, mode: 'write', dirty: false, saving: false, open: false });

export async function loadNotes(params = {}) {
  state = freshState();
  mount('notes', `<div class="notes-layout">
    <aside class="panel notes-side"><div class="sp-row"><h3>Your notes</h3><button class="btn btn-dark" id="newNote">New note</button></div>
      <input type="search" id="search" placeholder="Search titles and text" aria-label="Search notes" maxlength="100">
      <div class="sp-chips" id="filters">${FILTERS.map(([value, label]) => `<button class="sp-filter ${value === '' ? 'active' : ''}" data-source="${value}">${label}</button>`).join('')}</div>
      <div id="noteList" class="note-list" aria-live="polite"></div></aside>
    <section class="panel notes-editor" id="noteEditor"></section></div>`);

  setNavigationGuard(() => !state.dirty || confirm('You have unsaved changes in this note. Leave without saving?'));
  $('#newNote').onclick = () => guarded(startNew);
  let timer;
  $('#search').addEventListener('input', (event) => {
    clearTimeout(timer);
    timer = setTimeout(() => { state.query = event.target.value; refreshList(); }, 250);
  });
  $('#filters').addEventListener('click', (event) => {
    const button = event.target.closest('[data-source]');
    if (!button) return;
    state.source = button.dataset.source;
    $$('.sp-filter').forEach((b) => b.classList.toggle('active', b === button));
    refreshList();
  });
  $('#noteList').addEventListener('click', (event) => {
    const item = event.target.closest('[data-id]');
    if (item) guarded(() => openNote(Number(item.dataset.id)));
  });

  await refreshList();
  if (params.id) await openNote(Number(params.id));
  else if (state.items.length && !params.new) await openNote(state.items[0].id);
  else startNew();
}

window.addEventListener('beforeunload', (event) => {
  if (state?.dirty && document.getElementById('noteEditor')) { event.preventDefault(); event.returnValue = ''; }
});

const guarded = (action) => { if (!state.dirty || confirm('Discard your unsaved changes?')) action(); };

async function refreshList() {
  const query = new URLSearchParams({ q: state.query, source: state.source });
  try {
    const data = await api(`/notes?${query}`);
    state.items = data.items;
    state.total = data.total;
  } catch (error) { toast(error.message); return; }
  const list = $('#noteList');
  if (!list) return;
  list.innerHTML = state.items.map((n) => `<button class="note-item ${state.note?.id === n.id ? 'active' : ''}" data-id="${n.id}">
      <b>${n.pinned ? '<span title="Pinned">★</span> ' : ''}${esc(n.title)}</b>${n.source === 'generated' ? '<span class="sp-badge">Study</span>' : ''}
      <small>${esc(n.excerpt) || 'Empty note'}</small><small>${formatDate(n.updated_at)} · ${n.word_count} words</small></button>`).join('')
    || `<p class="sp-empty">${state.query || state.source ? 'No notes match.' : 'No notes yet. Write one, or generate notes in Study.'}</p>`;
}

async function openNote(id) {
  try {
    const note = await api(`/notes/${id}`);
    Object.assign(state, { note, title: note.title, body: note.body, pinned: note.pinned, dirty: false, mode: 'write' });
    renderEditor();
    refreshList();
  } catch (error) { toast(error.message); if (error.status === 404) { await refreshList(); startNew(); } }
}

function startNew() {
  Object.assign(state, { note: null, title: '', body: '', pinned: false, dirty: false, mode: 'write' });
  renderEditor();
  refreshList();
  $('#title')?.focus();
}

function renderEditor() {
  const editor = $('#noteEditor');
  if (!editor) return;
  const saved = state.note;
  editor.innerHTML = `
    <div class="sp-row"><input id="title" class="note-title" maxlength="120" placeholder="Name this note" aria-label="Note name" value="${esc(state.title)}">
      <div class="sp-tabs" role="tablist"><button role="tab" class="${state.mode === 'write' ? 'active' : ''}" data-mode="write">Write</button><button role="tab" class="${state.mode === 'preview' ? 'active' : ''}" data-mode="preview">Preview</button></div></div>
    <div id="surface">${state.mode === 'write'
      ? `<textarea id="body" class="note-body" aria-label="Note text" maxlength="100000" placeholder="Write in Markdown: # headings, **bold**, lists, \`code\`, tables">${esc(state.body)}</textarea>`
      : `<div class="md note-preview">${state.body.trim() ? renderMarkdown(state.body) : '<p class="sp-empty">Nothing to preview yet.</p>'}</div>`}</div>
    <div class="sp-row note-bar"><span class="sp-status" id="status" role="status"></span>
      <div class="sp-actions">
        <button class="btn btn-outline" id="pin" aria-pressed="${state.pinned}">${state.pinned ? 'Unpin' : 'Pin'}</button>
        <button class="btn btn-outline" id="copy">Copy</button><button class="btn btn-outline" id="download">Download .md</button>
        ${saved ? '<button class="btn btn-outline" id="delete">Delete</button>' : ''}
        <button class="btn btn-dark" id="save">${saved ? 'Save changes' : 'Save note'}</button></div></div>`;
  setStatus(saved ? `Last saved ${new Date(saved.updated_at + 'Z').toLocaleString()}` : 'Not saved yet');

  $('#title').addEventListener('input', (e) => { state.title = e.target.value; markDirty(); });
  $('#body')?.addEventListener('input', (e) => { state.body = e.target.value; markDirty(); });
  $$('[data-mode]', editor).forEach((b) => b.addEventListener('click', () => { state.mode = b.dataset.mode; renderEditor(); }));
  $('#pin').onclick = () => { state.pinned = !state.pinned; markDirty(); $('#pin').textContent = state.pinned ? 'Unpin' : 'Pin'; };
  $('#save').onclick = save;
  $('#copy').onclick = () => navigator.clipboard.writeText(state.body).then(() => toast('Copied to clipboard'), () => toast('Copy was blocked by the browser'));
  $('#download').onclick = () => downloadText(state.title || 'note', state.body);
  $('#delete')?.addEventListener('click', remove);
  saveShortcut(editor, save);
  if (state.mode === 'write') $('#body').focus({ preventScroll: true });
}

function setStatus(text, tone = '') {
  const el = $('#status');
  if (!el) return;
  el.textContent = text;
  el.className = `sp-status ${tone}`;
}

function markDirty() {
  state.dirty = true;
  setStatus('Unsaved changes', 'warn');
}

async function save() {
  if (state.saving) return;
  const title = state.title.trim();
  if (!title) { setStatus('Give the note a name before saving.', 'error'); $('#title').focus(); return; }
  state.saving = true;
  $('#save').disabled = true;
  try {
    const saved = state.note
      ? await api(`/notes/${state.note.id}`, { method: 'PUT', json: { title, body: state.body, pinned: state.pinned, revision: state.note.revision } })
      : await api('/notes', { method: 'POST', json: { title, body: state.body, source: 'written' } });
    Object.assign(state, { note: saved, title: saved.title, dirty: false });
    renderEditor();
    refreshList();
    setStatus(`Saved at ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`, 'ok');
  } catch (error) {
    setStatus(error.message, 'error');
    if (error.status === 409 && state.note && /another tab|changed somewhere/i.test(error.message)) {
      const reload = document.createElement('button');
      reload.className = 'sp-link-button';
      reload.textContent = 'Discard my edits and reload';
      reload.onclick = () => openNote(state.note.id);
      $('#status').append(' ', reload);
    }
  } finally {
    state.saving = false;
    const button = $('#save');
    if (button) button.disabled = false;
  }
}

async function remove() {
  if (!confirm(`Delete \u201c${state.note.title}\u201d? This cannot be undone.`)) return;
  try {
    await api(`/notes/${state.note.id}`, { method: 'DELETE' });
    toast('Note deleted');
    startNew();
  } catch (error) { toast(error.message); }
}
