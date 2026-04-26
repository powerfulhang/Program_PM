$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$userBin = Join-Path $HOME "bin"
$launcher = Join-Path $userBin "program-pm.cmd"

New-Item -ItemType Directory -Force -Path $userBin | Out-Null

$content = @"
@echo off
"$projectRoot\program-pm.cmd" %*
"@
Set-Content -Path $launcher -Value $content -Encoding ASCII

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (($userPath -split ";") -notcontains $userBin) {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$userBin", "User")
    Write-Host "Added $userBin to the user PATH. Open a new terminal before running program-pm."
} else {
    Write-Host "$userBin is already on the user PATH."
}

Write-Host "Installed launcher: $launcher"
