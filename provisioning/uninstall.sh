#!/usr/bin/env bash
# Remove HomeControl from a unit — reverses install.sh and phase2-spotify.sh.
#
#   sudo ./provisioning/uninstall.sh            # remove app, KEEP /etc/homecontrol (creds)
#   sudo ./provisioning/uninstall.sh --purge    # also remove config + the homecontrol user
#
# Not -e: keep going even if a piece is already gone (idempotent teardown).
set -u

PURGE=0
[[ "${1:-}" == "--purge" ]] && PURGE=1

INSTALL_DIR="/opt/homecontrol"
SERVICE_USER="homecontrol"
SERVICES=(homecontrol-kiosk homecontrol-core librespot)

[[ $EUID -eq 0 ]] || { echo "run as root (sudo)"; exit 1; }

echo "==> Stop + disable services"
for svc in "${SERVICES[@]}"; do
  systemctl stop "${svc}.service" 2>/dev/null && echo "    stopped ${svc}" || true
  systemctl disable "${svc}.service" 2>/dev/null || true
  rm -f "/etc/systemd/system/${svc}.service"
done
systemctl daemon-reload
systemctl reset-failed 2>/dev/null || true

echo "==> Remove install dir"
rm -rf "${INSTALL_DIR}"

echo "==> Remove runtime state"
rm -rf /var/lib/homecontrol /run/homecontrol

if [[ ${PURGE} -eq 1 ]]; then
  echo "==> Purge config (/etc/homecontrol — includes unit.env / Spotify creds)"
  rm -rf /etc/homecontrol
  echo "==> Remove service user '${SERVICE_USER}'"
  id -u "${SERVICE_USER}" >/dev/null 2>&1 && userdel --remove "${SERVICE_USER}" 2>/dev/null || true
else
  echo "==> Keeping /etc/homecontrol and the '${SERVICE_USER}' user (use --purge to remove)"
fi

echo "==> Done. HomeControl removed."
echo "    Note: apt packages (chromium, pipewire, avahi, librespot) are left installed."
