# yjcli

CLI that scaffolds YJ platform folders, services, and AI agent wiring
(Cursor, Claude Code, Codex).

Templates, skills, and root make files ship inside the package and are **copied**
into the target repo. Standing agent guidance lives in **`AGENTS.md`** only
(`CLAUDE.md` is a mirror).

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
- Skills under `.cursor/skills/`, `.claude/skills/`, `.agents/skills/` (Codex)
- Claude `settings.json`
- Root `Makefile`, `make.bat`, `TOOLS.md`, `.gitignore`
- Selected platform roots (`*/scripts/run.sh` / `run.bat`)

The root `Makefile` / `make.bat` is the repository-owned extension point for
project automation. Projects may add commands such as `<platform>-build` or
`<platform>-deploy` and reuse optional `NAME=<service>` selection. Defining and
implementing init/install/build/deploy behavior is the project's responsibility;
yjcli does not generate action scripts. Do not add per-service `scripts/`
directories or per-service Makefiles.

Operating rules (skill routing, output discipline) are in `AGENTS.md` — not in
`.cursor/rules` / `.claude/rules`.

## Run (`make`)

Platform targets are discovered from `*/scripts/run.sh` (after `init` / `platform add`).
Each service declares its local command as `RUN_COMMAND` in `.env.local-dev`.
New services include `.env.local-dev`, `.env.development`, `.env.production`, and
`.env.examples`. Only `.env.local-dev` and `.env.examples` are required;
development/production may be removed and other `.env.<environment>` files may
be added. Commit `.env.examples` only.
The platform runner executes that repository-owned declaration instead of
inferring npm, uv, Go, or another language/runtime from project manifests.

```bash
make <platform>                 # all services under that platform (concurrent)
make <platform> NAME=<service>  # one service
make help
```

## Sync

| Command | When |
|---------|------|
| `yjcli sync agents` | After editing `AGENTS.md` — refreshes `CLAUDE.md` |
| `yjcli sync skills` | Refresh packaged skills (Cursor / Claude / Codex) |
| `yjcli sync make` | Overwrite root `Makefile` / `make.bat` and each installed platform’s `scripts/run.sh` · `run.bat` |
| `yjcli sync all` | Soft upgrade — mirror CLAUDE + skills + make (**keeps** your `AGENTS.md`) |
| `yjcli sync migrate -y` | **Hard** upgrade — package template overwrites `AGENTS.md`, wipes skills dirs, drops legacy rules/`.agent`, refreshes settings/TOOLS/gitignore/make |

Edit `AGENTS.md` only; do not edit `CLAUDE.md` by hand. Use `migrate` when upgrading from older yjcli layouts (rules era).

## Options

- `--type` / `-t` — platform type (`backend`, `frontend`, …) on `init` / `platform add`.
- `--platform` / `-p` — existing platform root on `service add`.
- `--name` / `-n` — service/app name on `service add`.
- `--path <dir>` — target repo root (default: current directory).
- `--force` / `-f` — overwrite existing root/agent files without prompting (`init` only).

## Notes

- `platform add` only creates platform roots (no services, no skills/Makefile — use `service add` / `sync`).
- `service add` needs the platform root first (`init` or `platform add`).
- Non-interactive: pass `-t` / `--all` / `-p` / `-n` as needed.
- `doctor` checks the **installed package** assets, not your target repo.
- `sync skills` / `sync all` remove legacy `.cursor/rules` and `.claude/rules` if present.
- `sync migrate` also overwrites `AGENTS.md` from the package (destructive); requires `--yes` when non-interactive.

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
yjcli sync make
yjcli sync all
yjcli sync migrate --yes
yjcli doctor
```

<!-- BENCH:START -->

## Research: token & exploration

Not measured yet.

From the workspace root (sibling of this package), with `CURSOR_API_KEY` in `tools/.env`:

```bash
make bench                 # Cursor SDK: prepare → trials → report → this section
```

See `bench/README.md`.

<!-- BENCH:END -->
