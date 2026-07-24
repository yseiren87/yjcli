---
name: yj-mobile-app
description: >-
  Single mobile app architecture (Flutter). Use only when editing mobile-app/**.
  Same base architecture as frontend (entry/flow/view/infra, no domain by
  default) with Flutter/Dart primitives. Do not use for frontend/, pc-app/,
  backend/, backend-service/, cli/, or browser-extension/.
---

# yj-mobile-app

Requires `yj-arch-core`. Scope: **`mobile-app/` only**.

Stack: **Flutter (Dart)** + the repo's router/state choices (e.g. go_router, riverpod).

## Shape

```text
mobile-app/
  scripts/                   # platform-level only
  {app_name}/
    lib/
      main.dart, router.dart       # entry
      providers/{feature}_*.dart   # flow
      api/{feature}_api.dart       # flow
      screens/...                  # view
      widgets/...                  # view
      lib/ or core/                # infra
```

One `{app_name}` = one mobile service.

## Roles (same base as frontend)

```text
entry = main + router
flow  = providers + api
view  = screens (container) + presentational views/widgets
infra = shared clients/formatters/utils
```

**No `lib/domain/` by default.** Exception: offline DB/engine-heavy client logic.

## Rules

- Provider/store calls api; widgets do not call network directly.
- Container screen watches providers and passes plain props to presentational widgets.
- Routes declared at entry.
- Prefer symlink/consume `backend/proto/dist/dart` for MSA contracts when present. Do not copy `.proto` into the app.

## Import direction

```text
entry -> view
view (container) -> flow
flow -> api -> infra
view (presentational) -> constructor params only
```

## Editing scope

- `mobile-app/{app_name}/` only (+ linked proto dist if needed).
- Do not apply React/Electron folder conventions here.
