#!/usr/bin/env bash
# Development build for this platform (yjcli builder plugin; repository-owned).
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

"$BUILDER_DIR/build-common.sh" "$PLATFORM" development "$NAME"

echo "development build is not implemented."
echo "Implement build/package logic in: $SCRIPT_DIR/build-development.sh"
echo "Env values: $ROOT_DIR/tools/secrets/$PLATFORM/<service>/.env.development"

# Implementation examples:
# (cd "$ROOT_DIR/$PLATFORM/$NAME" && npm ci && npm run build:development)
# tar -czf "${NAME:-$PLATFORM}.tar.gz" -C "$ROOT_DIR/$PLATFORM" "${NAME:-.}"
exit 1
