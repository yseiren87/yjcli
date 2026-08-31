$ErrorActionPreference = "Stop"

$platformDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$services = Get-ChildItem -Path $platformDir -Directory |
    Where-Object {
        $_.Name -notin @("scripts", "proto") -and
        (Test-Path (Join-Path $_.FullName ".env.local-dev"))
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
        $command = "call scripts\run.bat `"$($service.Name)`""
        $processes += Start-Process `
            -FilePath $env:ComSpec `
            -ArgumentList @("/d", "/c", $command) `
            -WorkingDirectory $platformDir `
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
