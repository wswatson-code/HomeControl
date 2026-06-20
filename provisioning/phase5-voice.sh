#!/usr/bin/env bash
# Phase 5 — install the voice pipeline (wake word + whisper.cpp STT + Piper TTS).
#
# Prereqs: Phase 0 (install.sh) done, the audio HAT working (mic + speaker — see
# docs/audio-hat.md), and the Core Service running. Builds whisper.cpp from source and
# downloads the STT/TTS/wake-word models, then installs the homecontrol-voice service.
#
#   sudo ./provisioning/phase5-voice.sh
set -euo pipefail

INSTALL_DIR="/opt/homecontrol"
VOICE_DIR="${INSTALL_DIR}/voice"
MODELS_DIR="${VOICE_DIR}/models"

[[ $EUID -eq 0 ]] || { echo "run as root (sudo)"; exit 1; }

# Voice runs as the desktop session user (PipeWire mic/speaker live in that session).
DESKTOP_USER="${DESKTOP_USER:-$(getent passwd 1000 | cut -d: -f1)}"
[[ -n "${DESKTOP_USER}" ]] || { echo "no uid-1000 user found; export DESKTOP_USER and re-run"; exit 1; }
DESKTOP_UID="$(id -u "${DESKTOP_USER}")"
echo "==> Desktop session user: ${DESKTOP_USER} (uid ${DESKTOP_UID})"

echo "==> System packages (build tools for whisper.cpp; capture/playback use parec/paplay)"
apt-get update
apt-get install -y git cmake build-essential wget
# parec/paplay come from pulseaudio-utils (installed by install.sh at Phase 0).

echo "==> Voice venv + Python deps"
# Built/owned root, world-readable: the service (desktop user) only needs read+exec.
python3 -m venv "${VOICE_DIR}/.venv"
"${VOICE_DIR}/.venv/bin/pip" install --upgrade pip
"${VOICE_DIR}/.venv/bin/pip" install -e "${VOICE_DIR}[pipeline]"
# openWakeWord, with NO deps: its tflite-runtime requirement has no Python 3.13 wheel.
# We run it on the ONNX backend (onnxruntime came in via [pipeline]); its other runtime
# deps (numpy/scipy/tqdm/requests) are pinned in [pipeline] too.
"${VOICE_DIR}/.venv/bin/pip" install --no-deps "openwakeword>=0.6"

echo "==> Pre-download openWakeWord ONNX models (so the service never downloads at runtime)"
"${VOICE_DIR}/.venv/bin/python" -c "import openwakeword.utils as u; u.download_models()"

mkdir -p "${MODELS_DIR}"

echo "==> Build whisper.cpp + fetch the tiny.en model"
if [[ ! -x "${VOICE_DIR}/whisper.cpp/build/bin/whisper-cli" ]]; then
  git clone --depth 1 https://github.com/ggerganov/whisper.cpp "${VOICE_DIR}/whisper.cpp" 2>/dev/null || \
    (cd "${VOICE_DIR}/whisper.cpp" && git pull --ff-only)
  cmake -S "${VOICE_DIR}/whisper.cpp" -B "${VOICE_DIR}/whisper.cpp/build" -DCMAKE_BUILD_TYPE=Release
  cmake --build "${VOICE_DIR}/whisper.cpp/build" -j --target whisper-cli
fi
if [[ ! -f "${MODELS_DIR}/ggml-tiny.en.bin" ]]; then
  (cd "${VOICE_DIR}/whisper.cpp" && bash models/download-ggml-model.sh tiny.en)
  cp "${VOICE_DIR}/whisper.cpp/models/ggml-tiny.en.bin" "${MODELS_DIR}/"
fi

echo "==> Install Piper (TTS) + a voice"
# Piper ships prebuilt binaries per-arch; the Pi 5 is aarch64. URLs occasionally move —
# if either download fails, grab them by hand (see the printed note) and re-run.
if [[ ! -x "${VOICE_DIR}/piper/piper" ]]; then
  PIPER_URL="https://github.com/rhasspy/piper/releases/latest/download/piper_linux_aarch64.tar.gz"
  if wget -qO /tmp/piper.tgz "${PIPER_URL}"; then
    tar -xzf /tmp/piper.tgz -C "${VOICE_DIR}"   # extracts a 'piper/' dir
    rm -f /tmp/piper.tgz
  else
    echo "    !! could not download Piper from ${PIPER_URL}"
    echo "    Download the aarch64 release tarball manually, extract to ${VOICE_DIR}/piper, re-run."
  fi
fi
if [[ ! -f "${MODELS_DIR}/en_US-amy-medium.onnx" ]]; then
  VOICE_BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium"
  wget -qO "${MODELS_DIR}/en_US-amy-medium.onnx" "${VOICE_BASE}/en_US-amy-medium.onnx" || \
    echo "    !! download en_US-amy-medium.onnx manually into ${MODELS_DIR}"
  wget -qO "${MODELS_DIR}/en_US-amy-medium.onnx.json" "${VOICE_BASE}/en_US-amy-medium.onnx.json" || \
    echo "    !! download en_US-amy-medium.onnx.json manually into ${MODELS_DIR}"
fi

echo "==> Voice config defaults in /etc/homecontrol/unit.env"
grep -q HOMECONTROL_VOICE_WAKE_MODEL /etc/homecontrol/unit.env 2>/dev/null || cat >> /etc/homecontrol/unit.env <<'EOF'

# --- Phase 5: voice (wake word + whisper.cpp + Piper) ---
# Defaults match phase5-voice.sh's install layout; override per unit as needed.
# WAKE_MODEL: one or more (comma-separated) bundled names (alexa, hey_jarvis, hey_mycroft,
# hey_rhasspy) and/or .onnx paths; the unit wakes on any of them.
HOMECONTROL_VOICE_WAKE_MODEL=hey_jarvis
HOMECONTROL_VOICE_WAKE_THRESHOLD=0.5
HOMECONTROL_VOICE_LISTEN_CHIME=true
# Duck music while voice is active (fractions = music volume; 0.25 = 75% reduction).
HOMECONTROL_VOICE_DUCK=true
HOMECONTROL_VOICE_DUCK_LISTEN=0.25
HOMECONTROL_VOICE_DUCK_SPEAK=0.50
HOMECONTROL_VOICE_COMMAND_SECONDS=5
# Leave INPUT_DEVICE/OUTPUT_DEVICE empty to use the PipeWire default (the HAT).
HOMECONTROL_VOICE_INPUT_DEVICE=
HOMECONTROL_VOICE_OUTPUT_DEVICE=
EOF

echo "==> systemd unit (rendered for ${DESKTOP_USER})"
sed -e "s/@DESKTOP_USER@/${DESKTOP_USER}/g" -e "s/@DESKTOP_UID@/${DESKTOP_UID}/g" \
  "${INSTALL_DIR}/provisioning/systemd/homecontrol-voice.service" > /etc/systemd/system/homecontrol-voice.service
chmod 644 /etc/systemd/system/homecontrol-voice.service
systemctl daemon-reload

cat <<NOTE

==> Voice installed. To start:
    sudo systemctl enable --now homecontrol-voice
    journalctl -u homecontrol-voice -f

    Say the wake word ("hey jarvis"), then a command:
      "play"  /  "pause"  /  "next"  /  "turn it up"  /  "set volume to 40"
      "set a timer for 10 minutes"
    The kiosk shows a listening overlay; timers appear bottom-right and ring when done.

    Wake word, models, and devices are configurable in /etc/homecontrol/unit.env
    (HOMECONTROL_VOICE_*). See docs/voice.md.
NOTE
