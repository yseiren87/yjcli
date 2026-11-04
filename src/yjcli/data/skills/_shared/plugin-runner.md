### Runner (`tools/runner/`)

- `make <platform> [NAME=<service>]` (`./make.ps1` on Windows) calls `tools/runner/<platform>/runner.sh` / `runner.ps1`.
- Follow `tools/runner/GUIDE.md` (managed by yjcli — do not edit). The scripts are repository-owned: the skeleton already handles service discovery, `.env.local-dev`, concurrency and Ctrl+C; implement only `run_one` / `Invoke-RunOne`, keeping `.sh` and `.ps1` equivalent.
- Local runs always use `.env.local-dev` — do not hardcode HOST/PORT in scripts.
