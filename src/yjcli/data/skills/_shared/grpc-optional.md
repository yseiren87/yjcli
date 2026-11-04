## Optional: gRPC transport (protobuf)

Protobuf/gRPC is an **option** here, not this platform's default, and choosing it does **not** turn this into MSA. Use it only when a service's own external API is defined as proto. The cross-service "call only through generated clients" rule from `yj-backend-msa` does not apply.

The schema still lives in the shared root contract (see "Shared proto contract" below) — this platform has no proto location of its own. If several services here need gRPC contracts with each other, that is a signal the units belong in `backend-msa/` instead.
