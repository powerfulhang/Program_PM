#Requires -Version 5.1
<#
.SYNOPSIS
    Register Git Manager in the Windows Explorer right-click context menu.

.DESCRIPTION
    Adds "Open with Git Manager" to the Explorer background right-click menu
    (right-click blank space inside a folder). Uses HKCU so no admin needed.

.PARAMETER ExePath
    Path to GitManager.exe. If not specified, looks in ..\dist\GitManager.exe.

.File Name: install_context_menu.ps1
.Author: hang.shi
.Time: 2026-05-04
.Version: 1
#>

param(
    [string]$ExePath
)

$ErrorActionPreference = "Stop"

# Resolve exe path
if (-not $ExePath) {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $ExePath = Join-Path (Split-Path -Parent $scriptDir) "dist\GitManager.exe"
}

if (-not (Test-Path $ExePath)) {
    Write-Error "GitManager.exe not found at: $ExePath`nBuild it first with: python scripts\build.py"
    exit 1
}

$ExePath = (Resolve-Path $ExePath).Path

# Registry key for folder background right-click menu
$regPath = "HKCU:\Software\Classes\Directory\Background\shell\GitManager"

# Create the key
New-Item -Path $regPath -Force | Out-Null
Set-ItemProperty -Path $regPath -Name "(Default)" -Value "Open with Git Manager"
Set-ItemProperty -Path $regPath -Name "Icon" -Value "$ExePath"

# Create command subkey
$commandPath = Join-Path $regPath "command"
New-Item -Path $commandPath -Force | Out-Null
Set-ItemProperty -Path $commandPath -Name "(Default)" -Value "`"$ExePath`" `"%V`""

Write-Host "Context menu registered successfully."
Write-Host "  Menu:    Open with Git Manager"
Write-Host "  Command: `"$ExePath`" `"%V`""
Write-Host ""
Write-Host "Right-click blank space in any folder to see the menu entry."
Write-Host "On Windows 11, it appears under 'Show more options' or in the modern menu."
