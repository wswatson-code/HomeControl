#!/usr/bin/env bash
# On-unit diagnostics. Run after install (and after phase2) to see, at a glance, which
# layer is healthy and which is the problem:  ./provisioning/healthcheck.sh
#
# Read-only — checks status, never changes anything.
set -uo pipefail

CORE_URL="http://localhost:8080"
pass() { echo "  [ OK ] $1"; }
warn() { echo "  [WARN] $1"; }
fail() { echo "  [FAIL] $1"; }

echo "== HomeControl healthcheck =="

echo "- Core Service"
if curl -fsS --max-time 3 "${CORE_URL}/api/health" >/dev/null 2>&1; then
  pass "API responding on :8080"
  state=$(curl -fsS "${CORE_URL}/api/state")
  echo "        state: $(echo "$state" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d["unit"]["room"], "/", d["player"]["state"])' 2>/dev/null || echo '?')"
else
  fail "no API on :8080 — check: systemctl status homecontrol-core"
fi

echo "- Built UI"
if curl -fsS --max-time 3 "${CORE_URL}/" 2>/dev/null | grep -q 'id="app"'; then
  pass "Core Service is serving the built UI"
else
  warn "UI not served — ui/dist missing? build it (npm run build) or ship dist/"
fi

echo "- Audio (PipeWire)"
if systemctl --user -M homecontrol@ is-active pipewire >/dev/null 2>&1 || pgrep -x pipewire >/dev/null 2>&1; then
  pass "pipewire running"
else
  warn "pipewire not detected for the service user"
fi

echo "- mDNS (Avahi)"
systemctl is-active --quiet avahi-daemon && pass "avahi-daemon active" || warn "avahi-daemon not active"

echo "- Spotify (Phase 2)"
provider=$(grep -h '^HOMECONTROL_SPOTIFY_PROVIDER=' /etc/homecontrol/unit.env 2>/dev/null | tail -1 | cut -d= -f2)
if [[ "${provider:-mock}" == "librespot" ]]; then
  command -v librespot >/dev/null 2>&1 && pass "librespot installed: $(command -v librespot)" || fail "librespot not installed"
  systemctl is-active --quiet librespot && pass "librespot.service active" || fail "librespot.service not active — systemctl status librespot"
  for key in CLIENT_ID CLIENT_SECRET REFRESH_TOKEN; do
    val=$(grep -h "^HOMECONTROL_SPOTIFY_${key}=" /etc/homecontrol/unit.env 2>/dev/null | tail -1 | cut -d= -f2-)
    [[ -n "$val" ]] && pass "spotify ${key} set" || fail "spotify ${key} empty in unit.env"
  done
else
  echo "        provider=mock (Phase 1) — Spotify checks skipped"
fi

echo "- Kiosk"
systemctl is-active --quiet homecontrol-kiosk && pass "kiosk service active" || warn "kiosk not active (expected only after reboot into the GUI)"

echo "== done =="
