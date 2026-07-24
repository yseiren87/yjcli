# AGENTS.md

## 1. Project

- Name: `<name>`
- One-line purpose: `<purpose>`
- Domain / primary users: `<domain>`

---

## 2. Repository layout

Paths from `yjcli init` are fixed; add platform/app rows with `<path>` / `<role>` as needed.

| Path | Role |
|------|------|
| `AGENTS.md` | Agent / contributor guide (this file) |
| `CLAUDE.md` | Mirror of `AGENTS.md` — do not edit; refresh with `yjcli sync agents` |
| `TOOLS.md` | Release-tools feature spec (version / deploy / git) |
| `Makefile` | Root run entry — `make <platform>` (all services) or `NAME=<service>` (one); platforms auto-discovered |
| `make.bat` | Windows counterpart of root Makefile |
| `.gitignore` | Canonical ignore rules |
| `.cursor/skills/` | Cursor skills (copied from package) |
| `.cursor/rules/` | Cursor rules (copied from package) |
| `.claude/skills/` | Claude skills (copied from package) |
| `.claude/rules/` | Claude rules (copied from package) |
| `.claude/settings.json` | Claude settings |
| `<path>/` | `<role>` |
| `<path>/` | `<role>` |

---

## 3. Stack

| Area | Stack / versions |
|------|------------------|
| `<area>` | `<stack>` |
| `<area>` | `<stack>` |
| `<area>` | `<stack>` |

---

## 4. Commands

```bash
# install
<command>

# run / dev
<command>

# lint / typecheck
<command>

# build
<command>
```

---

## 5. Testing

- Framework: `<framework>`
- Location: `<paths>`
- Run all: `<command>`
- Run one: `<command>`
- Coverage / mocking notes: `<notes>`

---

## 6. Architecture boundaries

- Feature ownership: `<notes>`
- Import / layer rules: `<notes>`
- Generated / vendor code (do not hand-edit): `<paths>`

---

## 7. Coding conventions

- Language / style: `<notes>`
- Naming: `<notes>`
- Error handling: `<notes>`
- Logging: `<notes>`

---

## 8. Do / Don't

### Do

- `<item>`

### Don't

- `<item>`

---

## 9. Secrets & safety

- Never commit: `<patterns>`
- Local-only files: `<paths>`
- Destructive commands (require explicit user approval): `<commands>`

---

## 10. Git / PR

- Branch naming: `<pattern>`
- Commit message style: `<style>`
- PR checklist: `<items>`

---

## 11. Pointers

| Kind | Location |
|------|----------|
| Release tools spec | `TOOLS.md` |
| `<kind>` | `<path>` |
| `<kind>` | `<path>` |
