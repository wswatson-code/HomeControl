# Hardware validation runbook (Phases 0–2)

Validate a single unit end-to-end on real hardware before building Phase 3 (multi-room).
Work the gates in order — don't move on until each passes. If a gate fails, see
**Troubleshooting**. Run `./provisioning/healthcheck.sh` on the unit any time for a
status snapshot.

**You need:** a Raspberry Pi 5 (8GB), the 1024×600 touchscreen wired up, Spotify Premium,
a speaker/output, and (for the UI build) either Node on a dev box or on the Pi.

## What `install.sh` puts on the Pi

You do **not** need to pre-create any user or directory — the installer does it. After it
runs:

| Item | Location / value | Notes |
|------|------------------|-------|
| Install dir | `/opt/homecontrol` | the whole repo is copied here, owned by `homecontrol` |
| Service user | `homecontrol` | **auto-created** if missing: system account, no-login shell, added to `audio`, `video`, `render` groups |
| Config + secrets | `/etc/homecontrol/unit.env` | per-unit identity and Spotify creds — **not** in the repo |
| Python venv | `/opt/homecontrol/core/.venv` | created and owned by `homecontrol` |
| Cache (Phase 2) | `/var/lib/homecontrol/librespot-cache` | created by `phase2-spotify.sh` |
| systemd services | `homecontrol-core`, `homecontrol-kiosk`, `librespot` | core runs as `homecontrol`; **kiosk + librespot run as the desktop autologin user** (they need its Wayland/PipeWire session). All `Restart=always` |

Because the repo lives at `/opt/homecontrol`, off-device builds are copied there (e.g.
`sudo cp -r ui/dist /opt/homecontrol/ui/dist`), and the systemd units reference that path.

> **Session-owned services (kiosk + librespot).** Chromium needs the desktop user's Wayland
> compositor, and librespot's pulseaudio backend needs that user's PipeWire session — both are
> per-user session services. The `homecontrol` nologin account has neither, so these two units
> run as the **desktop autologin user** (chosen in Raspberry Pi Imager). `install.sh` and
> `phase2-spotify.sh` auto-detect that user (uid 1000) and fill it into the units; override by
> exporting `DESKTOP_USER` before running them. See Troubleshooting if a unit can't reach the
> session.

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

**Kiosk: "cannot open display" / "Missing X server or $DISPLAY" / no Wayland socket** —
user/session mismatch. The kiosk must run as the desktop autologin user; `install.sh`
auto-fills that (uid 1000). If it's still wrong, confirm with `loginctl` and check the socket
name: `ls /run/user/<uid>/` shows the real `wayland-*` (often `wayland-0`, **not** `wayland-1`)
— set `Environment=WAYLAND_DISPLAY=` to match. If the session is X11 rather than Wayland
(`echo $XDG_SESSION_TYPE`), drop the Wayland env and set `Environment=DISPLAY=:0` plus
`XAUTHORITY=/home/<user>/.Xauthority` instead.

**UI shows but header dot is red** — WebSocket not connecting. Confirm you're hitting the
Core Service origin (the kiosk uses `localhost:8080`, which serves both UI and `/ws`).

**Core Service crashes right after switching to Spotify** — `No module named 'httpx'`. The
librespot provider drives the Spotify Web API via `httpx`, an optional extra not in the base
install. `phase2-spotify.sh` installs it (`pip install -e ".[spotify]"`); if you skipped the
script, run that in `/opt/homecontrol/core` as `homecontrol` and restart the Core Service.

**librespot dies with `Invalid --backend "pulseaudio"`** — the binary was built without the
pulseaudio backend (librespot 0.8.x defaults to rodio only). Rebuild with the feature:
`cargo install librespot --locked --features pulseaudio-backend`, then `sudo cp
~/.cargo/bin/librespot /usr/bin/librespot` and restart. (apt's librespot, when available,
already includes it.)

**librespot dies with `PulseAudioSink Connection refused`** — it's running as a user with no
PipeWire session (e.g. `homecontrol`). It must run as the **desktop autologin user**, whose
session owns `/run/user/<uid>/pulse/native`. The provisioning scripts set this; if you edited
the unit by hand, set `User=` to that user and `Environment=XDG_RUNTIME_DIR=/run/user/<uid>`,
and `chown` the cache dir (`/var/lib/homecontrol/librespot-cache`) to them.

**No sound though librespot is connected** — wrong sink. List them as the desktop user:
`sudo -u <desktop-user> XDG_RUNTIME_DIR=/run/user/<uid> pactl list short sinks`, then point
`HOMECONTROL_LIBRESPOT_DEVICE` at the right one (default is `default`).

**Audio HAT silent / `No MCLK configured` in dmesg** — the Seeed `seeed-voicecard` driver
doesn't configure MCLK on Pi 5, so the WM8960 codec gets no master clock and every playback
fails (`ASoC error (-22)`) regardless of mixer settings. Switch to the in-kernel overlay
(`dtoverlay=wm8960-soundcard`) and follow [`audio-hat.md`](audio-hat.md) — covers the
overlay, mixer un-mute, sink name, and making it all survive a reboot.

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
