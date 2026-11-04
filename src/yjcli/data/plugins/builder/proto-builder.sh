#!/usr/bin/env bash
# Code generation for the shared proto contract (yjcli builder plugin; repository-owned).
#
# Read tools/builder/GUIDE.md ("Proto contract"), then implement one gen_<language>
# function per language below. Everything else — finding the languages under
# proto/dist/, argument checks — already works.
# This is the entry point `make proto-build` calls; builds of platforms that need the
# contract (e.g. backend-msa) call it first. It does not have to stay a single file:
# add helper scripts next to it and call them from here.
#
# Usage: tools/builder/proto/builder.sh [language]
set -euo pipefail
shopt -s nullglob

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
PROTO_DIR="$ROOT_DIR/proto"
LANGUAGE="${1:-}"

# ---------------------------------------------------------------- implement me
# gen_<language>
#   Generate code from $PROTO_DIR/*.proto into $OUT (= proto/dist/<language>/, which
#   also holds the library manifest — do not delete it). Remove generated files of
#   .proto files that no longer exist.
{{#if proto_lang_go}}
gen_go() {  # Go module {{proto_go_module}}
  echo "proto codegen for go is not implemented — read tools/builder/GUIDE.md" >&2
  return 1
  # protoc -I "$PROTO_DIR" \
  #   --go_out="$OUT" --go_opt=module={{proto_go_module}} \
  #   --go-grpc_out="$OUT" --go-grpc_opt=module={{proto_go_module}} \
  #   "$PROTO_DIR"/*.proto
  # (cd "$OUT" && go mod tidy)
}
{{/if}}
{{#if proto_lang_dart}}
gen_dart() {  # Dart package {{proto_dart_package}}
  echo "proto codegen for dart is not implemented — read tools/builder/GUIDE.md" >&2
  return 1
  # mkdir -p "$OUT/lib"
  # protoc -I "$PROTO_DIR" --dart_out=grpc:"$OUT/lib" "$PROTO_DIR"/*.proto
}
{{/if}}
{{#if proto_lang_python}}
gen_python() {  # Python package {{proto_python_package}}
  echo "proto codegen for python is not implemented — read tools/builder/GUIDE.md" >&2
  return 1
  # mkdir -p "$OUT/{{proto_python_package}}"
  # uv run --with grpcio-tools python -m grpc_tools.protoc -I "$PROTO_DIR" \
  #   --python_out="$OUT/{{proto_python_package}}" --pyi_out="$OUT/{{proto_python_package}}" \
  #   --grpc_python_out="$OUT/{{proto_python_package}}" "$PROTO_DIR"/*.proto
}
{{/if}}
# -----------------------------------------------------------------------------

if [ -n "$LANGUAGE" ]; then
  if [ ! -d "$PROTO_DIR/dist/$LANGUAGE" ]; then
    echo "unknown language: $LANGUAGE (expected $PROTO_DIR/dist/$LANGUAGE)" >&2
    exit 1
  fi
  languages=("$LANGUAGE")
else
  languages=()
  for dir in "$PROTO_DIR"/dist/*/; do
    languages+=("$(basename "$dir")")
  done
fi
if [ "${#languages[@]}" -eq 0 ]; then
  echo "no languages under $PROTO_DIR/dist" >&2
  exit 1
fi

schemas=("$PROTO_DIR"/*.proto)
if [ "${#schemas[@]}" -eq 0 ]; then
  echo "[proto] no .proto files in proto/ yet — nothing to generate"
  exit 0
fi

for lang in "${languages[@]}"; do
  OUT="$PROTO_DIR/dist/$lang"
  if ! declare -F "gen_$lang" >/dev/null; then
    echo "[proto] gen_$lang is not defined — add it to $0 (see tools/builder/GUIDE.md)" >&2
    exit 1
  fi
  echo "[proto] $lang -> proto/dist/$lang"
  "gen_$lang"
done
echo "[proto] done: ${languages[*]}"
