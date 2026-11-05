# yjcli

Wizard that scaffolds YJ-architecture repositories: platform code folders, services, tooling plugins, and AI agent wiring (Cursor, Claude Code, Codex).

Run `yjcli wizard` and it walks you through a checklist (`yjcli` or `yjcli help` prints help, `yjcli help <command>` the help of one command). On a configured repository the wizard starts from the stored configuration: checking adds, unchecking removes. Nothing is written until you confirm the plan at the end, and applying is all or nothing: if writing fails partway, everything already changed is restored. Every step can also be answered with a command-line argument, which skips that step.

## Install

```bash
uv tool install yjcli
yjcli --version
uv tool upgrade yjcli
```

## Quick start

```bash
cd /path/to/your-repo
yjcli wizard                            # interactive wizard
```

```text
  ✔ 1. LLM 대상     Cursor, Claude Code
  ✔ 2. 플랫폼       backend, frontend
  ✔ 3. 플러그인     runner, builder
  ▸ 4. 플랫폼 설정  (1/2) backend
  ○ 5. 확인 및 실행

? backend 새 서비스 이름 (공백 또는 , 로 구분, 없으면 enter): a1, a2
  → backend/a1, backend/a2
```

The same thing without prompts:

```bash
yjcli wizard -l cursor,claude -n backend=a1,a2 -n frontend=f1 --plugin runner,builder -y
```

## Steps

| # | Step | Argument | Notes |
|---|------|----------|-------|
| 1 | LLM targets | `-l/--llm cursor,claude,codex` · `all` | Multi-select (space toggles `[x]`) |
| 2 | Platforms | `-p/--platform …` · `all` | Multi-select. On a configured repository, unchecking a platform removes it with its code (see Removing) |
| 3 | Plugins | `--plugin runner,builder,deployer` · `all` · `none` | `deployer` can be checked only after `builder`; on the CLI it fails without `builder` |
| 4 | Platform settings | `-n/--name <platform>=a1,a2` (repeatable) · `--secrets all\|none\|<platforms>` | One screen per platform: existing services as a checklist (uncheck = remove), new service names (split with spaces or commas; `-n` alone also selects the platform), then options — `secrets` creates `tools/secrets/<platform>/<service>/.env.*` (on by default) |
| — | Proto languages | `--proto-lang go,dart,python` | The `proto` platform's screen in step 4 asks for languages instead of names; `--proto-lang` also selects `proto` |
| 5 | Confirm | `-y/--yes` · `--dry-run` | Removals are listed at the top and the default choice is 취소. Non-interactive runs need `--yes` or `--dry-run` |

`←` goes back one screen. Skills are not asked for — they follow the platforms.

## Platforms

Platforms hold **code only**: service folders, stack files and `.env.examples`. By default every service also gets its env values in `tools/secrets/<platform>/<service>/.env.{local-dev,development,production}` — **committed in plain text** (private repos only). This is a per-platform option (step 4, `--secrets`), not a plugin. A platform with it off gets no `tools/secrets/` folder, and its runner/builder/deployer scripts are generated without env file handling: the project supplies env values its own way.

`--secrets` replaces the whole choice like `--plugin` (`--secrets frontend` turns it off for every other platform); without it the stored choice is kept and a new platform starts with it on. Turning it on creates the env files of every existing service of that platform. Turning it off deletes `tools/secrets/<platform>/`, values you filled in included (after confirmation). Scripts you already implemented are not rewritten — the result lists them under **to check**.

| Platform | What | Skill |
|----------|------|-------|
| `backend` | single backend (API) | `yj-backend` |
| `backend-msa` | gRPC microservices; selects `proto` automatically | `yj-backend-msa` |
| `backend-ssr` | server-rendered backend; `views/` always | `yj-backend-ssr` |
| `frontend` | Vite + React + TS | `yj-frontend` |
| `mobile-app` | Flutter | `yj-mobile-app` |
| `pc-app` | Electron | `yj-pc-app` |
| `cli` | CLI apps | `yj-cli` |
| `browser-extension` | MV3; `native_*` services are native hosts | `yj-browser-extension` + `yj-backend` |
| `scheduler` | periodic batch jobs | `yj-scheduler` |
| `proto` | shared gRPC/protobuf contract (no services; you pick languages) | `yj-proto` |

