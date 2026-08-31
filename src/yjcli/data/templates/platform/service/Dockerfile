# Build stub for scripts/plugin-deploy-docker-swarm.sh (docker-swarm deploy).
# Language-agnostic template: yjcli does not assume a runtime, so this file has
# no FROM yet and will fail `docker build` until replaced — same "guard until
# implemented" contract as the other generated build/deploy scripts.
#
# The plugin passes ENVIRONMENT and every KEY=VALUE from the service's
# .env.development / .env.production as --build-arg (selected by which
# environment is being built), and resolves VERSION from this service's
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
# nginx/reverse-proxy is a separate plugin — do not add it here.
#
# TODO: replace this stub with the service's real build (delete this file
# instead if this service should not be deployed via docker-swarm).
