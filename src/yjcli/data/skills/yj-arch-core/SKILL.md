---
name: yj-arch-core
description: >-
  Repository architecture constitution for this monorepo. Use on every coding,
  review, or refactor task. Enforces fixed platform roots, unified env file
  names, universal entry/flow/domain/view/infra roles, acyclic imports, and
  minimal edit scope. Always apply together with exactly one matching yj-*
  platform skill for the folder being edited.
---

# yj-arch-core

## Purpose

Reduce AI cost and blast radius. Do not reinterpret the whole repo, add
wrappers/layers, or read unrelated platforms.

1. Existing repo conventions win when clearer than this skill.
2. Identify the platform root folder first, then load **only** that platform skill.
3. Edit the smallest file set that owns the change.

## Fixed platform roots

```text
backend/              # MSA + gRPC (yj-backend-msa)
backend-service/      # single BE (yj-backend-service)
frontend/             # yj-frontend
mobile-app/           # yj-mobile-app
pc-app/               # yj-pc-app
cli/                  # yj-cli
browser-extension/    # yj-browser-extension
```

```text
{platform}/
  scripts/            # platform-level only
  {service_name}/     # one deployable / one app
```

- `backend/proto/` is reserved (see yj-backend-msa).
- `browser-extension/native_{name}/` → **yj-backend-service**.
- Do not invent new platform roots or put app code at repo root.
- Do not add per-service `scripts/` or edit root Makefile for each new service/platform.
  Root `make <platform>` starts all services under that platform (concurrent); `NAME=<service>` runs one.
  Platforms are discovered via `*/scripts/run.sh`; services via sibling dirs (no script edits on `add service`).

## Environment (guardrails only)

Allowed files at each service root (no plain `.env`):

`.env.local-dev` · `.env.development` · `.env.production` · `.env.examples`

- Do not invent alternate names (including Vite `.env` / `.env.local`) unless a thin loader maps to this set.
- Env field sets come from `templates/platform/envs/<kind>/` via platform mapping (`listen` / `worker` / `app`).
  - `listen`: `backend` (PORT 8080), `frontend` (PORT 5173)
  - `worker`: `backend-service`, `browser-extension/native_*` (HOST/PORT optional comments)
  - `app`: `cli`, `mobile-app`, `pc-app`, `browser-extension` (NAME/VERSION only)
  Do not invent fields/filenames outside those templates.
- `HOST`/`PORT` are required for `listen`. For `worker` they are optional — add only if needed.
- Commit `.env.examples` only; never commit the other three.
- Local platform `run.*` uses `.env.local-dev` only — do not hardcode HOST/PORT in scripts.

## Skill routing

| Path | Platform skill |
|------|----------------|
| `backend/**` | `yj-backend-msa` |
| `backend-service/**` | `yj-backend-service` |
| `frontend/**` | `yj-frontend` |
| `mobile-app/**` | `yj-mobile-app` |
| `pc-app/**` | `yj-pc-app` |
| `cli/**` | `yj-cli` |
| `browser-extension/native_*/**` | `yj-backend-service` |
| `browser-extension/**` (other) | `yj-browser-extension` |

Never load all platform skills. Never apply a platform skill outside its folder.

## Universal roles

```text
entry   = executable entrypoint + route/command/screen registration + wiring
flow    = feature composition + dto / input-output shape
domain  = model + repository + rules (only where persistence lives)
view    = UI (only platforms that render UI)
infra   = shared technical modules (config, clients, logging, utils)
```

UI clients default to **no `domain`**: model = API types; rules live in flow.

## Import direction

Allowed: `entry -> flow -> domain -> infra`, `entry -> infra`, `flow -> infra`, `view -> flow`, `domain -> infra`.

Forbidden: `domain -> flow/entry/other domain`, `flow -> entry/other flow` (unless repo allows), `infra -> *`, `view -> domain/infra/network`, generated UI → project-specific imports.

Cycles are structure bugs — do not paper over with lazy imports or wrappers.

## Editing workflow

Before: platform skill → feature/domain → minimal file set → prefer reuse.

During: edit in place; no thin wrappers/adapters; no one-line functions unless the name is a real domain concept; keep feature work and drive-by refactors separate.

Avoid names: `{entity}_v2|_wrapper|_adapter|_helper`, `{feature}_manager|_processor`.

Avoid layers unless user requests: `usecases/`, `workflows/`, `orchestrations/`, `application/`, `controllers/`, `handlers/`.

`flow` is the composition layer — do not invent a layer above it.

After: summarize files, boundaries, new files, test/migration risk briefly.

## Cross-platform contracts

- Prefer generated clients / `backend/proto/dist/{lang}` over hand-copied DTOs.
- Do not import another platform's source tree.
- Do not read unrelated platforms unless the user task explicitly spans them.