The `proto` platform is the repository's only proto location: schemas in `proto/*.proto` at the root, generated libraries in `proto/dist/<language>/` for the languages you pick (`go`, `dart`, `python`). Each language folder starts with its library manifest — Go `go.mod`, Dart `pubspec.yaml`, Python `pyproject.toml` — named after the repository folder (e.g. `my-shop/proto`, `my_shop_proto`, `my-shop-proto`). Other platforms consume it through a path dependency, never a copy. Generated code is committed (`!proto/dist/` in the managed `.gitignore` block). Add or remove a language later with `yjcli proto add <language>` / `yjcli proto remove <language>`.

## Plugins (repository tooling under `tools/`)

yjcli builds the structure, not your build logic. Each plugin installs a **`tools/<plugin>/GUIDE.md`** (managed — the requirements) and, per platform, an entry script pair **`tools/<plugin>/<platform>/<plugin>.sh` / `.ps1`** (yours). The scripts already handle arguments, service lists and the shared mechanics; you implement one function in each, following the guide. One entry script is the starting point, not a limit — add helper scripts next to it as the platform needs.

| Plugin | Command | You implement | Already done by the skeleton |
|--------|---------|---------------|------------------------------|
| `runner` | `make <platform> [NAME=<service>]` | `run_one` — start one service | loads `.env.local-dev`, runs all services concurrently with `[service]` prefixes, Ctrl+C / failure stops all |
| `builder` | `make <platform>-build-<env> [NAME=…]`, `make proto-build [PROTO_LANG=…]` | `build_one` — build into `dist/<platform>/<service>/`; for `proto`, `gen_<language>` in `tools/builder/proto/builder.sh` | empties the output folder, writes `BUILD_INFO`, removes failed output; `backend-msa` builds run proto codegen first |
| `deployer` (needs `builder`) | `make <platform>-deploy-<env> [NAME=…]` | `deploy_one` — ship `dist/<platform>/<service>/` | checks the build and env file exist, warns on environment mismatch; never builds |

`<env>` is `development`, `production`, or any environment you add as `tools/secrets/<platform>/<service>/.env.<env>` (e.g. `staging`) for every service of the platform. On Windows use `make.ps1` with the same targets: `powershell -ExecutionPolicy Bypass -File make.ps1 <target> [NAME=<service>]`. Builds contain no env files; Docker deployments inject them at run time with `docker run --env-file tools/secrets/<platform>/<service>/.env.<env>`.

## Updating

### Pick up a new yjcli release

When skills, AGENTS.md rules or guides change in yjcli:

```bash
uv tool upgrade yjcli
yjcli status            # tells you a newer yjcli is installed
yjcli update --diff     # review what changes, then confirm (or -y)
```

`yjcli update` keeps your selection and only re-renders what yjcli owns; interactively it shows three steps — status (local edits that will be overwritten, and where to move them), changes by kind, confirm — and prints "최신 상태입니다" when there is nothing to do. A yjcli that is **older** than the one that last wrote `.yjcli/manifest.toml` refuses to run (so teammates on old versions cannot roll files back); `--force` overrides.

### Change the selection

Change only what you name; every other step keeps the value in `.yjcli/manifest.toml`.

```bash
yjcli wizard                               # everything at once, stored configuration as defaults
yjcli plugin add builder deployer          # add plugins (requirements must be named too)
yjcli plugin remove runner                 # remove a plugin (tools/runner/ goes)
yjcli llm add codex                        # add / remove LLM targets
yjcli llm remove cursor
yjcli platform add frontend -n frontend=f1 # add a platform (--no-secrets to skip tools/secrets/)
yjcli platform remove frontend             # remove a platform with its code, tools, env values and build output
yjcli service add -n backend=a3            # add services (names that already exist are kept as is)
yjcli service remove -n backend=a3         # remove services (the last one takes the platform)
yjcli proto add python                     # add / remove proto languages
yjcli proto remove dart
yjcli secrets on backend                   # turn tools/secrets/ on / off per platform
yjcli secrets off frontend
yjcli wizard --plugin runner,builder -y    # replace the whole plugin list (other steps unchanged)
yjcli plan --diff                          # show the plan only
```

