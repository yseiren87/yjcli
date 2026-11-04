## Shared proto contract

- The gRPC/protobuf contract lives **only** at the repository root: schemas in `proto/*.proto`, generated libraries in `proto/dist/<lang>/` (skill `yj-proto`). It belongs to no platform.
- Before adding or calling a gRPC API, look for the root `proto/` and work there. Never create a `proto/` folder or a `.proto` file inside a platform or service folder, and never copy `.proto` files or generated code into one.
- If the repository has no root `proto/` (or not the language you need under `proto/dist/`), stop and ask the user to add it with yjcli (`yjcli start` → platform `proto`, choosing the language) instead of creating it by hand.
- Consume the generated library through a path dependency on `proto/dist/<lang>/`: Go `require` + `replace`, Dart `path:` dependency, Python editable path dependency. Do not edit generated code — change the `.proto` and regenerate (see `yj-arch-core` › Tooling).
