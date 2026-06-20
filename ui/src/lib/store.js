// Single client-side mirror of the unit's state.
//
// The WebSocket at /ws is the source of truth: a `snapshot` on connect, then `player`
// deltas. REST POSTs are fire-and-forget commands; we let the socket reconcile rather
// than optimistically mutating. Position is interpolated locally between server ticks
// so the progress bar moves smoothly at 60fps without spamming the network.

import { writable, get } from "svelte/store";

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
// Phase 5 voice: pipeline phase (idle/listening/thinking/speaking) + last transcript/reply,
// and the active countdown timers. Both arrive in the snapshot and via their own events.
export const voice = writable({ phase: "idle", transcript: "", reply: "" });
export const timers = writable([]);
// Browse playback target: a Spotify device id, or null = the user's current/active device.
export const targetDevice = writable(null);
// Whether the Browse screen is open (shared so the now-playing button + startup auto-open
// can both drive it).
export const showBrowse = writable(false);

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
    timers.set(msg.data.timers ?? []);
    if (msg.data.voice) voice.set(msg.data.voice);
  } else if (msg.type === "player") {
    applyPlayer(msg.data);
  } else if (msg.type === "unit") {
    unit.set(msg.data);
  } else if (msg.type === "timers") {
    timers.set(msg.data.timers);
  } else if (msg.type === "voice") {
    voice.set(msg.data);
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

async function del(path) {
  await fetch(`/api${path}`, { method: "DELETE" });
}

async function getJSON(path) {
  const r = await fetch(`/api${path}`);
  if (!r.ok) throw new Error(`${path} -> ${r.status}`);
  return r.json();
}

export const commands = {
  play: () => post("/player/play"),
  pause: () => post("/player/pause"),
  next: () => post("/player/next"),
  previous: () => post("/player/previous"),
  seek: (position_ms) => post("/player/seek", { position_ms: Math.round(position_ms) }),
  setVolume: (volume) => post("/player/volume", { volume: Math.round(volume) }),
  // Device-local: stops the kiosk service (drops to the desktop). Off the public /api
  // contract; only meaningful from the on-device kiosk.
  stopKiosk: () => post("/system/kiosk/stop"),
  addTimer: (duration_ms, label = "") => post("/timer", { duration_ms, label }),
  dismissTimer: (id) => del(`/timer/${id}`),

  // --- browse (Spotify catalog) -------------------------------------------------
  // All list endpoints page via ?offset and return { ..., total } (search: { ..., totals }).
  search: (q, offset = 0) => getJSON(`/search?q=${encodeURIComponent(q)}&offset=${offset}`),
  getPlaylists: (offset = 0) => getJSON(`/browse/playlists?offset=${offset}`),
  getAlbums: (offset = 0) => getJSON(`/browse/albums?offset=${offset}`),
  getPlaylistTracks: (id, offset = 0) => getJSON(`/browse/playlist/${id}?offset=${offset}`),
  getAlbumTracks: (id, offset = 0) => getJSON(`/browse/album/${id}?offset=${offset}`),
  getArtist: (id) => getJSON(`/browse/artist/${id}`),
  getDevices: () => getJSON("/devices"),
  // Start playback on the chosen target device (null = current/active device).
  playContent: ({ context_uri = null, uris = null, offset = null } = {}) =>
    post("/play", { context_uri, uris, offset, device_id: get(targetDevice) }),
  transfer: (device_id, play = true) => post("/transfer", { device_id, play }),
};
