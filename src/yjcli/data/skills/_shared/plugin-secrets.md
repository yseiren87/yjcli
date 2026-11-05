### Secrets (`tools/secrets/`)

- Env values live only in `tools/secrets/<platform>/<service>/.env.<environment>`. Services keep `.env.examples` only — never create `.env*` value files inside a service folder.
- `.env.local-dev` is required (local runs). New services also start with `.env.development` and `.env.production`; remove unused ones or add others (`.env.staging`, `.env.test`, …) following the `.env.<environment>` naming pattern. An added environment works with `make <platform>-build-<environment>` / `make <platform>-deploy-<environment>` once every service of that platform has its file.
- These files are **committed in plain text** — the repository must stay private. Do not copy their values into code, docs, logs or commit messages.
- Value files list populated `FIELD=value` lines consecutively, without field-description comments or separator blank lines. Values are literal: no quotes, no `export`, no multi-line values (the `docker --env-file` format).
- When adding a field, add it to the service's `.env.examples` and to every `.env.<environment>` file of that service.
{{#if no_secrets}}
- No `tools/secrets/` for {{no_secrets_platforms}} (chosen in yjcli): env values there come from the project's own mechanism. Do not create `tools/secrets/` folders for those platforms; ask the user to turn it on with `yjcli secrets on <platform>` instead.
{{/if}}
