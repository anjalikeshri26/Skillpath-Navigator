import { session } from './state.js';

const BASE = localStorage.getItem('sp_api') || '/api';

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

function describe(detail) {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0];
    const field = Array.isArray(first.loc) ? first.loc[first.loc.length - 1] : '';
    return field ? `${field}: ${String(first.msg).replace(/^Value error, /, '')}` : first.msg;
  }
  return 'Request failed';
}

/** JSON request helper. Pass `json` for a JSON body or `form` for multipart. */
export async function api(path, { method = 'GET', json, form } = {}) {
  const headers = {};
  if (session.token) headers.Authorization = `Bearer ${session.token}`;
  let body;
  if (form) body = form;
  else if (json !== undefined) { headers['Content-Type'] = 'application/json'; body = JSON.stringify(json); }

  let response;
  try {
    response = await fetch(BASE + path, { method, headers, body });
  } catch {
    throw new ApiError('Cannot reach the server. Check that the backend is running.', 0);
  }
  if (response.status === 204) return null;
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401 && session.token) window.dispatchEvent(new CustomEvent('sp:unauthorized'));
    throw new ApiError(describe(data?.detail), response.status);
  }
  return data;
}
