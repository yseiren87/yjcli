---
name: dj-backend-service
description: >-
  Single deployable backend service architecture (non-MSA). Use when editing
  backend-service/** or browser-extension/native_*/**. Language-agnostic.
  Optional server-templating/SSR is an add-on chapter, not a separate platform.
  Do not use for backend/ (MSA), frontend/, mobile-app/, pc-app/, cli/, or
  browser-extension UI/background (non-native_*) paths.
---

# dj-backend-service

Requires `dj-arch-core`. Scope: **`backend-service/`** and **`browser-extension/native_*/`**.

## Shape

```text
backend-service/
  scripts/              # platform-level only
  {service_name}/
    apps/               # entry
    services/           # flow
    domains/            # domain (if this process owns persistence)
    modules/            # infra
    views/              # optional — only if SSR/templating enabled
```

`browser-extension/native_{name}/` uses the same roles and the same env templates as `backend-service` (scaffolded from `templates/platform/backend-service/`). Prefer calling it a native host service, not an MSA node, unless the user explicitly adopts MSA.

`HOST`/`PORT` are **optional** here — add them to `.env.*` only when the process actually listens.

## Default (API / worker / native host)

Roles: `entry`, `flow`, `domain` (if persistence), `infra`. No `view`.

```text
entry  = apps/{app_name}/main.{ext}
flow   = services/{feature}/dto.{ext} + service.{ext}
domain = domains/{domain}/model.{ext} (+ repository/rules/errors/types)
infra  = modules/{module}.{ext}
```

Same import rules as core: entry→flow→domain→infra. Handlers stay thin.

### domain (when persistence exists)

File responsibilities:

- `model.{ext}`: internal domain model, entity, schema, or data shape.
- `repository.{ext}`: persistence and retrieval using the domain model.
- `rules.{ext}`: domain-specific decision rules and pure validations (optional).
- `errors.{ext}` / `types.{ext}`: domain errors and value types (optional).

Rules:

- No HTTP/transport/template types in domain.
- Domains must not import apps or services.
- No domain→domain imports; compose in flow.
- Do not duplicate the same responsibility across multiple domains.

### Relation domain

Same rule as MSA: when two first-class domains have a managed relationship, add `domains/{relation_domain}/` for relationship mechanics only; compose related domains in a service. The relation domain must not import the related domains directly.

### Remote-only process

If the process has **no** local persistence (proxy/native host that only calls remote APIs): skip `domains/`; keep clients in `modules`, rules in `services`.

## Optional: server templating (SSR/MPA)

Templating is an **option**, not the folder identity. Enable only when the service must render HTML.

When enabled, add role `view`:

```text
view = views/{feature}/{page}.html | views/layouts/* | views/partials/*
```

Extra rules:

- Handlers: parse → call flow → build template context → render. No DB in handlers.
- flow returns plain data / view models — never HTML.
- templates: presentation only; no DB/service/domain calls.
- If the service is JSON-API only, do **not** create `views/`.

Guide when adding SSR later:

1. Add template engine wiring in `modules` + `apps`.
2. Add `views/` layout/partials.
3. Keep existing API flows reusable; do not fork business logic into templates.

## native_host notes

- Lives under `browser-extension/native_{name}/`.
- Follow this skill's structure; messaging contract with the extension is infra/entry concern.
- Do not put Chrome extension UI code inside `native_*`.

## Editing scope

- One `{service_name}` (or one `native_{name}`) only.
- Do not apply MSA/proto rules from `dj-backend-msa` unless the user migrates the unit into `backend/`.
