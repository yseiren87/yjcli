## Optional: gRPC transport (protobuf)

Protobuf/gRPC is an **option**, not this platform's default, and choosing it
does **not** turn this into MSA. Enable only when a single service's own
external API is defined as proto. There is no shared multi-service contract
here, no fan-out to sibling services, and the cross-service "call only through
generated clients" rule from `yj-backend-msa` does not apply.

Keep the schema at `{platform}/proto/*.proto` with generated output in
`{platform}/proto/dist/{lang}` — the reserved location the build tooling
detects automatically. If more than one service under this platform needs its
own independent proto contract at the same time, that is a signal the units
belong in `backend-msa/` instead — do not invent a second proto location.

Codegen (protoc; buf is not used) is wired into the repository's build tooling
(see `yj-arch-core` › Tooling). Implement it there, not as an ad-hoc command.
