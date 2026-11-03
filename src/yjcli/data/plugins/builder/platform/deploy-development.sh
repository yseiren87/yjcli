#!/usr/bin/env bash
# Development deployment for this platform (yjcli builder plugin; repository-owned).
# Shared orchestration (build, then every steps/deploy-*.sh) lives in
# tools/builder/deploy-common.sh; this file owns upload/rollout guidance only.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILDER_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PLATFORM="$(basename "$SCRIPT_DIR")"
NAME="${1:-}"
shift || true

"$BUILDER_DIR/deploy-common.sh" "$PLATFORM" development "$NAME" "$@"

echo "development upload is not implemented."
echo "Implement upload/deploy logic in: $SCRIPT_DIR/deploy-development.sh"
echo "Examples: docker push, scp, S3 upload, kubectl apply"

# Development upload examples:
# docker push "registry.example.com/$NAME:development"
# scp "$ARTIFACT" "dev-server:/srv/$NAME/"
# aws s3 sync "$DIST_DIR" "s3://example-development/$NAME/"
# kubectl apply -k deploy/overlays/development
exit 1
