#!/usr/bin/env bash
# Shared deploy host for every platform (yjcli builder plugin, managed by yjcli).
# Runs tools/builder/<platform>/build-<environment>.sh, then every
# tools/builder/steps/deploy-*.sh present (none ship by default — add one, e.g.
# steps/deploy-docker-swarm.sh, to opt in). The per-platform
# deploy-development.sh / deploy-production.sh call this first and then own
# upload/rollout guidance only.
set -euo pipefail
shopt -s nullglob

BUILDER_DIR="$(cd "$(dirname "$0")" && pwd)"
PLATFORM="${1:-}"
ENVIRONMENT="${2:-}"
NAME="${3:-}"
shift 3 || true

case "$ENVIRONMENT" in
  development|production) ;;
  *)
    echo "usage: $0 <platform> <development|production> [service] [args...]"
    exit 1
    ;;
esac

"$BUILDER_DIR/$PLATFORM/build-$ENVIRONMENT.sh" "$NAME" "$@"

for step in "$BUILDER_DIR"/steps/deploy-*.sh; do
  [ -x "$step" ] || continue
  "$step" "$PLATFORM" "$ENVIRONMENT" "$NAME"
done
