# Build stub for scripts/plugin-build-docker.sh (docker image build only — no
# push, no swarm/stack rollout; that is a deploy-side scripts/plugin-deploy-*.sh
# job, e.g. plugin-deploy-docker-swarm.sh, none of which ship by default).
# Language-agnostic template: yjcli does not assume a runtime, so this file has
# no FROM yet and will fail `docker build` until replaced — same "guard until
# implemented" contract as the other generated build/deploy scripts.
#
# plugin-build-docker.sh passes ENVIRONMENT and every KEY=VALUE from the
# service's .env.development / .env.production as --build-arg (selected by
# which environment is being built), and resolves VERSION from this service's
# package.json/pyproject.toml version field, or the VERSION env var if the
# language has no such file. Declare the ARGs you need below.
#
# Example (Node.js):
#   FROM node:20-slim AS build
#   WORKDIR /app
#   COPY package.json package-lock.json ./
#   RUN npm ci
#   COPY . .
#   RUN npm run build
#
#   FROM node:20-slim
#   WORKDIR /app
#   COPY --from=build /app ./
#   ARG VERSION
#   ARG ENVIRONMENT
#   CMD ["node", "dist/main.js"]
#
# Example (Python):
#   FROM python:3.12-slim
#   WORKDIR /app
#   COPY pyproject.toml ./
#   RUN pip install .
#   COPY . .
#   ARG VERSION
#   ARG ENVIRONMENT
#   CMD ["python", "-m", "app"]
#
# Registry tagging/push and swarm/stack rollout are a deploy-side plugin's job
# (scripts/plugin-deploy-*.sh), not this file. nginx/reverse-proxy is also a
# separate plugin — do not add it here.
#
# TODO: replace this stub with the service's real build (delete this file
# instead if this service should not be built as a docker image).
