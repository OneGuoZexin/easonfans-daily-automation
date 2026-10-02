$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "EasonFans每日自动化.lnk"
$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($shortcutPath)
$shortcut.TargetPath = "powershell.exe"
$shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$root\run_daily.ps1`""
$shortcut.WorkingDirectory = $root
$shortcut.IconLocation = "powershell.exe,0"
$shortcut.Save()
Write-Host "Shortcut created: $shortcutPath"
