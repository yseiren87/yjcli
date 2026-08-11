#!/usr/bin/env bash
# Shared build/package preparation for development and production deploys.
# Replace the implementation guard below with repository-specific commands.
set -euo pipefail

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

echo "[deploy] platform: $(basename "$PLATFORM_DIR")"
echo "[deploy] environment: $ENVIRONMENT"
echo "[deploy] service: ${NAME:-all}"
echo "deploy common is not implemented."
echo "Implement build/package logic in: $SCRIPT_DIR/deploy-common.sh"
echo "Examples: docker build, archive creation, frontend build"

# Implementation examples:
# docker build -t "example/${NAME:-platform}:$ENVIRONMENT" "$PLATFORM_DIR"
# tar -czf "${NAME:-platform}.tar.gz" -C "$PLATFORM_DIR" "${NAME:-.}"
# (cd "$PLATFORM_DIR/$NAME" && npm ci && npm run build)
exit 1
