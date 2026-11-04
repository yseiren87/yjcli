### Deployer (`tools/deployer/`)

- `make <platform>-deploy-<env> [NAME=<service>]` (`./make.ps1` on Windows) calls
  `tools/deployer/<platform>/deployer.sh` / `deployer.ps1`. It never builds.
- Follow `tools/deployer/GUIDE.md` (managed by yjcli — do not edit). Input is
  `dist/<platform>/<service>/` only; env values are injected at run time
  (`docker run --env-file tools/secrets/<platform>/<service>/.env.<env>`), never
  baked into an image. Dockerfiles live under `tools/deployer/<platform>/`.
  Implement only `deploy_one` / `Invoke-DeployOne`, keeping `.sh` and `.ps1` equivalent.
