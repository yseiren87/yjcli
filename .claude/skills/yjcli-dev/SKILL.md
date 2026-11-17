---
name: yjcli-dev
description: >-
  Development guide for the yjcli codebase itself (not the repositories it
  generates). Use whenever changing yjcli behavior: adding or removing a
  selectable item (platform, service, plugin, LLM, optional skill,
  environment, secrets option), a command or wizard screen, a template,
  guide or skill under src/yjcli/data/, or an ownership policy. Gives the
  expected behavior of every command, the files to touch per kind of change,
  how to verify, and known pitfalls.
---

# yjcli-dev

Checklist for changing yjcli. The e2e suite is the guarantee; this skill says what to change and what to check. When a change makes anything here wrong, update this file in the same change.

## 1. Expected behavior

Every changing command runs one flow (`cli.run`): checks → collect into `Request` → `fill_defaults` → `resolve` to `Config` → `build_plan` → confirm → `apply` (all or nothing, rollback on failure) → result. The manifest (`.yjcli/manifest.toml`) is written last and only by `apply`.

| Command | Creates | Deletes (folder-level, after one confirmation) | Manifest | e2e |
|---|---|---|---|---|
| `wizard` (new) | code, agent wiring, env files, plugins, `.gitignore`, `AGENTS.md` | — | whole file | 10–16 |
| `wizard` (configured) | what was checked | what was unchecked (code removal allowed: the confirmation lists it, default 취소) | changed keys | 21 |
| `update` | new managed/seed files of this version | managed files yjcli no longer ships | `yjcli_version`, `[files]` | 30–33 |
| `platform add <p>` | `<p>/<service>/`, tool scripts, env files, skill | — | `[platforms."<p>"]` | 20 |
| `platform remove <p>` | — | `<p>/`, `tools/*/<p>/`, `tools/secrets/<p>/`, `dist/<p>/`, skills no other platform uses; refused while another platform requires `<p>` | section removed | 40 |
| `service add -n p=a` | `<p>/<a>/`, `tools/secrets/<p>/<a>/.env.*` | — | `services` | 20 |
| `service remove -n p=a` | — | `<p>/<a>/`, `tools/secrets/<p>/<a>/`, `dist/<p>/<a>/`; the last service takes the platform | `services` | 40 |
| `proto add\|remove <lang>` | `proto/dist/<lang>/` (+ `proto` platform) | `proto/dist/<lang>/` | `languages` | 20, 40 |
| `llm add\|remove <id>` | skills folder, instructions/settings | skills folder (unless shared), `CLAUDE.md`, settings; `AGENTS.md` stays | `llms` | 20, 40 |
| `plugin add\|remove <id>` | `tools/<id>/`, `Makefile`, `make.ps1` | `tools/<id>/`; Makefiles when no plugin is left | `plugins` | 20, 40 |
| `skill add\|remove <id>` | `<skills dir>/<id>/` for every LLM | the same; `.yjcli/skills/<id>.md` stays | `skills` | 20, 40 |
| `env add\|remove <env>` | `.env.<env>` for every service with secrets | every `.env.<env>`; `local-dev` / `production` cannot be removed | `[files]` only (the list is read from disk) | 22 |
| `secrets on\|off <p>` | env files of every service of `<p>` | `tools/secrets/<p>/` | `secrets = false` | 20, 40 |

Rules that hold everywhere:

