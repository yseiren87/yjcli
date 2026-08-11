@echo off
setlocal EnableExtensions EnableDelayedExpansion
rem Deploy scripts intentionally fail until their printed implementation steps are completed.

if /I "%~1"=="" goto help
if /I "%~1"=="help" goto help

set "TARGET=%~1"
set "PLATFORM=%TARGET:-deploy-development=%"
if /I not "%PLATFORM%"=="%TARGET%" (
  set "DEPLOY_ENV=development"
  goto parse_start
)
set "PLATFORM=%TARGET:-deploy-production=%"
if /I not "%PLATFORM%"=="%TARGET%" (
  set "DEPLOY_ENV=production"
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
if defined DEPLOY_ENV (
  call "%PLATFORM%\scripts\deploy-%DEPLOY_ENV%.bat" "%NAME%"
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
echo   make.bat ^<platform^>-deploy-development [NAME=^<service^>]
echo   make.bat ^<platform^>-deploy-production  [NAME=^<service^>]
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
echo          make.bat backend-deploy-development NAME=api
echo          make.bat backend-deploy-production NAME=api
exit /b 0
