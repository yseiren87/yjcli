param(
    [Parameter(Mandatory = $true)][string]$Platform
)
$ErrorActionPreference = "Stop"

# Run every service of one platform concurrently (yjcli runner plugin).
$rootDir = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$platformDir = Join-Path $rootDir $Platform
$secretsDir = Join-Path (Join-Path $rootDir "tools\secrets") $Platform

if (-not (Test-Path $platformDir)) {
    Write-Host "unknown platform: $Platform"
    exit 1
}

$services = Get-ChildItem -Path $platformDir -Directory |
    Where-Object {
        $_.Name -ne "proto" -and
        (Test-Path (Join-Path (Join-Path $secretsDir $_.Name) ".env.local-dev"))
    } |
    Sort-Object Name

if (-not $services) {
    Write-Host "no services under $platformDir (run: yjcli service add)"
    exit 1
}

$processes = @()
$exitCode = 0
try {
    foreach ($service in $services) {
        Write-Host "starting $($service.Name)"
        $command = "call `"$PSScriptRoot\run.bat`" `"$Platform`" `"$($service.Name)`""
        $processes += Start-Process `
            -FilePath $env:ComSpec `
            -ArgumentList @("/d", "/c", $command) `
            -WorkingDirectory $rootDir `
            -NoNewWindow `
            -PassThru
    }

    Write-Host "All services are running. Press Ctrl+C to stop them all."
    while ($processes.Where({ -not $_.HasExited }).Count -gt 0) {
        Start-Sleep -Milliseconds 250
    }
    if ($processes.Where({ $_.ExitCode -ne 0 }).Count -gt 0) {
        $exitCode = 1
    }
}
finally {
    foreach ($process in $processes) {
        if (-not $process.HasExited) {
            & taskkill.exe /PID $process.Id /T /F *> $null
        }
    }
}

exit $exitCode
