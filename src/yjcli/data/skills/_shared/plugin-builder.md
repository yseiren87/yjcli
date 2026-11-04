### Builder (`tools/builder/`)

- `make <platform>-build-<env> [NAME=<service>]` (`./make.ps1` on Windows) calls `tools/builder/<platform>/builder.sh` / `builder.ps1` with `<env>` = `development` | `production`.
- Follow `tools/builder/GUIDE.md` (managed by yjcli — do not edit). Builds go to `dist/<platform>/<service>/` at the repository root, runnable on their own and without env value files. Implement only `build_one` / `Invoke-BuildOne` (and the proto function where present), keeping `.sh` and `.ps1` equivalent.
