### Secrets (`tools/secrets/`)

- Env values live only in `tools/secrets/<platform>/<service>/.env.<environment>`. Services keep `.env.examples` only — never create `.env*` value files inside a service folder.
- Every service has `.env.local-dev` (local runs) and `.env.production`. Other environments (`.env.development`, `.env.staging`, …) are added and removed for every service at once with `yjcli env add <env>` / `yjcli env remove <env>` — do not create or delete them by hand. An added environment works with `make <platform>-build-<env>` / `make <platform>-deploy-<env>`.
- These files are **committed in plain text** — the repository must stay private. Do not copy their values into code, docs, logs or commit messages.
- Value files list populated `FIELD=value` lines consecutively, without field-description comments or separator blank lines. Values are literal: no quotes, no `export`, no multi-line values (the `docker --env-file` format).
- When adding a field, add it to the service's `.env.examples` and to every `.env.<environment>` file of that service.
{{#if no_secrets}}
- No `tools/secrets/` for {{no_secrets_platforms}} (chosen in yjcli): env values there come from the project's own mechanism. Do not create `tools/secrets/` folders for those platforms; ask the user to turn it on with `yjcli secrets on <platform>` instead.
{{/if}}
