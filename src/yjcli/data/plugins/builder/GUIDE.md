# Builder guide

> Managed by yjcli — regenerated on every run. Do not edit; put project notes in `AGENTS.md`. The scripts under `tools/builder/<platform>/` are yours.

The builder turns each service into a runnable build under `dist/`. It only builds — deploying is the deployer's job.

## Entry points

| Command | Script |
|---|---|
| `make <platform>-build-<env>` / `./make.ps1 <platform>-build-<env>` | `tools/builder/<platform>/builder.sh <env>` / `builder.ps1 <env>` |
| `… NAME=<service>` | same script, with `<service>` as the second argument |

`<env>` is `development` or `production`. Current services:

{{service_list}}

## Output contract

- Every service builds into **`dist/<platform>/<service>/`** at the repository root (never inside the service folder).
- That folder alone must be runnable: the deployer copies it as-is.
- It must not contain env value files (`.env.*`). Env values are supplied when the build runs, not when it is built.
- `dist/<platform>/<service>/BUILD_INFO` records `platform`, `service`, `environment`, `version`, `built_at`. It is written only after a successful build and marks the folder as complete; a failed build leaves no output.
- `dist/` is git-ignored.

## What is already implemented

Each `builder.sh` / `builder.ps1` ships a working skeleton:

- Checks `<env>` and the optional service; builds every service when omitted.
- Empties `dist/<platform>/<service>/` before each build.
- Runs your build function inside `<platform>/<service>/`, then writes `BUILD_INFO`. Version: the service's `package.json` / `pyproject.toml` `version`, else the `VERSION` env var, else `unknown`.
- Stops at the first failing service with a non-zero exit code.
{{#if has_proto}}
- On platforms that can have a `proto/` contract, runs your proto function once before the services when `<platform>/proto/` exists.
{{/if}}

## What you implement

- `builder.sh`: `build_one <service>` · `builder.ps1`: `Invoke-BuildOne <service>` — build one service into `$OUT` / `$Out`.
- Available: the environment, the output folder, and the path of `tools/secrets/<platform>/<service>/.env.<env>` (`$ENV_FILE` / `$EnvFile`). Read it only for values that must be fixed at build time (e.g. a frontend bundle); never copy it into the output.
{{#if has_proto}}
- `build_proto` / `Invoke-BuildProto` — generate code from `<platform>/proto/*.proto` into `<platform>/proto/dist/<lang>/` (protoc is the standard). `proto/dist/` is generated source the services compile against; it is not a deployable build and does not go to `dist/`.
{{/if}}

Until implemented they print a pointer to this guide and fail.

## Requirements

- Build for where the service will run. If the deploy target is a Linux container, produce something that runs there (e.g. `GOOS=linux` for Go, or dependencies installed for Linux).
- `builder.sh` and `builder.ps1` produce the same output.
- `builder.sh` must work on macOS's bash 3.2.

## More than one script

yjcli ships one entry script per platform. That is a starting point, not a limit: when a platform needs more (per-language build steps, per-service scripts, a shared helper), add files under `tools/builder/<platform>/` or `tools/builder/` and call them from the entry script instead of growing one file indefinitely. Keep the entry script name — `make` calls it.
