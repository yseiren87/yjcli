#!/usr/bin/env bash
# Plugin: protoc codegen.
# Auto-detected by build-common.sh (runs every scripts/plugin-build-*.sh) when
# {platform}/proto/ exists. Not backend-specific — any platform opts in by
# creating proto/. See yj-backend-msa's "proto" section and
# yj-backend-service's "gRPC transport" chapter.
# Also runnable standalone: ./plugin-build-proto.sh <env> [service]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLATFORM_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROTO_DIR="$PLATFORM_DIR/proto"

[ -d "$PROTO_DIR" ] || exit 0

echo "[build] proto: $PROTO_DIR (protoc codegen is not implemented)"
echo "Implement protoc generation in: $SCRIPT_DIR/plugin-build-proto.sh"
echo "Schema source: $PROTO_DIR/*.proto -> generated output: $PROTO_DIR/dist/{lang}"

# Implementation example:
# protoc \
#   --proto_path="$PROTO_DIR" \
#   --go_out="$PROTO_DIR/dist/go" --go-grpc_out="$PROTO_DIR/dist/go" \
#   "$PROTO_DIR"/*.proto
exit 0
