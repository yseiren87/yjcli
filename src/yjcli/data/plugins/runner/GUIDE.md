# Runner guide

> Managed by yjcli — regenerated on every run. Do not edit; put project notes in `AGENTS.md`. The scripts under `tools/runner/` are repository-owned: keep them in line with this guide.

The runner starts services locally for development.

## Entry points

| Command | Script |
|---|---|
| `make <platform>` / `./make.ps1 <platform>` | `tools/runner/<platform>/runner.sh` / `runner.ps1` |
| `make <platform> NAME=<service>` | same script, with `<service>` as the first argument |

Current services:

{{service_list}}

## Behavior

- Services: every folder under `<platform>/`, or only the service given as the argument (an unknown name is an error).
- Env: before a service starts, export `tools/secrets/<platform>/<service>/.env.local-dev` (plain `KEY=VALUE` lines, values taken literally). Skip a service without that file, with a warning.
{{#if no_secrets}}
- No `tools/secrets/` for {{no_secrets_platforms}} (chosen in yjcli): the runner exports nothing and services read env values from the project's own mechanism.
{{/if}}
- Start every service concurrently and prefix each output line with `[<service>]`.
- Ctrl+C stops every service the runner started, including child processes (npm → node, uv → python), and exits.
- A service that exits non-zero stops the others, and the runner exits with its code. A service that exits 0 just leaves the set.

## Structure

- Keep the per-service command in one function: `run_one <service>` (`runner.sh`) / `Invoke-RunOne <service>` (`runner.ps1`). It runs inside `<platform>/<service>/` with the env already exported and starts **one** service in the foreground.
- In `runner.sh` prefer `exec <command>` so signals reach the service. In `runner.ps1` run the command directly so it stays attached until the service exits.
- Commands come from the service's own tooling (`go run .`, `npm run dev`, `uv run …`). The runner does not install dependencies or build for deployment.

## Requirements

- Local runs with `tools/secrets/` always use `.env.local-dev` — never `.env.development` / `.env.production`, and never hardcode `HOST` / `PORT`.
- `runner.sh` and `runner.ps1` behave the same.
- `runner.sh` works on macOS's bash 3.2: no `wait -n`, no associative arrays, guard empty arrays with `${arr[@]+"${arr[@]}"}`.
- `runner.ps1` stays ASCII-only so Windows PowerShell 5.1 reads it correctly.

## User input

When a script needs anything from the user (a target, a version, a confirmation, a message), it asks for everything up front and acts only at the end:

1. Checks first: run what needs no input (tools, files, `BUILD_INFO`, credentials) right away and stop with a clear message before asking anything.
2. Collect every input: ask all questions in a row and keep the answers in variables. Nothing is changed while asking. Re-ask on an invalid answer instead of exiting.
3. Show the plan: one screen with every answer and what will happen (services, environment, target, irreversible steps).
4. Confirm once: a single `y` (anything else quits without changes).
5. Run: execute every step with the stored values and no further prompts. On failure stop, undo what can be undone, and say what is left.

Arguments and env vars come before prompts: a value given on the command line is not asked again, and when stdin is not a terminal (CI) the script never prompts — it fails listing the missing values instead.

## More than one script

One entry script per platform is a starting point, not a limit: when a platform needs more (per-service launch scripts, a shared helper, a watcher), add files under `tools/runner/<platform>/` or `tools/runner/` and call them from the entry script instead of growing one file indefinitely. Keep the entry script name — `make` calls it.

Everything under `tools/runner/` belongs to this plugin: removing the plugin in yjcli deletes `tools/runner/`, and removing a platform deletes `tools/runner/<platform>/` — files you added there included.
