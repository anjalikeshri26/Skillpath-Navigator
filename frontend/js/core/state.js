import { api } from './api.js';

const TOKEN_KEY = 'sp_token';
const USER_KEY = 'sp_user';

export const session = {
  token: localStorage.getItem(TOKEN_KEY) || '',
  user: JSON.parse(localStorage.getItem(USER_KEY) || 'null'),
};

export function setSession({ access_token, user }) {
  session.token = access_token;
  setUser(user);
  localStorage.setItem(TOKEN_KEY, access_token);
}

export function setUser(user) {
  session.user = user;
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearSession() {
  session.token = '';
  session.user = null;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  metaPromise = null;
}

let metaPromise = null;
/** Roles, topics and AI availability. Fetched once per session. */
export function getMeta() {
  metaPromise ??= api('/meta').catch((error) => { metaPromise = null; throw error; });
  return metaPromise;
}