- Code (service, platform, proto) is deleted only by a `remove` command or the wizard's confirmation; a list-replacing argument (`-p`, `--plugin`, `-l`, `--secrets`, `--skill`) that would delete code under `--yes` is refused (`Plan.removes_code`, e2e 42).
- Non-interactive runs need `--yes` or `--dry-run`; `--dry-run` / `plan` write nothing (e2e 50, 51).
- Policies (`catalog.py`): managed (always overwritten; a local edit is backed up to `.yjcli/backup/<time>/` with a `MERGE.md`), seed (created once, then the project's; deleting one opts out), block (`AGENTS.md` / `.gitignore`: only the block is regenerated; backed up when the block content was edited by hand), code (created once, never touched).
- A second identical run reports nothing to do (`c.quiet(...)` in e2e).

## 2. Files to touch per kind of change

### A new selectable item (like optional skills or environments)

1. `catalog.py` — the catalog entry / constant.
2. `selection.py` — `Request` field, `Config` field (with a default, it is constructed positionally), `stored_config`, `fill_defaults` (value for a new and for a configured repository), `resolve` (validation, errors phrased as the argument that fixes them).
3. `repo.py` — manifest load and dump; add new `Manifest` fields at the end (positional use in tests); decide what a manifest without the key means.
4. `plan.py` — `_wanted` (files to create), `_removals` (folders/files to delete, `code=True` only for project code), `_context` (template variables), AGENTS.md blocks, the `Manifest(...)` call.
5. `ui/wizard.py` — the screen in `_screens`, `STEPS`, the `done`/`answered` tuples in `_header`, and every hard-coded step index after the new screen.
6. `cli.py` — option type, `_wizard_collect` parameter (keyword, default `None`), `wizard` and `plan` signatures, add/remove commands (`_toggled` for id lists), `status` line.
7. `ui/report.py` — a row in the plan summary (`_with_diff` for before/after), `next_steps` if relevant.
8. Templates under `data/` that mention it; README (wizard step table, command list, removal table).
9. Tests — `tests/test_plan.py` (`plan_for` / `run` helpers take the new argument), e2e cases (§3).

### A new platform

`catalog.py` (`Platform`: folders, env kind, port, stack, skills, requires), `data/templates/platform/<stack>/`, `data/skills/yj-<platform>/SKILL.md` with routes in `SKILLS`, `references.py` if it changes path patterns, README platform table, e2e 11/12.

### Templates, guides, skills (`src/yjcli/data/`)

- Template language (`template.py`): `{{var}}`, `{{#if x}}…{{else}}…{{/if}}`, `{{include:file}}`; standalone tag lines disappear. Stack files use plain `substitute` with explicit tokens only (`__NAME__`, `__PORT__`, `__ENV_SCRIPTS__`).
- A changed seed template (tool scripts, env files, settings) is reported as "시작 템플릿이 바뀌었습니다" on every existing repository: change seeds only when the new text is worth that notice.
- Guides are plain guidelines for the target project, never "already implemented" wording.
- Repository text is English; CLI output is Korean.

### Policy or apply changes

`plan._compare` / `_merge` / `_agents` / `_gitignore`, `apply.py` (every new change kind must be undoable in `_Undo`), `ui/report.py` labels and counts, README ownership table, e2e 30/31/53.

## 3. Verify

1. `uv run python -m unittest discover -s tests`
2. `scripts/e2e.sh` (all) or `scripts/e2e.sh -k <case>`; a full run removes sandbox folders that no longer match a case. Keep case numbering by area (1x create, 2x add, 3x update, 4x remove, 5x arguments) and update case titles when behavior changes.
3. For add/remove behavior, run the real command in the scratchpad and read the manifest:

   ```bash
   Y=/Users/yangs/Storage/Project/Private/yjcli/.venv/bin/yjcli
   $Y wizard -l claude -n backend=a1 --plugin none -y
   $Y <thing> remove <id> -y && cat .yjcli/manifest.toml && ls <affected folders>
   $Y <thing> add <id> -y && cat .yjcli/manifest.toml
   $Y update --dry-run   # expect "최신 상태입니다"
   ```

4. Existing repositories: create one with the previous release (or a sandbox case) and run `update --dry-run --diff`; nothing the project owns may change, and user files stay.

## 4. Pitfalls

- Adding a wizard screen makes the interactive e2e cases (15, 21, and any `c.keys(...)` flow) hang waiting for input: add the key press for the new screen. If a full run seems stuck, look for a `KEYS` python process.
- Generated `.sh` must run on macOS bash 3.2 (no `wait -n`, no associative arrays, guard empty arrays); `.ps1` templates must be ASCII (unit test).
- `vite.config.ts` keeps `__APP_NAME__` literally — never add it to substitution tokens.
- Typer 0.27 vendors click: no `import click`.
- `Plan.changes` order matters: removals first, then writes; the manifest is applied last.
- Env files: `local-dev` / `production` are fixed (`catalog.FIXED_ENVS`); added environments come from disk (`repo.added_environments`), so deleting them by hand removes them from the manifest on the next run.
- Do not bump the package version or `MIN_SUPPORTED`; `release.sh` does. Report when a change needs a new minimum.
