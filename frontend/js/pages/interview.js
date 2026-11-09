import { api } from '../core/api.js';
import { esc, toast, $ } from '../core/dom.js';
import { mount } from '../core/shell.js';
import { getMeta, session } from '../core/state.js';
import { createRecognizer, speak, stopSpeaking, support, watchVoices } from '../voice/speech.js';

const LABELS = { technical_accuracy: 'Technical accuracy', depth: 'Depth', communication: 'Communication', structure: 'Structure' };
const READINESS = { not_ready: 'Not ready yet', developing: 'Developing', interview_ready: 'Interview ready' };
let iv = null;
let recognizer = null;

export async function loadInterview() {
  endSession(false);
  const [meta, history] = await Promise.all([getMeta(), api('/interview/sessions')]);
  const page = mount('interview', `
    <div class="page-intro"><div><h2>Interview lab</h2>
      <p class="muted">A voice or text interview with a Groq-powered interviewer. Questions can start from projects on your resume, and you get a rubric-based evaluation at the end.</p></div></div>
    <section class="panel voice-interview-panel"><div class="voice-interview-top"><div><h3>Practice session</h3>
      <p class="muted">Speech uses your browser's own recognition and voices, so there is no extra cost. Chrome or Edge works best.</p></div><div class="voice-orb" id="orb">◎</div></div>
      <div class="field-grid">
        <label>Target role<select id="role">${meta.roles.map((r) => `<option ${r === session.user?.target_role ? 'selected' : ''}>${esc(r)}</option>`).join('')}</select></label>
        <label>Difficulty<select id="difficulty"><option>Easy</option><option selected>Medium</option><option>Hard</option><option>Advanced</option></select></label>
        <label>Interviewer voice<select id="voiceMode"><option value="shuffle">Shuffle</option><option value="female">Female</option><option value="male">Male</option></select></label>
      </div>
      <label><input type="checkbox" id="useResume" checked> Ask about my resume when one is uploaded</label>
      <div class="voice-actions"><button class="btn btn-dark" id="start">Start interview</button>
        <button class="btn btn-outline" id="mic" disabled>Start listening</button><button class="btn btn-outline" id="end" disabled>End interview</button><span class="voice-status" id="status">Ready when you are</span></div>
      <div class="voice-note" id="note">${support.speaking ? '' : 'Speech output is unavailable here. You can read the questions and type answers.'}</div>
      <div class="voice-transcript" id="transcript"><div class="transcript-empty">The conversation will appear here.</div></div>
      <form class="voice-text-fallback" id="textForm"><input id="textAnswer" maxlength="2000" placeholder="Type your answer" autocomplete="off" disabled><button class="btn btn-dark" id="send" disabled>Send</button></form>
      <div id="feedback"></div></section>
    <section class="panel"><div class="panel-heading"><h3>Past interviews</h3></div>${history.map((h) => `<div class="history-row"><span><b>${esc(h.role)}</b><small>${esc(h.difficulty)} · ${h.turns} turns</small></span><strong>${h.average ? `${h.average}/5` : 'not evaluated'}</strong></div>`).join('') || '<p class="sp-empty">None yet.</p>'}</section>`);

  watchVoices((n) => { if (n) $('#note', page).textContent = `${n} English system voice(s) available. Gender is inferred from voice names, which browsers do not expose reliably.`; });
  recognizer = createRecognizer({
    onFinal: (text) => answer(text),
    onStart: () => { status('Listening…'); $('#mic').textContent = 'Stop listening'; },
    onEnd: () => { $('#mic') && ($('#mic').textContent = 'Start listening'); },
    onError: (code) => status(`Microphone problem (${code}). You can type instead.`),
  });
  $('#start', page).onclick = start;
  $('#mic', page).onclick = () => ($('#mic').textContent.startsWith('Stop') ? recognizer?.stop() : recognizer?.start());
  $('#end', page).onclick = () => endSession(true);
  $('#textForm', page).onsubmit = (event) => {
    event.preventDefault();
    const input = $('#textAnswer');
    const text = input.value.trim();
    if (text) { input.value = ''; answer(text); }
  };
}

const status = (text) => {
  const el = $('#status');
  if (el) el.textContent = text;
  $('#orb')?.classList.toggle('speaking', /speaking|listening/i.test(text));
};

