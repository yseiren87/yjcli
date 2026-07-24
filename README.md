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
yjcli add service -p backend -n api
# edit AGENTS.md, then:
yjcli sync agents

make backend                 # start all backend services
make backend NAME=api        # start one service
```

## Platforms

Use with `-p` / `--platform` (repeatable):

`backend` · `backend-service` · `frontend` · `mobile-app` · `pc-app` · `cli` · `browser-extension`

## What `init` creates

- `AGENTS.md`, `CLAUDE.md` (mirror of `AGENTS.md`)
- `.cursor/` / `.claude/` skills, rules, and Claude `settings.json`
- Root `Makefile`, `make.bat`, `TOOLS.md`, `.gitignore`
- Selected platform roots (`*/scripts/run.sh` / `run.bat`)

## Run (`make`)

Platform targets are discovered from `*/scripts/run.sh` (after `add platform`). No Makefile edits when adding services.

```bash
make <platform>                 # all services under that platform (concurrent)
make <platform> NAME=<service>  # one service
make help

# Windows:
make.bat <platform>
make.bat <platform> NAME=<service>
```

Examples: `make backend`, `make backend NAME=api`.

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

- `--path <dir>` — target repo root (default: current directory). Works on `init`, `add`, `sync`.
- `--force` / `-f` — overwrite existing root/agent files without prompting (`init`, `add`).

## Notes

- `add service` needs the platform root first (`init` or `add platform`).
- Non-interactive use requires flags (`-p` / `-n` / `--all`, etc.); omit them only in a TTY prompt.
- `doctor` checks the **installed package** assets, not your target repo.
- Services are discovered by directory; `add service` does not edit `run.sh` / `Makefile`.

## Commands

```bash
yjcli init
yjcli init --all
yjcli init -p backend -p frontend
yjcli init --force

yjcli add platform
yjcli add platform --all
yjcli add platform -p cli

yjcli add service
yjcli add service -p backend -n api

yjcli sync agents
yjcli sync skills
yjcli sync rules
yjcli sync make
yjcli sync all
yjcli doctor
```
