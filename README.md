# yjcli

Wizard that scaffolds YJ-architecture repositories: platform code folders, services, tooling plugins, and AI agent wiring (Cursor, Claude Code, Codex).

Run `yjcli start` and it walks you through a checklist (`yjcli` alone prints help). Nothing is written until you confirm the plan at the end. Every step can also be answered with a command-line argument, which skips that step.

## Install

```bash
uv tool install yjcli
yjcli --version
uv tool upgrade yjcli
```

## Quick start

```bash
cd /path/to/your-repo
yjcli start                             # interactive wizard
```

```text
  ✔ 1. LLM 대상     Cursor, Claude Code
  ✔ 2. 플랫폼       backend, frontend
  ✔ 3. 플러그인     runner, builder
  ▸ 4. 서비스 이름  (1/2) backend
  ○ 5. 확인 및 실행

? backend 서비스 이름 (공백 또는 , 로 구분): a1, a2
  → backend/a1, backend/a2
```

The same thing without prompts:

```bash
yjcli start -l cursor,claude -n backend=a1,a2 -n frontend=f1 --plugin runner,builder -y
```

## Steps

| # | Step | Argument | Notes |
|---|------|----------|-------|
| 1 | LLM targets | `-l/--llm cursor,claude,codex` · `all` | Multi-select (space toggles `[x]`) |
| 2 | Platforms | `-p/--platform …` · `all` | Multi-select |
| 3 | Plugins | `--plugin runner,builder,deployer` · `all` · `none` | `deployer` can be checked only after `builder`; on the CLI it fails without `builder` |
| 4 | Service names | `-n/--name <platform>=a1,a2` (repeatable) | One screen per platform; split names with spaces or commas. `-n` alone also selects the platform |
| — | Platform options | `-o/--option backend=proto` | Asked right after the names of a new platform |
| 5 | Confirm | `-y/--yes` · `--dry-run` | Non-interactive runs need `--yes` or `--dry-run` |

`←` goes back one screen. Skills are not asked for — they follow the platforms.

## Platforms

Platforms hold **code only**: service folders, stack files and `.env.examples`. Every service also gets its env values in `tools/secrets/<platform>/<service>/.env.{local-dev,development,production}` — **committed in plain text** (private repos only). This is not a plugin; it is always created.

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

yjcli builds the structure, not your build logic. Each plugin installs a **`tools/<plugin>/GUIDE.md`** (managed — the requirements) and, per platform, an entry script pair **`tools/<plugin>/<platform>/<plugin>.sh` / `.ps1`** (yours). The scripts already handle arguments, service lists and the shared mechanics; you implement one function in each, following the guide. One entry script is the starting point, not a limit — add helper scripts next to it as the platform needs.

| Plugin | Command | You implement | Already done by the skeleton |
|--------|---------|---------------|------------------------------|
| `runner` | `make <platform> [NAME=<service>]` | `run_one` — start one service | loads `.env.local-dev`, runs all services concurrently with `[service]` prefixes, Ctrl+C / failure stops all |
| `builder` | `make <platform>-build-<env> [NAME=…]` | `build_one` — build into `dist/<platform>/<service>/` (+ `build_proto` where `proto/` can exist) | empties the output folder, writes `BUILD_INFO`, removes failed output |
| `deployer` (needs `builder`) | `make <platform>-deploy-<env> [NAME=…]` | `deploy_one` — ship `dist/<platform>/<service>/` | checks the build and env file exist, warns on environment mismatch; never builds |

`<env>` is `development` or `production`. On Windows use `make.ps1` with the same targets: `powershell -ExecutionPolicy Bypass -File make.ps1 <target> [NAME=<service>]`. Builds contain no env files; Docker deployments inject them at run time with `docker run --env-file tools/secrets/<platform>/<service>/.env.<env>`.

## Updating

### Pick up a new yjcli release

When skills, AGENTS.md rules or guides change in yjcli:

```bash
uv tool upgrade yjcli
yjcli status            # tells you a newer yjcli is installed
yjcli update --diff     # review what changes, then confirm (or -y)
```

`yjcli update` keeps your selection and only re-renders what yjcli owns. A yjcli that is **older** than the one that last wrote `.yjcli/manifest.toml` refuses to run (so teammates on old versions cannot roll files back); `--force` overrides.

### Change the selection

Change only what you name; every other step keeps the value in `.yjcli/manifest.toml`.

```bash
yjcli plugin add builder deployer          # add plugins (requirements must be named too)
yjcli plugin remove runner                 # remove a plugin
yjcli llm add codex                        # add / remove LLM targets
yjcli llm remove cursor
yjcli service add -n backend=a3            # add services (names that already exist are kept as is)
yjcli start                                # wizard, stored selection as defaults
yjcli start --plugin runner,builder -y     # replace the whole plugin list (other steps unchanged)
yjcli plan --diff                          # show the plan only
```

`-n <platform>=<names>` is declarative: an existing service in the list is left alone with a note, only new names are created.

### What yjcli owns vs. what you own

| File kind | On update |
|-----------|-----------|
| managed (skills, `CLAUDE.md`, `tools/*/GUIDE.md`, `Makefile`, `make.ps1`) | refreshed; skipped with a warning if you edited it (`--force` overwrites) |
| blocks (`AGENTS.md` `<!-- yjcli:rules/skills/layout -->`, `.gitignore` `# >>> yjcli:managed`) | only the block is regenerated; everything outside is yours |
| seed (`AGENTS.md` body, env files, `tools/*/<platform>/*.{sh,ps1}`, settings) | created once (when its owner is new, or when a newer yjcli adds it); yours afterwards — deleting one opts out |

