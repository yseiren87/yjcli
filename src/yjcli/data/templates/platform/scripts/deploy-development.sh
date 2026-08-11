#!/usr/bin/env bash
# Development deployment entry point. Keep shared preparation in deploy-common.sh.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
NAME="${1:-}"
shift || true

"$SCRIPT_DIR/deploy-common.sh" development "$NAME" "$@"

echo "development upload is not implemented."
echo "Implement upload/deploy logic in: $SCRIPT_DIR/deploy-development.sh"
echo "Examples: docker push, scp, S3 upload, kubectl apply"

# Development upload examples:
# docker push "registry.example.com/$NAME:development"
# scp "$ARTIFACT" "dev-server:/srv/$NAME/"
# aws s3 sync "$DIST_DIR" "s3://example-development/$NAME/"
# kubectl apply -k deploy/overlays/development
exit 1
