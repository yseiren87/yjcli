#!/usr/bin/env bash
# Build step: docker image build (yjcli builder plugin, managed by yjcli).
# Build stage only — no push, no swarm/stack rollout; that belongs in a
# deploy-side tools/builder/steps/deploy-*.sh, not here.
# Run by tools/builder/build-common.sh for every platform; applies per service
# that has a Dockerfile (delete it to opt that service out).
# Also runnable standalone: tools/builder/steps/docker.sh <platform> <env> [service]
set -euo pipefail
shopt -s nullglob

ROOT_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
PLATFORM="${1:-}"
ENVIRONMENT="${2:-}"
NAME="${3:-}"
PLATFORM_DIR="$ROOT_DIR/$PLATFORM"
SECRETS_DIR="$ROOT_DIR/tools/secrets/$PLATFORM"

case "$ENVIRONMENT" in
  development|production) ;;
  *)
    echo "usage: $0 <platform> <development|production> [service]"
    exit 1
    ;;
esac

[ -n "$PLATFORM" ] && [ -d "$PLATFORM_DIR" ] || exit 0

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
  local env_file="$SECRETS_DIR/$name/.env.$ENVIRONMENT"

  [ -f "$dockerfile" ] || return 0

  echo "[build] docker: $name (image build is not implemented)"
  echo "Implement it in: tools/builder/steps/docker.sh"

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
  # Registry tagging/push and swarm/stack rollout are a deploy-side step's job
  # (tools/builder/steps/deploy-*.sh), not this one.
}

if [ -n "$NAME" ]; then
  build_one "$NAME"
else
  for dir in "$PLATFORM_DIR"/*/; do
    svc="$(basename "$dir")"
    case "$svc" in
      proto) continue ;;
    esac
    build_one "$svc"
  done
fi
exit 0
