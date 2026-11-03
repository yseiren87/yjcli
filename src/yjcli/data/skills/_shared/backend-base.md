## Roles

Roles: `entry`, `flow`, `domain?`, `infra`.

```text
entry  = apps/{app_name}/main.{ext}     # wiring only
flow   = services/{feature}/dto.{ext} + service.{ext}
domain = domains/{domain}/…             # optional slots
infra  = modules/{module}.{ext}
```

Same import rules as core: entry→flow→domain→infra (skip domain hop when omitted). Handlers stay thin — no DTO/policy/utils dump in `apps/`.

### domain (owned concept)

Create `domains/` only when this process owns a concept (authority). Persistence is optional.

File slots (use only what exists):

- `model.{ext}`: internal domain model, entity, schema, or data shape.
- `repository.{ext}`: persistence/retrieval — only if stored here.
- `rules.{ext}`: domain-specific decisions and pure validations.
- `errors.{ext}` / `types.{ext}`: domain errors and value types.

Rules:

- Valid: data+rules · data only · rules only.
- No HTTP/transport/template types in domain.
- Domains must not import apps or services.
- No domain→domain imports; compose in flow.
- Do not duplicate the same responsibility across multiple domains.

### Relation domain

When two first-class domains have a managed relationship, add `domains/{relation_domain}/` for relationship mechanics only; compose related domains in a service. The relation domain must not import the related domains directly.

### Remote-only / proxy / thin host

If the process owns **no** local concept (only calls remote APIs / messaging):

- Omit `domains/`.
- Clients in `modules`; feature orchestration + feature-local rules in `services`.
- If a **shared** policy grows across features, prefer a small rules-only domain over stuffing `apps/`.
