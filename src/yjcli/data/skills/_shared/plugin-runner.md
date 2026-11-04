### Runner (`tools/runner/`)

- `make <platform> [NAME=<service>]` (`./make.ps1` on Windows) calls `tools/runner/<platform>/runner.sh` / `runner.ps1`.
- Follow `tools/runner/GUIDE.md` (managed by yjcli — do not edit). The scripts are repository-owned and must follow that guide (service discovery, `.env.local-dev`, concurrency, Ctrl+C); the per-service command lives in `run_one` / `Invoke-RunOne`. Keep `.sh` and `.ps1` equivalent, and re-check the scripts against the guide when yjcli updates it.
- Local runs always use `.env.local-dev` — do not hardcode HOST/PORT in scripts.
