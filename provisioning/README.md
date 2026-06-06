# Provisioning a HomeControl unit

Turns a Raspberry Pi 5 (800x480 touchscreen) into a HomeControl appliance.

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

## What lands in later phases (not installed yet)

| Phase | Adds |
|------|------|
| 3 — Multi-room | `snapserver` / `snapclient`, group config, librespot → FIFO |
| 5 — Voice | openWakeWord + Vosk/whisper.cpp + Piper models, ReSpeaker mic driver |
| 6 — Intercom | `aiortc` deps, WebRTC signaling |
| 6.5 — Smart home | Home Assistant URL + long-lived token in `unit.env` |

Each phase ships its own `provisioning/phaseN-*.sh` so this stays incremental and
reviewable. Home Assistant itself runs on a **separate host**, not on a unit.

## Notes

- The UI build needs Node/npm. `install.sh` builds it if present; otherwise build
  `ui/` on a dev machine or CI and ship `ui/dist/`.
- `start-kiosk.sh` waits for `/api/health` before launching Chromium, so a slow first
  boot never shows an error page.
