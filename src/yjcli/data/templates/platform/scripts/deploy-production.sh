#!/usr/bin/env bash
# Production deployment entry point. Keep shared preparation in deploy-common.sh.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
NAME="${1:-}"
shift || true

"$SCRIPT_DIR/deploy-common.sh" production "$NAME" "$@"

echo "production upload is not implemented."
echo "Implement upload/deploy logic in: $SCRIPT_DIR/deploy-production.sh"
echo "Examples: registry push, production upload, release rollout"

# Recommended production steps:
# - validate VERSION or release tag
# - upload the artifact or push the container image
# - deploy to the production environment and run a health check
# - roll back on failure
exit 1
