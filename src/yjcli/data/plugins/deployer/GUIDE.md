# Deployer guide

> Managed by yjcli — regenerated on every run. Do not edit; put project notes in `AGENTS.md`. The scripts under `tools/deployer/` are repository-owned: keep them in line with this guide.

The deployer ships what the builder put in `dist/`. It never builds.

## Entry points

| Command | Script |
|---|---|
| `make <platform>-deploy-<env>` / `./make.ps1 <platform>-deploy-<env>` | `tools/deployer/<platform>/deployer.sh <env>` / `deployer.ps1 <env>` |
| `… NAME=<service>` | same script, with `<service>` as the second argument |

`<env>` is any environment the builder accepts (`development`, `production`, or one you added as `tools/secrets/<platform>/<service>/.env.<env>`). Build first with `make <platform>-build-<env>`. Current services:

{{service_list}}

## Behavior

- Reject an invalid environment name and `local-dev`. Deploy every service when no service is given; an unknown name is an error.
- Before deploying anything, check that every service has a complete build (`dist/<platform>/<service>/BUILD_INFO`) and `tools/secrets/<platform>/<service>/.env.<env>`. If one is missing, deploy nothing and say which build to run.
{{#if no_secrets}}
- No `tools/secrets/` for {{no_secrets_platforms}} (chosen in yjcli): skip the env file check and `--env-file`; the target supplies env values at run time by the project's own mechanism.
{{/if}}
- Warn when `BUILD_INFO` says the build was made for another environment.
- Stop at the first failing service with a non-zero exit code.

## Structure

- Keep the per-service deploy in one function: `deploy_one <service>` (`deployer.sh`) / `Invoke-DeployOne <service>` (`deployer.ps1`). It runs inside `dist/<platform>/<service>/` and reads from `$IN` / `$In`.
- It can use the environment, the build folder, the env file path (`$ENV_FILE` / `$EnvFile`) and the script folder (`$SCRIPT_DIR` / `$ScriptDir`).

## Requirements

- Input is `dist/<platform>/<service>/` only. Do not rebuild from source here.
- Env values come from `tools/secrets/<platform>/<service>/.env.<env>` at **run time**, so one build works in any environment.
- `deployer.sh` and `deployer.ps1` behave the same. `deployer.sh` works on macOS's bash 3.2; `deployer.ps1` stays ASCII-only.

### Docker

When a service is shipped as a container:

- The image only copies the build: `docker build -f <Dockerfile> dist/<platform>/<service>` with `COPY . /app` — no compiling inside the image beyond what the runtime needs.
- Never copy `.env.*` into the image and never pass env values as `--build-arg`.
- Inject them when the container starts: `docker run --env-file tools/secrets/<platform>/<service>/.env.<env> …` (or `env_file:` in compose / the orchestrator's equivalent).
- `--env-file` reads plain `KEY=VALUE` lines: no quotes, no `export`, no multi-line values. Keep the secrets files in that format.
- Keep Dockerfiles under `tools/deployer/<platform>/` (e.g. `Dockerfile`, or `<service>.Dockerfile` when services differ) — service folders hold code only.

Other targets (static hosting, scp, app stores, …) follow the same rule: the input is `dist/`, env values are supplied by the target at run time.

## User input

When a script needs anything from the user (a target, a version, a confirmation, a message), it asks for everything up front and acts only at the end:

1. Checks first: run what needs no input (tools, files, `BUILD_INFO`, credentials) right away and stop with a clear message before asking anything.
2. Collect every input: ask all questions in a row and keep the answers in variables. Nothing is changed while asking. Re-ask on an invalid answer instead of exiting.
3. Show the plan: one screen with every answer and what will happen (services, environment, target, irreversible steps).
4. Confirm once: a single `y` (anything else quits without changes).
5. Run: execute every step with the stored values and no further prompts. On failure stop, undo what can be undone, and say what is left.

Arguments and env vars come before prompts: a value given on the command line is not asked again, and when stdin is not a terminal (CI) the script never prompts — it fails listing the missing values instead.

## More than one script

One entry script per platform is a starting point, not a limit: when a platform needs more (Dockerfiles, per-service deploy scripts, rollout and health-check helpers), add files under `tools/deployer/<platform>/` or `tools/deployer/` and call them from the entry script instead of growing one file indefinitely. Keep the entry script name — `make` calls it.

Everything under `tools/deployer/` belongs to this plugin: removing the plugin in yjcli deletes `tools/deployer/`, and removing a platform deletes `tools/deployer/<platform>/` — files you added there included.
