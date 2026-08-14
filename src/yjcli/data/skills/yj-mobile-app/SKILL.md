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
      providers/{feature}.dart     # flow state/orchestration
      repositories/{feature}.dart  # optional flow data-source composition/mapping
      api/{feature}.dart           # infra remote client
      screens/{feature}/           # container view
      widgets/{feature}/           # presentational view
      lib/ or core/                # infra
```

One `{app_name}` = one mobile service.

## Roles (same base as frontend)

```text
entry = main + router
flow  = providers/{feature}.dart + repositories/{feature}.dart
view  = screens/{feature} + widgets/{feature}
infra = api/{feature}.dart clients + shared clients/formatters/utils
```

Flow and view use the same `{feature}` boundary under separate role roots. A
feature repository belongs to flow, not beside `screens/` or `widgets/` as a
view-level module.

Use a repository only when it composes data sources, cache, mapping, or feature
IO. A thin remote transport client belongs at `api/{feature}.dart` as infra; do
not add a repository that merely forwards every API call.

**No `lib/domain/` by default.** Feature rules live in providers (flow).  
Exception: heavy **client-owned** offline DB/engine concepts only.

Missing domain ≠ put feature logic in `main.dart` / router registration.

## Rules

- Provider calls its feature repository when composition is needed; otherwise
  it may call the feature `api` directly. Widgets do not call repositories or
  network clients directly.
- Keep one file per feature directly under `providers/`, `repositories/`, and
  `api/`; do not add a redundant `{feature}/` directory for a single file.
- Container screen watches providers and passes plain props to presentational widgets.
- Routes declared at entry (thin); feature work stays in providers/api.
- Prefer symlink/consume `backend/proto/dist/dart` for MSA contracts when present. Do not copy `.proto` into the app.

## Import direction

```text
entry -> view
view (container) -> flow
flow -> infra (including api)
view (presentational) -> constructor params only
```

## Editing scope

- `mobile-app/{app_name}/` only (+ linked proto dist if needed).
- Do not apply React/Electron folder conventions here.
