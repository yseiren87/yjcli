#!/usr/bin/env bash
# Plugin: docker image build (build stage only — no push, no swarm/stack
# rollout; that belongs in a deploy-side plugin-deploy-*.sh, not here).
# Auto-detected by build-common.sh (runs every scripts/plugin-build-*.sh) per
# service that has a Dockerfile. Not tied to one platform — any service opts
# in by keeping its Dockerfile; delete it to opt out.
# Also runnable standalone: ./plugin-build-docker.sh <env> [service]
set -euo pipefail
shopt -s nullglob

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLATFORM_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENVIRONMENT="${1:-}"
NAME="${2:-}"

case "$ENVIRONMENT" in
  development|production) ;;
  *)
    echo "usage: $0 <development|production> [service]"
    exit 1
    ;;
esac

# Version resolution order: package.json (Node.js) -> pyproject.toml (Python)
# -> VERSION env var (any other language). Extend this function for more
# package-manifest formats as needed.
resolve_version() {
  local service_dir="$1"
  if [ -f "$service_dir/package.json" ]; then
    grep -m1 '"version"' "$service_dir/package.json" \
      | sed -E 's/.*"version"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/'
    return
  fi
  if [ -f "$service_dir/pyproject.toml" ]; then
    grep -m1 -E '^version[[:space:]]*=' "$service_dir/pyproject.toml" \
      | sed -E 's/^version[[:space:]]*=[[:space:]]*"([^"]+)".*/\1/'
    return
  fi
  if [ -n "${VERSION:-}" ]; then
    printf '%s' "$VERSION"
    return
  fi
  return 1
}

build_one() {
  local name="$1"
  local service_dir="$PLATFORM_DIR/$name"
  local dockerfile="$service_dir/Dockerfile"
  local env_file="$service_dir/.env.$ENVIRONMENT"

  [ -f "$dockerfile" ] || return 0

  echo "[build] docker: $name (image build is not implemented)"
  echo "Implement it in: $SCRIPT_DIR/plugin-build-docker.sh"

  if [ ! -f "$env_file" ]; then
    echo "[build] $name: missing $env_file (docker build always uses .env.$ENVIRONMENT)"
    return 0
  fi

  local version
  if ! version="$(resolve_version "$service_dir")" || [ -z "$version" ]; then
    echo "[build] $name: could not resolve a version (no package.json/pyproject.toml version, and VERSION is unset)"
    echo "Set VERSION=<x.y.z> for services whose language has no package-manifest version field."
    return 0
  fi

  echo "[build] $name: env=$env_file version=$version dockerfile=$dockerfile"

  # Implementation example:
  # local build_args=(--build-arg "VERSION=$version" --build-arg "ENVIRONMENT=$ENVIRONMENT")
  # while IFS='=' read -r key value; do
  #   [ -n "$key" ] && build_args+=(--build-arg "$key=$value")
  # done < <(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "$env_file")
  # docker build "${build_args[@]}" \
  #   -t "$name:$version-$ENVIRONMENT" \
  #   -f "$dockerfile" "$service_dir"
  #
  # Registry tagging/push and swarm/stack rollout are a deploy-side plugin's
  # job (scripts/plugin-deploy-*.sh), not this one.
}

if [ -n "$NAME" ]; then
  build_one "$NAME"
else
  for dir in "$PLATFORM_DIR"/*/; do
    svc="$(basename "$dir")"
    case "$svc" in
      scripts|proto) continue ;;
    esac
    build_one "$svc"
  done
fi
exit 0
