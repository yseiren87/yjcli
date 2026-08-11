@echo off
setlocal EnableExtensions
rem Production deployment entry point. Keep shared preparation in deploy-common.bat.

set "SCRIPT_DIR=%~dp0"
set "NAME=%~1"
shift

call "%SCRIPT_DIR%deploy-common.bat" production "%NAME%" %*
if errorlevel 1 exit /b %ERRORLEVEL%

echo production upload is not implemented.
echo Implement upload/deploy logic in: %SCRIPT_DIR%deploy-production.bat
echo Examples: registry push, production upload, release rollout

rem Recommended production steps:
rem - validate VERSION or release tag
rem - upload the artifact or push the container image
rem - deploy to production and run a health check
rem - roll back on failure
exit /b 1
