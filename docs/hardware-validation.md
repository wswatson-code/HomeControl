# Hardware validation runbook (Phases 0–2)

Validate a single unit end-to-end on real hardware before building Phase 3 (multi-room).
Work the gates in order — don't move on until each passes. If a gate fails, see
**Troubleshooting**. Run `./provisioning/healthcheck.sh` on the unit any time for a
status snapshot.

**You need:** a Raspberry Pi 5 (8GB), the 800×480 touchscreen wired up, Spotify Premium,
a speaker/output, and (for the UI build) either Node on a dev box or on the Pi.

---

## Gate 0 — Base image & install

```bash
# Fresh Raspberry Pi OS Bookworm (64-bit). On the Pi:
git clone <your-repo> homecontrol && cd homecontrol
sudo ./provisioning/install.sh
```

**Build the UI** (the installer skips this if Node is absent). Either build on this
Windows dev box and copy `ui/dist/` to the Pi, or on the Pi:

```bash
cd ui && npm ci && npm run build && cd ..
sudo cp -r ui/dist /opt/homecontrol/ui/dist     # if you built off-device
sudo systemctl restart homecontrol-core
```

**Pass when:**
- `systemctl status homecontrol-core` → active (running)
- `curl -s localhost:8080/api/health` → `{"status":"ok"}`
- `./provisioning/healthcheck.sh` → Core Service + Built UI both `[ OK ]`

## Gate 1 — Kiosk on the touchscreen

```bash
sudo reboot
```

**Pass when:** after boot the screen shows the now-playing UI fullscreen (mock provider:
"Midnight City — M83"), header dot is green (WebSocket connected), and tapping
play/pause/next/the seek bar/volume all respond. This is the **mock** provider — no
Spotify yet. Confirms display, touch, kiosk autostart, and the full UI↔API↔WS loop.

## Gate 2 — Spotify playback (librespot)

```bash
sudo ./provisioning/phase2-spotify.sh
# one-time, on any machine with a browser:
python provisioning/spotify/pair.py --client-id <id> --client-secret <secret>
sudo nano /etc/homecontrol/unit.env      # paste client id/secret/refresh token
sudo systemctl restart homecontrol-core
sudo systemctl enable --now librespot
```

**Pass when:**
1. `healthcheck.sh` → all Spotify checks `[ OK ]` (librespot active, creds set).
2. In the Spotify app: **Devices** lists this room. Select it.
3. Play a track from your phone → **audio comes out of the Pi**, and the kiosk shows the
   real title/artist/art with the progress bar advancing.
4. On the kiosk: play/pause/next/seek/volume control the actual playback (Web API path).
5. Pause/skip from your phone → the kiosk reflects it within ~1s (onevent + reconcile).

That's the Phase 0–2 base proven. **Then** Phase 3.

---

## Troubleshooting (known gotchas)

**Core Service won't start** — `journalctl -u homecontrol-core -n 50`. Usual cause: the
venv didn't install. Re-run `sudo -u homecontrol /opt/homecontrol/core/.venv/bin/pip
install -e /opt/homecontrol/core`.

**Kiosk: black screen / Chromium won't launch** — binary name and display backend vary.
`start-kiosk.sh` already auto-detects `chromium` vs `chromium-browser` and only passes
the Wayland flag under Wayland. Check `journalctl -u homecontrol-kiosk`. If it launched
before the API, it self-recovers (the script waits on `/api/health`).

**UI shows but header dot is red** — WebSocket not connecting. Confirm you're hitting the
Core Service origin (the kiosk uses `localhost:8080`, which serves both UI and `/ws`).

**No sound in Gate 2** — librespot's audio backend. Default is `pulseaudio` (PipeWire's
shim). Check `HOMECONTROL_LIBRESPOT_BACKEND=pulseaudio` and that `pipewire-pulse` is
running. List sinks: `sudo -u homecontrol pactl list short sinks`. Point
`HOMECONTROL_LIBRESPOT_DEVICE` at the right sink if `default` is wrong.

**librespot device missing from the Spotify app** — librespot uses zeroconf/mDNS. Confirm
`avahi-daemon` is active and the phone is on the same LAN/VLAN (mDNS doesn't cross
subnets). `journalctl -u librespot`.

**Playback fails / HTTP 500 / NonPlayable** — a known librespot regression on some 2025
builds. Pin a known-good version (rebuild via `cargo install librespot --version X.Y.Z
--locked`) and restart. Premium is required — free accounts will not play.

**Kiosk controls don't affect real playback** — the Web API requires the device to be
*active*. The provider calls `ensure_active()`, but if control still no-ops, select the
device once in the Spotify app to activate it, then retry. Confirm the refresh token has
`user-modify-playback-state` scope (it does if minted by `pair.py`).

**Token errors in logs** — refresh token wrong/expired or client id/secret mismatch.
Re-run `pair.py` and update `unit.env`. The same Spotify account must own both the OAuth
app token and the librespot session.
