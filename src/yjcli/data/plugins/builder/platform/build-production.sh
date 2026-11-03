#!/usr/bin/env bash
# Production build for this platform (yjcli builder plugin; repository-owned).
# Shared steps (proto codegen, SSR assets, docker image) run first through
# tools/builder/build-common.sh. Replace the guard below with this platform's
# real build/package commands.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILDER_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT_DIR="$(cd "$BUILDER_DIR/../.." && pwd)"
PLATFORM="$(basename "$SCRIPT_DIR")"
NAME="${1:-}"
shift || true

"$BUILDER_DIR/build-common.sh" "$PLATFORM" production "$NAME"

echo "production build is not implemented."
echo "Implement build/package logic in: $SCRIPT_DIR/build-production.sh"
echo "Env values: $ROOT_DIR/tools/secrets/$PLATFORM/<service>/.env.production"

# Implementation examples:
# (cd "$ROOT_DIR/$PLATFORM/$NAME" && npm ci && npm run build:production)
# tar -czf "${NAME:-$PLATFORM}.tar.gz" -C "$ROOT_DIR/$PLATFORM" "${NAME:-.}"
exit 1
