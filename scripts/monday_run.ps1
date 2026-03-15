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
$claudePrompt = @"
請處理本週 AI 新聞週報，日期：$today。

【工作目錄】C:\Users\inice\ai-weekly

【步驟】
1. 讀取 data\filtered.json（每篇文章含 title、url、source、language、summary_original、content_original）

2. 對每篇文章完成以下處理（參考 scripts\ai_score.py 的 SCORING_GUIDE）：
   - score（0~10）：斌斌是 3D 手辦原型師，3D AI 相關新聞優先給高分
   - title_cht：繁體中文標題
   - title_ja：日語標題
   - tags：3~5 個標籤，# 開頭，例如 ["#GPT-5","#OpenAI","#LLM"]
   - summary_points_cht：3~5 條繁體中文重點（陣列）
   - summary_points_ja：3~5 條日語重點（陣列）
   - content_cht：若有 content_original 則完整翻譯；否則根據標題和摘要補寫，300字以上
   - content_ja：同上，日語版本

3. 將處理結果存入 data\$today.json，格式：
   {"date":"$today","articles":{"ai_industry":[...],"ai_agent":[...],"3d_ai":[...]}}

4. 呼叫 scripts\ai_score.py 的 save_weekly() 更新 data\index.json 和 data\search_index.json

5. git add data\$today.json data\index.json data\search_index.json
   git commit -m "weekly: $today 週報發布"
   git push

6. 執行 python scripts\send_email.py $today 發送郵件通知
"@

claude --dangerously-skip-permissions -p $claudePrompt

"[$now] 週報處理完成" | Add-Content $logFile
