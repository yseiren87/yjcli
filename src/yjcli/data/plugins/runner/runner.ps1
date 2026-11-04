# Local runner for platform "{{platform}}" (yjcli runner plugin; repository-owned).
#
# Read tools/runner/GUIDE.md, then implement Invoke-RunOne below. Everything
# else - service discovery, .env.local-dev loading, concurrent start, [service]
# output prefix, Ctrl+C / failure cleanup - already works.
# This is the entry point `make.ps1 {{platform}}` calls. It does not have to stay
# a single file: add helper scripts next to it and call them from here.
#
# Usage: tools/runner/{{platform}}/runner.ps1 [service]
param(
    [string]$Service = "",
    [switch]$Child  # internal: run one service in the foreground
)
$ErrorActionPreference = "Stop"

$ScriptDir = $PSScriptRoot
$RootDir = (Resolve-Path (Join-Path $ScriptDir "..\..\..")).Path
$Platform = Split-Path $ScriptDir -Leaf
$PlatformDir = Join-Path $RootDir $Platform
$SecretsDir = Join-Path (Join-Path $RootDir "tools\secrets") $Platform

# ---------------------------------------------------------------- implement me
# Invoke-RunOne <service>
#   Start one service in the foreground and stay attached until it exits.
#   Runs inside $PlatformDir\<service> with its .env.local-dev already in $env:.
#   Print with Write-Output (Write-Host bypasses the [service] prefix).
function Invoke-RunOne([string]$Name) {
    Write-Output "runner for $Platform/$Name is not implemented - read tools/runner/GUIDE.md"
    exit 1
    # Examples:
    # go run .
    # npm run dev
    # uv run python -m app
}
# -----------------------------------------------------------------------------

function Get-EnvFile([string]$Name) {
    Join-Path (Join-Path $SecretsDir $Name) ".env.local-dev"
}

if ($Child) {
    Set-Location (Join-Path $PlatformDir $Service)
    # KEY=VALUE lines, values taken literally (same rules as docker --env-file).
    foreach ($entry in Get-Content (Get-EnvFile $Service)) {
        if ($entry -eq "" -or $entry.StartsWith("#") -or -not $entry.Contains("=")) { continue }
        $key, $value = $entry.Split("=", 2)
        Set-Item -Path "env:$key" -Value $value
    }
    Invoke-RunOne $Service 2>&1 | ForEach-Object { Write-Host "[$Service] $_" }
    if ($LASTEXITCODE) { exit $LASTEXITCODE }
    exit 0
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

$shell = (Get-Process -Id $PID).Path
$procs = @()
$names = @()
foreach ($name in $services) {
    if (-not (Test-Path (Get-EnvFile $name))) {
        Write-Host "[$name] skipped: missing tools/secrets/$Platform/$name/.env.local-dev"
        continue
    }
    $p = Start-Process -FilePath $shell -NoNewWindow -PassThru -ArgumentList @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $PSCommandPath, "-Service", $name, "-Child")
    $null = $p.Handle  # keeps ExitCode readable after exit
    $procs += $p
    $names += $name
}
if ($procs.Count -eq 0) {
    Write-Host "no runnable services under $PlatformDir"
    exit 1
}
Write-Host "running $($procs.Count) service(s): $($names -join ' ') - Ctrl+C to stop"

# Stops a process and everything it started (npm -> node, uv -> python, ...).
function Stop-Tree([int]$Id) {
    if ($env:OS -eq "Windows_NT") {
        & taskkill.exe /PID $Id /T /F *> $null
    } else {
        foreach ($child in @(& pgrep -P $Id 2>$null)) { Stop-Tree ([int]$child) }
        Stop-Process -Id $Id -Force -ErrorAction SilentlyContinue
    }
}

function Stop-All {
    foreach ($p in $procs) {
        if (-not $p.HasExited) { Stop-Tree $p.Id }
    }
}

# A service that exits non-zero stops the rest and its code becomes ours; one
# that exits 0 just leaves the set. Ctrl+C lands in `finally`.
$code = 0
$done = @{}
$finished = $false
try {
    while ($done.Count -lt $procs.Count) {
        for ($i = 0; $i -lt $procs.Count; $i++) {
            $p = $procs[$i]
            if ($done.ContainsKey($i) -or -not $p.HasExited) { continue }
            $done[$i] = $true
            if ($p.ExitCode -ne 0) {
                Write-Host "[$($names[$i])] exited with $($p.ExitCode) - stopping the others"
                $code = $p.ExitCode
                break
            }
        }
        if ($code -ne 0) { break }
        Start-Sleep -Milliseconds 500
    }
    $finished = $true
} finally {
    Stop-All
    if (-not $finished) { exit 130 }  # Ctrl+C
}
exit $code
