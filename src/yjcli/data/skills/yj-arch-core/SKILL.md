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
  scripts/            # platform run + deploy entry points
  {service_name}/     # one deployable / one app
```

- `backend/proto/` is reserved (see yj-backend-msa).
- `browser-extension/native_{name}/` → **yj-backend-service**.
- Do not invent new platform roots or put app code at repo root.
- Do not create a `Makefile` inside any service folder, including generic `run`,
  `install`, or `help` targets. Do not add per-service `scripts/`.
  Root `make <platform>` starts all services under that platform (concurrent); `NAME=<service>` runs one.
  Platforms run via `*/scripts/run.*`; services are sibling dirs created with `yjcli service add`.
- The root `Makefile` / `make.bat` wires platform run, build, and deploy commands. Use
  `<platform>-build-development|production [NAME=<service>]` for builds and
  `<platform>-deploy-development|production [NAME=<service>]` for deploys.
  `build-common.sh` owns shared build/package preparation; the environment-specific
  build script (`build-development.sh` / `build-production.sh`) calls it.
  `deploy-common.sh` owns shared deploy orchestration (calls the matching build
  script, then runs deploy plugins); the environment-specific deploy script
  (`deploy-development.sh` / `deploy-production.sh`) calls it first and then
  owns upload/rollout guidance only. Generated build/deploy scripts fail with an
  implementation prompt until the repository replaces their guarded stubs.
- `run.*` ships as `.sh` + `.bat` + `.ps1` (local dev runs natively per platform).
  `build-*` and `deploy-*` are `.sh` only — build/deploy tooling is not native to
  Windows, so `make.bat` runs those targets through WSL.
- Build/deploy scripts are repository-owned after creation. `yjcli sync make` installs
  missing build/deploy scripts but preserves existing ones.
- `build-common.sh` is the same file for every platform — it is not backend-specific.
  It is a thin plugin host: it runs every `scripts/plugin-build-*.sh` file present,
  then falls through to its own generic build guard. Each capability is its own
  file, self-detected by folder presence at runtime, not by branching on platform
  name — so any platform can opt in. (A deploy-side plugin would be
  `plugin-deploy-*.sh` — the naming segment names the consumer.)
  - `plugin-build-proto.sh` → protoc codegen guard when `<platform>/proto/` exists
    (schema `proto/*.proto` → generated `proto/dist/{lang}`). `backend` always has
    this (fixed gRPC MSA root); any other platform gets the same guard only if it
    creates a `proto/` folder too — do not assume gRPC on non-backend platforms.
    protoc is the standard; buf is not used.
  - `plugin-build-ssr.sh` → template/asset build guard when
    `<platform>/{service}/views/` exists, checked per service (or across all
    services when no service is targeted). Any platform's service may opt in by
    creating `views/` — this is not backend-service-specific either.
  - `plugin-build-docker.sh` → docker image **build only** guard (no push, no
    swarm/stack rollout — that is a deploy-side plugin's job, not this one),
    per service that has a `Dockerfile` (delete it to opt that service out).
    Builds use `{service}/.env.development` or `.env.production` matching the
    target environment. Image version: the service's `package.json` or
    `pyproject.toml` `version` field when present, else the `VERSION` env var.
  None of these plugins imply each other, and none imply MSA: a backend-service
  using gRPC is still a single deployable, not multiple services sharing a
  proto contract. Each plugin is also runnable standalone (e.g.
  `./plugin-build-proto.sh development`) for testing without the base build guard.
- `yjcli service add` adds `Dockerfile` + `.dockerignore` to new services under
  deployable platforms (`backend`, `backend-service`, `frontend`, `scheduler`)
  — not under `cli`/`mobile-app`/`pc-app`/`browser-extension`, which are
  local/client artifacts, not docker-swarm services. The Dockerfile is
  language-agnostic with no `FROM` yet — `docker build` fails until replaced,
  same guard-until-implemented contract as the other stubs.
- `deploy-common.sh` is the deploy-side plugin host, same contract as
  `build-common.sh`: after calling the matching build script, it runs every
  `scripts/plugin-deploy-*.sh` file present. None ship by default — a project
  adds one (e.g. an image-push + `docker stack deploy` plugin, `kubectl apply`,
  nginx/reverse-proxy) when it needs it. `deploy-development.sh` /
  `deploy-production.sh` call `deploy-common.sh` and then own upload/rollout
  guidance only.
- `Diff.md` is an optional, user-maintained reference for meaningful architecture
  differences from yjcli defaults and their manual restoration notes. Update it
  when that record would help, but never treat it as an automated sync, migration,
  backup, comparison, or restoration mechanism. Never place secrets in it.


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
2. One feature’s IO / mapping / orchestration? → the platform-defined flow
   boundary (commonly `services/{feature}`)
3. Clients, config, logging, technical helpers? → infra (`modules`)  
4. Bootstrap / register only? → entry (`apps` or platform entry files)  
5. Otherwise do not invent a new home — extend an existing flow

UI clients default to **no `domain`**: model = API types; feature rules live in flow.  
Exception only for heavy client-owned offline DB/engine concepts.

UI platform skills may map flow and view to separate technical roots. Those
roots must use the same feature boundary so one feature's flow and view remain
easy to locate without mixing their roles.

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
