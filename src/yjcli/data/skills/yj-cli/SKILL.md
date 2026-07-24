---
name: yj-cli
description: >-
  Single CLI application architecture, language-agnostic. Use only when editing
  cli/**. Commands are routes; optional domains only when the CLI owns local
  persistence. Do not use for backend/, backend-service/, frontend/,
  mobile-app/, pc-app/, or browser-extension/.
---

# yj-cli

Requires `yj-arch-core`. Scope: **`cli/` only**.

## Shape

```text
cli/
  scripts/       # platform-level only
  {app_name}/
    apps/        # entry — command tree
    services/    # flow
    domains/     # only if persistence-owning
    modules/     # infra
```

One `{app_name}` = one CLI service.

## Two shapes

```text
persistence-owning cli  -> uses domain (local db/files)
remote-client cli       -> no domain; clients in modules; rules in services
```

## Roles

```text
entry  = apps/{app_name}/main.{ext} (+ optional command group files same package)
flow   = services/{feature}/dto.{ext} + service.{ext}
domain = domains/{domain}/...   # persistence-owning only
infra  = modules/{module}.{ext} # config, http, db, output formatters
```

### entry

- Build root command, register subcommands, wire deps, dispatch.
- Command handlers: parse flags/args → call flow → format output. No business logic / no direct domain.

### flow

- Feature operations. Return data or domain errors; do not print or parse argv.
- Reuse across commands; do not create one service per command automatically.

### domain

- Only when CLI persists locally. No knowledge of flags/stdout formats.

### infra

- Printing helpers OK; **what** to print is decided in the command (entry).

## Import direction

```text
entry -> flow -> domain -> infra
entry -> infra
flow  -> infra
```

Forbidden: command→domain/db/http directly; service→stdout/argv; cross-platform source imports.

## Editing scope

- `cli/{app_name}/` only.
- Native messaging hosts that belong to extensions live under `browser-extension/native_*` and use `yj-backend-service`, not this skill — unless the user places a pure CLI under `cli/`.
