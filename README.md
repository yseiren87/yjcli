# yjcli

Wizard that scaffolds YJ-architecture repositories: platform code folders,
services, tooling plugins, and AI agent wiring (Cursor, Claude Code, Codex).

Run `yjcli` with no arguments and it walks you through a checklist. Nothing is
written until you confirm the plan at the end. Every step can also be answered
with a command-line argument, which skips that step.

## Install

```bash
uv tool install yjcli
yjcli --version
uv tool upgrade yjcli
```

## Quick start

```bash
cd /path/to/your-repo
yjcli                                   # interactive wizard
```

```text
  ✔ 1. LLM 대상     Cursor, Claude Code
  ✔ 2. 플랫폼       backend, frontend
  ✔ 3. 플러그인     runner, secrets
  ▸ 4. 서비스 이름  (1/2) backend
  ○ 5. 확인 및 실행

? backend 서비스 이름 (공백 또는 , 로 구분): a1, a2
  → backend/a1, backend/a2
```

The same thing without prompts:

```bash
yjcli -l cursor,claude -n backend=a1,a2 -n frontend=f1 --plugin runner,secrets -y
```

## Steps

| # | Step | Argument | Notes |
|---|------|----------|-------|
| 1 | LLM targets | `-l/--llm cursor,claude,codex` · `all` | Multi-select (space toggles `[x]`) |
| 2 | Platforms | `-p/--platform …` · `all` | Multi-select |
| 3 | Plugins | `--plugin runner,secrets,builder` · `all` · `none` | Required plugins are added automatically |
| 4 | Service names | `-n/--name <platform>=a1,a2` (repeatable) | One screen per platform; split names with spaces or commas. `-n` alone also selects the platform |
| — | Platform options | `-o/--option backend=proto` | Asked right after the names of a new platform |
| 5 | Confirm | `-y/--yes` · `--dry-run` | Non-interactive runs need `--yes` or `--dry-run` |

`←` goes back one screen. Skills are not asked for — they follow the platforms.

## Platforms

Platforms hold **code only**: service folders, stack files and `.env.examples`.

| Platform | What | Skill |
|----------|------|-------|
| `backend` | single backend (API); optional `proto` | `yj-backend` |
| `backend-msa` | gRPC microservices; `proto/` always | `yj-backend-msa` |
| `backend-ssr` | server-rendered backend; `views/` always; optional `proto` | `yj-backend-ssr` |
| `frontend` | Vite + React + TS | `yj-frontend` |
| `mobile-app` | Flutter | `yj-mobile-app` |
| `pc-app` | Electron | `yj-pc-app` |
| `cli` | CLI apps | `yj-cli` |
| `browser-extension` | MV3; `native_*` services are native hosts | `yj-browser-extension` + `yj-backend` |
| `scheduler` | periodic batch jobs | `yj-scheduler` |

## Plugins (repository tooling under `tools/`)

| Plugin | Installs | Requires |
|--------|----------|----------|
| `runner` | `tools/runner/run.{sh,bat,ps1}`, root `Makefile` / `make.bat` → `make <platform> [NAME=<service>]` | `secrets` |
| `secrets` | `tools/secrets/<platform>/<service>/.env.{local-dev,development,production}` — **committed in plain text** (private repos only) | — |
| `builder` | `tools/builder/` (build/deploy hosts, `steps/{proto,ssr,docker}.sh`, per-platform stubs), `Dockerfile` for deployable services → `make <platform>-build-<env>` / `-deploy-<env>` | `secrets` |

Each service declares its local command as `RUN_COMMAND` in
`tools/secrets/<platform>/<service>/.env.local-dev`; the runner exports that file
and runs it. Generated build/deploy stubs fail with an implementation prompt
until you replace them.

## Updating

Run `yjcli` again in a configured repo (it finds `.yjcli/manifest.toml`). The
stored selection is the default; change what you need and confirm.

```bash
yjcli -y                              # refresh managed files to the installed version
yjcli --plugin runner,secrets,builder -y   # add the builder plugin
yjcli service add -n backend=a3       # add services
yjcli plan                            # show the plan only
yjcli status                          # selection + managed files you edited
```

| File kind | On update |
|-----------|-----------|
| managed (`tools/runner/*`, `Makefile`, skills, `CLAUDE.md`, builder hosts/steps) | refreshed; skipped with a warning if you edited it (`--force` overwrites) |
| seed (`AGENTS.md`, env files, build/deploy stubs, `Dockerfile`, settings) | created once when its owner is new; yours afterwards |
| blocks (`AGENTS.md` `<!-- yjcli:… -->`, `.gitignore` `# >>> yjcli:managed`) | only the block is regenerated |

yjcli never deletes services or files you own. Removing a plugin or LLM deletes
only its managed files; your own skills in the skills folders are left alone.

## Development

```bash
uv sync
uv run python -m unittest discover -s tests   # unit tests
scripts/e2e.sh                                 # end-to-end scenarios into ./sandbox
scripts/e2e.sh -k wizard -v                    # one case, with output on failure
```

Design notes: [`docs/redesign.md`](docs/redesign.md).
