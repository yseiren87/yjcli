# Builder guide

> Managed by yjcli — regenerated on every run. Do not edit; put project notes in `AGENTS.md`. The scripts under `tools/builder/` are repository-owned: keep them in line with this guide.

The builder turns each service into a runnable build under `dist/`. It only builds — deploying is the deployer's job.

## Entry points

| Command | Script |
|---|---|
| `make <platform>-build-<env>` / `./make.ps1 <platform>-build-<env>` | `tools/builder/<platform>/builder.sh <env>` / `builder.ps1 <env>` |
| `… NAME=<service>` | same script, with `<service>` as the second argument |

`<env>` is an environment name: `development` and `production` come with every service; add more (`staging`, `test`, …) by creating `tools/secrets/<platform>/<service>/.env.<env>` for every service of the platform. `local-dev` is for local runs only. Current services:

{{service_list}}

## Output contract

- Every service builds into **`dist/<platform>/<service>/`** at the repository root (never inside the service folder).
- That folder alone must be runnable: the deployer copies it as-is.
- It must not contain env value files (`.env.*`). Env values are supplied when the build runs, not when it is built.
- `dist/<platform>/<service>/BUILD_INFO` records `platform`, `service`, `environment`, `version`, `built_at`. Write it only after a successful build: it marks the folder as complete, and the deployer refuses a folder without it. A failed build leaves no output.
- Version: the service's `package.json` / `pyproject.toml` `version`, else the `VERSION` env var, else `unknown`.
- `dist/` is git-ignored.

## Behavior

- Reject an invalid environment name and `local-dev`. Build every service when no service is given; an unknown name is an error.
- On platforms with `tools/secrets/`, every service being built needs `.env.<env>`; if one is missing, build nothing and say which file to add.
- Empty `dist/<platform>/<service>/` before each build.
- Stop at the first failing service with a non-zero exit code.
{{#if platform_proto}}
- On platforms that need the shared proto contract (`backend-msa`), run `tools/builder/proto/builder.sh` once before the services.
{{/if}}

## Structure

- Keep the per-service build in one function: `build_one <service>` (`builder.sh`) / `Invoke-BuildOne <service>` (`builder.ps1`). It runs inside `<platform>/<service>/` and writes into `$OUT` / `$Out`.
- It can use the environment, the output folder, and the path of `tools/secrets/<platform>/<service>/.env.<env>` (`$ENV_FILE` / `$EnvFile`). Read that file only for values that must be fixed at build time (e.g. a frontend bundle); never copy it into the output.
{{#if no_secrets}}
- No `tools/secrets/` for {{no_secrets_platforms}} (chosen in yjcli): there is no `$ENV_FILE`, and build-time values come from the project's own mechanism.
{{/if}}

{{#if platform_proto}}
## Proto contract

The shared gRPC/protobuf contract lives at the repository root in `proto/` (schemas `proto/*.proto`); there is no proto folder inside any platform. Languages generated now: {{proto_languages}}.

| Command | Script |
|---|---|
| `make proto-build` / `./make.ps1 proto-build` | `tools/builder/proto/builder.sh` / `builder.ps1` — every language under `proto/dist/` |
| `… PROTO_LANG=<language>` | same script, one language |

- One function per language: `gen_<language>` (`builder.sh`) / `Invoke-Gen<Language>` (`builder.ps1`). Languages are the folders under `proto/dist/`. Skip the run when there is no `.proto` yet, and fail with a pointer here when a language has no function (add one when you add a language later).
- Output goes to `proto/dist/<language>/` — a library package, not a deployable build (`dist/` at the root is unrelated). Each folder has its manifest: Go `go.mod` (module `{{proto_go_module}}`), Dart `pubspec.yaml` (`{{proto_dart_package}}`, code in `lib/`), Python `pyproject.toml` (`{{proto_python_dist}}`, package `{{proto_python_package}}/`). Keep the manifest; regenerate only the code, and remove code of deleted `.proto` files.
- Keep only what a consumer needs: generated code plus the manifest (Go also `go.sum` after `go mod tidy`). No lock files (`pubspec.lock`, `uv.lock`) — consumers own those.
- Consumers use a path dependency on `proto/dist/<language>/` (Go `replace`, Dart `path:`, Python editable path), never a copy of the `.proto` files.
- protoc is the standard (buf is not used). Generated code is committed so consumers and CI build without protoc.

{{/if}}
## Requirements

- Build for where the service will run. If the deploy target is a Linux container, produce something that runs there (e.g. `GOOS=linux` for Go, or dependencies installed for Linux).
- `builder.sh` and `builder.ps1` produce the same output.
- `builder.sh` works on macOS's bash 3.2; `builder.ps1` stays ASCII-only.

## User input

When a script needs anything from the user (a target, a version, a confirmation, a message), it asks for everything up front and acts only at the end:

1. Checks first: run what needs no input (tools, files, `BUILD_INFO`, credentials) right away and stop with a clear message before asking anything.
2. Collect every input: ask all questions in a row and keep the answers in variables. Nothing is changed while asking. Re-ask on an invalid answer instead of exiting.
3. Show the plan: one screen with every answer and what will happen (services, environment, target, irreversible steps).
4. Confirm once: a single `y` (anything else quits without changes).
5. Run: execute every step with the stored values and no further prompts. On failure stop, undo what can be undone, and say what is left.

Arguments and env vars come before prompts: a value given on the command line is not asked again, and when stdin is not a terminal (CI) the script never prompts — it fails listing the missing values instead.

## More than one script

One entry script per platform is a starting point, not a limit: when a platform needs more (per-language build steps, per-service scripts, a shared helper), add files under `tools/builder/<platform>/` or `tools/builder/` and call them from the entry script instead of growing one file indefinitely. Keep the entry script name — `make` calls it.

Everything under `tools/builder/` belongs to this plugin: removing the plugin in yjcli deletes `tools/builder/`, and removing a platform deletes `tools/builder/<platform>/` — files you added there included.
