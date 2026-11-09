import { api } from '../core/api.js';
import { esc, toast, $ } from '../core/dom.js';
import { mount } from '../core/shell.js';
import { getMeta, session, setUser } from '../core/state.js';

const YEARS = ['1st Year', '2nd Year', '3rd Year', '4th Year', 'Graduate', 'Other'];
const LEVELS = ['Beginner', 'Intermediate', 'Advanced'];
const options = (list, selected) => list.map((x) => `<option ${x === selected ? 'selected' : ''}>${esc(x)}</option>`).join('');

export async function loadProfile() {
  const [profile, meta] = await Promise.all([api('/me'), getMeta()]);
  setUser(profile);
  const page = mount('profile', `
    <div class="page-intro"><div><h2>Profile settings</h2><p class="muted">Your target role and level decide which skills your roadmap includes.</p></div></div>
    <form class="profile-form panel" id="profileForm">
      <label>Full name<input value="${esc(profile.name)}" disabled></label>
      <label>Email address<input value="${esc(profile.email)}" disabled></label>
      <label>College / University<input name="college" maxlength="180" value="${esc(profile.college)}"></label>
      <label>Branch<input name="branch" maxlength="100" value="${esc(profile.branch)}"></label>
      <label>Academic year<select name="academic_year">${options(YEARS, profile.academic_year)}</select></label>
      <label>Current skill level<select name="skill_level">${options(LEVELS, profile.skill_level)}</select></label>
      <label>Target role<select name="target_role">${options(meta.roles, profile.target_role)}</select></label>
      <label>Target package<input name="target_package" maxlength="40" value="${esc(profile.target_package)}" placeholder="e.g. 8 LPA"></label>
      <button class="btn btn-dark" type="submit">Save changes</button><span class="muted" id="profileStatus" aria-live="polite"></span>
    </form>`);
  $('#profileForm', page).addEventListener('submit', async (event) => {
    event.preventDefault();
    const status = $('#profileStatus', page);
    status.textContent = 'Saving…';
    try {
      setUser(await api('/profile', { method: 'PATCH', json: Object.fromEntries(new FormData(event.currentTarget)) }));
      status.textContent = 'Saved. Your roadmap was recalculated.';
    } catch (error) {
      status.textContent = error.message;
      toast(error.message);
    }
  });
}
