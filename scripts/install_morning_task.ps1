# Registers a Windows scheduled task that syncs Gmail every morning, so the dashboard
# is up to date when you open it. Run once:  powershell -File scripts\install_morning_task.ps1
# Remove it with:  Unregister-ScheduledTask -TaskName "JobsTracker morning sync"

param([string]$At = "07:00")

$backend = Split-Path -Parent $PSScriptRoot
# pythonw.exe = Python without a console window (no black window popping up at 7:00)
$python = Join-Path (Split-Path -Parent $backend) "venv\Scripts\pythonw.exe"

$action = New-ScheduledTaskAction -Execute $python `
    -Argument "-m app.services.sync --scheduled" -WorkingDirectory $backend
$trigger = New-ScheduledTaskTrigger -Daily -At $At
# StartWhenAvailable: if the laptop was off or asleep at 7:00, run as soon as it wakes up
$options = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

Register-ScheduledTask -TaskName "JobsTracker morning sync" -Action $action -Trigger $trigger `
    -Settings $options -Force `
    -Description "Syncs job application emails from Gmail for the JobsTracker dashboard." | Out-Null

Write-Host "Scheduled: JobsTracker morning sync, every day at $At (logs: $backend\logs\sync.log)"
