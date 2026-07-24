# yjcli

CLI that scaffolds YJ platform folders, services, and Cursor/Claude agent wiring.

Templates, skills, rules, and root make files ship inside the package and are **copied** into the target repo.

## Install

```bash
uv tool install yjcli
# pin a version:
uv tool install yjcli==0.0.5

yjcli --version
yjcli -h
```

Upgrade / remove:

```bash
uv tool upgrade yjcli
uv tool uninstall yjcli
```

## Quick start

```bash
uv tool install yjcli
cd /path/to/your-repo
yjcli init --all
yjcli service add -p backend -n api
# edit AGENTS.md, then:
yjcli sync agents

make backend                 # start all backend services
make backend NAME=api        # start one service
```

## Platforms

Use with `-t` / `--type` (repeatable on `init` / `platform add`):

`backend` · `backend-service` · `frontend` · `mobile-app` · `pc-app` · `cli` · `browser-extension`

## What `init` creates

- `AGENTS.md`, `CLAUDE.md` (mirror of `AGENTS.md`)
- `.cursor/` / `.claude/` skills, rules, and Claude `settings.json`
- Root `Makefile`, `make.bat`, `TOOLS.md`, `.gitignore`
- Selected platform roots (`*/scripts/run.sh` / `run.bat`)

## Run (`make`)

Platform targets are discovered from `*/scripts/run.sh` (after `init` / `platform add`).

```bash
make <platform>                 # all services under that platform (concurrent)
make <platform> NAME=<service>  # one service
make help
```

## Sync

| Command | When |
|---------|------|
| `yjcli sync agents` | After editing `AGENTS.md` — refreshes `CLAUDE.md` |
| `yjcli sync skills` | Refresh packaged skills only |
| `yjcli sync rules` | Refresh packaged rules only |
| `yjcli sync make` | Overwrite root `Makefile` / `make.bat` and each installed platform’s `scripts/run.sh` · `run.bat` |
| `yjcli sync all` | After upgrading `yjcli` — agents + skills + rules + make (+ platform run scripts) |

Edit `AGENTS.md` only; do not edit `CLAUDE.md` by hand.

## Options

- `--type` / `-t` — platform type (`backend`, `frontend`, …) on `init` / `platform add`.
- `--platform` / `-p` — existing platform root on `service add`.
- `--name` / `-n` — service/app name on `service add`.
- `--path <dir>` — target repo root (default: current directory).
- `--force` / `-f` — overwrite existing root/agent files without prompting (`init` only).

## Notes

- `platform add` only creates platform roots (no services, no skills/rules/Makefile — use `service add` / `sync`).
- `service add` needs the platform root first (`init` or `platform add`).
- Non-interactive: pass `-t` / `--all` / `-p` / `-n` as needed.
- `doctor` checks the **installed package** assets, not your target repo.

## Commands

```bash
yjcli init
yjcli init --all
yjcli init -t backend -t frontend
yjcli init --force

yjcli platform add
yjcli platform add --all
yjcli platform add -t cli

yjcli service add
yjcli service add -p backend -n api

yjcli sync agents
yjcli sync skills
yjcli sync rules
yjcli sync make
yjcli sync all
yjcli doctor
```
