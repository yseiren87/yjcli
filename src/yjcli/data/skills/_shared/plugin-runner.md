### Runner (`tools/runner/`)

- Root `make <platform>` starts every service of that platform concurrently;
  `make <platform> NAME=<service>` starts one. Both call
  `tools/runner/run.sh <platform> [service]` (`run.bat` / `run.ps1` on Windows).
- `tools/runner/` and the root `Makefile` / `make.bat` are managed by yjcli and
  regenerated — do not edit them.
- Each service declares its repository-owned local command as `RUN_COMMAND` in
  `tools/secrets/<platform>/<service>/.env.local-dev`. The runner exports that
  file and executes the declaration; it never infers commands from
  `package.json`, `pyproject.toml`, `go.mod`, or other manifests.
- Local runs always use `.env.local-dev` — do not hardcode HOST/PORT in scripts.
