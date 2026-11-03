#!/usr/bin/env bash
# Shared build host for every platform (yjcli builder plugin, managed by yjcli).
# Called by tools/builder/<platform>/build-<environment>.sh.
#
# Runs every tools/builder/steps/*.sh (proto, ssr, docker, …) in order. Each step
# self-detects whether it applies by folder/file presence (proto/, views/,
# Dockerfile), never by platform name. Project-specific build/package logic
# belongs in tools/builder/<platform>/build-<environment>.sh, not here.
set -euo pipefail
shopt -s nullglob

BUILDER_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$BUILDER_DIR/../.." && pwd)"
PLATFORM="${1:-}"
ENVIRONMENT="${2:-}"
NAME="${3:-}"

if [ -z "$PLATFORM" ] || [ ! -d "$ROOT_DIR/$PLATFORM" ]; then
  echo "usage: $0 <platform> <development|production> [service]"
  echo "unknown platform: ${PLATFORM:-<empty>}"
  exit 1
fi

case "$ENVIRONMENT" in
  development|production) ;;
  *)
    echo "usage: $0 <platform> <development|production> [service]"
    exit 1
    ;;
esac

if [ -n "$NAME" ] && [ ! -d "$ROOT_DIR/$PLATFORM/$NAME" ]; then
  echo "unknown service: $NAME (expected $ROOT_DIR/$PLATFORM/$NAME)"
  exit 1
fi

echo "[build] platform: $PLATFORM"
echo "[build] environment: $ENVIRONMENT"
echo "[build] service: ${NAME:-all}"

for step in "$BUILDER_DIR"/steps/*.sh; do
  case "$(basename "$step")" in
    deploy-*) continue ;;
  esac
  [ -x "$step" ] || continue
  "$step" "$PLATFORM" "$ENVIRONMENT" "$NAME"
done
