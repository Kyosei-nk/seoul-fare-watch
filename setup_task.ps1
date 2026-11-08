# Windows のタスク スケジューラに「2時間おきに実行」を登録する（1回だけ実行すればOK）
$script = Join-Path $PSScriptRoot "run_local.ps1"
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$script`""
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddHours(7) -RepetitionInterval (New-TimeSpan -Hours 2) -RepetitionDuration (New-TimeSpan -Days 50)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries
Register-ScheduledTask -TaskName "TripFareWatch" -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Write-Host "登録しました。止めるときは: Unregister-ScheduledTask -TaskName TripFareWatch"
