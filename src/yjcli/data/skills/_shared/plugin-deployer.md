### Deployer (`tools/deployer/`)

- `make <platform>-deploy-<env> [NAME=<service>]` (`./make.ps1` on Windows) calls `tools/deployer/<platform>/deployer.sh` / `deployer.ps1`. It never builds.
- Follow `tools/deployer/GUIDE.md` (managed by yjcli — do not edit). Input is `dist/<platform>/<service>/` only; env values are injected at run time (with `tools/secrets/`: `docker run --env-file tools/secrets/<platform>/<service>/.env.<env>`), never baked into an image. Dockerfiles live under `tools/deployer/<platform>/`. The per-service deploy lives in `deploy_one` / `Invoke-DeployOne`. Keep `.sh` and `.ps1` equivalent, and re-check the scripts against the guide when yjcli updates it.
