@echo off
setlocal EnableExtensions EnableDelayedExpansion

if /I "%~1"=="" goto help
if /I "%~1"=="help" goto help

set "PLATFORM=%~1"
if not exist "%PLATFORM%\scripts\run.bat" (
  echo Unknown target: %PLATFORM%
  echo Expected: %PLATFORM%\scripts\run.bat ^(yjcli add platform^)
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
echo.
echo Available platforms (dirs with scripts\run.bat):
set "FOUND="
for /d %%D in (*) do (
  if exist "%%D\scripts\run.bat" (
    echo   %%D
    set "FOUND=1"
  )
)
if not defined FOUND echo   ^(none — run: yjcli add platform^)
echo.
echo Example: make.bat backend
echo          make.bat backend NAME=api
exit /b 0
