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
- Start every service concurrently and prefix each output line with `[<service>]`.
- Ctrl+C stops every service the runner started, including child processes (npm → node, uv → python), and exits.
- A service that exits non-zero stops the others, and the runner exits with its code. A service that exits 0 just leaves the set.

## Structure

- Keep the per-service command in one function: `run_one <service>` (`runner.sh`) / `Invoke-RunOne <service>` (`runner.ps1`). It runs inside `<platform>/<service>/` with the env already exported and starts **one** service in the foreground.
- In `runner.sh` prefer `exec <command>` so signals reach the service. In `runner.ps1` run the command directly so it stays attached until the service exits.
- Commands come from the service's own tooling (`go run .`, `npm run dev`, `uv run …`). The runner does not install dependencies or build for deployment.

## Requirements

- Local runs always use `.env.local-dev` — never `.env.development` / `.env.production`, and never hardcode `HOST` / `PORT`.
- `runner.sh` and `runner.ps1` behave the same.
- `runner.sh` works on macOS's bash 3.2: no `wait -n`, no associative arrays, guard empty arrays with `${arr[@]+"${arr[@]}"}`.
- `runner.ps1` stays ASCII-only so Windows PowerShell 5.1 reads it correctly.

## More than one script

One entry script per platform is a starting point, not a limit: when a platform needs more (per-service launch scripts, a shared helper, a watcher), add files under `tools/runner/<platform>/` or `tools/runner/` and call them from the entry script instead of growing one file indefinitely. Keep the entry script name — `make` calls it.
