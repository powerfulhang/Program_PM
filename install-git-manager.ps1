$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$userBin = Join-Path $HOME "bin"
$launcher = Join-Path $userBin "git-manager.cmd"

New-Item -ItemType Directory -Force -Path $userBin | Out-Null

$content = @"
@echo off
call "$projectRoot\git-manager.cmd" %*
exit /b %ERRORLEVEL%
"@
Set-Content -Path $launcher -Value $content -Encoding ASCII

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ([string]::IsNullOrWhiteSpace($userPath)) {
    [Environment]::SetEnvironmentVariable("Path", $userBin, "User")
    Write-Host "Added $userBin to the user PATH. Open a new terminal before running git-manager."
} elseif (($userPath -split ";") -notcontains $userBin) {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$userBin", "User")
    Write-Host "Added $userBin to the user PATH. Open a new terminal before running git-manager."
} else {
    Write-Host "$userBin is already on the user PATH."
}

Write-Host "Installed launcher: $launcher"
Write-Host "For this PowerShell session only, run: `$env:Path = `"$userBin;`$env:Path`""
