#Requires -Version 5.1
<#
.SYNOPSIS
    Clean up old Program PM installation artifacts.

.DESCRIPTION
    Removes the old ~/bin/program-pm.cmd launcher that was created by the
    previous install-program-pm.ps1 script. Safe to run multiple times.

.File Name: cleanup_old_install.ps1
.Author: hang.shi
.Time: 2026-05-04
.Version: 1
#>

$ErrorActionPreference = "Stop"

$userBin = Join-Path $HOME "bin"
$oldLauncher = Join-Path $userBin "program-pm.cmd"

if (Test-Path $oldLauncher) {
    Remove-Item $oldLauncher -Force
    Write-Host "Removed old launcher: $oldLauncher"
} else {
    Write-Host "Old launcher not found (already clean): $oldLauncher"
}

# Check if old context menu entry exists and remove it
$oldRegPath = "HKCU:\Software\Classes\Directory\Background\shell\ProgramPM"
if (Test-Path $oldRegPath) {
    Remove-Item -Path $oldRegPath -Recurse -Force
    Write-Host "Removed old context menu entry: $oldRegPath"
}

Write-Host ""
Write-Host "Cleanup complete. Current state:"
Write-Host "  - Use dist\GitManager.exe for standalone launch"
Write-Host "  - Use scripts\install_context_menu.ps1 for right-click integration"
