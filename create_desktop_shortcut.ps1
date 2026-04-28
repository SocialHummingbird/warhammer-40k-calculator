$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Launcher = Join-Path $Root "start_warhammer_calculator.ps1"
$Icon = Join-Path $Root "web\assets\app-icon.ico"
$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "Warhammer 40K Calculator.lnk"

if (-not (Test-Path -LiteralPath $Launcher)) {
    throw "Launcher script not found: $Launcher"
}

if (-not (Test-Path -LiteralPath $Icon)) {
    throw "App icon not found: $Icon"
}

$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$Shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$Launcher`""
$Shortcut.WorkingDirectory = $Root
$Shortcut.IconLocation = $Icon
$Shortcut.Description = "Launch the local Warhammer 40K Calculator web app"
$Shortcut.Save()

Write-Host "Desktop shortcut ready: $ShortcutPath"
