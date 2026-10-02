$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$taskName = "EasonFans Daily Automation"
$python = (Get-Command python).Source
$script = Join-Path $root "easonfans_daily.py"
$action = New-ScheduledTaskAction -Execute $python -Argument "`"$script`" --run" -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Daily -At 20:00
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description "Daily easonfans forum automation at 20:00" -Force | Out-Null
Write-Host "Scheduled task installed: $taskName"
