# HomeControl

A Linux appliance for the Raspberry Pi 5 (800×480 touchscreen) that plays Spotify,
synchronizes playback across rooms, acts as a hands-free voice intercom, controls
smart-home devices via Home Assistant, and ships with iOS/Android companion apps.

This is a **systems-integration** project: proven open components do the heavy lifting
(librespot, Snapcast, openWakeWord, Vosk/whisper.cpp, Piper, WebRTC). Our code is the
orchestrator — the **Core Service** — plus the UI, the mobile app, and the inter-unit
protocol.

- Architecture & rationale → [`docs/architecture.md`](docs/architecture.md)
- Implementation design → [`docs/design.md`](docs/design.md)
- Hardware bring-up → [`docs/hardware-validation.md`](docs/hardware-validation.md)

## Status

| Phase | Scope | State |
|------:|-------|-------|
| 0 | Base image & provisioning (systemd, kiosk, PipeWire/Avahi) | Written — **awaiting hardware validation** |
| 1 | Core Service skeleton + kiosk UI (mock playback) | **Done, verified locally** |
| 2 | Spotify via librespot + Web API control | **Code done, verified locally** — needs Pi + Premium |
| 3 | Multi-room sync (Snapcast) | Not started |
| 4 | Discovery + inter-unit mesh | Not started |
| 5 | Voice (wake word → STT → NLU → TTS) | Not started |
| 6 | Intercom (hands-free, WebRTC) | Not started |
| 6.5 | Smart home (Home Assistant client) | Not started |
| 6.7 | Mobile app (Flutter) | Not started |
| 7 | Hardening | Not started |

CI runs lint + tests + an OpenAPI drift check (Python) and a Vite build (UI) on every
push. "Verified locally" means the non-hardware logic is unit-tested and smoke-tested on
a dev machine; audio, librespot, and systemd are validated on the Pi per the runbook.

## Layout

```
core/          Python Core Service (FastAPI + asyncio) — orchestrator + API
ui/            Svelte web app (Chromium kiosk)
mobile/        Flutter app (iOS + Android) — control + config, LAN-only   [phase 6.7]
api/           Shared API contract (exported openapi.json)
provisioning/  Pi OS setup: install/healthcheck scripts, systemd units, kiosk, Spotify
docs/          Architecture, design, and hardware-validation docs
```

## Dev quickstart (any machine — no Pi needed)

The Core Service runs with a **mock** Spotify provider, so the whole API + UI develop
without hardware or credentials.

### Core Service

```bash
cd core
python -m venv .venv && . .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m homecontrol                             # http://localhost:8080
```

- `GET  /api/state` — full unit + player snapshot
- `GET  /api/health` — liveness
- `POST /api/player/{play,pause,next,previous,seek,volume}` — transport
- `WS   /ws` — realtime state (snapshot on connect, then deltas)
- `GET  /docs` — interactive OpenAPI docs

### Kiosk UI

```bash
cd ui
npm ci
npm run dev      # http://localhost:5173, proxies /api and /ws to :8080
npm run build    # emits ui/dist, which the Core Service serves itself in production
```

### Checks (what CI runs)

```bash
cd core
ruff check .
pytest -q
python scripts/export_openapi.py     # regenerate the contract after API changes
```

## Running on a Pi

See [`docs/hardware-validation.md`](docs/hardware-validation.md). In short:
`sudo ./provisioning/install.sh`, build/ship `ui/dist`, reboot into the kiosk, then
`sudo ./provisioning/phase2-spotify.sh` + `provisioning/spotify/pair.py` for Spotify.
`./provisioning/healthcheck.sh` reports per-layer status.

## Requirements

- Raspberry Pi 5 (8GB) + 800×480 touchscreen per unit
- Spotify **Premium** (librespot requires it)
- A Home Assistant instance on a separate host (phase 6.5)
