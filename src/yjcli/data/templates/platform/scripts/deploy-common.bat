@echo off
setlocal EnableExtensions
rem Shared build/package preparation for development and production deploys.
rem Replace the implementation guard below with repository-specific commands.

set "SCRIPT_DIR=%~dp0"
for %%D in ("%SCRIPT_DIR%..") do set "PLATFORM_DIR=%%~fD"
set "ENVIRONMENT=%~1"
set "NAME=%~2"

if /I not "%ENVIRONMENT%"=="development" if /I not "%ENVIRONMENT%"=="production" (
  echo usage: %~nx0 ^<development^|production^> [service] [args...]
  exit /b 1
)

if defined NAME if not exist "%PLATFORM_DIR%\%NAME%\" (
  echo unknown service: %NAME% ^(expected %PLATFORM_DIR%\%NAME%^)
  exit /b 1
)

for %%D in ("%PLATFORM_DIR%") do set "PLATFORM_NAME=%%~nxD"
echo [deploy] platform: %PLATFORM_NAME%
echo [deploy] environment: %ENVIRONMENT%
if defined NAME (echo [deploy] service: %NAME%) else echo [deploy] service: all
echo deploy common is not implemented.
echo Implement build/package logic in: %SCRIPT_DIR%deploy-common.bat
echo Examples: docker build, archive creation, frontend build

rem Implementation examples:
rem docker build -t "example/%NAME%:%ENVIRONMENT%" "%PLATFORM_DIR%"
rem tar -a -c -f "%NAME%.zip" -C "%PLATFORM_DIR%" "%NAME%"
rem cd /d "%PLATFORM_DIR%\%NAME%" ^&^& npm ci ^&^& npm run build
exit /b 1
