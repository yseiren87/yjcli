@echo off
setlocal EnableExtensions EnableDelayedExpansion
set "PLATFORM_DIR=%~dp0.."
cd /d "%PLATFORM_DIR%"

if "%~1"=="" goto run_all

set "NAME=%~1"
shift
if /I "%NAME%"=="scripts" (
  echo reserved name: %NAME%
  exit /b 1
)
if /I "%NAME%"=="proto" (
  echo reserved name: %NAME%
  exit /b 1
)

set "SERVICE_DIR=%PLATFORM_DIR%\%NAME%"
set "ENV_FILE=%SERVICE_DIR%\.env.local-dev"
set "PID_FILE=%SERVICE_DIR%\.run.pid"

if not exist "%SERVICE_DIR%\" (
  echo unknown service: %NAME%
  exit /b 1
)
if not exist "%ENV_FILE%" (
  echo missing %ENV_FILE% ^(local run always uses .env.local-dev^)
  exit /b 1
)

rem Load KEY=VALUE from .env.local-dev
for /f "usebackq tokens=1* delims==" %%A in (`findstr /R "^[A-Za-z_][A-Za-z0-9_]*=" "%ENV_FILE%"`) do (
  set "%%A=%%B"
)

echo [%NAME%] env: %ENV_FILE%

if defined PORT (
  call :kill_by_port %PORT%
) else (
  echo [%NAME%] PORT unset in .env.local-dev; using pidfile fallback
)
call :kill_by_pidfile

cd /d "%SERVICE_DIR%"

if exist "package.json" (
  set "EXTRA="
  if defined HOST set "EXTRA=!EXTRA! --host %HOST%"
  if defined PORT set "EXTRA=!EXTRA! --port %PORT%"
  call npm start -- !EXTRA! %*
  exit /b %ERRORLEVEL%
)

echo [%NAME%] exists but has no run convention yet.
exit /b 1

:run_all
set "ANY="
for /d %%D in (*) do (
  if /I not "%%~nxD"=="scripts" if /I not "%%~nxD"=="proto" (
    if exist "%%D\.env.local-dev" (
      echo starting %%~nxD
      start "%%~nxD" cmd /c "cd /d "%PLATFORM_DIR%" && call scripts\run.bat %%~nxD"
      set "ANY=1"
    )
  )
)
if not defined ANY (
  echo no services under %PLATFORM_DIR% ^(run: yjcli service add^)
  exit /b 1
)
echo All services started in separate windows.
exit /b 0

:kill_by_port
set "KPORT=%~1"
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R ":%KPORT% .*LISTENING"') do (
  echo stopping pid %%P on port %KPORT%
  taskkill /F /PID %%P >nul 2>&1
)
exit /b 0

:kill_by_pidfile
if not exist "%PID_FILE%" exit /b 0
set /p OLD_PID=<"%PID_FILE%"
if defined OLD_PID (
  echo stopping pid %OLD_PID% from %PID_FILE%
  taskkill /F /PID %OLD_PID% >nul 2>&1
)
del /f /q "%PID_FILE%" >nul 2>&1
exit /b 0
