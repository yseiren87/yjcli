---
name: yj-backend-msa
description: >-
  Backend MSA architecture with mandatory gRPC/protobuf. Use only when creating
  or editing code under backend/. Language-agnostic (Go/Python/Java/etc.).
  Covers backend/{service}, backend/proto, and proto/dist/{lang}. Supports owner,
  policy, and edge/gateway services (domains optional). Optional server-templating
  (SSR) add-on for a service that must render HTML, same as backend-service — not
  a separate platform. Do not use for backend-service/, frontend/, mobile-app/,
  pc-app/, cli/, or browser-extension/.
---

# yj-backend-msa

Requires `yj-arch-core`. Scope: **`backend/` only**.

## Shape

```text
backend/
  scripts/                 # platform-level only
  proto/                   # owned by backend MSA only
    *.proto
    dist/
      golang/
      python/
      java/
      dart/
      ...
  {service_name}/
    apps/                  # entry
    services/              # flow
    domains/               # domain (optional — owned concepts only)
    modules/               # infra
```

- One `{service_name}` = one deployable microservice.
- Do not over-split domains into tiny services. Split by cohesive business capability.
- gRPC + protobuf are **mandatory**. External API surface is proto, not ad-hoc JSON structs copied across services.

## Service stereotypes (same folders, different fill)

| Kind | `domains/` | Typical contents |
|------|------------|------------------|
| **Owner** | yes | model ± repository ± rules for concepts this service stores/decides |
| **Policy** | yes (rules-focused) | shared authz/quota/aggregation policy; often **no** repository |
| **Edge / BFF / gateway** | usually **omit** | `services/{feature}` + `modules` clients; add rules-only domain only if policy is shared across many features |

Omit empty `domains/` trees. Do not invent fake repositories to “have a domain”.

## proto

- Sources live only in `backend/proto/`.
- Generated stubs go to `backend/proto/dist/{lang}/`.
- Other platforms (e.g. `mobile-app`) may **symlink** to `backend/proto/dist/{lang}` — they must not own `.proto` copies.
- Prefer package boundaries in proto that align with service boundaries.
- Regeneration is wired through `backend/scripts/plugin-build-proto.sh` — a plugin
  file every platform gets (not backend-specific), which auto-detects
  `backend/proto/` and adds a protoc codegen guard (protoc is the standard here;
  buf is not used). It runs automatically as part of `build-common.sh`, invoked via
  `make backend-build-development|production`, and is also runnable standalone.
  Implement codegen there, not as an ad-hoc one-off command.

## Optional: server templating (SSR/MPA)

Templating is an **option**, not something MSA forbids. Enable only when a
service must render HTML itself (e.g. an edge/gateway serving an admin page).
Most services stay gRPC-only — do not create `views/` speculatively.

When enabled for `{service_name}`, add role `view`:

```text
view = views/{feature}/{page}.html | views/layouts/* | views/partials/*
```

Extra rules:

- Handlers: parse → call flow → build template context → render. No DB in handlers.
- flow returns plain data / view models — never HTML.
- templates: presentation only; no DB/service/domain calls.
- Template/asset bundling is wired the same way as proto: `plugin-build-ssr.sh`
  auto-detects `{service_name}/views/` and adds a build guard for it. Implement
  the bundling there, not as an ad-hoc one-off command.
- If the service is gRPC-only, do **not** create `views/`.

## Roles inside `{service_name}`

```text
entry  = apps/{app_name}/main.{ext}   # wiring / registration only
flow   = services/{feature}/dto.{ext} + service.{ext}
domain = domains/{domain}/…           # optional slots; see below
infra  = modules/{module}.{ext}
```

### entry

- Init, gRPC server registration, dependency wiring only.
- No business logic. No feature DTOs, policy, or utils dump under `apps/`.
- No direct domain calls (always through flow).

### flow

- Feature/workflow composition. DTOs for this service's use of contracts.
- Reuse services across RPCs; do not create a service per RPC automatically.
- Do not import other services' source trees; call them over gRPC using generated clients.
- Edge/gateway: put aggregation and feature-local mapping here — not in `apps/`.

### domain

Create only for **owned concepts** (this service is the authority). File slots are optional:

- `model.{ext}`: internal domain model, entity, schema, or data shape.
- `repository.{ext}`: persistence/retrieval — only if this process stores the concept.
- `rules.{ext}`: domain-specific decisions and pure validations.
- `errors.{ext}` / `types.{ext}`: domain errors and value types.

Rules:

- Valid: data+rules · data only · rules only. Repository is **not** required.
- No gRPC/transport types in domain.
- Domains must not import apps or services.
- No domain→domain imports; compose in flow.
- Do not duplicate the same responsibility across multiple domains.

### Relation domain

When two domains are both first-class concepts and their relationship is managed directly, create a relation domain.

Use when:

- `{domain_a}` and `{domain_b}` are both first-class concepts.
- Neither is merely a field of the other.
- The relationship itself is created, deleted, queried, or constrained.
- Multiple RPCs/routes express the same relationship from different perspectives.

```text
domains/{domain_a}/
domains/{domain_b}/
domains/{relation_domain}/
services/{relation_feature}/
  dto.{ext}
  service.{ext}
```

- The relation domain owns relationship mechanics only.
- It must not import the related domains directly.
- Existence checks, policy checks, and cross-domain composition belong in the service (flow).

### Edge / gateway placement

```text
apps/server/           # main + register only
services/{feature}/    # feature dto + orchestration
domains/{policy}/      # optional rules-only shared policy
modules/clients/       # downstream gRPC client factories
```

Forbidden in edge services: stuffing DTO/utils/policy into `apps/server/*` because “there is no domain”.

### infra

- config, db, logging, gRPC client factories, auth adapters, low-level helpers.
- No business logic or domain-specific helpers.
- Do not turn modules into a generic utilities dump.
- Modules must not import apps, services, or domains.

## Import direction

```text
entry -> flow -> domain -> infra
entry -> infra
flow  -> infra (including generated gRPC clients)
```

When `domains/` is omitted: `entry -> flow -> infra` (and `entry -> infra`).

Forbidden: handler→domain, domain→flow, cross-service source imports, new layers above flow, feature logic in entry.

## Editing scope

- Touch one `{service_name}` plus, if needed, `backend/proto` (and regenerate dist).
- Do not open `frontend/` or other platforms unless the user explicitly asks for a cross-change.
