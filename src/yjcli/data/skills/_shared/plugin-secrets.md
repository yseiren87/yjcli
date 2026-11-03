### Secrets (`tools/secrets/`)

- Env values live only in `tools/secrets/<platform>/<service>/.env.<environment>`.
  Services keep `.env.examples` only — never create `.env*` value files inside
  a service folder.
- `.env.local-dev` is required. New services also start with `.env.development`
  and `.env.production`; remove unused ones or add others (`.env.staging`,
  `.env.test`, …) following the `.env.<environment>` naming pattern.
- These files are **committed in plain text** — the repository must stay
  private. Do not copy their values into code, docs, logs or commit messages.
- Value files list populated `FIELD=value` lines consecutively, without
  field-description comments or separator blank lines.
- When adding a field, add it to the service's `.env.examples` and to every
  `.env.<environment>` file of that service.
