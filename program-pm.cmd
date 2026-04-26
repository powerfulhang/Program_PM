@echo off
setlocal
set "PM_ROOT=%~dp0"
if exist "%PM_ROOT%.venv\Scripts\python.exe" (
    "%PM_ROOT%.venv\Scripts\python.exe" -m program_pm %*
) else (
    python -m program_pm %*
)
