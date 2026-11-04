#!/usr/bin/env bash
# Local runner for platform "{{platform}}" (yjcli runner plugin; repository-owned).
#
# Read tools/runner/GUIDE.md, then implement run_one below. Everything else —
# service discovery, .env.local-dev loading, concurrent start, [service] output
# prefix, Ctrl+C / failure cleanup — already works.
# This is the entry point `make {{platform}}` calls. It does not have to stay a
# single file: add helper scripts next to it and call them from here.
#
# Usage: tools/runner/{{platform}}/runner.sh [service]
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
PLATFORM="$(basename "$SCRIPT_DIR")"
PLATFORM_DIR="$ROOT_DIR/$PLATFORM"
SECRETS_DIR="$ROOT_DIR/tools/secrets/$PLATFORM"
NAME="${1:-}"

# ---------------------------------------------------------------- implement me
# run_one <service>
#   Start one service in the foreground and stay attached (prefer `exec`).
#   Runs inside $PLATFORM_DIR/<service> with its .env.local-dev already exported.
run_one() {
  echo "runner for $PLATFORM/$1 is not implemented — read tools/runner/GUIDE.md" >&2
  return 1
  # Examples:
  # exec go run .
  # exec npm run dev
  # exec uv run python -m app
}
# -----------------------------------------------------------------------------

list_services() {
  local dir
  for dir in "$PLATFORM_DIR"/*/; do
    [ -d "$dir" ] || continue
    case "$(basename "$dir")" in
      proto) continue ;;
    esac
    basename "$dir"
  done
}

if [ -n "$NAME" ]; then
  if [ "$NAME" = "proto" ] || [ ! -d "$PLATFORM_DIR/$NAME" ]; then
    echo "unknown service: $NAME (expected $PLATFORM_DIR/$NAME)" >&2
    exit 1
  fi
  services=("$NAME")
else
  services=()
  while IFS= read -r line; do
    services+=("$line")
  done < <(list_services)
fi

start_service() {
  local name="$1"
  local env_file="$SECRETS_DIR/$name/.env.local-dev"
  (
    cd "$PLATFORM_DIR/$name" || exit 1
    # KEY=VALUE lines, values taken literally (same rules as docker --env-file).
    while IFS= read -r entry || [ -n "$entry" ]; do
      case "$entry" in
        '' | \#*) continue ;;
      esac
      export "${entry%%=*}=${entry#*=}"
    done <"$env_file"
    run_one "$name"
  ) 2>&1 | while IFS= read -r line; do printf '[%s] %s\n' "$name" "$line"; done
  return "${PIPESTATUS[0]}"
}

pids=()
names=()
# Each service runs in its own process group (job control) so cleanup can stop
# the whole tree (npm -> node, uv -> python, …), and Ctrl+C reaches this script only.
set -m
for name in ${services[@]+"${services[@]}"}; do
  if [ ! -f "$SECRETS_DIR/$name/.env.local-dev" ]; then
    echo "[$name] skipped: missing tools/secrets/$PLATFORM/$name/.env.local-dev" >&2
    continue
  fi
  start_service "$name" &
  pids+=("$!")
  names+=("$name")
done
set +m

if [ "${#pids[@]}" -eq 0 ]; then
  echo "no runnable services under $PLATFORM_DIR" >&2
  exit 1
fi
echo "running ${#pids[@]} service(s): ${names[*]} — Ctrl+C to stop"

stop_all() {
  local pid
  for pid in "${pids[@]}"; do
    [ "$pid" = "-" ] && continue
    kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
  done
  for pid in "${pids[@]}"; do
    [ "$pid" = "-" ] && continue
    wait "$pid" 2>/dev/null || true
  done
}

trap 'trap - INT TERM; echo "stopping…" >&2; stop_all; exit 130' INT TERM

# bash 3.2 (macOS) has no `wait -n`: poll. A service that exits non-zero stops
# the rest and its code becomes ours; one that exits 0 just leaves the set.
running=${#pids[@]}
while [ "$running" -gt 0 ]; do
  for i in "${!pids[@]}"; do
    pid="${pids[$i]}"
    [ "$pid" = "-" ] && continue
    kill -0 "$pid" 2>/dev/null && continue
    code=0
    wait "$pid" || code=$?
    pids[$i]="-"
    running=$((running - 1))
    if [ "$code" -ne 0 ]; then
      echo "[${names[$i]}] exited with $code — stopping the others" >&2
      trap - INT TERM
      stop_all
      exit "$code"
    fi
  done
  sleep 0.5
done
exit 0
