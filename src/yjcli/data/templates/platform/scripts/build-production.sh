#!/usr/bin/env bash
# Production build entry point. Keep shared preparation in build-common.sh.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
NAME="${1:-}"
shift || true

"$SCRIPT_DIR/build-common.sh" production "$NAME" "$@"
