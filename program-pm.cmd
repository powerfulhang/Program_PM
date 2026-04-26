@echo off
setlocal
set "PM_ROOT=%~dp0"
set "CALLER_DIR=%CD%"
pushd "%PM_ROOT%" >nul
if exist "%PM_ROOT%.venv\Scripts\python.exe" (
    "%PM_ROOT%.venv\Scripts\python.exe" -m program_pm --cwd "%CALLER_DIR%" %*
) else (
    python -m program_pm --cwd "%CALLER_DIR%" %*
)
set "EXIT_CODE=%ERRORLEVEL%"
popd >nul
exit /b %EXIT_CODE%
