#!/usr/bin/env bash
# librespot --onevent hook.
#
# librespot runs this on every player event, passing state via environment variables
# (PLAYER_EVENT, TRACK_ID, OLD_TRACK_ID, DURATION_MS, POSITION_MS, VOLUME). We forward
# the relevant ones to the local Core Service, which maps them to UI state. Fire-and-
# forget with a short timeout so a slow/dead Core Service never stalls playback.
set -u

CORE_URL="http://localhost:8080/internal/spotify/event"

payload=$(cat <<JSON
{
  "PLAYER_EVENT": "${PLAYER_EVENT:-}",
  "TRACK_ID": "${TRACK_ID:-}",
  "OLD_TRACK_ID": "${OLD_TRACK_ID:-}",
  "DURATION_MS": "${DURATION_MS:-}",
  "POSITION_MS": "${POSITION_MS:-}",
  "VOLUME": "${VOLUME:-}"
}
JSON
)

curl -fsS --max-time 2 -X POST "${CORE_URL}" \
  -H "Content-Type: application/json" \
  -d "${payload}" >/dev/null 2>&1 || true
