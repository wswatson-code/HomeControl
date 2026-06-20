#!/usr/bin/env bash
# Phase 2 — install librespot (Spotify Connect) on a HomeControl unit.
#
# Prereqs: Phase 0 (install.sh) has run. Spotify Premium account. A Spotify developer
# app (client id/secret) and a refresh token from the one-time pairing — see
# provisioning/spotify/pair.py and the printed instructions below.
#
#   sudo ./provisioning/phase2-spotify.sh
set -euo pipefail

INSTALL_DIR="/opt/homecontrol"
SERVICE_USER="homecontrol"
ENV_FILE="/etc/homecontrol/unit.env"

[[ $EUID -eq 0 ]] || { echo "run as root (sudo)"; exit 1; }

# librespot runs as the desktop session user (it owns the PipeWire/pulse audio session the
# pulseaudio backend connects to), NOT the homecontrol system account. Detect uid 1000 (the
# standard Pi OS autologin user) or override by exporting DESKTOP_USER.
DESKTOP_USER="${DESKTOP_USER:-$(getent passwd 1000 | cut -d: -f1)}"
[[ -n "${DESKTOP_USER}" ]] || { echo "no uid-1000 user found; export DESKTOP_USER and re-run"; exit 1; }
DESKTOP_UID="$(id -u "${DESKTOP_USER}")"
echo "==> Desktop session user: ${DESKTOP_USER} (uid ${DESKTOP_UID})"

echo "==> Install librespot"
# Prefer a distro/prebuilt package; fall back to cargo for source builds. Pin a known-
# good version in production (2025 saw playback regressions on some builds).
if ! command -v librespot >/dev/null 2>&1; then
  if apt-get install -y librespot 2>/dev/null; then
    echo "    installed librespot from apt"
  else
    echo "    apt package unavailable — build from source WITH the pulseaudio backend"
    echo "    (librespot 0.8.x defaults to rodio only; --backend pulseaudio needs the feature):"
    echo "      sudo apt-get install -y cargo libpulse-dev libasound2-dev"
    echo "      cargo install librespot --locked --features pulseaudio-backend"
    echo "      sudo cp ~/.cargo/bin/librespot /usr/bin/librespot"
    echo "    then re-run this script."
    exit 1
  fi
fi

echo "==> Core Service Spotify deps (httpx) into the venv"
# The librespot provider drives playback through the Spotify Web API, whose client needs
# httpx — an OPTIONAL extra not pulled by the base install. Without this the Core Service
# crashes on startup ("No module named 'httpx'") the moment the provider is set to librespot.
sudo -u "${SERVICE_USER}" "${INSTALL_DIR}/core/.venv/bin/pip" install -e "${INSTALL_DIR}/core[spotify]"

echo "==> Cache dir (owned by ${DESKTOP_USER} — the user librespot runs as)"
install -d -o "${DESKTOP_USER}" -g "${DESKTOP_USER}" /var/lib/homecontrol/librespot-cache

echo "==> Spotify config in ${ENV_FILE}"
# Append placeholders if absent — the operator fills in real values (never commit them).
grep -q HOMECONTROL_SPOTIFY_CLIENT_ID "${ENV_FILE}" 2>/dev/null || cat >> "${ENV_FILE}" <<'EOF'

# --- Phase 2: Spotify (Premium required) ---
HOMECONTROL_SPOTIFY_PROVIDER=librespot
HOMECONTROL_SPOTIFY_CLIENT_ID=
HOMECONTROL_SPOTIFY_CLIENT_SECRET=
HOMECONTROL_SPOTIFY_REFRESH_TOKEN=
# librespot process args (consumed by librespot.service, not the Core Service):
HOMECONTROL_LIBRESPOT_BACKEND=pulseaudio
HOMECONTROL_LIBRESPOT_DEVICE=default
EOF

echo "==> onevent hook + systemd unit"
chmod +x "${INSTALL_DIR}/provisioning/spotify/onevent.sh"
# Render the desktop user/uid into the unit (librespot needs that user's PipeWire session).
sed -e "s/@DESKTOP_USER@/${DESKTOP_USER}/g" -e "s/@DESKTOP_UID@/${DESKTOP_UID}/g" \
  "${INSTALL_DIR}/provisioning/systemd/librespot.service" > /etc/systemd/system/librespot.service
chmod 644 /etc/systemd/system/librespot.service
systemctl daemon-reload

cat <<'NOTE'

==> librespot installed. Before starting:
    1. Create a Spotify app at https://developer.spotify.com/dashboard
       (redirect URI http://127.0.0.1:8000/callback), note the client id/secret.
    2. Run the one-time pairing to mint a refresh token:
         python provisioning/spotify/pair.py --client-id ... --client-secret ...
       Paste client id/secret/refresh-token into /etc/homecontrol/unit.env.
    3. Switch the Core Service to the real provider + restart:
         systemctl restart homecontrol-core
         systemctl enable --now librespot
    4. Open Spotify on your phone -> Devices -> pick this room. Music + UI should track.
NOTE
