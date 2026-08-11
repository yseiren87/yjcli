@echo off
setlocal EnableExtensions
rem Development deployment entry point. Keep shared preparation in deploy-common.bat.

set "SCRIPT_DIR=%~dp0"
set "NAME=%~1"
shift

call "%SCRIPT_DIR%deploy-common.bat" development "%NAME%" %*
if errorlevel 1 exit /b %ERRORLEVEL%

echo development upload is not implemented.
echo Implement upload/deploy logic in: %SCRIPT_DIR%deploy-development.bat
echo Examples: docker push, scp, S3 upload, kubectl apply

rem Development upload examples:
rem docker push "registry.example.com/%NAME%:development"
rem scp "%ARTIFACT%" "dev-server:/srv/%NAME%/"
rem aws s3 sync "%DIST_DIR%" "s3://example-development/%NAME%/"
rem kubectl apply -k deploy/overlays/development
exit /b 1
