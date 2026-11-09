/** Browser speech helpers. Everything degrades to typed input and on-screen text when unsupported. */
const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;

export const support = { speaking: 'speechSynthesis' in window, listening: Boolean(Recognition) };

const FEMALE = /female|aria|jenny|sara|samantha|zira|heera|priya|ava|emma|natasha|sonia|karen|susan|hazel|libby|google us english/i;
const MALE = /male|guy|david|mark|james|ryan|christopher|eric|george|daniel|thomas|ravi|prabhat|andrew|brian|aaron/i;

let voices = [];
let lastVoice = '';

export function watchVoices(onChange) {
  if (!support.speaking) return;
  const update = () => {
    voices = speechSynthesis.getVoices().filter((v) => /^en([-_]|$)/i.test(v.lang));
    onChange?.(voices.length);
  };
  update();
  speechSynthesis.onvoiceschanged = update;
}

function pick(mode) {
  const female = voices.filter((v) => FEMALE.test(v.name));
  const male = voices.filter((v) => !FEMALE.test(v.name) && MALE.test(v.name));
  let pool = mode === 'female' ? female : mode === 'male' ? male : [...female, ...male];
  if (!pool.length) pool = voices;
  const fresh = pool.filter((v) => v.name !== lastVoice);
  const choice = (fresh.length ? fresh : pool)[Math.floor(Math.random() * (fresh.length || pool.length))];
  lastVoice = choice?.name ?? '';
  return choice ?? null;
}

export function speak(text, mode = 'shuffle') {
  return new Promise((resolve) => {
    if (!support.speaking) return resolve();
    speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'en-US';
    utterance.rate = 1.02;
    const voice = pick(mode);
    if (voice) utterance.voice = voice;
    utterance.onend = utterance.onerror = () => resolve();
    speechSynthesis.speak(utterance);
  });
}

export const stopSpeaking = () => support.speaking && speechSynthesis.cancel();

/** Returns {start, stop} or null when the browser has no speech recognition. */
export function createRecognizer({ onFinal, onStart, onEnd, onError }) {
  if (!Recognition) return null;
  let active = null;
  return {
    start() {
      active?.abort();
      active = new Recognition();
      active.lang = 'en-US';
      active.continuous = false;
      active.interimResults = false;
      active.onstart = () => onStart?.();
      active.onresult = (event) => {
        const text = [...event.results].filter((r) => r.isFinal).map((r) => r[0].transcript).join(' ').trim();
        if (text) onFinal(text);
      };
      active.onerror = (event) => { if (!['aborted', 'no-speech'].includes(event.error)) onError?.(event.error); };
      active.onend = () => onEnd?.();
      try { active.start(); } catch { onError?.('could not start'); }
    },
    stop() { try { active?.stop(); } catch { /* already stopped */ } },
  };
}
