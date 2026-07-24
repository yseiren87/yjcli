@echo off
setlocal EnableExtensions

if /I "%~1"=="" goto help
if /I "%~1"=="help" goto help
if /I "%~1"=="run" goto run

echo Unknown target: %~1
exit /b 1

:help
echo Usage:
echo   make.bat run PLATFORM=^<platform^> NAME=^<service^>
echo.
echo Platforms: backend backend-service frontend mobile-app pc-app cli browser-extension
exit /b 0

:run
set "PLATFORM="
set "NAME="
shift
:parse
if "%~1"=="" goto run_exec
set "ARG=%~1"
if /I "%ARG:~0,9%"=="PLATFORM=" set "PLATFORM=%ARG:~9%"
if /I "%ARG:~0,5%"=="NAME=" set "NAME=%ARG:~5%"
shift
goto parse

:run_exec
if "%PLATFORM%"=="" (
  echo PLATFORM required
  exit /b 1
)
if "%NAME%"=="" (
  echo NAME required
  exit /b 1
)
if not exist "%PLATFORM%\scripts\run.bat" (
  echo missing: %PLATFORM%\scripts\run.bat
  exit /b 1
)
call "%PLATFORM%\scripts\run.bat" "%NAME%"
exit /b %ERRORLEVEL%
