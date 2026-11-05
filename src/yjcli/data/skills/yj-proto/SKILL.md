---
name: yj-proto
description: >-
  Shared gRPC/protobuf contract at the repository root: proto/*.proto schemas
  and generated per-language libraries in proto/dist/<lang>/ (Go, Dart,
  Python), consumed by other platforms through path dependencies. Use only
  when editing {{self_routes}}.
---

# yj-proto

Requires `yj-arch-core`. Scope: {{self_routes}}.

## Shape

```text
proto/                      # the only proto location in the repository
  {domain}/v1/*.proto       # schemas (flat proto/*.proto is fine while small)
  dist/
    go/        go.mod       # module {{proto_go_module}}
    dart/      pubspec.yaml # package {{proto_dart_package}}, code in lib/
    python/    pyproject.toml  # distribution {{proto_python_dist}}, package {{proto_python_package}}/
```

Only the languages chosen in yjcli exist under `dist/`. Adding a language is a yjcli change (`yjcli proto add <language>`), not a hand-made folder.

## Schemas

- One `package` per domain and major version: `{domain}.v1`. Directory path mirrors the package.
- Name services `{Thing}Service`, RPCs as verbs (`GetOrder`, `ListOrders`), and give every RPC its own `{Rpc}Request` / `{Rpc}Response` messages.
- Set language options so generated paths are stable, e.g. `option go_package = "{{proto_go_module}}/{domain}/v1;{domain}v1";`.
- Keep schemas transport-only: no business rules in comments that code must parse, no service-internal types.

## Compatibility

- Never change a field's number or type, and never reuse a removed number or name — mark it `reserved`.
- Add fields and RPCs; do not repurpose them. A breaking change is a new package version (`v2`) alongside the old one until every consumer moves.
- Consumers in this repository update in the same change as the schema when they must.

## Generated libraries

- `proto/dist/<lang>/` is generated code plus its library manifest. Never edit generated files; change the `.proto` and regenerate.
- Keep the manifest (`go.mod` / `pubspec.yaml` / `pyproject.toml`); Go also keeps `go.sum`. No lock files (`pubspec.lock`, `uv.lock`) — consumers own them.
- Generated code is committed so consumers and CI build without protoc.
{{#if builder}}
- Codegen uses protoc (buf is not used) and runs through `make proto-build` (`tools/builder/proto/builder.sh`, one `gen_<language>` function per language — see `tools/builder/GUIDE.md`). Implement it there, not as an ad-hoc command.
{{else}}
- Codegen uses protoc (buf is not used). The builder plugin, which hosts it (`make proto-build`), is not installed: ask the user to add it (`yjcli plugin add builder`) instead of writing an ad-hoc script.
{{/if}}

## Consumers

- Other platforms depend on `proto/dist/<lang>/` by path: Go `require {{proto_go_module}} v0.0.0` + `replace {{proto_go_module}} => <relative path>`, Dart `{{proto_dart_package}}: { path: <relative path> }`, Python editable path dependency on `proto/dist/python`.
- No consumer keeps its own copy of `.proto` files or generated code.

## AI scope

- Stay in `proto/` unless the task also updates a consumer for a schema change.
- After changing a schema, regenerate every language under `dist/`.
