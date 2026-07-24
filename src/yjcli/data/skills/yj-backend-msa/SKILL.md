---
name: yj-backend-msa
description: >-
  Backend MSA architecture with mandatory gRPC/protobuf. Use only when creating
  or editing code under backend/. Language-agnostic (Go/Python/Java/etc.).
  Covers backend/{service}, backend/proto, and proto/dist/{lang}. Do not use for
  backend-service/, frontend/, mobile-app/, pc-app/, cli/, or browser-extension/.
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
    domains/               # domain
    modules/               # infra
```

- One `{service_name}` = one deployable microservice.
- Do not over-split domains into tiny services. Split by cohesive business capability.
- gRPC + protobuf are **mandatory**. External API surface is proto, not ad-hoc JSON structs copied across services.

## proto

- Sources live only in `backend/proto/`.
- Generated stubs go to `backend/proto/dist/{lang}/`.
- Other platforms (e.g. `mobile-app`) may **symlink** to `backend/proto/dist/{lang}` — they must not own `.proto` copies.
- Prefer package boundaries in proto that align with service boundaries.

## Roles inside `{service_name}`

```text
entry  = apps/{app_name}/main.{ext}
flow   = services/{feature}/dto.{ext} + service.{ext}
domain = domains/{domain}/model.{ext} (+ repository/rules/errors/types)
infra  = modules/{module}.{ext}
```

### entry

- Init, gRPC server registration, dependency wiring only.
- No business logic. No direct domain calls (always through flow).

### flow

- Feature/workflow composition. DTOs for this service's use of contracts.
- Reuse services across RPCs; do not create a service per RPC automatically.
- Do not import other services' source trees; call them over gRPC using generated clients.

### domain

File responsibilities:

- `model.{ext}`: internal domain model, entity, schema, or data shape.
- `repository.{ext}`: persistence and retrieval using the domain model.
- `rules.{ext}`: domain-specific decision rules and pure validations (optional).
- `errors.{ext}`: domain-specific errors or exceptions (optional).
- `types.{ext}`: enums, value types, and domain-only type definitions (optional).

Rules:

- Persistence + rules for concepts this service owns.
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

Forbidden: handler→domain, domain→flow, cross-service source imports, new layers above flow.

## Editing scope

- Touch one `{service_name}` plus, if needed, `backend/proto` (and regenerate dist).
- Do not open `frontend/` or other platforms unless the user explicitly asks for a cross-change.
