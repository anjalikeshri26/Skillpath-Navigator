import { session } from './state.js';
import { toast } from './dom.js';

const routes = new Map();
let landingHandler = () => {};

export const registerRoute = (name, loader) => routes.set(name, loader);
export const onLanding = (handler) => { landingHandler = handler; };

let guard = null;
let currentHash = '';
let reverting = false;

/** A page with unsaved work registers a function that returns false to veto leaving it. */
export const setNavigationGuard = (fn) => { guard = fn; };
export const clearNavigationGuard = () => { guard = null; };

export function navigate(name, params = {}) {
  const query = new URLSearchParams(params).toString();
  const target = `#/${name}${query ? `?${query}` : ''}`;
  if (location.hash === target) {
    if (!guard || guard()) { guard = null; render(); }
  } else {
    location.hash = target;
  }
}

function onHashChange() {
  if (reverting) { reverting = false; return; }
  if (guard && !guard()) {
    reverting = true;
    location.hash = currentHash; // put the address back; the hashchange this causes is ignored above
    return;
  }
  guard = null;
  currentHash = location.hash;
  render();
}

function parse() {
  const match = location.hash.match(/^#\/([a-z-]+)(?:\?(.*))?$/);
  return match ? { name: match[1], params: Object.fromEntries(new URLSearchParams(match[2] || '')) } : null;
}

let renderId = 0;
export async function render() {
  const route = parse();
  if (!session.token || !route) {
    if (!session.token) landingHandler();
    else navigate('dashboard');
    return;
  }
  const loader = routes.get(route.name) || routes.get('dashboard');
  const current = ++renderId;
  try {
    await loader(route.params, () => current === renderId); // loaders can check whether they are still the active page
  } catch (error) {
    if (current === renderId) toast(error.message || 'Could not open this page');
  }
}

export function startRouter() {
  currentHash = location.hash;
  window.addEventListener('hashchange', onHashChange);
  return render();
}
