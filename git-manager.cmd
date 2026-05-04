@echo off
setlocal
set "GM_ROOT=%~dp0"
set "CALLER_DIR=%CD%"
pushd "%GM_ROOT%" >nul
if exist "%GM_ROOT%.venv\Scripts\python.exe" (
    "%GM_ROOT%.venv\Scripts\python.exe" -m git_manager --cwd "%CALLER_DIR%" %*
) else (
    python -m git_manager --cwd "%CALLER_DIR%" %*
)
set "EXIT_CODE=%ERRORLEVEL%"
popd >nul
exit /b %EXIT_CODE%
