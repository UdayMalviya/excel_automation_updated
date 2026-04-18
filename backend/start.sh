#!/usr/bin/env bash
set -euo pipefail

DISPLAY_NUMBER="${DISPLAY:-:99}"
DISPLAY_ID="${DISPLAY_NUMBER#:}"
APP_HOST="${APP_HOST:-0.0.0.0}"
APP_PORT="${APP_PORT:-8000}"
VNC_PORT="${VNC_PORT:-5900}"
NOVNC_PORT="${NOVNC_PORT:-6080}"

cleanup() {
  echo "Shutting down background services..."
  jobs -p | xargs -r kill || true
}

trap cleanup EXIT INT TERM

echo "Cleaning stale X11 locks..."
rm -f "/tmp/.X${DISPLAY_ID}-lock" "/tmp/.X11-unix/X${DISPLAY_ID}" || true

mkdir -p /tmp/.X11-unix
chmod 1777 /tmp/.X11-unix

echo "Starting Xvfb on ${DISPLAY_NUMBER}..."
Xvfb "${DISPLAY_NUMBER}" -screen 0 1440x900x24 -ac +extension RANDR > /tmp/xvfb.log 2>&1 &

echo "Waiting for X display readiness..."
for _ in $(seq 1 40); do
  if xdpyinfo -display "${DISPLAY_NUMBER}" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

if ! xdpyinfo -display "${DISPLAY_NUMBER}" >/dev/null 2>&1; then
  echo "Xvfb did not become ready"
  if [ -f /tmp/xvfb.log ]; then
    echo "---- /tmp/xvfb.log ----"
    cat /tmp/xvfb.log
    echo "-----------------------"
  fi
  exit 1
fi

export DISPLAY="${DISPLAY_NUMBER}"

echo "Starting fluxbox..."
fluxbox > /tmp/fluxbox.log 2>&1 &

echo "Starting x11vnc on port ${VNC_PORT}..."
x11vnc \
  -display "${DISPLAY_NUMBER}" \
  -forever \
  -shared \
  -rfbport "${VNC_PORT}" \
  -nopw \
  -xkb \
  > /tmp/x11vnc.log 2>&1 &

echo "Starting noVNC on port ${NOVNC_PORT}..."
websockify \
  --web=/usr/share/novnc \
  "${NOVNC_PORT}" \
  "localhost:${VNC_PORT}" \
  > /tmp/novnc.log 2>&1 &

echo "Starting FastAPI with reload..."
exec uvicorn src.api.main:app --host "${APP_HOST}" --port "${APP_PORT}" --reload
