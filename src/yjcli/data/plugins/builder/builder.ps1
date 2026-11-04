# Build for platform "{{platform}}" (yjcli builder plugin; repository-owned).
#
# Read tools/builder/GUIDE.md, then implement Invoke-BuildOne below{{#if proto}} (and Invoke-BuildProto){{/if}}.
# Everything else - argument checks, service list, emptying
# dist\{{platform}}\<service>\, writing BUILD_INFO - already works.
# This is the entry point `make.ps1 {{platform}}-build-<env>` calls. It does not
# have to stay a single file: add helper scripts next to it and call them from here.
#
# Usage: tools/builder/{{platform}}/builder.ps1 <development|production> [service]
param(
    [string]$Environment = "",
    [string]$Service = ""
)
$ErrorActionPreference = "Stop"

$ScriptDir = $PSScriptRoot
$RootDir = (Resolve-Path (Join-Path $ScriptDir "..\..\..")).Path
$Platform = Split-Path $ScriptDir -Leaf
$PlatformDir = Join-Path $RootDir $Platform
$SecretsDir = Join-Path (Join-Path $RootDir "tools\secrets") $Platform
$DistDir = Join-Path (Join-Path $RootDir "dist") $Platform

# ---------------------------------------------------------------- implement me
# Invoke-BuildOne <service>
#   Build one service into $Out (= dist\{{platform}}\<service>\, already empty) so
#   that folder alone can run. Runs inside $PlatformDir\<service>.
#   Available: $Environment, $Out, $EnvFile (tools\secrets\...\.env.<env> - read it
#   only for build-time values; never copy it into $Out).
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
{{#if proto}}

# Invoke-BuildProto
#   Generate code from $PlatformDir\proto\*.proto into $PlatformDir\proto\dist\<lang>\.
#   Runs once before the services when $PlatformDir\proto\ exists.
function Invoke-BuildProto {
    Write-Host "proto codegen for $Platform is not implemented - read tools/builder/GUIDE.md"
    exit 1
    # Example:
    # protoc --proto_path="$PlatformDir\proto" --go_out="$PlatformDir\proto\dist\go" `
    #   --go-grpc_out="$PlatformDir\proto\dist\go" (Get-ChildItem "$PlatformDir\proto\*.proto")
}
{{/if}}
# -----------------------------------------------------------------------------

if ($Environment -notin @("development", "production")) {
    Write-Host "usage: builder.ps1 <development|production> [service]"
    exit 1
}

if ($Service) {
    if ($Service -eq "proto" -or -not (Test-Path (Join-Path $PlatformDir $Service) -PathType Container)) {
        Write-Host "unknown service: $Service (expected $PlatformDir\$Service)"
        exit 1
    }
    $services = @($Service)
} else {
    $services = @(Get-ChildItem -Path $PlatformDir -Directory | Where-Object { $_.Name -ne "proto" } |
        Sort-Object Name | ForEach-Object { $_.Name })
}
if ($services.Count -eq 0) {
    Write-Host "no services under $PlatformDir"
    exit 1
}

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
{{#if proto}}

if (Test-Path (Join-Path $PlatformDir "proto") -PathType Container) {
    Write-Host "[build] proto"
    $global:LASTEXITCODE = 0
    Invoke-BuildProto
    Assert-LastExit "proto codegen"
}
{{/if}}

# A failed build leaves no half-written output behind; BUILD_INFO marks a complete build.
$partial = $null
try {
    foreach ($name in $services) {
        $Out = Join-Path $DistDir $name
        $EnvFile = Join-Path (Join-Path $SecretsDir $name) ".env.$Environment"
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
