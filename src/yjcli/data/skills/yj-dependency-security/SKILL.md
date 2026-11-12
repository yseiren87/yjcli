---
name: yj-dependency-security
description: >-
  Open-source component security (CVE check) for every platform. Load together
  with the platform skill whenever a third-party dependency is added, upgraded,
  replaced or vendored: package manifests and lock files (package.json,
  go.mod, pubspec.yaml, pyproject.toml / uv.lock, ...) and committed copies
  of third-party files (e.g. static/vendor/*.js).
---

# yj-dependency-security

Requires `yj-arch-core`. The goal is not a list of banned libraries but a habit: **every time a dependency is introduced or its version changes, check it for known vulnerabilities first.**

## When

- Adding a dependency, changing its version (including lock-file-only bumps you make on purpose), or replacing it.
- Committing a third-party file into the repository (vendored JS/CSS, copied SDK sources). These are dependencies too, just without a manifest.
- Not needed for code that only uses dependencies already present at the same version.

## Check

1. Look up known CVEs for the exact version: the organization's scanner (OSMS/SCA) result if there is one, otherwise a public source — the ecosystem audit tool (`npm audit`, `govulncheck`, `pip-audit`, `dart pub outdated` + advisories) or a CVE database (OSV, NVD, GitHub Advisory).
2. Prefer the smallest dependency that does the job; a new transitive tree is new attack surface.

## When a serious CVE is found

Decide in this order:

1. **Patched version** of the same library exists → pin to it.
2. **No patch** → switch to an alternative library without the CVE.
3. **No good alternative and the use is simple** (a few plain calls, none of the library's distinctive features) → remove the library and implement just the part actually used.

Replacing a library with own code is a decision for that moment, not a permanent ban: when a suitable library without CVEs exists later, switching back is fine.

## Record

- Report every CVE found and the response (pinned version / replacement / own implementation) in the task result.
- If the project keeps a dependency-security log (see `AGENTS.md` pointers), add the entry there as well.

## Don't

- Do not add or vendor a library out of habit ("latest", "popular", "convenient") without the check.
- Do not treat a library name as forbidden by itself — the criterion is always the CVE status at that moment and how much of the library is really used.
- Do not silence audit findings (ignore lists, `--force`, pinned-but-vulnerable versions) without telling the user.
