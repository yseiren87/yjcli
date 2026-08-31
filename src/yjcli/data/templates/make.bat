@echo off
setlocal EnableExtensions EnableDelayedExpansion
rem Build/deploy scripts are POSIX shell (.sh) only (Docker etc. are not native to
rem Windows); those targets run through WSL. run.* stays native Windows.
rem Build/deploy scripts intentionally fail until their printed implementation steps
rem are completed.

if /I "%~1"=="" goto help
if /I "%~1"=="help" goto help

set "TARGET=%~1"
set "ACTION="

set "PLATFORM=%TARGET:-build-development=%"
if /I not "%PLATFORM%"=="%TARGET%" (
  set "ACTION=build-development"
  goto parse_start
)
set "PLATFORM=%TARGET:-build-production=%"
if /I not "%PLATFORM%"=="%TARGET%" (
  set "ACTION=build-production"
  goto parse_start
)
set "PLATFORM=%TARGET:-deploy-development=%"
if /I not "%PLATFORM%"=="%TARGET%" (
  set "ACTION=deploy-development"
  goto parse_start
)
set "PLATFORM=%TARGET:-deploy-production=%"
if /I not "%PLATFORM%"=="%TARGET%" (
  set "ACTION=deploy-production"
  goto parse_start
)
set "PLATFORM=%TARGET%"

:parse_start
if not exist "%PLATFORM%\scripts\run.bat" (
  echo Unknown target: %PLATFORM%
  echo Expected: %PLATFORM%\scripts\run.bat ^(yjcli platform add^)
  exit /b 1
)

set "NAME="
shift
:parse
if "%~1"=="" goto run_exec
set "ARG=%~1"
if /I "%ARG:~0,5%"=="NAME=" set "NAME=%ARG:~5%"
shift
goto parse

:run_exec
if defined ACTION (
  where wsl >nul 2>&1
  if errorlevel 1 (
    echo wsl.exe not found. Build/deploy scripts are .sh only; install WSL to run %ACTION% on Windows.
    exit /b 1
  )
  if not exist "%PLATFORM%\scripts\%ACTION%.sh" (
    echo missing: %PLATFORM%\scripts\%ACTION%.sh
    exit /b 1
  )
  wsl bash "%PLATFORM%/scripts/%ACTION%.sh" "%NAME%"
  exit /b !ERRORLEVEL!
)
if "%NAME%"=="" (
  call "%PLATFORM%\scripts\run.bat"
) else (
  call "%PLATFORM%\scripts\run.bat" "%NAME%"
)
exit /b %ERRORLEVEL%

:help
echo Usage:
echo   make.bat ^<platform^>                 # all services ^(separate windows^)
echo   make.bat ^<platform^> NAME=^<service^>  # one service
echo   make.bat ^<platform^>-build-development  [NAME=^<service^>]  ^(via WSL^)
echo   make.bat ^<platform^>-build-production   [NAME=^<service^>]  ^(via WSL^)
echo   make.bat ^<platform^>-deploy-development [NAME=^<service^>]  ^(via WSL^)
echo   make.bat ^<platform^>-deploy-production  [NAME=^<service^>]  ^(via WSL^)
echo.
echo Available platforms (dirs with scripts\run.bat):
set "FOUND="
for /d %%D in (*) do (
  if exist "%%D\scripts\run.bat" (
    echo   %%D
    set "FOUND=1"
  )
)
if not defined FOUND echo   ^(none — run: yjcli platform add^)
echo.
echo Example: make.bat backend
echo          make.bat backend NAME=api
echo          make.bat backend-build-development NAME=api
echo          make.bat backend-deploy-production NAME=api
exit /b 0