`-n <platform>=<names>` is declarative: an existing service in the list is left alone with a note, only new names are created.

### What yjcli owns vs. what you own

| File kind | On update |
|-----------|-----------|
| managed (skills, `CLAUDE.md`, `tools/*/GUIDE.md`, `Makefile`, `make.ps1`) | always refreshed; a local edit is overwritten and listed under **to check** (a same-named file yjcli never wrote is skipped unless `--force`) |
| blocks (`AGENTS.md` `<!-- yjcli:rules/skills/layout -->`, `.gitignore` `# >>> yjcli:managed`) | only the block is regenerated; everything outside is yours (a block whose markers were removed is appended again at the end) |
| seed (`AGENTS.md` body, env files, `tools/*/<platform>/*.{sh,ps1}`, settings) | created once (when its owner is new, or when a newer yjcli adds it); yours afterwards — deleting one opts out. When its starting template changes, it is left as is and listed under **to check** |

Tool scripts follow their `tools/<tool>/GUIDE.md`: the guide is the contract and is updated with yjcli, the scripts are the project's implementation of it. After an update, re-check the scripts against any guide that changed.

A run never stops halfway: it applies everything, then prints one result — every created, changed and deleted file, followed by **to check** (overwritten local edits, changed seed templates, re-added blocks, warnings).

Customize a skill without losing updates: write the extra rules in `.yjcli/skills/<skill>.md` (e.g. `.yjcli/skills/yj-backend.md`). yjcli appends them to that skill for every LLM on each render. Put project-wide agent rules under `### Project rules` in AGENTS.md (outside the blocks).

### Removing

Removing is confirmed once and then clean: the confirmation lists every folder that goes (with file counts, default choice 취소), and after that everything that belongs to what you removed is deleted folder by folder — whether you edited it or not, files you added there included. Nothing is left behind.

| Removed | Deleted | Kept |
|---|---|---|
| LLM | its skills folder (your own skills in it included), `CLAUDE.md`, `.claude/settings.json` | the tool's other settings (`.cursor/rules`, `.claude/settings.local.json`, …), `AGENTS.md`, paths another LLM uses |
| plugin | `tools/<plugin>/`; `Makefile` / `make.ps1` when no plugin is left | |
| service | `<platform>/<service>/`, `tools/secrets/<platform>/<service>/`, `dist/<platform>/<service>/` | |
| platform | `<platform>/`, `tools/*/<platform>/`, `tools/secrets/<platform>/`, `dist/<platform>/`, skills no other platform uses | |
| proto language / proto | `proto/dist/<language>/` / `proto/` (schemas included) and `tools/builder/proto/`; `proto` stays while `backend-msa` uses it | |
| secrets off | `tools/secrets/<platform>/` | implemented scripts (listed under **to check**) |

Code (services, platforms, proto) is deleted only by a `remove` command or the wizard's confirmation. If a list-replacing argument (`-p`, `--plugin`, `-l`, `--secrets`) would delete code under `--yes`, yjcli refuses and prints the `remove` command to run instead. A failed apply restores everything, removed folders included.

yjcli also reports **stale references**: lines outside the yjcli blocks of `AGENTS.md`, in `CLAUDE.md` or in `.yjcli/skills/*.md` that point at a plugin, LLM, platform or service that is not set up (e.g. `tools/runner/` after `yjcli plugin remove runner`), with file and line number. It never edits them; fix them by hand.

## Rebuilding a repo made with an older yjcli (0.4.x / 0.3.x / 0.2.x)

yjcli 0.5 does not work on repos set up by an earlier version: it stops with a message instead of updating them. Remove what the old yjcli generated and set the repo up again; service source code stays where it is. Work on a new branch.

**From 0.4.x** only the proto layout changed, so it is short:

