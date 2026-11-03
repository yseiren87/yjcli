#!/usr/bin/env bash
# Build step: server-templating (SSR/MPA) template/asset build (yjcli builder
# plugin, managed by yjcli). Run by tools/builder/build-common.sh for every
# platform; applies per service when <platform>/<service>/views/ exists.
# backend-ssr services always have views/; any other service opts in by
# creating views/.
# Also runnable standalone: tools/builder/steps/ssr.sh <platform> <env> [service]
set -euo pipefail
shopt -s nullglob

ROOT_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
PLATFORM="${1:-}"
NAME="${3:-}"
PLATFORM_DIR="$ROOT_DIR/$PLATFORM"

[ -n "$PLATFORM" ] && [ -d "$PLATFORM_DIR" ] || exit 0

if [ -n "$NAME" ]; then
  candidates=("$PLATFORM_DIR/$NAME/views")
else
  candidates=("$PLATFORM_DIR"/*/views)
fi

found=0
for dir in ${candidates[@]+"${candidates[@]}"}; do
  if [ -d "$dir" ]; then
    found=1
    echo "[build] views: $dir (template/asset build is not implemented)"
  fi
done
[ "$found" -eq 1 ] || exit 0

echo "Implement template/asset bundling in: tools/builder/steps/ssr.sh"

# Implementation example:
# (cd "$PLATFORM_DIR/${NAME:-<service>}" && npm ci && npm run build:views)
exit 0
