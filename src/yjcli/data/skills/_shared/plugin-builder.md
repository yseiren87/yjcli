### Builder (`tools/builder/`)

- Builds: `make <platform>-build-development|production [NAME=<service>]` →
  `tools/builder/<platform>/build-<environment>.sh`. Deploys:
  `make <platform>-deploy-development|production [NAME=<service>]` →
  `tools/builder/<platform>/deploy-<environment>.sh`.
- `tools/builder/build-common.sh`, `deploy-common.sh` and `steps/*.sh` are
  managed by yjcli and regenerated. Put build/package logic in
  `tools/builder/<platform>/build-<environment>.sh` and upload/rollout in
  `deploy-<environment>.sh` — those are repository-owned and fail with an
  implementation prompt until implemented.
- `build-common.sh` runs every `steps/*.sh`. Each step self-detects by
  folder/file presence, never by platform name, so any platform can opt in:
  - `steps/proto.sh` → protoc codegen when `<platform>/proto/` exists
    (`proto/*.proto` → `proto/dist/{lang}`). protoc is the standard; buf is not used.
  - `steps/ssr.sh` → template/asset build when `<platform>/<service>/views/` exists.
  - `steps/docker.sh` → docker image **build only** (no push, no swarm/stack
    rollout) for each service with a `Dockerfile`, using
    `tools/secrets/<platform>/<service>/.env.<environment>`. Image version: the
    service's `package.json`/`pyproject.toml` `version`, else the `VERSION` env var.
- Deploy-side steps are `steps/deploy-*.sh` (none ship by default — e.g. image
  push + `docker stack deploy`, `kubectl apply`); `deploy-common.sh` runs them
  after the build.
- Deployable services get a `Dockerfile` + `.dockerignore` stub with no `FROM`
  yet — `docker build` fails until it is replaced. Delete it to opt a service out.
- `build-*` / `deploy-*` are `.sh` only — build/deploy tooling is not native to
  Windows, so `make.bat` runs those targets through WSL.
