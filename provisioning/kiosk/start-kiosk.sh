#!/usr/bin/env bash
# Launch Chromium in kiosk mode pointed at the local Core Service, which serves the
# built UI. Waits for the API to come up first so we never flash an error page.
set -euo pipefail

CORE_URL="http://localhost:8080"

echo "kiosk: waiting for Core Service at ${CORE_URL} ..."
until curl -fs "${CORE_URL}/api/health" >/dev/null 2>&1; do
  sleep 1
done
echo "kiosk: Core Service is up, launching Chromium"

# Binary name differs across releases: Pi OS Bookworm ships `chromium`, older images
# and the Debian wrapper ship `chromium-browser`. Use whichever exists.
CHROMIUM="$(command -v chromium || command -v chromium-browser || true)"
[[ -n "${CHROMIUM}" ]] || { echo "kiosk: no chromium binary found"; exit 1; }

# Only pass the Wayland ozone flag when we're actually under Wayland; on an X session
# it would fail to start. Bookworm's default labwc compositor sets WAYLAND_DISPLAY.
OZONE=()
[[ -n "${WAYLAND_DISPLAY:-}" ]] && OZONE=(--ozone-platform=wayland)

# --kiosk: fullscreen, no chrome. The flags below suppress first-run popups and the
# 'restore pages' bubble that would otherwise sit on top of the UI after a crash.
exec "${CHROMIUM}" \
  --kiosk \
  --app="${CORE_URL}" \
  --window-size=1024,600 \
  --window-position=0,0 \
  --noerrdialogs \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --disable-pinch \
  --overscroll-history-navigation=0 \
  --check-for-update-interval=31536000 \
  --autoplay-policy=no-user-gesture-required \
  "${OZONE[@]}"