Customize a skill without losing updates: write the extra rules in `.yjcli/skills/<skill>.md` (e.g. `.yjcli/skills/yj-backend.md`). yjcli appends them to that skill for every LLM on each render. Put project-wide agent rules under `### Project rules` in AGENTS.md (outside the blocks).

yjcli never deletes services or files you own. Removing a plugin or LLM (or deleting a service folder) deletes the files yjcli made for it that you never changed. Files you changed are kept and listed as **left-over files** in the summary and in `yjcli status`; `--purge` (on `update`, `start`, `plugin remove`, `llm remove`, or the wizard's confirm step) deletes them too. Env value files under `tools/secrets/` are never purged.

yjcli also reports **stale references**: lines outside the yjcli blocks of `AGENTS.md`, in `CLAUDE.md` or in `.yjcli/skills/*.md` that point at a plugin, LLM, platform or service that is not set up (e.g. `tools/runner/` after `yjcli plugin remove runner`), with file and line number. It never edits them; fix them by hand.

## Rebuilding a repo made with an older yjcli (0.3.x / 0.2.x)

yjcli 0.4 does not work on repos set up by an earlier version: it stops with a message instead of updating them. Remove what the old yjcli generated and set the repo up again; service source code stays where it is. Work on a new branch.

1. **Save what you will move back:** copy `AGENTS.md` aside (your project notes), and any run/build/deploy logic or Dockerfiles you wrote — 0.3.x: `RUN_COMMAND` lines in `tools/secrets/**/.env.local-dev`, `tools/builder/<platform>/{build,deploy}-*.sh`, service `Dockerfile`s; 0.2.x: `<platform>/scripts/`, service `Dockerfile`s.
2. **0.2.x only — rename platforms and move env values:**
   - Back up the untracked env files first: `find . -name node_modules -prune -o -type f -name '.env.*' ! -name '.env.examples' -print0 | tar --null -czf ~/env-backup.tgz -T -`
   - `git mv backend backend-msa`, then move each `backend-service/<svc>` to `backend-ssr/<svc>` if it has `views/`, otherwise to `backend/<svc>`.
   - Move every `<platform>/<service>/.env.*` except `.env.examples` to `tools/secrets/<platform>/<service>/`.
3. **Delete the old yjcli output:** `.yjcli/`, `AGENTS.md`, `CLAUDE.md`, `Makefile`, `make.bat`, the `yj-*` folders in `.cursor/skills`, `.claude/skills`, `.agents/skills` (keep your own skills), service `Dockerfile` / `.dockerignore`, `.gitignore` if you never edited it, and — 0.3.x — `tools/runner/`, `tools/builder/`; 0.2.x — `*/scripts/`, `TOOLS.md`, `Diff.md`. **Keep `tools/secrets/`**: yjcli never overwrites existing value files (remove the `RUN_COMMAND` lines from them).
4. **Set up again** with the platforms that exist (services are picked up from their folders): `yjcli start -l claude -p backend-msa,backend,frontend --plugin runner,builder,deployer --dry-run`, then the same with `-y`.
5. **Move your content back:** project notes go outside the `<!-- yjcli:… -->` blocks of the new `AGENTS.md`; the run command goes into `run_one` (`tools/runner/<platform>/runner.sh` / `.ps1`); build logic into `build_one` (output to `dist/<platform>/<service>/`); deploy logic into `deploy_one`, with Dockerfiles under `tools/deployer/<platform>/` and env values passed at run time (`--env-file`) — see each `tools/<tool>/GUIDE.md`. Frontend apps' `vite.config.ts` should load env from `tools/secrets/frontend/<app>/` (`envDir`).
6. **Fix old paths** in code, CI and symlinks (0.2.x: `backend/proto` → `backend-msa/proto`, `backend-service/…`, `<platform>/scripts/…`).
7. **Check:** `yjcli update --dry-run` reports no changes, `make <platform> NAME=<service>` runs once `run_one` is implemented, and `tools/secrets/` is tracked by git (private repos only) before you commit.

## Development

```bash
uv sync
uv run python -m unittest discover -s tests   # unit tests
scripts/e2e.sh                                 # end-to-end scenarios into ./sandbox
scripts/e2e.sh -k wizard -v                    # one case, with output on failure
scripts/e2e.sh -k fullspec                     # sandbox/24-fullspec: every LLM, platform and plugin
brew install powershell                        # optional: enables the make.ps1 / .ps1 case
```

## Releasing (maintainers)

```bash
./release.sh                  # bump → tests → build + PyPI dry-run → commit/tag/push → publish
./release.sh --publish-only   # publish an already pushed release/X.Y.Z tag
```

Every step waits for `y` or `exit` (case-insensitive). Uncommitted changes do not block: they are listed in step 1 and committed together with the version bump in step 5, where you type the commit message. The bump step asks for `major`, `minor` or `fix` (no default) and bumps the `pyproject.toml` version, which always equals the last release (only `release.sh` changes it). Tags follow `release/X.Y.Z`. Tokens go in `.env.release` (git-ignored):

```bash
UV_PUBLISH_TOKEN=pypi-...       # required
GITHUB_TOKEN=github_pat_...     # optional, used only for git push
```
