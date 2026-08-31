#!/usr/bin/env bash
# Shared build/package preparation for development and production builds.
# Replace the implementation guard below with repository-specific commands.
#
# This file is identical across every platform. Optional capabilities live as
# separate scripts/plugin-build-*.sh files (e.g. plugin-build-proto.sh,
# plugin-build-ssr.sh) — the "build" segment names the consumer (deploy-side
# plugins would be plugin-deploy-*.sh instead), each self-detecting whether it
# applies by folder presence, no platform-name branching. Every
# plugin-build-*.sh present is run in order; none are wired to one platform.
set -euo pipefail
shopt -s nullglob

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLATFORM_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENVIRONMENT="${1:-}"
NAME="${2:-}"

case "$ENVIRONMENT" in
  development|production) ;;
  *)
    echo "usage: $0 <development|production> [service] [args...]"
    exit 1
    ;;
esac

if [ -n "$NAME" ] && [ ! -d "$PLATFORM_DIR/$NAME" ]; then
  echo "unknown service: $NAME (expected $PLATFORM_DIR/$NAME)"
  exit 1
fi

echo "[build] platform: $(basename "$PLATFORM_DIR")"
echo "[build] environment: $ENVIRONMENT"
echo "[build] service: ${NAME:-all}"

for plugin in "$SCRIPT_DIR"/plugin-build-*.sh; do
  [ -x "$plugin" ] || continue
  "$plugin" "$ENVIRONMENT" "$NAME"
done

echo "build common is not implemented."
echo "Implement build/package logic in: $SCRIPT_DIR/build-common.sh"
echo "Examples: docker build, archive creation, frontend build"

# Implementation examples:
# docker build -t "example/${NAME:-platform}:$ENVIRONMENT" "$PLATFORM_DIR"
# tar -czf "${NAME:-platform}.tar.gz" -C "$PLATFORM_DIR" "${NAME:-.}"
# (cd "$PLATFORM_DIR/$NAME" && npm ci && npm run build)
exit 1
