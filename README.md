# yjcli

CLI that scaffolds YJ platform folders, services, and Cursor/Claude agent wiring.

Templates, skills, and rules ship inside the package and are **copied** into the target repo.

## Install

```bash
uv tool install yjcli
# pin a version:
uv tool install yjcli==0.0.3

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
# edit AGENTS.md, then:
yjcli sync agents
```

## Platforms

Use with `-p` / `--platform` (repeatable):

`backend` · `backend-service` · `frontend` · `mobile-app` · `pc-app` · `cli` · `browser-extension`

## What `init` creates

- `AGENTS.md`, `CLAUDE.md` (mirror of `AGENTS.md`)
- `.cursor/` / `.claude/` skills, rules, and Claude `settings.json`
- Root `Makefile`, `make.bat`, `TOOLS.md`, `.gitignore`
- Selected platform roots (and shared `scripts/` helpers)

## Sync

| Command | When |
|---------|------|
| `yjcli sync agents` | After editing `AGENTS.md` — refreshes `CLAUDE.md` |
| `yjcli sync skills` | Refresh packaged skills only |
| `yjcli sync rules` | Refresh packaged rules only |
| `yjcli sync all` | After upgrading `yjcli` — agents + skills + rules |

Edit `AGENTS.md` only; do not edit `CLAUDE.md` by hand.

## Options

- `--path <dir>` — target repo root (default: current directory). Works on `init`, `add`, `sync`.
- `--force` / `-f` — overwrite existing root/agent files without prompting (`init`, `add`).

## Notes

- `add service` needs the platform root first (`init` or `add platform`).
- Non-interactive use requires flags (`-p` / `-n` / `--all`, etc.); omit them only in a TTY prompt.
- `doctor` checks the **installed package** assets, not your target repo.

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
yjcli sync all
yjcli doctor
```
