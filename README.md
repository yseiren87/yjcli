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

`backend` · `backend-service` · `frontend` · `mobile-app` · `pc-app` · `cli` · `browser-extension` · `scheduler`

## What `init` creates

- `AGENTS.md`, `CLAUDE.md` (mirror of `AGENTS.md`)
- Skills under `.cursor/skills/`, `.claude/skills/`, `.agents/skills/` (Codex)
- Claude `settings.json`
- Root `Makefile`, `make.bat`, `TOOLS.md`, `.gitignore`
- `Diff.md` — user-maintained architecture difference and manual restoration notes
- Selected platform roots with `scripts/run.*` and development/production build/deploy templates

The root `Makefile` / `make.bat` wires platform run, build, and deploy entry points.
Build/deploy templates print the exact file to implement and fail until the project
supplies its build/package and upload logic. They remain platform-level; do not add
per-service `scripts/` directories or per-service Makefiles.

`run.*` ships as `.sh` + `.bat` + `.ps1` since local dev runs natively per platform.
`build-*` and `deploy-*` ship as `.sh` only — build/deploy tooling (Docker, etc.) is
not native to Windows, so `make.bat` runs those targets through WSL; macOS/Linux use
the shell script directly.

`build-common.sh` is the same file for every platform and is a thin plugin host:
it runs every `scripts/plugin-build-*.sh` file present, then falls through to its
own generic build guard. The `build` segment names the consumer (a deploy-side
plugin would be `plugin-deploy-*.sh` instead). Each plugin is its own file —
visible in `scripts/`, and runnable standalone — and self-detects whether it
applies by folder presence, not a platform-name check, so any platform can opt in.

- `plugin-build-proto.sh` → protoc codegen guard when `<platform>/proto/` exists.
  `backend` always has this (fixed gRPC MSA root, see `yj-backend-msa`); any other
  platform (including `backend-service`) gets the same guard only if it creates
  `proto/` too. protoc is the standard; buf is not used.
- `plugin-build-ssr.sh` → template/asset build guard when
  `<platform>/{service}/views/` exists, checked per service. Any platform's
  service can opt in by creating `views/`.
- `plugin-build-docker.sh` → docker image **build only** (no push, no
  swarm/stack rollout — that belongs in a deploy-side plugin) guard, per
  service that has a `Dockerfile` (delete it to opt that service out). Builds
  always use `.env.development` or `.env.production` depending on which
  environment is targeted. The image version comes from the service's
  `package.json`/`pyproject.toml` `version` field when present, otherwise the
  `VERSION` env var — set it for languages with no package-manifest version
  field.

None of these plugins imply each other, and using gRPC in `backend-service` does
not make it MSA — see `yj-backend-msa` / `yj-backend-service` for what each
option chapter actually changes.

- `yjcli service add` adds `Dockerfile` + `.dockerignore` to new services under
  deployable platforms (`backend`, `backend-service`, `frontend`, `scheduler`);
  `cli`/`mobile-app`/`pc-app`/`browser-extension` are local/client artifacts, not
  docker-swarm services, so they don't get one. The Dockerfile is
  language-agnostic and intentionally has no `FROM` yet — `docker build` fails
  until it's replaced, matching every other generated build/deploy stub.

`deploy-common.sh` is the same kind of plugin host for the deploy side: after
calling the matching build script, it runs every `scripts/plugin-deploy-*.sh`
file present (none ship by default — pushing an image, `docker stack deploy`,
`kubectl apply`, etc. are deploy-side plugins the project adds). `deploy-development.sh`
/ `deploy-production.sh` call `deploy-common.sh` and then own their own
upload/rollout guidance only.

`Diff.md` is created only when missing, including with `init --force`. yjcli never
reads, updates, overwrites, or uses it for automatic restoration during sync or
migration.

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
make <platform>-build-development  [NAME=<service>]
make <platform>-build-production   [NAME=<service>]
make <platform>-deploy-development [NAME=<service>]
make <platform>-deploy-production  [NAME=<service>]
make help
```

## Sync

| Command | When |
|---------|------|
| `yjcli sync agents` | After editing `AGENTS.md` — refreshes `CLAUDE.md` |
| `yjcli sync skills` | Refresh packaged skills (Cursor / Claude / Codex) |
| `yjcli sync make` | Overwrite root make/run files; install missing build/deploy scripts while preserving implemented ones |
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

- `platform add` creates platform roots and their run/deploy scripts (no services, skills, or root Makefile).
- `service add` needs the platform root first (`init` or `platform add`).
- Non-interactive: pass `-t` / `--all` / `-p` / `-n` as needed, and pass
  `--yes` for every `sync` command.
- `doctor` checks the **installed package** assets, not your target repo.
- `sync skills` / `sync all` remove legacy `.cursor/rules` and `.claude/rules` if present.
- `sync migrate` also overwrites `AGENTS.md` from the package (destructive).

## Commands

```bash
yjcli init
yjcli init --all
yjcli init -t backend -t frontend
yjcli init --force

yjcli platform add
yjcli platform add --all
yjcli platform add -t cli
yjcli platform add -t scheduler

yjcli service add
yjcli service add -p backend -n api
yjcli service add -p scheduler -n operations

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
