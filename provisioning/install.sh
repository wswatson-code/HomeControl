#!/usr/bin/env bash
# Provision a Raspberry Pi 5 as a HomeControl unit.
#
# Phase 0 baseline: installs the Core Service + kiosk and the audio/discovery stack
# they sit on. Subsystem packages (librespot, snapcast, voice models, aiortc) are
# installed by their own phase scripts as those land — kept out of here so this stays
# runnable and reviewable now.
#
# Run on a fresh Pi OS Bookworm (64-bit):  sudo ./provisioning/install.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
INSTALL_DIR="/opt/homecontrol"
SERVICE_USER="homecontrol"

require_root() { [[ $EUID -eq 0 ]] || { echo "run as root (sudo)"; exit 1; }; }
require_root

echo "==> System packages"
apt-get update
apt-get install -y \
  python3 python3-venv python3-pip \
  curl \
  pipewire pipewire-pulse wireplumber \
  avahi-daemon
# Chromium package name varies: `chromium` on Pi OS Bookworm, `chromium-browser` older.
apt-get install -y chromium || apt-get install -y chromium-browser

echo "==> Service user"
id -u "${SERVICE_USER}" >/dev/null 2>&1 || useradd --system --create-home --shell /usr/sbin/nologin "${SERVICE_USER}"
# Audio + video group access for PipeWire and the framebuffer/GPU.
usermod -aG audio,video,render "${SERVICE_USER}"

echo "==> Copy repo to ${INSTALL_DIR}"
mkdir -p "${INSTALL_DIR}"
cp -r "${REPO_DIR}/." "${INSTALL_DIR}/"
chown -R "${SERVICE_USER}:${SERVICE_USER}" "${INSTALL_DIR}"

echo "==> Core Service venv"
sudo -u "${SERVICE_USER}" python3 -m venv "${INSTALL_DIR}/core/.venv"
sudo -u "${SERVICE_USER}" "${INSTALL_DIR}/core/.venv/bin/pip" install --upgrade pip
sudo -u "${SERVICE_USER}" "${INSTALL_DIR}/core/.venv/bin/pip" install -e "${INSTALL_DIR}/core"

echo "==> Build kiosk UI (requires Node; skipped if absent)"
if command -v npm >/dev/null 2>&1; then
  (cd "${INSTALL_DIR}/ui" && sudo -u "${SERVICE_USER}" npm ci && sudo -u "${SERVICE_USER}" npm run build)
else
  echo "    npm not found — install Node and run 'npm ci && npm run build' in ui/ before first boot"
fi

echo "==> Unit identity (/etc/homecontrol/unit.env)"
mkdir -p /etc/homecontrol
if [[ ! -f /etc/homecontrol/unit.env ]]; then
  cat > /etc/homecontrol/unit.env <<EOF
# Per-unit identity. Edit ROOM to the physical location.
HOMECONTROL_UNIT_ID=$(cat /etc/machine-id)
HOMECONTROL_ROOM=Living Room
HOMECONTROL_SPOTIFY_PROVIDER=mock
EOF
fi

echo "==> systemd units"
chmod +x "${INSTALL_DIR}/provisioning/kiosk/start-kiosk.sh"
# The kiosk must run as the desktop autologin user (it needs that user's Wayland/PipeWire
# session), not the homecontrol system account. Detect that user — uid 1000 on a standard
# Pi OS image — or override by exporting DESKTOP_USER. render_unit fills the placeholders.
DESKTOP_USER="${DESKTOP_USER:-$(getent passwd 1000 | cut -d: -f1)}"
[[ -n "${DESKTOP_USER}" ]] || { echo "no uid-1000 user found; export DESKTOP_USER and re-run"; exit 1; }
DESKTOP_UID="$(id -u "${DESKTOP_USER}")"
echo "    desktop session user: ${DESKTOP_USER} (uid ${DESKTOP_UID})"
render_unit() {  # render_unit <template> <dest> — fill the @DESKTOP_USER@/@DESKTOP_UID@ placeholders
  sed -e "s/@DESKTOP_USER@/${DESKTOP_USER}/g" -e "s/@DESKTOP_UID@/${DESKTOP_UID}/g" "$1" > "$2"
  chmod 644 "$2"
}
install -m 644 "${INSTALL_DIR}/provisioning/systemd/homecontrol-core.service" /etc/systemd/system/
render_unit "${INSTALL_DIR}/provisioning/systemd/homecontrol-kiosk.service" /etc/systemd/system/homecontrol-kiosk.service
systemctl daemon-reload
systemctl enable --now homecontrol-core.service
systemctl enable homecontrol-kiosk.service

echo "==> Done. Core Service on :8080. Reboot to launch the kiosk."
