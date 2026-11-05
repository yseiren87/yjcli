#!/usr/bin/env bash
# Build for platform "{{platform}}" (yjcli builder plugin; repository-owned).
#
# Read tools/builder/GUIDE.md, then implement build_one below.
# Everything else — argument checks, service list, emptying
# dist/{{platform}}/<service>/, writing BUILD_INFO — already works.
# This is the entry point `make {{platform}}-build-<env>` calls. It does not have
# to stay a single file: add helper scripts next to it and call them from here.
#
# User input (see GUIDE.md): if this script ever needs answers from the user, run the
# checks first, ask everything up front, show the plan, confirm once, then run with no
# further prompts. Arguments come before prompts; never prompt when stdin is not a terminal.
#
# Usage: tools/builder/{{platform}}/builder.sh <environment> [service]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
PLATFORM="$(basename "$SCRIPT_DIR")"
PLATFORM_DIR="$ROOT_DIR/$PLATFORM"
{{#if env_files}}
SECRETS_DIR="$ROOT_DIR/tools/secrets/$PLATFORM"
{{/if}}
DIST_DIR="$ROOT_DIR/dist/$PLATFORM"
ENVIRONMENT="${1:-}"
NAME="${2:-}"

# ---------------------------------------------------------------- implement me
# build_one <service>
#   Build one service into $OUT (= dist/{{platform}}/<service>/, already empty) so
#   that folder alone can run. Runs inside $PLATFORM_DIR/<service>.
{{#if env_files}}
#   Available: $ENVIRONMENT, $OUT, $ENV_FILE (tools/secrets/…/.env.$ENVIRONMENT —
#   read it only for build-time values; never copy it into $OUT).
{{else}}
#   Available: $ENVIRONMENT, $OUT. Never copy env value files into $OUT.
{{/if}}
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
  echo "usage: $0 <environment> [service]   (development, production, staging, ...)" >&2
  exit 1
}

# Any environment name: development and production come with every service; add more
# (staging, test, ...) by creating tools/secrets/<platform>/<service>/.env.<name>.
# local-dev is for local runs (tools/runner) only.
case "$ENVIRONMENT" in
  "" | local-dev | *[!A-Za-z0-9_-]*) usage ;;
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
{{#if env_files}}

# The environment must exist for every service before anything is built.
missing=0
for name in "${services[@]}"; do
  if [ ! -f "$SECRETS_DIR/$name/.env.$ENVIRONMENT" ]; then
    echo "[build] $PLATFORM/$name: missing tools/secrets/$PLATFORM/$name/.env.$ENVIRONMENT" >&2
    missing=1
  fi
done
[ "$missing" -eq 0 ] || exit 1
{{/if}}

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
{{#if env_files}}
  ENV_FILE="$SECRETS_DIR/$name/.env.$ENVIRONMENT"
{{/if}}
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