function bubble(speaker, text) {
  const area = $('#transcript');
  area.querySelector('.transcript-empty')?.remove();
  const line = document.createElement('div');
  line.className = `voice-line ${speaker === 'candidate' ? 'candidate' : 'interviewer'}`;
  const label = document.createElement('b');
  label.textContent = speaker === 'candidate' ? 'YOU' : 'INTERVIEWER';
  const body = document.createElement('p');
  body.textContent = text;
  line.append(label, body);
  area.append(line);
  area.scrollTop = area.scrollHeight;
}

function setControls(running) {
  $('#start').disabled = running;
  $('#end').disabled = !running;
  $('#mic').disabled = !running || !recognizer;
  $('#textAnswer').disabled = !running;
  $('#send').disabled = !running;
}

async function start() {
  setControls(true);
  $('#transcript').innerHTML = '';
  $('#feedback').innerHTML = '';
  status('Preparing your interviewer…');
  try {
    const data = await api('/interview/sessions', { method: 'POST', json: { role: $('#role').value, difficulty: $('#difficulty').value, use_resume: $('#useResume').checked } });
    iv = { id: data.session_id, busy: false, answered: 0 };
    bubble('interviewer', data.question);
    if (data.resume_grounded) $('#note').textContent = 'This interview draws on your uploaded resume.';
    await speakAndListen(data.question);
  } catch (error) {
    iv = null;
    setControls(false);
    status('Could not start');
    toast(error.message);
  }
}

async function speakAndListen(text) {
  status('Interviewer is speaking…');
  await speak(text, $('#voiceMode')?.value);
  if (iv) { status('Your turn'); if (recognizer) recognizer.start(); }
}

async function answer(text) {
  if (!iv || iv.busy) return;
  iv.busy = true;
  recognizer?.stop();
  bubble('candidate', text);
  status('Thinking…');
  try {
    const data = await api(`/interview/sessions/${iv.id}/turns`, { method: 'POST', json: { text } });
    iv.answered++;
    bubble('interviewer', data.response);
    iv.busy = false;
    await speakAndListen(data.response);
  } catch (error) {
    iv.busy = false;
    status('That answer was not sent. Try again.');
    toast(error.message);
  }
}

function endSession(showEvaluate) {
  recognizer?.stop();
  stopSpeaking();
  const finished = iv;
  iv = null;
  if (!showEvaluate || !$('#feedback')) return;
  setControls(false);
  status('Interview ended');
  if (!finished?.answered) return;
  $('#feedback').innerHTML = '<button class="btn btn-outline" id="evaluate">Evaluate my interview</button>';
  $('#evaluate').onclick = async (event) => {
    event.target.disabled = true;
    event.target.textContent = 'Evaluating…';
    try {
      $('#feedback').innerHTML = renderEvaluation(await api(`/interview/sessions/${finished.id}/evaluate`, { method: 'POST' }));
    } catch (error) {
      event.target.disabled = false;
      event.target.textContent = 'Evaluate my interview';
      toast(error.message);
    }
  };
}

function renderEvaluation(e) {
  return `<div class="feedback-box sp-stack"><h3>${esc(READINESS[e.overall_readiness])} · ${e.average}/5 average</h3>
    <div class="sp-rubric">${Object.entries(e.scores).map(([k, v]) => `<div><b>${v}/5</b><span>${esc(LABELS[k])}</span></div>`).join('')}</div>
    ${e.strengths.length ? `<div><h4>Strengths</h4><ul class="sp-list">${e.strengths.map((s) => `<li>${esc(s)}</li>`).join('')}</ul></div>` : ''}
    ${e.improvements.length ? `<div><h4>To improve</h4><ul class="sp-list">${e.improvements.map((s) => `<li>${esc(s)}</li>`).join('')}</ul></div>` : ''}
    ${e.answer_notes.length ? `<div><h4>Answer by answer</h4>${e.answer_notes.map((n) => `<p><b>${esc(n.question)}</b><br>${esc(n.feedback)}${n.evidence ? `<br><span class="sp-quote">“${esc(n.evidence)}”</span>` : ''}</p>`).join('')}</div>` : ''}
    <p class="sp-field-note">Scored by an AI model against a fixed rubric. Treat it as practice feedback, not a verdict.</p></div>`;
}
