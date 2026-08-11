# AGENTS.md

## 1. Project

- Name: `<name>`
- One-line purpose: `<purpose>`
- Domain / primary users: `<domain>`

---

## 2. Agent operating rules

Shared by Cursor, Claude Code, and Codex. Edit this file only; `CLAUDE.md` is a mirror (`yjcli sync agents`).

### Skills

When creating, modifying, reviewing, or refactoring code:

1. Read and follow skill `yj-arch-core`.
2. Load **exactly one** matching platform skill for the folder being edited:

| Path | Skill |
|------|--------|
| `backend/**` | `yj-backend-msa` |
| `backend-service/**` | `yj-backend-service` |
| `frontend/**` | `yj-frontend` |
| `mobile-app/**` | `yj-mobile-app` |
| `pc-app/**` | `yj-pc-app` |
| `cli/**` | `yj-cli` |
| `browser-extension/native_*/**` | `yj-backend-service` |
| `browser-extension/**` (other) | `yj-browser-extension` |
| `scheduler/**` | `yj-scheduler` |

Never load all platform skills. Never apply a platform skill outside its folder.

Skills are installed under:

- `.cursor/skills/` (Cursor)
- `.claude/skills/` (Claude Code)
- `.agents/skills/` (Codex)

### Output & docs

- Present results concisely; summarize as a table when possible.
- Show only the summary. Do not dump raw execution output, full logs, or intermediate artifacts.
- No filler, no repeated explanations.
- Switch to detailed output only when the user explicitly asks (e.g. "자세히"): keep the table first, then reasoning and the key code excerpts.
- Do not create or modify docs (README, etc.) unless the user explicitly asks. When editing a doc, rewrite it in context so it stays in sync with the code.

---

## 3. Repository layout

Paths from `yjcli init` are fixed; add platform/app rows with `<path>` / `<role>` as needed.

| Path | Role |
|------|------|
| `AGENTS.md` | Agent / contributor guide (this file) — source of truth |
| `CLAUDE.md` | Mirror of `AGENTS.md` — do not edit; refresh with `yjcli sync agents` |
| `TOOLS.md` | Release-tools feature spec (version / deploy / git) |
| `Diff.md` | User-maintained reference for project differences from yjcli defaults; yjcli never updates or restores from it |
| `Makefile` | Root entry — run via `make <platform>`; deploy via `<platform>-deploy-development\|production`, optionally with `NAME=<service>` |
| `make.bat` | Extensible Windows counterpart of root Makefile |
| `<platform>/scripts/deploy-common.*` | Repository-owned shared build/package implementation |
| `<platform>/scripts/deploy-development.*` | Repository-owned development upload/deploy implementation |
| `<platform>/scripts/deploy-production.*` | Repository-owned production upload/deploy implementation |
| `.gitignore` | Canonical ignore rules |
| `.cursor/skills/` | Cursor skills (copied from package) |
| `.claude/skills/` | Claude skills (copied from package) |
| `.agents/skills/` | Codex skills (copied from package) |
| `.claude/settings.json` | Claude settings |
| `<path>/` | `<role>` |
| `<path>/` | `<role>` |

---

## 4. Stack

| Area | Stack / versions |
|------|------------------|
| `<area>` | `<stack>` |
| `<area>` | `<stack>` |
| `<area>` | `<stack>` |

---

## 5. Commands

```bash
# install
<command>

# run / dev
<command>

# lint / typecheck
<command>

# build
<command>

# deploy (generated stubs fail until implemented)
make <platform>-deploy-development [NAME=<service>]
make <platform>-deploy-production [NAME=<service>]
```

---

## 6. Testing

- Framework: `<framework>`
- Location: `<paths>`
- Run all: `<command>`
- Run one: `<command>`
- Coverage / mocking notes: `<notes>`

---

## 7. Architecture boundaries

- Feature ownership: `<notes>`
- Import / layer rules: `<notes>`
- Generated / vendor code (do not hand-edit): `<paths>`

---

## 8. Coding conventions

- Language / style: `<notes>`
- Naming: `<notes>`
- Error handling: `<notes>`
- Logging: `<notes>`

---

## 9. Do / Don't

### Do

- `<item>`
- Record meaningful architecture differences from yjcli defaults in `Diff.md` when useful for manual restoration.

### Don't

- `<item>`
- Do not expect `Diff.md` to drive sync, migration, comparison, backup, or automatic restoration.
- Do not put secrets in `Diff.md`.

---

## 10. Secrets & safety

- Never commit: `<patterns>`
- Local-only files: `<paths>`
- Destructive commands (require explicit user approval): `<commands>`

---

## 11. Git / PR

- Branch naming: `<pattern>`
- Commit message style: `<style>`
- PR checklist: `<items>`

---

## 12. Pointers

| Kind | Location |
|------|----------|
| Release tools spec | `TOOLS.md` |
| Architecture differences | `Diff.md` |
| Packaged skills (source) | installed via `yjcli` → `.cursor` / `.claude` / `.agents` skills |
| `<kind>` | `<path>` |
