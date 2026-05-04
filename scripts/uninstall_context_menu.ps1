#Requires -Version 5.1
<#
.SYNOPSIS
    Remove Git Manager from the Windows Explorer right-click context menu.

.File Name: uninstall_context_menu.ps1
.Author: hang.shi
.Time: 2026-05-04
.Version: 1
#>

$ErrorActionPreference = "Stop"

$regPath = "HKCU:\Software\Classes\Directory\Background\shell\GitManager"

if (Test-Path $regPath) {
    Remove-Item -Path $regPath -Recurse -Force
    Write-Host "Context menu entry removed."
} else {
    Write-Host "Context menu entry not found (already removed)."
}
