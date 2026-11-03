#!/usr/bin/env bash
# Production deployment for this platform (yjcli builder plugin; repository-owned).
# Shared orchestration (build, then every steps/deploy-*.sh) lives in
# tools/builder/deploy-common.sh; this file owns upload/rollout guidance only.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILDER_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PLATFORM="$(basename "$SCRIPT_DIR")"
NAME="${1:-}"
shift || true

"$BUILDER_DIR/deploy-common.sh" "$PLATFORM" production "$NAME" "$@"

echo "production upload is not implemented."
echo "Implement upload/deploy logic in: $SCRIPT_DIR/deploy-production.sh"
echo "Examples: registry push, production upload, release rollout"

# Recommended production steps:
# - validate VERSION or release tag
# - upload the artifact or push the container image
# - deploy to the production environment and run a health check
# - roll back on failure
exit 1
