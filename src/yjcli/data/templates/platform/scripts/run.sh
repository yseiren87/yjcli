#!/usr/bin/env bash
# Run service(s) under this platform.
# Always loads {service}/.env.local-dev (never development/production).
# Usage:
#   ./scripts/run.sh                 # all services concurrently
#   ./scripts/run.sh <service> [args...]
set -euo pipefail

PLATFORM_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PLATFORM_DIR"

list_services() {
  local d name
  for d in */ ; do
    name="${d%/}"
    case "$name" in
      scripts|proto) continue ;;
    esac
    [ -d "$name" ] && printf '%s\n' "$name"
  done | sort
}

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
  local pid_file="$1"
  if [ ! -f "$pid_file" ]; then
    return 0
  fi
  local old_pid
  old_pid="$(tr -d '[:space:]' <"$pid_file" || true)"
  if [ -n "$old_pid" ] && kill -0 "$old_pid" 2>/dev/null; then
    echo "stopping pid $old_pid from $pid_file"
    kill "$old_pid" 2>/dev/null || true
    sleep 0.3
    kill -9 "$old_pid" 2>/dev/null || true
  fi
  rm -f "$pid_file"
}

run_one() {
  local NAME="$1"
  shift || true
  case "$NAME" in
    scripts|proto)
      echo "reserved name: $NAME"
      return 1
      ;;
  esac

  local SERVICE_DIR="$PLATFORM_DIR/$NAME"
  local ENV_FILE="$SERVICE_DIR/.env.local-dev"
  local PID_FILE="$SERVICE_DIR/.run.pid"

  if [ ! -d "$SERVICE_DIR" ]; then
    echo "unknown service: $NAME (expected $SERVICE_DIR)"
    return 1
  fi
  if [ ! -f "$ENV_FILE" ]; then
    echo "missing $ENV_FILE (local run always uses .env.local-dev)"
    return 1
  fi

  # Load KEY=VALUE from .env.local-dev (ignore comments/blank lines)
  set -a
  # shellcheck disable=SC1090
  source <(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "$ENV_FILE" || true)
  set +a

  echo "[$NAME] env: $ENV_FILE"
  if [ -n "${PORT:-}" ]; then
    kill_by_port "$PORT"
  else
    echo "[$NAME] PORT unset in .env.local-dev; using pidfile fallback"
  fi
  kill_by_pidfile "$PID_FILE"

  start_and_track() {
    "$@" &
    local pid=$!
    echo "$pid" >"$PID_FILE"
    echo "[$NAME] started pid $pid (tracked in $PID_FILE)"
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
    local -a extra=()
    if [ -n "${HOST:-}" ]; then
      extra+=(--host "$HOST")
    fi
    if [ -n "${PORT:-}" ]; then
      extra+=(--port "$PORT")
    fi
    if npm run | grep -qE '^  start$'; then
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

  echo "[$NAME] exists at $SERVICE_DIR"
  echo "No run convention found yet (add Makefile target 'run' or package.json scripts)."
  return 1
}

run_all() {
  local -a services=()
  local line name
  while IFS= read -r line; do
    [ -n "$line" ] && services+=("$line")
  done < <(list_services)

  if [ "${#services[@]}" -eq 0 ]; then
    echo "no services under $PLATFORM_DIR (run: yjcli add service)"
    exit 1
  fi

  echo "starting ${#services[@]} service(s) concurrently: ${services[*]}"
  local -a pids=()
  for name in "${services[@]}"; do
    ( run_one "$name" ) &
    pids+=($!)
  done

  cleanup() {
    local p
    for p in "${pids[@]}"; do
      kill "$p" 2>/dev/null || true
    done
  }
  trap cleanup INT TERM

  local fail=0
  local p
  for p in "${pids[@]}"; do
    if ! wait "$p"; then
      fail=1
    fi
  done
  exit "$fail"
}

if [ "${#}" -lt 1 ]; then
  run_all
fi

NAME="$1"
shift
run_one "$NAME" "$@"
