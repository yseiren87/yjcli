#!/usr/bin/env bash
# Build for platform "{{platform}}" (yjcli builder plugin; repository-owned).
#
# Read tools/builder/GUIDE.md, then implement build_one below.
# Everything else — argument checks, service list, emptying
# dist/{{platform}}/<service>/, writing BUILD_INFO — already works.
# This is the entry point `make {{platform}}-build-<env>` calls. It does not have
# to stay a single file: add helper scripts next to it and call them from here.
#
# Usage: tools/builder/{{platform}}/builder.sh <development|production> [service]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
PLATFORM="$(basename "$SCRIPT_DIR")"
PLATFORM_DIR="$ROOT_DIR/$PLATFORM"
SECRETS_DIR="$ROOT_DIR/tools/secrets/$PLATFORM"
DIST_DIR="$ROOT_DIR/dist/$PLATFORM"
ENVIRONMENT="${1:-}"
NAME="${2:-}"

# ---------------------------------------------------------------- implement me
# build_one <service>
#   Build one service into $OUT (= dist/{{platform}}/<service>/, already empty) so
#   that folder alone can run. Runs inside $PLATFORM_DIR/<service>.
#   Available: $ENVIRONMENT, $OUT, $ENV_FILE (tools/secrets/…/.env.$ENVIRONMENT —
#   read it only for build-time values; never copy it into $OUT).
build_one() {
  echo "builder for $PLATFORM/$1 is not implemented — read tools/builder/GUIDE.md" >&2
  return 1
  # Examples:
  # CGO_ENABLED=0 GOOS=linux go build -o "$OUT/app" .
  # npm ci && npm run build && cp -R dist/. "$OUT/"
  # uv build --wheel --out-dir "$OUT"
}
# -----------------------------------------------------------------------------

usage() {
  echo "usage: $0 <development|production> [service]" >&2
  exit 1
}

case "$ENVIRONMENT" in
  development | production) ;;
  *) usage ;;
esac

if [ -n "$NAME" ]; then
  if [ ! -d "$PLATFORM_DIR/$NAME" ]; then
    echo "unknown service: $NAME (expected $PLATFORM_DIR/$NAME)" >&2
    exit 1
  fi
  services=("$NAME")
else
  services=()
  for dir in "$PLATFORM_DIR"/*/; do
    [ -d "$dir" ] || continue
    services+=("$(basename "$dir")")
  done
fi
if [ "${#services[@]}" -eq 0 ]; then
  echo "no services under $PLATFORM_DIR" >&2
  exit 1
fi

# package.json / pyproject.toml version, else $VERSION, else "unknown".
resolve_version() {
  local dir="$1" v=""
  if [ -f "$dir/package.json" ]; then
    v="$(sed -nE 's/^[[:space:]]*"version"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/p' "$dir/package.json" | head -n1)"
  elif [ -f "$dir/pyproject.toml" ]; then
    v="$(sed -nE 's/^version[[:space:]]*=[[:space:]]*"([^"]+)".*/\1/p' "$dir/pyproject.toml" | head -n1)"
  fi
  printf '%s' "${v:-${VERSION:-unknown}}"
}
{{#if needs_proto}}

# This platform consumes the shared proto contract: generate it first.
if [ -x "$ROOT_DIR/tools/builder/proto/builder.sh" ]; then
  echo "[build] proto contract (tools/builder/proto/builder.sh)"
  "$ROOT_DIR/tools/builder/proto/builder.sh"
fi
{{/if}}

# A failed build leaves no half-written output behind; BUILD_INFO marks a complete build.
PARTIAL=""
trap '[ -n "$PARTIAL" ] && rm -rf "$PARTIAL"' EXIT

for name in "${services[@]}"; do
  OUT="$DIST_DIR/$name"
  ENV_FILE="$SECRETS_DIR/$name/.env.$ENVIRONMENT"
  echo "[build] $PLATFORM/$name ($ENVIRONMENT) -> dist/$PLATFORM/$name"
  rm -rf "$OUT"
  mkdir -p "$OUT"
  PARTIAL="$OUT"
  (cd "$PLATFORM_DIR/$name" && build_one "$name")
  {
    echo "platform=$PLATFORM"
    echo "service=$name"
    echo "environment=$ENVIRONMENT"
    echo "version=$(resolve_version "$PLATFORM_DIR/$name")"
    echo "built_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  } >"$OUT/BUILD_INFO"
  PARTIAL=""
done
echo "[build] done: ${services[*]}"
