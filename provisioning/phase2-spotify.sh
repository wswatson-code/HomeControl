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

echo "==> Install librespot"
# Prefer a distro/prebuilt package; fall back to cargo for source builds. Pin a known-
# good version in production (2025 saw playback regressions on some builds).
if ! command -v librespot >/dev/null 2>&1; then
  if apt-get install -y librespot 2>/dev/null; then
    echo "    installed librespot from apt"
  else
    echo "    apt package unavailable — install via cargo:"
    echo "      apt-get install -y cargo libpulse-dev libasound2-dev"
    echo "      sudo -u ${SERVICE_USER} cargo install librespot --locked"
    echo "    then re-run this script."
    exit 1
  fi
fi

echo "==> Cache dir"
install -d -o "${SERVICE_USER}" -g "${SERVICE_USER}" /var/lib/homecontrol/librespot-cache

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
install -m 644 "${INSTALL_DIR}/provisioning/systemd/librespot.service" /etc/systemd/system/
systemctl daemon-reload

cat <<'NOTE'

==> librespot installed. Before starting:
    1. Create a Spotify app at https://developer.spotify.com/dashboard
       (redirect URI http://localhost:8888/callback), note the client id/secret.
    2. Run the one-time pairing to mint a refresh token:
         python provisioning/spotify/pair.py --client-id ... --client-secret ...
       Paste client id/secret/refresh-token into /etc/homecontrol/unit.env.
    3. Switch the Core Service to the real provider + restart:
         systemctl restart homecontrol-core
         systemctl enable --now librespot
    4. Open Spotify on your phone -> Devices -> pick this room. Music + UI should track.
NOTE
