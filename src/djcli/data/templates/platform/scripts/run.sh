#!/usr/bin/env bash
# Run a service under this platform.
# Always loads {service}/.env.local-dev (never development/production).
# Usage: ./scripts/run.sh <service_name> [args...]
set -euo pipefail

PLATFORM_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PLATFORM_DIR"

if [ "${#}" -lt 1 ]; then
  echo "Usage: $0 <service_name> [args...]"
  echo "Available services:"
  for d in */ ; do
    name="${d%/}"
    case "$name" in
      scripts|proto) continue ;;
    esac
    [ -d "$name" ] && echo "  $name"
  done
  exit 1
fi

NAME="$1"
shift
case "$NAME" in
  scripts|proto)
    echo "reserved name: $NAME"
    exit 1
    ;;
esac

SERVICE_DIR="$PLATFORM_DIR/$NAME"
ENV_FILE="$SERVICE_DIR/.env.local-dev"
PID_FILE="$SERVICE_DIR/.run.pid"

if [ ! -d "$SERVICE_DIR" ]; then
  echo "unknown service: $NAME (expected $SERVICE_DIR)"
  exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
  echo "missing $ENV_FILE (local run always uses .env.local-dev)"
  exit 1
fi

# Load KEY=VALUE from .env.local-dev (ignore comments/blank lines)
set -a
# shellcheck disable=SC1090
source <(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "$ENV_FILE" || true)
set +a

kill_by_port() {
  local port="$1"
  local pids=""
  if command -v lsof >/dev/null 2>&1; then
    pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  elif command -v fuser >/dev/null 2>&1; then
    fuser -k "${port}/tcp" >/dev/null 2>&1 || true
    return 0
  fi
  if [ -n "$pids" ]; then
    echo "stopping listeners on port $port: $pids"
    # shellcheck disable=SC2086
    kill $pids 2>/dev/null || true
    sleep 0.3
    # shellcheck disable=SC2086
    kill -9 $pids 2>/dev/null || true
  fi
}

kill_by_pidfile() {
  if [ ! -f "$PID_FILE" ]; then
    return 0
  fi
  local old_pid
  old_pid="$(tr -d '[:space:]' <"$PID_FILE" || true)"
  if [ -n "$old_pid" ] && kill -0 "$old_pid" 2>/dev/null; then
    echo "stopping pid $old_pid from $PID_FILE"
    kill "$old_pid" 2>/dev/null || true
    sleep 0.3
    kill -9 "$old_pid" 2>/dev/null || true
  fi
  rm -f "$PID_FILE"
}

echo "env: $ENV_FILE"
if [ -n "${PORT:-}" ]; then
  kill_by_port "$PORT"
else
  echo "PORT unset in .env.local-dev; using pidfile fallback"
fi
kill_by_pidfile

start_and_track() {
  # Runs command in background, writes pid, waits (Ctrl+C forwards signal)
  "$@" &
  local pid=$!
  echo "$pid" >"$PID_FILE"
  echo "started pid $pid (tracked in $PID_FILE)"
  trap 'kill "$pid" 2>/dev/null || true; rm -f "$PID_FILE"; exit 130' INT TERM
  wait "$pid"
  local code=$?
  rm -f "$PID_FILE"
  exit "$code"
}

cd "$SERVICE_DIR"

if [ -f "Makefile" ]; then
  export HOST="${HOST:-}"
  export PORT="${PORT:-}"
  start_and_track make run "$@"
fi

if [ -f "package.json" ]; then
  export HOST="${HOST:-}"
  export PORT="${PORT:-}"
  extra=()
  if [ -n "${HOST:-}" ]; then
    extra+=(--host "$HOST")
  fi
  if [ -n "${PORT:-}" ]; then
    extra+=(--port "$PORT")
  fi
  if npm run | grep -qE '^  start$'; then
    # Prefer passing host/port through to vite when present
    if [ "${#extra[@]}" -gt 0 ]; then
      start_and_track npm start -- "${extra[@]}" "$@"
    else
      start_and_track npm start -- "$@"
    fi
  fi
  if npm run | grep -qE '^  dev$'; then
    if [ "${#extra[@]}" -gt 0 ]; then
      start_and_track npm run dev -- "${extra[@]}" "$@"
    else
      start_and_track npm run dev -- "$@"
    fi
  fi
  start_and_track npm start -- "$@"
fi

echo "Service '$NAME' exists at $SERVICE_DIR"
echo "No run convention found yet (add Makefile target 'run' or package.json scripts)."
exit 1
