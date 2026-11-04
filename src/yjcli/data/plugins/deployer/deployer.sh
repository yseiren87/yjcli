#!/usr/bin/env bash
# Deploy for platform "{{platform}}" (yjcli deployer plugin; repository-owned).
#
# Read tools/deployer/GUIDE.md, then implement deploy_one below. Everything else
# — argument checks, service list, checking that dist/{{platform}}/<service>/ and
# the env file exist, warning on a BUILD_INFO environment mismatch — already works.
# The deployer never builds: run `make {{platform}}-build-<env>` first.
# This is the entry point `make {{platform}}-deploy-<env>` calls. It does not have
# to stay a single file: add helper scripts next to it and call them from here.
#
# Usage: tools/deployer/{{platform}}/deployer.sh <development|production> [service]
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
# deploy_one <service>
#   Deploy the build in $IN (= dist/{{platform}}/<service>/). Runs inside $IN.
#   Available: $ENVIRONMENT, $IN, $ENV_FILE (tools/secrets/…/.env.$ENVIRONMENT),
#   $SCRIPT_DIR (keep a Dockerfile etc. here, not in the service folder).
deploy_one() {
  echo "deployer for $PLATFORM/$1 is not implemented — read tools/deployer/GUIDE.md" >&2
  return 1
  # Docker (the image only copies $IN; env comes in at run time, never baked):
  # docker build -t "$1:$ENVIRONMENT" -f "$SCRIPT_DIR/Dockerfile" "$IN"
  # docker run -d --name "$1" --env-file "$ENV_FILE" "$1:$ENVIRONMENT"
  # Other targets:
  # scp -r "$IN/." "server:/srv/$1/"
  # aws s3 sync "$IN" "s3://example-$ENVIRONMENT/$1/"
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
  if [ "$NAME" = "proto" ] || [ ! -d "$PLATFORM_DIR/$NAME" ]; then
    echo "unknown service: $NAME (expected $PLATFORM_DIR/$NAME)" >&2
    exit 1
  fi
  services=("$NAME")
else
  services=()
  for dir in "$PLATFORM_DIR"/*/; do
    [ -d "$dir" ] || continue
    case "$(basename "$dir")" in
      proto) continue ;;
    esac
    services+=("$(basename "$dir")")
  done
fi
if [ "${#services[@]}" -eq 0 ]; then
  echo "no services under $PLATFORM_DIR" >&2
  exit 1
fi

# Check every service before deploying any of them.
missing=0
for name in "${services[@]}"; do
  if [ ! -f "$DIST_DIR/$name/BUILD_INFO" ]; then
    echo "[deploy] $PLATFORM/$name: no build in dist/$PLATFORM/$name — run: make $PLATFORM-build-$ENVIRONMENT NAME=$name" >&2
    missing=1
  fi
  if [ ! -f "$SECRETS_DIR/$name/.env.$ENVIRONMENT" ]; then
    echo "[deploy] $PLATFORM/$name: missing tools/secrets/$PLATFORM/$name/.env.$ENVIRONMENT" >&2
    missing=1
  fi
done
[ "$missing" -eq 0 ] || exit 1

for name in "${services[@]}"; do
  IN="$DIST_DIR/$name"
  ENV_FILE="$SECRETS_DIR/$name/.env.$ENVIRONMENT"
  built="$(sed -n 's/^environment=//p' "$IN/BUILD_INFO")"
  if [ "$built" != "$ENVIRONMENT" ]; then
    echo "[deploy] warning: dist/$PLATFORM/$name was built for $built, deploying to $ENVIRONMENT" >&2
  fi
  echo "[deploy] $PLATFORM/$name ($ENVIRONMENT)"
  (cd "$IN" && deploy_one "$name")
done
echo "[deploy] done: ${services[*]}"
