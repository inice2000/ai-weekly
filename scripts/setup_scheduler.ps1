# 設置 Windows 任務計劃程序
# 執行一次即可，設置兩個觸發器：
#   1. 每週一 09:30 自動運行
#   2. 每次登錄時運行（開機後自動判斷條件）

$taskName = "澄澄AI週報"
$scriptPath = "C:\Users\inice\ai-weekly\scripts\monday_run.ps1"
$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$scriptPath`""

# 觸發器1：每週一 09:30
$trigger1 = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At "09:30"

# 觸發器2：登錄時（開機後自動判斷）
$trigger2 = New-ScheduledTaskTrigger -AtLogOn

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable

# 刪除舊任務（如果存在）
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

# 創建新任務
Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger1, $trigger2 `
    -Settings $settings `
    -Description "澄澄每週一自動處理AI新聞週報並發送郵件通知" | Out-Null

Write-Host "✓ 任務計劃程序設置完成：$taskName"
Write-Host "  觸發器1：每週一 09:30"
Write-Host "  觸發器2：每次登錄（自動判斷條件）"
