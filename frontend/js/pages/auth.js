import { api } from '../core/api.js';
import { esc, toast } from '../core/dom.js';
import { setSession } from '../core/state.js';
import { navigate } from '../core/router.js';

export function showAuth(mode = 'login') {
  const registering = mode === 'register';
  document.body.classList.remove('in-app');
  document.getElementById('app').innerHTML = `<div class="auth-shell">
    <div class="auth-aside"><a class="brand" href="#" data-page="home"><span class="brand-mark">S</span><span>skillpath<span class="brand-light"> navigator</span></span></a>
      <div class="auth-message"><h2>Your plan is<br>waiting <em>here.</em></h2><p>Sign in to see your roadmap, notes and test history.</p></div></div>
    <div class="auth-form-wrap"><div class="auth-form">
      <h1>${registering ? 'Create your account' : 'Welcome back'}</h1>
      <p class="muted">${registering ? 'Set up your profile and get a plan built around your target role.' : 'Sign in to pick up where you left off.'}</p>
      <form id="authForm">
        ${registering ? '<label>Full name<input name="name" required minlength="2" maxlength="120" autocomplete="name"></label>' : ''}
        <label>Email address<input type="email" name="email" required autocomplete="email"></label>
        <label>Password<input type="password" name="password" required minlength="8" maxlength="72" autocomplete="${registering ? 'new-password' : 'current-password'}"></label>
        ${registering ? '<p class="sp-field-note">At least 8 characters, with a letter and a number.</p><label>College / University<input name="college" maxlength="180"></label><label>Branch<input name="branch" maxlength="100" placeholder="e.g. CSE (AI/ML)"></label>' : ''}
        <button class="btn btn-dark auth-submit" type="submit">${registering ? 'Create account' : 'Sign in'}</button>
      </form>
      <div class="auth-switch">${registering ? 'Already registered?' : 'New here?'} <a href="#" data-action="${registering ? 'login' : 'register'}">${registering ? 'Log in' : 'Create an account'}</a></div>
    </div></div></div>`;
  document.getElementById('authForm').addEventListener('submit', (event) => submit(event, registering));
}

async function submit(event, registering) {
  event.preventDefault();
  const button = event.target.querySelector('button');
  button.disabled = true;
  try {
    const data = await api(registering ? '/auth/register' : '/auth/login', { method: 'POST', json: Object.fromEntries(new FormData(event.target)) });
    setSession(data);
    navigate('dashboard');
  } catch (error) {
    toast(error.message);
  } finally {
    button.disabled = false;
  }
}
