# Runner guide

> Managed by yjcli — regenerated on every run. Do not edit; put project notes in `AGENTS.md`. The scripts under `tools/runner/<platform>/` are yours.

The runner starts services locally for development.

## Entry points

| Command | Script |
|---|---|
| `make <platform>` / `./make.ps1 <platform>` | `tools/runner/<platform>/runner.sh` / `runner.ps1` |
| `make <platform> NAME=<service>` | same script, with `<service>` as the first argument |

Current services:

{{service_list}}

## What is already implemented

Each `runner.sh` / `runner.ps1` ships a working skeleton:

- Service list: the folders under `<platform>/`, or the one named service.
- Env: exports `tools/secrets/<platform>/<service>/.env.local-dev` (plain `KEY=VALUE` lines, values taken literally). A service without that file is skipped with a warning.
- Starts every service concurrently, prefixing each output line with `[<service>]`.
- **Ctrl+C** stops every service it started (whole process tree) and exits.
- A service that exits non-zero stops the others; the runner exits with its code. A service that exits 0 just leaves the set.

## What you implement

One function per script, starting **one** service in the foreground:

- `runner.sh`: `run_one <service>` — prefer `exec <command>` so signals reach it.
- `runner.ps1`: `Invoke-RunOne <service>` — run the command directly (it must stay attached until the service exits).

It runs inside `<platform>/<service>/` with the env already exported. Until it is implemented it prints a pointer to this guide and fails.

## Requirements

- Local runs always use `.env.local-dev` — never `.env.development` / `.env.production`, and never hardcode `HOST` / `PORT`.
- `runner.sh` and `runner.ps1` behave the same.
- `runner.sh` must work on macOS's bash 3.2 (no `wait -n`, no associative arrays, guard empty arrays with `${arr[@]+"${arr[@]}"}`).
- Commands come from the service's own tooling (`go run .`, `npm run dev`, `uv run …`); the runner does not install dependencies or build for deployment.

## More than one script

yjcli ships one entry script per platform. That is a starting point, not a limit: when a platform needs more (per-service launch scripts, a shared helper, a watcher), add files under `tools/runner/<platform>/` or `tools/runner/` and call them from the entry script instead of growing one file indefinitely. Keep the entry script name — `make` calls it.
