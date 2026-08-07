---
name: yj-arch-core
description: >-
  Repository architecture constitution for this monorepo. Use on every coding,
  review, or refactor task. Enforces fixed platform roots, unified env file
  names, universal entry/flow/domain/view/infra roles (domain = owned concept,
  persistence optional), acyclic imports, and minimal edit scope. Always apply
  together with exactly one matching yj-* platform skill for the folder being
  edited.
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
scheduler/            # yj-scheduler
```

```text
{platform}/
  scripts/            # platform-level only
  {service_name}/     # one deployable / one app
```

- `backend/proto/` is reserved (see yj-backend-msa).
- `browser-extension/native_{name}/` → **yj-backend-service**.
- Do not invent new platform roots or put app code at repo root.
- Do not create a `Makefile` inside any service folder, including generic `run`,
  `install`, or `help` targets. Do not add per-service `scripts/`.
  Root `make <platform>` starts all services under that platform (concurrent); `NAME=<service>` runs one.
  Platforms run via `*/scripts/run.*`; services are sibling dirs created with `yjcli service add`.
- The root `Makefile` / `make.bat` is repository-owned and may be extended. Prefer
  `<platform>-<action> [NAME=<service>]` when an action should target all services
  or one service (for example, `backend-deploy`). The repository owns and implements
  actions such as init/install/build/deploy; yjcli does not generate action scripts.


## Environment (guardrails only)

Required files at each service root (no plain `.env`):

`.env.local-dev` · `.env.examples`

- New services also start with `.env.development` and `.env.production`, but these
  are optional. Remove them when unused or add environments such as `.env.staging`,
  `.env.test`, or `.env.qa` as the project requires. Environment files must follow
  the `.env.<environment>` naming pattern; do not use plain `.env` or Vite's
  `.env.local` convention unless a thin loader maps it to this structure.
- Env field sets come from `templates/platform/envs/<kind>/` via platform mapping (`listen` / `worker` / `app`).
  - `listen`: `backend` (PORT 8080), `frontend` (PORT 5173)
  - `worker`: `backend-service`, `browser-extension/native_*`, `scheduler` (HOST/PORT optional)
  - `app`: `cli`, `mobile-app`, `pc-app`, `browser-extension` (NAME/VERSION only)
  Do not invent fields outside those templates; environment filenames remain
  extensible through the `.env.<environment>` pattern above.
- `HOST`/`PORT` are required for `listen`. For `worker` they are optional — add only if needed.
- `.env.examples` is the committed field contract. Format every entry as one
  comment line followed by one empty `FIELD=` line, with one blank line between
  entries.
- Every other `.env.<environment>` file lists populated `FIELD=value` lines
  consecutively, without field-description comments or separator blank lines.
- Commit `.env.examples` only; never commit `.env.local-dev` or any other
  environment value file.
- Local platform `run.*` uses `.env.local-dev` only — do not hardcode HOST/PORT in scripts.
- Each service declares its repository-owned local `RUN_COMMAND` in `.env.local-dev`.
  Platform `run.*` must execute that declaration and must not infer commands from
  `package.json`, `pyproject.toml`, `go.mod`, or other language/runtime manifests.

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
| `scheduler/**` | `yj-scheduler` |

Never load all platform skills. Never apply a platform skill outside its folder.

## Universal roles

```text
entry   = executable entrypoint + route/command/screen registration + wiring
flow    = feature composition + dto / input-output shape
domain  = owned business concept (authority); persistence optional
view    = UI (only platforms that render UI)
infra   = shared technical modules (config, clients, logging, utils)
```

### Domain (owned concept — not “must have DB”)

Create `domains/{name}/` only when **this deployable owns** a concept (it is the authority for that idea).

Optional file slots inside a domain (use only what exists):

- `model` — data shape / entity (optional)
- `repository` — persistence/retrieval (optional; only if this process stores it)
- `rules` — decisions / pure policy (optional)
- `errors` / `types` — domain-only errors and value types (optional)

Valid shapes: data+rules · data only · rules only.  
If the deployable owns **no** concept → **omit `domains/` entirely**.

Missing domain does **not** mean collapse into entry. Still use flow + infra.

Placement when unsure:

1. Owned concept / shared policy across features? → domain  
2. One feature’s IO / mapping / orchestration? → flow (`services/{feature}`)  
3. Clients, config, logging, technical helpers? → infra (`modules`)  
4. Bootstrap / register only? → entry (`apps` or platform entry files)  
5. Otherwise do not invent a new home — extend an existing flow

UI clients default to **no `domain`**: model = API types; feature rules live in flow.  
Exception only for heavy client-owned offline DB/engine concepts.

## Import direction

Allowed: `entry -> flow -> domain -> infra`, `entry -> infra`, `flow -> infra`, `view -> flow`, `domain -> infra`.

Forbidden: `domain -> flow/entry/other domain`, `flow -> entry/other flow` (unless repo allows), `infra -> *`, `view -> domain/infra/network`, generated UI → project-specific imports.

Entry must stay thin: no feature DTOs, business policy, or grab-bag utils in entry packages.

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
