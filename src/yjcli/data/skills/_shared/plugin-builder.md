### Builder (`tools/builder/`)

- `make <platform>-build-<env> [NAME=<service>]` (`./make.ps1` on Windows) calls `tools/builder/<platform>/builder.sh` / `builder.ps1` with `<env>` = `development`, `production` or any environment added as `tools/secrets/<platform>/<service>/.env.<env>`.
- Follow `tools/builder/GUIDE.md` (managed by yjcli — do not edit). Builds go to `dist/<platform>/<service>/` at the repository root, runnable on their own and without env value files. The per-service build lives in `build_one` / `Invoke-BuildOne` (proto codegen in `gen_<language>`). Keep `.sh` and `.ps1` equivalent, and re-check the scripts against the guide when yjcli updates it.
