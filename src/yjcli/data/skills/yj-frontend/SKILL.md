---
name: yj-frontend
description: >-
  Single frontend app architecture. Required stack: Vite + React + TypeScript +
  react-router. Use only when editing frontend/**. Feature-level flow/view
  separation; no domain folder by default. No plain .env. Do not use for
  mobile-app/, pc-app/, backend/, backend-service/, cli/, or browser-extension/.
---

# yj-frontend

Requires `yj-arch-core`. Scope: **`frontend/` only**.

## Required stack

**Vite + React + TypeScript + react-router** (mandatory).  
Do not scaffold CRA, Next.js, Webpack-only, or non-Vite bundlers unless the user explicitly overrides.

## Shape

```text
frontend/
  scripts/                 # platform-level only
  {app_name}/
    src/
      main.tsx, App.tsx          # entry
      stores/{feature}.ts        # flow state/orchestration
      api/{feature}/             # flow API access/mapping
      pages/{feature}/           # container view
      components/{feature}/      # presentational view
      lib/, hooks/               # infra
```

One `{app_name}` = one web app. No micro-frontends unless the user requests it.

## Roles

```text
entry = src/main.tsx, src/App.tsx (routes)
flow  = stores/{feature}.ts + api/{feature}
view  = pages/{feature} + components/{feature} (+ generated ui primitives)
infra = lib/*, hooks/*
```

Flow and view use the same `{feature}` boundary under separate role roots. Do
not place a feature store or API module beside `pages/` or `components/` as if
it were a view.

**No `src/domains/` by default.** Model = API types; feature rules live in store/container (flow).  
Exception: heavy **client-owned** offline DB/engine concepts only (then optional domain slots per core).

Missing domain ≠ dump DTOs/utils into `main.tsx` / `App.tsx`. Keep feature work under stores/api.

## Rules

- Follow `yj-arch-core` env names; listen apps need `HOST`/`PORT`. No plain `.env`.
- `npm start` / local mode must mean local-dev — do not silently point bare start at development/production deploy envs.
- Store calls the same feature's `api`; pages/components do not call network directly.
- Keep one store file per feature directly under `stores/`; do not add a
  redundant `{feature}/` directory for a single store file.
- Container route wires store + router; presentational page takes props only.
- Routes declared at entry — do not scatter route tables; entry stays registration-thin.
- Generated UI primitives: do not hand-edit or duplicate.
- Consume backend contracts via generated client or `backend/proto/dist/{lang}` — never copy `.proto` into frontend.

## Optional: server templating (SSR)

Templating is an **option**, not this app's default. Most apps stay a
client-rendered SPA — enable only when this app must render HTML server-side
(e.g. a lightweight SSR/SSG entry alongside the Vite build).

When enabled, add sibling to `src/`:

```text
views/{page}.html | views/layouts/* | views/partials/*
```

- Template/asset bundling is wired the same way as other platforms:
  `plugin-build-ssr.sh` auto-detects `{app_name}/views/` and adds a build
  guard for it. Implement the bundling there, not as an ad-hoc one-off command.
- Keep `src/` (client bundle) and `views/` (server-rendered templates)
  separate; do not fold template markup into `pages/`/`components/`.
- Do **not** create `views/` speculatively — it does not apply to a normal
  client-only SPA.

## Import direction

```text
entry -> view
view (container) -> flow (store)
store -> api -> infra
view (presentational) -> props only
```

## Editing scope

- Stay inside `frontend/{app_name}/` (and linked contract dist if needed).
- Do not load Electron/Flutter skills for React web work.
