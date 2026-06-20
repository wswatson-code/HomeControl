#!/usr/bin/env bash
# Sync this git checkout to the runtime copy at /opt/homecontrol and reload services.
#
# install.sh copies the repo to /opt/homecontrol once; after that the checkout and the
# runtime copy drift every time you pull. This re-syncs them in one step: code over,
# dependencies refreshed, UI rebuilt, services restarted — while preserving the runtime
# state that doesn't live in the repo (venvs, node_modules, the built whisper.cpp/Piper/
# models, and /etc/homecontrol/unit.env).
#
# Run after `git pull`:  sudo ./provisioning/deploy.sh
#
# NOTE: this does NOT re-render systemd unit files (they carry per-unit @DESKTOP_USER@
# values filled at install time). If you changed a .service template, re-run the relevant
# install.sh / phaseN-*.sh instead.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
INSTALL_DIR="/opt/homecontrol"
SERVICE_USER="homecontrol"

[[ $EUID -eq 0 ]] || { echo "run as root (sudo)"; exit 1; }
[[ -d "${INSTALL_DIR}" ]] || { echo "${INSTALL_DIR} missing — run install.sh first"; exit 1; }
command -v rsync >/dev/null 2>&1 || apt-get install -y rsync

echo "==> Sync ${REPO_DIR} -> ${INSTALL_DIR}"
# --delete so /opt mirrors the checkout, but protect everything that's generated on the
# device and not tracked in git: venvs, node_modules, the rebuilt UI, and the whisper.cpp/
# Piper/model trees that phase5 builds into /opt directly.
rsync -a --delete \
  --exclude '.git' \
  --exclude '.venv' \
  --exclude 'node_modules' \
  --exclude 'ui/dist' \
  --exclude 'voice/whisper.cpp' \
  --exclude 'voice/models' \
  --exclude 'voice/piper' \
  "${REPO_DIR}/" "${INSTALL_DIR}/"
chown -R "${SERVICE_USER}:${SERVICE_USER}" "${INSTALL_DIR}"

echo "==> Core deps (editable; picks up any new dependencies)"
sudo -u "${SERVICE_USER}" "${INSTALL_DIR}/core/.venv/bin/pip" install -q -e "${INSTALL_DIR}/core[spotify]"

if [[ -x "${INSTALL_DIR}/voice/.venv/bin/pip" ]]; then
  echo "==> Voice deps (Phase 5 present)"
  "${INSTALL_DIR}/voice/.venv/bin/pip" install -q -e "${INSTALL_DIR}/voice[pipeline]"
  "${INSTALL_DIR}/voice/.venv/bin/pip" install -q --no-deps "openwakeword>=0.6"
fi

echo "==> Rebuild kiosk UI"
if command -v npm >/dev/null 2>&1; then
  (cd "${INSTALL_DIR}/ui" && sudo -u "${SERVICE_USER}" npm ci --silent && sudo -u "${SERVICE_USER}" npm run build)
else
  echo "    npm not found — build ui/ on a dev box and copy dist/ to ${INSTALL_DIR}/ui/dist"
fi

echo "==> Restart services"
restart_if_present() {
  local svc="$1"
  if systemctl cat "${svc}.service" >/dev/null 2>&1; then
    echo "    restarting ${svc}"
    systemctl restart "${svc}" || echo "    (${svc} failed — check: journalctl -u ${svc} -n 30)"
  fi
}
systemctl daemon-reload
# Core first (others depend on it); kiosk last (briefly drops the screen).
for svc in homecontrol-core librespot homecontrol-voice homecontrol-kiosk; do
  restart_if_present "${svc}"
done

echo "==> Deployed. Quick check:  curl -s localhost:8080/api/health"
