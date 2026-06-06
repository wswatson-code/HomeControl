// Single client-side mirror of the unit's state.
//
// The WebSocket at /ws is the source of truth: a `snapshot` on connect, then `player`
// deltas. REST POSTs are fire-and-forget commands; we let the socket reconcile rather
// than optimistically mutating. Position is interpolated locally between server ticks
// so the progress bar moves smoothly at 60fps without spamming the network.

import { writable } from "svelte/store";

export const connected = writable(false);
export const unit = writable(null);
export const player = writable({
  state: "stopped",
  track: null,
  position_ms: 0,
  volume: 50,
  shuffle: false,
  repeat: "off",
});

let socket = null;
let reconnectTimer = null;

function applyPlayer(p) {
  player.set(p);
}

function onMessage(event) {
  const msg = JSON.parse(event.data);
  if (msg.type === "snapshot") {
    unit.set(msg.data.unit);
    applyPlayer(msg.data.player);
  } else if (msg.type === "player") {
    applyPlayer(msg.data);
  } else if (msg.type === "unit") {
    unit.set(msg.data);
  }
}

export function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  socket = new WebSocket(`${proto}://${location.host}/ws`);

  socket.onopen = () => connected.set(true);
  socket.onmessage = onMessage;
  socket.onclose = () => {
    connected.set(false);
    // Resilience: a unit/service restart shouldn't leave the kiosk dead.
    clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(connect, 1000);
  };
  socket.onerror = () => socket.close();
}

// Smoothly advance position locally while playing; the next server tick corrects drift.
let lastTick = null;
function rafLoop(now) {
  if (lastTick != null) {
    const dt = now - lastTick;
    player.update((p) => {
      if (p.state === "playing" && p.track && p.position_ms < p.track.duration_ms) {
        return { ...p, position_ms: Math.min(p.position_ms + dt, p.track.duration_ms) };
      }
      return p;
    });
  }
  lastTick = now;
  requestAnimationFrame(rafLoop);
}
requestAnimationFrame(rafLoop);

// --- commands -------------------------------------------------------------------

async function post(path, body) {
  await fetch(`/api${path}`, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
}

export const commands = {
  play: () => post("/player/play"),
  pause: () => post("/player/pause"),
  next: () => post("/player/next"),
  previous: () => post("/player/previous"),
  seek: (position_ms) => post("/player/seek", { position_ms: Math.round(position_ms) }),
  setVolume: (volume) => post("/player/volume", { volume: Math.round(volume) }),
};
