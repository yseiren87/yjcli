#!/usr/bin/env bash
# Plugin: server-templating (SSR/MPA) template/asset build.
# Auto-detected by build-common.sh (runs every scripts/plugin-build-*.sh) per
# service when {platform}/{service}/views/ exists. Not backend-service-specific
# — any platform's service opts in by creating views/. See yj-backend-service's
# and yj-backend-msa's "server templating" chapters.
# Also runnable standalone: ./plugin-build-ssr.sh <env> [service]
set -euo pipefail
shopt -s nullglob

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLATFORM_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
NAME="${2:-}"

if [ -n "$NAME" ]; then
  candidates=("$PLATFORM_DIR/$NAME/views")
else
  candidates=("$PLATFORM_DIR"/*/views)
fi

found=0
for dir in "${candidates[@]}"; do
  if [ -d "$dir" ]; then
    found=1
    echo "[build] views: $dir (template/asset build is not implemented)"
  fi
done
[ "$found" -eq 1 ] || exit 0

echo "Implement template/asset bundling in: $SCRIPT_DIR/plugin-build-ssr.sh"

# Implementation example:
# (cd "$PLATFORM_DIR/${NAME:-<service>}" && npm ci && npm run build:views)
exit 0
