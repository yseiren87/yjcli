---
name: yj-browser-extension
description: >-
  Browser extension architecture (MV3, JS/TS). Use when editing
  browser-extension/** except native_*/** paths. Covers background, content
  scripts, and popup/options as one extension service with multiple contexts.
  For browser-extension/native_*/**, use yj-backend-service instead. Do not use
  for frontend/, mobile-app/, pc-app/, backend/, backend-service/, or cli/.
---

# yj-browser-extension

Requires `yj-arch-core`. Scope: **`browser-extension/`** excluding **`native_*/`**.

## Shape

```text
browser-extension/
  scripts/            # platform-level only
  {extension_name}/
    manifest.json
    src/
      background/     # privileged entry + flow
      content/        # view/adapters per site
      popup/          # view
      lib/            # infra
  native_{name}/      # NOT this skill → yj-backend-service
```

One `{extension_name}` = one extension service (multi-context, not microservices).

## Contexts

```text
background = entry + flow (chrome.* privileges, message router)
content    = view/DOM adapter (per site)
popup/options = view
lib        = infra
```

No `domain` folder in the extension UI/background by default. Durable state → `chrome.storage` or a companion `native_*` / remote backend.  
Feature rules and orchestration live in background flow — not in listeners/`apps`-style entry dumps.

### background

- Listeners register and route to `services/{feature}` (or equivalent flow modules).
- Orchestrate downloads, DNR, fetch, native messaging from flow — not from raw listeners with business logic or DTO piles.
- MV3 background is a **non-persistent service worker**: do not rely on module-level globals surviving restarts. Persist durable state in `chrome.storage` (or native host / remote backend).

### content

- One module per site/target. Message background for privileged work.
- Split isolated vs MAIN world only when page globals are required.

### popup/options

- UI only; talk to background via messaging.

## native_host

- Folder name: `native_{name}/` under `browser-extension/`.
- Architecture: **`yj-backend-service`** (single local process).
- When editing `native_*`, do not apply extension UI rules; load `yj-backend-service`.
- Extension ↔ host contract stays explicit (native messaging / local HTTP).

## Import direction

```text
content/popup -> messaging -> background entry -> background flow -> lib / chrome.*
lib must not import background/content/popup
```

Forbidden: content↔content business coupling; UI calling privileged chrome APIs that belong in background.

## Editing scope

- One `{extension_name}` context at a time when possible.
- Companion host changes → switch to `yj-backend-service`.
