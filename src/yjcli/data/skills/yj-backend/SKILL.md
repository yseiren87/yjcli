---
name: yj-backend
description: >-
  Single deployable backend service architecture (API / worker / native host,
  non-MSA, no server templating). Language-agnostic. Optional gRPC/protobuf
  transport is an add-on chapter — choosing gRPC does not make this MSA.
  Domains are optional owned concepts (not persistence-only). Use only when
  editing {{self_routes}}.
---

# yj-backend

Requires `yj-arch-core`. Scope: {{self_routes}}.

## Shape

```text
backend/
  {service_name}/
    apps/               # entry
    services/           # flow
    domains/            # domain (optional — owned concepts only)
    modules/            # infra
  proto/                # optional — only with the gRPC option
```

No `views/` here: server-rendered HTML belongs in `backend-ssr/` (`yj-backend-ssr`).

`browser-extension/native_{name}/` uses the same roles and the `worker` env kind. Call it a native host service, not an MSA node.

`HOST`/`PORT` are required for `backend/` services (listen) and optional for native hosts — add them only when the process actually listens.

{{include:backend-base.md}}

{{include:grpc-optional.md}}

## native_host notes

- Lives under `browser-extension/native_{name}/`.
- Follow this skill's structure; the messaging contract with the extension is an infra/entry concern.
- Do not put Chrome extension UI code inside `native_*`.

## Editing scope

- One `{service_name}` (or one `native_{name}`) only.
- Do not apply MSA/proto rules from `yj-backend-msa` unless the user moves the unit into `backend-msa/`.