1. Move the schemas to the root: `mkdir -p proto && git mv backend-msa/proto/*.proto proto/` (likewise `backend/proto`, `backend-ssr/proto` if you used them), then delete the old `<platform>/proto/` folders including their generated `dist/`.
2. Delete `.yjcli/manifest.toml` (keep `.yjcli/skills/`), and the `tools/builder/<platform>/builder.sh` / `.ps1` you never implemented (every function still says "is not implemented") so the 0.5 skeleton replaces them — before step 3, or they count as opted out.
3. Set up again with the same selection plus the languages: `yjcli wizard -l <llms> -p <platforms> --plugin <plugins> --proto-lang go,dart --force --dry-run`, then the same with `-y`. `--force` is needed because without a manifest yjcli does not recognise its own skills, Makefile and GUIDEs; it only overwrites those. Your AGENTS.md text outside the blocks, the scripts you implemented and env values are kept.
4. Move your codegen from `build_proto` (in `tools/builder/<platform>/builder.sh` / `.ps1`) into `gen_<language>` in `tools/builder/proto/builder.sh` / `.ps1`, writing to `proto/dist/<language>/`; then remove `build_proto` from the platform builders.
5. Point consumers at `proto/dist/<language>/` with a path dependency (Go `replace`, Dart `path:`, Python editable path) instead of `backend-msa/proto/dist/...` symlinks, and regenerate: `make proto-build`.

**From 0.3.x / 0.2.x:**

1. **Save what you will move back:** copy `AGENTS.md` aside (your project notes), and any run/build/deploy logic or Dockerfiles you wrote — 0.3.x: `RUN_COMMAND` lines in `tools/secrets/**/.env.local-dev`, `tools/builder/<platform>/{build,deploy}-*.sh`, service `Dockerfile`s; 0.2.x: `<platform>/scripts/`, service `Dockerfile`s.
2. **0.2.x only — rename platforms and move env values:**
   - Back up the untracked env files first: `find . -name node_modules -prune -o -type f -name '.env.*' ! -name '.env.examples' -print0 | tar --null -czf ~/env-backup.tgz -T -`
   - `git mv backend backend-msa`, then move each `backend-service/<svc>` to `backend-ssr/<svc>` if it has `views/`, otherwise to `backend/<svc>`.
   - Move every `<platform>/<service>/.env.*` except `.env.examples` to `tools/secrets/<platform>/<service>/`.
3. **Delete the old yjcli output:** `.yjcli/`, `AGENTS.md`, `CLAUDE.md`, `Makefile`, `make.bat`, the `yj-*` folders in `.cursor/skills`, `.claude/skills`, `.agents/skills` (keep your own skills), service `Dockerfile` / `.dockerignore`, `.gitignore` if you never edited it, and — 0.3.x — `tools/runner/`, `tools/builder/`; 0.2.x — `*/scripts/`, `TOOLS.md`, `Diff.md`. **Keep `tools/secrets/`**: yjcli never overwrites existing value files (remove the `RUN_COMMAND` lines from them).
4. **Set up again** with the platforms that exist (services are picked up from their folders): `yjcli wizard -l claude -p backend-msa,backend,frontend --plugin runner,builder,deployer --proto-lang go --dry-run`, then the same with `-y`. Move `backend-msa/proto/*.proto` to the root `proto/` first (see "From 0.4.x").
5. **Move your content back:** project notes go outside the `<!-- yjcli:… -->` blocks of the new `AGENTS.md`; the run command goes into `run_one` (`tools/runner/<platform>/runner.sh` / `.ps1`); build logic into `build_one` (output to `dist/<platform>/<service>/`); deploy logic into `deploy_one`, with Dockerfiles under `tools/deployer/<platform>/` and env values passed at run time (`--env-file`) — see each `tools/<tool>/GUIDE.md`. Frontend apps' `vite.config.ts` should load env from `tools/secrets/frontend/<app>/` (`envDir`).
6. **Fix old paths** in code, CI and symlinks (`backend-msa/proto` / `backend/proto` → root `proto/`, `backend-service/…`, `<platform>/scripts/…`).
7. **Check:** `yjcli update --dry-run` reports no changes, `make <platform> NAME=<service>` runs once `run_one` is implemented, and `tools/secrets/` is tracked by git (private repos only) before you commit.

## Development

```bash
uv sync
uv run python -m unittest discover -s tests   # unit tests
scripts/e2e.sh                                 # end-to-end scenarios into ./sandbox
scripts/e2e.sh -k wizard -v                    # one case, with output on failure
scripts/e2e.sh -k everything                   # sandbox/11-create-everything: every LLM, platform and plugin
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
