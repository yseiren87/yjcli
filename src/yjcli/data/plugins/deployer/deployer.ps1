# Deploy for platform "{{platform}}" (yjcli deployer plugin; repository-owned).
#
# Read tools/deployer/GUIDE.md, then implement Invoke-DeployOne below. Everything
{{#if env_files}}
# else - argument checks, service list, checking that dist\{{platform}}\<service>\
# and the env file exist, warning on a BUILD_INFO environment mismatch - already works.
{{else}}
# else - argument checks, service list, checking that dist\{{platform}}\<service>\
# exists, warning on a BUILD_INFO environment mismatch - already works. This
# platform has no tools/secrets/: the target supplies env values at run time.
{{/if}}
# The deployer never builds: run `make.ps1 {{platform}}-build-<env>` first.
# This is the entry point `make.ps1 {{platform}}-deploy-<env>` calls. It does not
# have to stay a single file: add helper scripts next to it and call them from here.
#
# Usage: tools/deployer/{{platform}}/deployer.ps1 <environment> [service]
param(
    [string]$Environment = "",
    [string]$Service = ""
)
$ErrorActionPreference = "Stop"

$ScriptDir = $PSScriptRoot
$RootDir = (Resolve-Path (Join-Path $ScriptDir "..\..\..")).Path
$Platform = Split-Path $ScriptDir -Leaf
$PlatformDir = Join-Path $RootDir $Platform
{{#if env_files}}
$SecretsDir = Join-Path (Join-Path $RootDir "tools\secrets") $Platform
{{/if}}
$DistDir = Join-Path (Join-Path $RootDir "dist") $Platform

# ---------------------------------------------------------------- implement me
# Invoke-DeployOne <service>
#   Deploy the build in $In (= dist\{{platform}}\<service>\). Runs inside $In.
{{#if env_files}}
#   Available: $Environment, $In, $EnvFile (tools\secrets\...\.env.<env>),
#   $ScriptDir (keep a Dockerfile etc. here, not in the service folder).
{{else}}
#   Available: $Environment, $In, $ScriptDir (keep a Dockerfile etc. here, not
#   in the service folder).
{{/if}}
#   Check $LASTEXITCODE after each native command (`if ($LASTEXITCODE) { exit $LASTEXITCODE }`);
#   the skeleton checks only the last one.
function Invoke-DeployOne([string]$Name) {
    Write-Host "deployer for $Platform/$Name is not implemented - read tools/deployer/GUIDE.md"
    exit 1
    # Docker (the image only copies $In; env comes in at run time, never baked):
    # docker build -t "${Name}:$Environment" -f (Join-Path $ScriptDir "Dockerfile") $In
{{#if env_files}}
    # docker run -d --name $Name --env-file $EnvFile "${Name}:$Environment"
{{else}}
    # docker run -d --name $Name "${Name}:$Environment"   # env values from the target
{{/if}}
    # Other targets:
    # scp -r "$In\*" "server:/srv/$Name/"
    # aws s3 sync $In "s3://example-$Environment/$Name/"
}
# -----------------------------------------------------------------------------

# Any environment name: development and production come with every service; add more
# (staging, test, ...) by creating tools\secrets\<platform>\<service>\.env.<name>.
# local-dev is for local runs (tools/runner) only.
if (-not $Environment -or $Environment -eq "local-dev" -or $Environment -notmatch '^[A-Za-z0-9_-]+$') {
    Write-Host "usage: deployer.ps1 <environment> [service]   (development, production, staging, ...)"
    exit 1
}

if ($Service) {
    if (-not (Test-Path (Join-Path $PlatformDir $Service) -PathType Container)) {
        Write-Host "unknown service: $Service (expected $PlatformDir\$Service)"
        exit 1
    }
    $services = @($Service)
} else {
    $services = @(Get-ChildItem -Path $PlatformDir -Directory |
        Sort-Object Name | ForEach-Object { $_.Name })
}
if ($services.Count -eq 0) {
    Write-Host "no services under $PlatformDir"
    exit 1
}

# Check every service before deploying any of them.
$missing = $false
foreach ($name in $services) {
    if (-not (Test-Path (Join-Path (Join-Path $DistDir $name) "BUILD_INFO"))) {
        Write-Host "[deploy] $Platform/${name}: no build in dist/$Platform/$name - run: make.ps1 $Platform-build-$Environment NAME=$name"
        $missing = $true
    }
{{#if env_files}}
    if (-not (Test-Path (Join-Path (Join-Path $SecretsDir $name) ".env.$Environment"))) {
        Write-Host "[deploy] $Platform/${name}: missing tools/secrets/$Platform/$name/.env.$Environment"
        $missing = $true
    }
{{/if}}
}
if ($missing) { exit 1 }

foreach ($name in $services) {
    $In = Join-Path $DistDir $name
{{#if env_files}}
    $EnvFile = Join-Path (Join-Path $SecretsDir $name) ".env.$Environment"
{{/if}}
    $built = (Get-Content (Join-Path $In "BUILD_INFO") | Where-Object { $_ -like "environment=*" } |
        Select-Object -First 1) -replace "^environment=", ""
    if ($built -ne $Environment) {
        Write-Host "[deploy] warning: dist/$Platform/$name was built for $built, deploying to $Environment"
    }
    Write-Host "[deploy] $Platform/$name ($Environment)"
    Push-Location $In
    try {
        $global:LASTEXITCODE = 0
        Invoke-DeployOne $name
        if ($LASTEXITCODE) {
            Write-Host "deploy of $name failed with exit code $LASTEXITCODE"
            exit $LASTEXITCODE
        }
    } finally {
        Pop-Location
    }
}
Write-Host "[deploy] done: $($services -join ' ')"
