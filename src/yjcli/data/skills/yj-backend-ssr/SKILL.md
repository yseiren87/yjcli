---
name: yj-backend-ssr
description: >-
  Single deployable server-rendered backend (SSR/MPA) architecture,
  language-agnostic. Server templating is mandatory here (views/), on top of
  the single-backend roles; optional gRPC/protobuf transport is an add-on
  chapter. Use only when editing {{self_routes}}.
---

# yj-backend-ssr

Requires `yj-arch-core`. Scope: {{self_routes}}.

## Shape

```text
backend-ssr/
  {service_name}/
    apps/               # entry
    services/           # flow
    domains/            # domain (optional — owned concepts only)
    modules/            # infra
    views/              # view — templates (required)
```

`HOST`/`PORT` are required (listen).

{{include:backend-base.md}}

## Server templating (SSR/MPA)

Every service renders HTML, so role `view` is always present:

```text
view = views/{feature}/{page}.html | views/layouts/* | views/partials/*
```

Rules:

- Handlers: parse → call flow → build template context → render. No DB in handlers.
- flow returns plain data / view models — never HTML.
- templates: presentation only; no DB/service/domain calls.
- Template engine wiring lives in `modules` + `apps`.
- Keep API flows reusable; do not fork business logic into templates.
- Template/asset bundling is wired into the repository's build tooling, which detects `views/` per service (see `yj-arch-core` › Tooling). Implement it there, not as an ad-hoc command.
- A JSON-API-only service belongs in `backend/` (`yj-backend`), not here.

{{include:grpc-optional.md}}

{{include:proto-contract.md}}

## Editing scope

- One `{service_name}` only.
- Do not apply MSA/proto rules from `yj-backend-msa`.
