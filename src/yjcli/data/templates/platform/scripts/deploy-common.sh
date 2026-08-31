#!/usr/bin/env bash
# Shared deploy orchestration for development and production deploys: runs the
# matching build script, then every scripts/plugin-deploy-*.sh present (none
# ship by default — add one, e.g. plugin-deploy-docker-swarm.sh, to opt in).
# The environment-specific deploy-development.sh / deploy-production.sh call
# this first and then own upload/rollout guidance only.
set -euo pipefail
shopt -s nullglob

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENVIRONMENT="${1:-}"
NAME="${2:-}"
shift 2

case "$ENVIRONMENT" in
  development|production) ;;
  *)
    echo "usage: $0 <development|production> [service] [args...]"
    exit 1
    ;;
esac

"$SCRIPT_DIR/build-$ENVIRONMENT.sh" "$NAME" "$@"

for plugin in "$SCRIPT_DIR"/plugin-deploy-*.sh; do
  [ -x "$plugin" ] || continue
  "$plugin" "$ENVIRONMENT" "$NAME"
done
