// A looping alarm tone via the Web Audio API — no audio file to ship or decode.
// Kept module-global so multiple fired timers share one tone (and one stop).

let ctx = null;
let interval = null;

function ensureCtx() {
  if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)();
  return ctx;
}

// Call once at app start. Browsers create an AudioContext "suspended" and only let it run
// after a user gesture — but timers fire on a delay/voice with no gesture, so prime the
// context now and resume it on the first interaction. On the kiosk Chromium runs with
// --autoplay-policy=no-user-gesture-required so it's already unlocked; this makes the alarm
// work in any other browser (dev, mobile view) too.
export function initAlarmAudio() {
  const c = ensureCtx();
  const unlock = () => {
    if (c.state === "suspended") c.resume();
  };
  unlock();
  window.addEventListener("pointerdown", unlock);
  window.addEventListener("keydown", unlock);
}

function beep() {
  if (!ctx) return;
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = "sine";
  osc.frequency.value = 880;
  gain.gain.setValueAtTime(0.0001, ctx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.3, ctx.currentTime + 0.02);
  gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.4);
  osc.connect(gain).connect(ctx.destination);
  osc.start();
  osc.stop(ctx.currentTime + 0.45);
}

export function startAlarm() {
  if (interval) return; // already ringing
  const c = ensureCtx();
  const begin = () => {
    beep(); // first beep only after the context is actually running, so it isn't lost
    interval = setInterval(beep, 800);
  };
  if (c.state === "suspended") c.resume().then(begin, begin);
  else begin();
}

export function stopAlarm() {
  clearInterval(interval);
  interval = null;
}
