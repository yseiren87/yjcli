# Build for platform "{{platform}}" (yjcli builder plugin; repository-owned).
#
# Read tools/builder/GUIDE.md, then implement Invoke-BuildOne below.
# Everything else - argument checks, service list, emptying
# dist\{{platform}}\<service>\, writing BUILD_INFO - already works.
# This is the entry point `make.ps1 {{platform}}-build-<env>` calls. It does not
# have to stay a single file: add helper scripts next to it and call them from here.
#
# Usage: tools/builder/{{platform}}/builder.ps1 <environment> [service]
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
# Invoke-BuildOne <service>
#   Build one service into $Out (= dist\{{platform}}\<service>\, already empty) so
#   that folder alone can run. Runs inside $PlatformDir\<service>.
{{#if env_files}}
#   Available: $Environment, $Out, $EnvFile (tools\secrets\...\.env.<env> - read it
#   only for build-time values; never copy it into $Out).
{{else}}
#   Available: $Environment, $Out. Never copy env value files into $Out.
{{/if}}
#   Check $LASTEXITCODE after each native command (`if ($LASTEXITCODE) { exit $LASTEXITCODE }`);
#   the skeleton checks only the last one.
function Invoke-BuildOne([string]$Name) {
    Write-Host "builder for $Platform/$Name is not implemented - read tools/builder/GUIDE.md"
    exit 1
    # Examples:
    # $env:CGO_ENABLED = "0"; $env:GOOS = "linux"; go build -o (Join-Path $Out "app") .
    # npm ci; npm run build; Copy-Item -Recurse dist\* $Out
    # uv build --wheel --out-dir $Out
}
# -----------------------------------------------------------------------------

# Any environment name: development and production come with every service; add more
# (staging, test, ...) by creating tools\secrets\<platform>\<service>\.env.<name>.
# local-dev is for local runs (tools/runner) only.
if (-not $Environment -or $Environment -eq "local-dev" -or $Environment -notmatch '^[A-Za-z0-9_-]+$') {
    Write-Host "usage: builder.ps1 <environment> [service]   (development, production, staging, ...)"
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
{{#if env_files}}

# The environment must exist for every service before anything is built.
$missing = $false
foreach ($name in $services) {
    if (-not (Test-Path (Join-Path (Join-Path $SecretsDir $name) ".env.$Environment"))) {
        Write-Host "[build] $Platform/${name}: missing tools/secrets/$Platform/$name/.env.$Environment"
        $missing = $true
    }
}
if ($missing) { exit 1 }
{{/if}}

# package.json / pyproject.toml version, else $env:VERSION, else "unknown".
function Resolve-Version([string]$Dir) {
    $v = $null
    $pkg = Join-Path $Dir "package.json"
    $py = Join-Path $Dir "pyproject.toml"
    if (Test-Path $pkg) {
        $m = Select-String -Path $pkg -Pattern '^\s*"version"\s*:\s*"([^"]+)"' | Select-Object -First 1
        if ($m) { $v = $m.Matches[0].Groups[1].Value }
    } elseif (Test-Path $py) {
        $m = Select-String -Path $py -Pattern '^version\s*=\s*"([^"]+)"' | Select-Object -First 1
        if ($m) { $v = $m.Matches[0].Groups[1].Value }
    }
    if (-not $v) { $v = $env:VERSION }
    if (-not $v) { $v = "unknown" }
    $v
}

function Assert-LastExit([string]$What) {
    if ($LASTEXITCODE) {
        Write-Host "$What failed with exit code $LASTEXITCODE"
        exit $LASTEXITCODE
    }
}
{{#if needs_proto}}

# This platform consumes the shared proto contract: generate it first.
$protoBuilder = Join-Path $RootDir "tools\builder\proto\builder.ps1"
if (Test-Path $protoBuilder) {
    Write-Host "[build] proto contract (tools/builder/proto/builder.ps1)"
    & $protoBuilder
    Assert-LastExit "proto codegen"
}
{{/if}}

# A failed build leaves no half-written output behind; BUILD_INFO marks a complete build.
$partial = $null
try {
    foreach ($name in $services) {
        $Out = Join-Path $DistDir $name
{{#if env_files}}
        $EnvFile = Join-Path (Join-Path $SecretsDir $name) ".env.$Environment"
{{/if}}
        Write-Host "[build] $Platform/$name ($Environment) -> dist/$Platform/$name"
        if (Test-Path $Out) { Remove-Item -Recurse -Force $Out }
        New-Item -ItemType Directory -Force -Path $Out | Out-Null
        $partial = $Out
        Push-Location (Join-Path $PlatformDir $name)
        try {
            $global:LASTEXITCODE = 0
            Invoke-BuildOne $name
            Assert-LastExit "build of $name"
        } finally {
            Pop-Location
        }
        @(
            "platform=$Platform"
            "service=$name"
            "environment=$Environment"
            "version=$(Resolve-Version (Join-Path $PlatformDir $name))"
            "built_at=$((Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ'))"
        ) | Set-Content -Path (Join-Path $Out "BUILD_INFO") -Encoding ascii
        $partial = $null
    }
} finally {
    if ($partial) { Remove-Item -Recurse -Force $partial -ErrorAction SilentlyContinue }
}
Write-Host "[build] done: $($services -join ' ')"
