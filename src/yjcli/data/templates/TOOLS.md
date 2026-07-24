# TOOLS.md — Release tools (feature spec)

Language-agnostic **feature specification** for local release tooling.  
Not an architecture diary and not tied to a specific stack.

**How to use**

1. Keep or copy this file into a repo.
2. Fill project-specific facts in §0 (inputs).
3. Ask an agent/dev: *Implement TOOLS.md using \<language/toolchain\>.*
4. Implementation may be Make + scripts, a small CLI, CI jobs, etc. — as long as behaviors below are met.

---

## 0. Project inputs (fill before implement)

| ID | Input | Value |
|----|--------|--------|
| I1 | Product / package name | `<name>` |
| I2 | Canonical version location | `<file + field>` — semver `X.Y.Z` |
| I3 | Other version mirrors (optional) | `<paths or none>` |
| I4 | Git root | `<path>` |
| I5 | Default branch | `<branch>` |
| I6 | Git remote name + URL | `<origin + url>` |
| I7 | Production publish target | `<registry/host + package id>` |
| I8 | Staging publish target (optional) | `<or none>` |
| I9 | Secrets store | `<e.g. ignored .env path>` |
| I10 | Secret: publish token name(s) | `<ENV keys>` |
| I11 | Secret: git push token name (if HTTPS PAT) | `<ENV key or none if SSH>` |
| I12 | Version tag pattern | `<e.g. vX.Y.Z or release/X.Y.Z>` |
| I13 | Preferred invoke style | `<make / cli / npm scripts / …>` |

---

## 1. Goals

Provide three capabilities, invocable from a single local entry surface (I13):

| ID | Capability | Intent |
|----|------------|--------|
| C1 | **Version** | Read/bump canonical semver; keep mirrors in sync if any |
| C2 | **Deploy** | Build and publish artifacts to configured targets |
| C3 | **Git release** | Commit (optional), tag, push using non-interactive auth when scripted |

Out of scope: app business logic, scaffold of product code, editor agent rules (see `AGENTS.md`).

---

## 2. Shared requirements

| ID | Requirement |
|----|-------------|
| S1 | No secrets in git. Tokens only via I9/I10/I11. |
| S2 | Destructive steps (publish, push, tag) require **explicit** confirmation (`y`/`n`). No default answer. |
| S3 | User can abort the whole flow with `exit` on any prompt (clean exit). |
| S4 | Steps are logged with clear section boundaries (readable in a terminal). |
| S5 | Missing config/secrets → fail with actionable message (what to set, where). |
| S6 | Do not force-overwrite existing git tags matching I12 unless the project explicitly opts in (default: **fail**). |
| S7 | Interactive answers: yes/no prompts accept only `y`/`n`/`exit` (also `yes`/`no`). Empty or other input → **re-ask** (never treat Enter as No/Yes). Free-text prompts: empty → re-ask unless the step allows empty; `exit` cancels. |

---

## 3. C1 — Version management

### 3.1 Behaviors

| ID | Behavior |
|----|----------|
| V1 | Read version from I2; must match `X.Y.Z`. |
| V2 | Support bumps: `major` → `X+1.0.0`, `minor` → `X.Y+1.0`, `fix` → `X.Y.Z+1`. |
| V3 | After bump, write I2; if I3 is non-empty, update those to the same version. |
| V4 | Optional: show latest version from production target I7 when query is possible; if unavailable, warn and continue. |
| V5 | Interactive bump: ask whether to bump (S7); if yes, ask `major`/`minor`/`fix` (invalid/empty → re-ask; cancel per S3). |
| V6 | Non-interactive mode (optional): accept bump kind via flags/env; do not hang on stdin. |

### 3.2 Acceptance

- Given I2 = `1.2.3`, bump `fix` → I2 (and I3) become `1.2.4`.
- Invalid version string in I2 → hard fail before publish/tag.

---

## 4. C2 — Deploy / publish

### 4.1 Behaviors

| ID | Behavior |
|----|----------|
| D1 | **Test**: run project-defined verification before publish (unit/smoke/e2e — project chooses). Fail stops the pipeline. |
| D2 | **Build**: produce publishable artifact(s) for I7 (and I8 if used). |
| D3 | **Validate** (recommended): dry-run or registry check when the ecosystem supports it. |
| D4 | **Confirm** then **Publish** to I7 using I10. Confirm per S7 (`y`/`n`/`exit`; no default). |
| D5 | Provide a **staging path** when I8 exists: publish to I8 without requiring a version bump or git push (unless project opts in). |
| D6 | Production path may optionally chain into C3 after successful publish (project chooses). |

### 4.2 Acceptance

- Failed D1 or D2 → no publish.
- Confirm `n` → no publish, abort. Confirm empty/garbage → re-ask. `exit` → clean cancel.
- Missing I10 → fail per S5.

---

## 5. C3 — Git release (push / tag)

### 5.1 Behaviors

| ID | Behavior |
|----|----------|
| G1 | Operate only on git root I4. |
| G2 | Show status: branch, remote I6, current version (I2), whether tag I12(version) exists. |
| G3 | **Commit**: if working tree dirty, ask to commit (S7). `n` or cancel → **stop** (no tag/push). Require non-empty message. If clean, proceed without a new commit. |
| G4 | **Tag**: create tag from I12 + current I2 version; confirm per S7; if exists → fail (S6). |
| G5 | **Push**: confirm per S7, then push current branch + new tag to I6. |
| G6 | Auth: non-interactive for scripted use (PAT from I11 for HTTPS, or SSH agent). Do not open browser login flows in the happy path. |
| G7 | Never persist raw tokens into remote URLs in git config. |

### 5.2 Acceptance

- Clean tree + new version tag → tag created and pushed when confirmed (`y`).
- Dirty tree + commit declined (`n`) → no tag, no push.
- Existing tag → fail, no force-push by default.
- Missing I11 when HTTPS PAT is required → fail per S5.

---

## 6. Suggested entry surface (names are free)

Implementers pick I13 names; map behaviors roughly like:

| Entry | Calls |
|-------|--------|
| Help | List entries |
| Version / bump | C1 |
| Deploy production | C1 (optional ask) → C2 → optional C3 |
| Deploy staging | C2 against I8 (usually skip C1 bump & C3) |
| Git release only | C3 |

Exact command names are **not** part of this spec.

---

## 7. Non-goals

- Mandating Python/Node/Go/Make/etc.
- Mandating a `tools/` directory layout.
- Replacing product CI; this spec may be implemented as CI, local scripts, or both.
- Defining app platforms, scaffolds, or agent skills.

---

## 8. Implementation notes for agents

When asked to implement this file:

1. Read §0 values; if empty, ask the user for I1–I13 before coding.
2. Choose toolchain from the user’s language request + existing repo norms.
3. Implement C1→C2→C3 against the IDs above; keep secrets out of the repo.
4. Add a short “Implemented by” note under §9 (paths to scripts/workflows only).

---

## 9. Implemented by (fill after coding)

| Capability | Entry / path |
|------------|----------------|
| C1 Version | `<…>` |
| C2 Deploy | `<…>` |
| C3 Git release | `<…>` |
| Secrets example | `<…>` |
