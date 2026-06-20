# Provisioning a HomeControl unit

Turns a Raspberry Pi 5 (1024x600 touchscreen) into a HomeControl appliance.

## Phase 0 baseline (now)

```bash
sudo ./provisioning/install.sh
sudo reboot
```

Installs and enables:
- **Core Service** (`homecontrol-core.service`) → API + UI on `:8080`
- **Chromium kiosk** (`homecontrol-kiosk.service`) → fullscreen UI on the touchscreen
- Base stack the later phases need: **PipeWire** (audio mixer), **Avahi** (mDNS discovery)

Per-unit identity lives in `/etc/homecontrol/unit.env` — set `HOMECONTROL_ROOM`.

## Phase 2 — Spotify (librespot)

```bash
sudo ./provisioning/phase2-spotify.sh        # installs librespot + systemd unit
python provisioning/spotify/pair.py --client-id ... --client-secret ...   # mint refresh token
# paste creds into /etc/homecontrol/unit.env, then:
sudo systemctl restart homecontrol-core && sudo systemctl enable --now librespot
```

Requires **Spotify Premium**. librespot runs as its own service and advertises this
room as a Connect device; the Core Service drives it via the Web API and reflects
state from `--onevent` hooks. Phase 2 plays audio directly (pulseaudio backend); the
switch to the Snapcast FIFO happens in Phase 3.

## Updating a provisioned unit

`install.sh` copies the repo to `/opt/homecontrol` once; after that the checkout and the
runtime copy drift on every `git pull`. To re-sync code + deps + UI and restart services in
one step:

```bash
git pull
sudo ./provisioning/deploy.sh
```

It preserves on-device state not in the repo (venvs, `node_modules`, the built
whisper.cpp/Piper/models, `unit.env`). It does **not** re-render systemd unit files — if you
changed a `.service` template, re-run `install.sh` or the relevant `phaseN-*.sh`.

## Phase 5 — Voice (wake word + STT + TTS)

```bash
sudo ./provisioning/phase5-voice.sh          # builds whisper.cpp, fetches models, installs the unit
sudo systemctl enable --now homecontrol-voice
```

On-device, no cloud: openWakeWord → whisper.cpp → intent → Core API → Piper TTS, plus
countdown timers/alarms. Runs as its own service (`homecontrol-voice`, as the desktop
session user — needs the PipeWire mic/speaker). Requires the audio HAT working first
(mic + speaker). Wake word and models are configurable in `unit.env`. Full guide:
[`docs/voice.md`](../docs/voice.md).

## What lands in later phases (not installed yet)

| Phase | Adds |
|------|------|
| 3 — Multi-room | `snapserver` / `snapclient`, group config, librespot → FIFO |
| 6 — Intercom | `aiortc` deps, WebRTC signaling |
| 6.5 — Smart home | Home Assistant URL + long-lived token in `unit.env` |

Each phase ships its own `provisioning/phaseN-*.sh` so this stays incremental and
reviewable. Home Assistant itself runs on a **separate host**, not on a unit.

## Notes

- The UI build needs Node/npm. `install.sh` builds it if present; otherwise build
  `ui/` on a dev machine or CI and ship `ui/dist/`.
- `start-kiosk.sh` waits for `/api/health` before launching Chromium, so a slow first
  boot never shows an error page.
- `homecontrol-kiosk` and `librespot` run as the **desktop autologin user** (they need that
  user's Wayland/PipeWire session); the installer auto-detects it (uid 1000, or `DESKTOP_USER`
  override). Only the Core Service runs as the `homecontrol` system user.
- librespot must be built with the `pulseaudio-backend` feature (apt's package is fine; a
  bare `cargo install librespot` is not — it ships rodio only).
- **Audio HAT (ReSpeaker 2-Mic / WM8960):** use `dtoverlay=wm8960-soundcard`, NOT the Seeed
  driver — the Seeed driver fails with `No MCLK configured` on Pi 5 and produces silence.
  Full setup + persistence steps in [`docs/audio-hat.md`](../docs/audio-hat.md).
- The kiosk UI has a power button (header, top-right) that stops the kiosk service and drops
  to the desktop. It works via a tightly-scoped sudoers grant (`sudoers.d/homecontrol-kiosk`)
  letting the Core Service run exactly `systemctl stop homecontrol-kiosk.service`. `sudo
  systemctl stop homecontrol-kiosk` over SSH does the same; `start` brings it back.
