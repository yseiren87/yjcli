@echo off
setlocal EnableExtensions EnableDelayedExpansion
rem Run service(s) of one platform (yjcli runner plugin).
rem Always loads tools\secrets\<platform>\<service>\.env.local-dev.
rem The service owns RUN_COMMAND there; this runner does not infer a language/runtime.
rem Usage:
rem   tools\runner\run.bat <platform>                     (all services)
rem   tools\runner\run.bat <platform> <service> [args...]
for %%I in ("%~dp0..\..") do set "ROOT_DIR=%%~fI"
set "SECRETS_DIR=%ROOT_DIR%\tools\secrets"

if "%~1"=="" (
  echo usage: %~nx0 ^<platform^> [service] [args...]
  exit /b 1
)
set "PLATFORM=%~1"
set "PLATFORM_DIR=%ROOT_DIR%\%PLATFORM%"
if not exist "%PLATFORM_DIR%\" (
  echo unknown platform: %PLATFORM%
  exit /b 1
)

if "%~2"=="" goto run_all

set "NAME=%~2"
if /I "%NAME%"=="proto" (
  echo reserved name: %NAME%
  exit /b 1
)

rem Collect extra args after <platform> <service> (shift does not affect %*).
set "EXTRA="
shift
shift
:collect
if "%~1"=="" goto collected
set "EXTRA=!EXTRA! %1"
shift
goto collect
:collected

set "SERVICE_DIR=%PLATFORM_DIR%\%NAME%"
set "ENV_FILE=%SECRETS_DIR%\%PLATFORM%\%NAME%\.env.local-dev"
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
  rem %%~B removes optional dotenv quotes while preserving the value text.
  set "%%A=%%~B"
)

echo [%NAME%] env: %ENV_FILE%

if defined PORT (
  call :kill_by_port %PORT%
) else (
  echo [%NAME%] PORT unset in .env.local-dev; using pidfile fallback
)
call :kill_by_pidfile

cd /d "%SERVICE_DIR%"

if not defined RUN_COMMAND (
  echo [%NAME%] RUN_COMMAND is unset in %ENV_FILE%
  echo Declare the service-owned local command, for example: RUN_COMMAND=your-command --flag
  exit /b 1
)

echo [%NAME%] command: !RUN_COMMAND!
call !RUN_COMMAND!!EXTRA!
exit /b %ERRORLEVEL%

:run_all
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1" "%PLATFORM%"
exit /b %ERRORLEVEL%

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
