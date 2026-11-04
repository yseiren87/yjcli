# CLAUDE.md

## Language

- Talk to the user in **Korean** (answers, explanations, questions, progress updates, summaries).
- Write everything that goes into the repository in **English**: documentation, Markdown files, code comments, templates, commit-ready text.
- Exception: the CLI's own user-facing output (wizard prompts, summaries, error messages in `src/yjcli/`) is Korean, as it already is. Keep new messages consistent with that.

## Commits, pushes and versions

- Commits, tags and pushes are done by the user with `./release.sh`. Do not commit or push unless the user explicitly asks.
- Do not change the package version (`pyproject.toml`, `uv version`) either — `./release.sh` bumps it. If a change needs a new minimum version (e.g. `MIN_SUPPORTED`), say so in the report instead.
- After finishing a change, do **not** suggest committing, ask whether to commit, or end with "commit when ready"-style notes. Just report what changed and how it was verified.

## Project

yjcli is a Python CLI (Typer + questionary + rich) that scaffolds YJ-architecture repositories: platform/service code folders, `tools/` plugins (runner, builder, deployer), env value files (`tools/secrets/`), and agent wiring (AGENTS.md, skills for Cursor / Claude Code / Codex).

- `src/yjcli/catalog/` — LLMs, platforms, plugins, skills.
- `src/yjcli/core/` — selection → planner → executor, manifest, template renderer.
- `src/yjcli/ui/` — wizard and prompts.
- `src/yjcli/data/` — templates rendered into target repos (plugins, skills, root files).
- `scripts/e2e.py` — end-to-end scenarios written into `sandbox/<case>/` (git-ignored).

## Environment

- Use `uv` only (installed via Homebrew). Never install or use a global Python; run Python through `uv run`.
- The global `yjcli` command is installed from this folder in editable mode (`uv tool install --force --editable .`); reinstall after changing the version.

## Checks

Run both after changes and report the results:

```bash
uv run python -m unittest discover -s tests   # unit tests
scripts/e2e.sh                                 # all e2e cases (scripts/e2e.sh -k <name> for one)
```

When a case is added, renamed or removed, keep the numbering in `scripts/e2e.py` consistent; a full e2e run removes sandbox folders that no longer match a case.

## Conventions

- Markdown: no hard wraps — a sentence never spans lines; each paragraph or list item is one line. Tables, code blocks, YAML frontmatter and standalone template-tag lines are exempt.
- Generated `.sh` scripts must run on macOS's bash 3.2 (no `wait -n`, no associative arrays, guard empty arrays).
- Generated `.ps1` templates must be ASCII-only (Windows PowerShell 5.1 reads BOM-less files as ANSI); a unit test enforces this.
- yjcli builds structure, not project logic: tooling templates ship a working skeleton plus a `GUIDE.md`, and the target project implements one function per script.
- No backward compatibility with repos made before `MIN_SUPPORTED` in `core/manifest.py` (currently 0.5.0; capped at the installed version until a release bumps it).
