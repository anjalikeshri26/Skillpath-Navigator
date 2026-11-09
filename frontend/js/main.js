import { toast } from './core/dom.js';
import { clearSession, session } from './core/state.js';
import { clearNavigationGuard, onLanding, registerRoute, startRouter } from './core/router.js';
import { showAuth } from './pages/auth.js';
import { loadAssistant } from './pages/assistant.js';
import { loadDashboard } from './pages/dashboard.js';
import { loadInterview } from './pages/interview.js';
import { loadProfile } from './pages/profile.js';
import { loadNotes } from './pages/notes.js';
import { loadResume } from './pages/resume.js';
import { loadRoadmap } from './pages/roadmap.js';
import { loadStudy } from './pages/study.js';
import { loadTests } from './pages/quiz.js';

const app = document.getElementById('app');
const landingHtml = app.innerHTML;

onLanding(() => {
  document.body.classList.remove('in-app');
  // Landing-page anchors (#method, #features) also fire hashchange; only redraw if the landing page is not showing.
  if (!app.querySelector('.hero')) app.innerHTML = landingHtml;
});

registerRoute('dashboard', loadDashboard);
registerRoute('roadmap', loadRoadmap);
registerRoute('resume', loadResume);
registerRoute('tests', loadTests);
registerRoute('study', loadStudy);
registerRoute('notes', loadNotes);
registerRoute('assistant', loadAssistant);
registerRoute('interview', loadInterview);
registerRoute('profile', loadProfile);

function signOut(message) {
  clearNavigationGuard();
  clearSession();
  history.replaceState(null, '', location.pathname);
  showAuth('login');
  if (message) toast(message);
}

document.addEventListener('click', (event) => {
  const target = event.target instanceof Element ? event.target : null;
  const action = target?.closest('[data-action]');
  if (action) {
    event.preventDefault();
    if (action.dataset.action === 'logout') signOut();
    else showAuth(action.dataset.action);
    return;
  }
  if (target?.closest('[data-page="home"]')) {
    event.preventDefault();
    session.token ? (location.hash = '#/dashboard') : (app.innerHTML = landingHtml);
  }
});

window.addEventListener('sp:unauthorized', () => signOut('Your session has expired. Please sign in again.'));

startRouter();
