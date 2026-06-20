// A looping alarm tone via the Web Audio API — no audio file to ship or decode.
// Kept module-global so multiple fired timers share one tone (and one stop).

let ctx = null;
let interval = null;

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
  if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)();
  if (ctx.state === "suspended") ctx.resume();
  beep();
  interval = setInterval(beep, 800);
}

export function stopAlarm() {
  clearInterval(interval);
  interval = null;
}
