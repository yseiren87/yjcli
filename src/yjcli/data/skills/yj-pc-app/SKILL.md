---
name: yj-pc-app
description: >-
  Single Electron desktop app architecture. Use only when editing pc-app/**.
  Stack may resemble frontend (React/TS) in the renderer, but process split
  (main/preload/renderer) is mandatory and different from frontend/. Do not use
  for frontend/, mobile-app/, backend/, backend-service/, cli/, or
  browser-extension/.
---

# yj-pc-app

Requires `yj-arch-core`. Scope: **`pc-app/` only**.

Stack: **Electron** + TypeScript; renderer typically React + react-router (same UI stack family as frontend, different architecture).

## Shape

```text
pc-app/
  scripts/         # platform-level only
  {app_name}/
    main/          # privileged process (backend-like)
    preload/       # bridge only
    renderer/      # UI (frontend-like)
```

One `{app_name}` = one desktop service.

## Processes

### main (`entry`, `flow`, `domain?`, `infra`)

```text
entry  = main/index.ts          # lifecycle, window, ipc registration only
flow   = main/services/{feature}.ts
domain = main/domains/{domain}/ # optional — owned concepts (fs/db and/or shared policy)
infra  = main/modules/{module}.ts
```

- ipc handlers thin → call flow. No feature DTO/policy dump in `main/index` or ipc registration files.
- `domains/` only when main owns a concept; repository optional (rules-only OK). Omit folder if none.
- Do not expose Node/fs directly to renderer.

### preload (`infra` bridge)

- `contextBridge` API only; thin `ipcRenderer.invoke` wrappers.
- No business logic. Keep channel/payload contract aligned with main + renderer api.

### renderer (`entry`, `flow`, `view`, `infra` — no domain)

```text
entry = renderer/src/main.tsx, App.tsx
flow  = stores + api (api talks to window bridge, not raw fetch to Node)
view  = pages/components
infra = lib/, hooks/
```

Same container/presentational split as frontend. No `renderer/src/domains/`.

## Import direction

```text
main entry -> main flow -> main domain? -> main infra
renderer view -> renderer store -> renderer api -> preload bridge
renderer must not import Node/Electron/fs
```

Missing main domain ≠ put logic in entry; keep orchestration in `main/services`.

## Contracts

- Prefer local ipc contract types shared carefully inside the app.
- If a future lang/client can consume `backend/proto/dist/{lang}`, symlink that dist — do not copy proto sources. Electron renderer often will not use gRPC stubs directly; do not force it.

## Environment gotchas

- Electron binary not auto-downloaded (`Error: Electron uninstall` / missing `node_modules/electron/dist`): `electron@42+` dropped the `postinstall` lifecycle script, so `npm install` may not fetch the binary.
  - One-off: `npx install-electron` (or `node node_modules/electron/install.js`).
  - Permanent: app `package.json` → `"scripts": { "postinstall": "install-electron" }` (real npm lifecycle name; `postinstall:electron` does **not** run).
  - Note: recent Electron majors may require a newer Node (check the package engines).

## Editing scope

- Stay in `pc-app/{app_name}/` and the process you are changing.
- Do not use `yj-frontend` as a substitute; renderer likeness ≠ same skill.
