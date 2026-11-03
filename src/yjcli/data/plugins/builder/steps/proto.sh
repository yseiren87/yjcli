#!/usr/bin/env bash
# Build step: protoc codegen (yjcli builder plugin, managed by yjcli).
# Run by tools/builder/build-common.sh for every platform; applies only when
# <platform>/proto/ exists. backend-msa always has proto/; any other platform
# opts in by creating proto/.
# Also runnable standalone: tools/builder/steps/proto.sh <platform> <env> [service]
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
PLATFORM="${1:-}"
PROTO_DIR="$ROOT_DIR/$PLATFORM/proto"

[ -n "$PLATFORM" ] && [ -d "$PROTO_DIR" ] || exit 0

echo "[build] proto: $PROTO_DIR (protoc codegen is not implemented)"
echo "Implement protoc generation in: tools/builder/steps/proto.sh"
echo "Schema source: $PROTO_DIR/*.proto -> generated output: $PROTO_DIR/dist/{lang}"

# Implementation example:
# protoc \
#   --proto_path="$PROTO_DIR" \
#   --go_out="$PROTO_DIR/dist/go" --go-grpc_out="$PROTO_DIR/dist/go" \
#   "$PROTO_DIR"/*.proto
exit 0
