# 澄澄週報自動化啟動腳本
# 觸發條件：東京時間週一 09:30 之後，且本週尚未處理

$ErrorActionPreference = "SilentlyContinue"

# 取得東京時間
$jst = [System.TimeZoneInfo]::FindSystemTimeZoneById("Tokyo Standard Time")
$now = [System.TimeZoneInfo]::ConvertTimeFromUtc([DateTime]::UtcNow, $jst)
$today = $now.ToString("yyyy-MM-dd")

# 條件1：必須是週一
if ($now.DayOfWeek -ne "Monday") {
    exit 0
}

# 條件2：必須是 09:30 之後
if ($now.Hour -lt 9 -or ($now.Hour -eq 9 -and $now.Minute -lt 30)) {
    exit 0
}

# 條件3：本週尚未處理（避免重複運行）
$weekFile = "C:\Users\inice\ai-weekly\data\$today.json"
if (Test-Path $weekFile) {
    exit 0
}

# 記錄日誌
$logFile = "C:\Users\inice\ai-weekly\data\run.log"
"[$now] 開始週報處理" | Add-Content $logFile

# git pull 拿到最新 filtered.json
Set-Location "C:\Users\inice\ai-weekly"
git pull --quiet

# 確認 filtered.json 存在
if (-not (Test-Path "data\filtered.json")) {
    "[$now] filtered.json 不存在，跳過" | Add-Content $logFile
    exit 1
}

# 讀取 .env 環境變數
Get-Content "C:\Users\inice\claudeAgent\.env" | ForEach-Object {
    if ($_ -match "^\s*([^#][^=]+)=(.+)$") {
        [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim())
    }
}

# 啟動澄澄處理週報（非交互模式）
$claudePrompt = "請處理本週AI新聞週報。步驟：1.讀取 C:\Users\inice\ai-weekly\data\filtered.json 2.為每條新聞打分(0-10)並翻譯摘要成繁體中文和日語 3.將結果存入 C:\Users\inice\ai-weekly\data\$today.json 4.更新 C:\Users\inice\ai-weekly\data\index.json 5.git add/commit/push 6.執行 python C:\Users\inice\ai-weekly\scripts\send_email.py $today 發送郵件通知"

claude --dangerously-skip-permissions -p $claudePrompt

"[$now] 週報處理完成" | Add-Content $logFile
