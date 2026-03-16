# 澄澄週報自動化啟動腳本 v2
# 設計原則：claude -p 只負責輸出 JSON，PowerShell 負責解析與儲存
# 徹底解決舊版「claude -p 不執行工具調用導致進度文件未保存」的問題

$ErrorActionPreference = "SilentlyContinue"

# 設定控制台編碼為 UTF-8，確保中日文 prompt 正確傳遞給 claude
[Console]::InputEncoding  = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
# claude 輸出按行拆成陣列，管道時須用此變數控制編碼
$OutputEncoding = [System.Text.Encoding]::UTF8

$jst = [System.TimeZoneInfo]::FindSystemTimeZoneById("Tokyo Standard Time")

function Get-JstNow { [System.TimeZoneInfo]::ConvertTimeFromUtc([DateTime]::UtcNow, $jst) }

$logFile = "C:\Users\inice\ai-weekly\data\run.log"

function Log($msg) {
    $ts = (Get-JstNow).ToString("yyyy-MM-dd HH:mm:ss")
    "[$ts] $msg" | Add-Content $logFile
    Write-Host "[$ts] $msg"
}

# ── 提取 claude 輸出中的 <result>...</result> 內容 ───────────
# 注意：PowerShell 捕獲外部程式輸出時會按行拆成陣列，必須先 -join 合併
function Extract-Result($output) {
    $text = if ($output -is [array]) { $output -join "`n" } else { $output }
    if ($text -match '(?s)<result>\s*(.*?)\s*</result>') {
        return $matches[1].Trim()
    }
    return $null
}

# ── 啟動條件檢查 ─────────────────────────────────────────────
$now = Get-JstNow
$today = $now.ToString("yyyy-MM-dd")

# 條件1：必須是週一
if ($now.DayOfWeek -ne "Monday") { exit 0 }

# 條件2：必須是 09:30 之後
if ($now.Hour -lt 9 -or ($now.Hour -eq 9 -and $now.Minute -lt 30)) { exit 0 }

# 條件3：本週尚未處理
$weekFile = "C:\Users\inice\ai-weekly\data\$today.json"
if (Test-Path $weekFile) { exit 0 }

Log "=== 週報處理開始 ==="
Set-Location "C:\Users\inice\ai-weekly"
git pull --quiet

if (-not (Test-Path "data\filtered.json")) {
    Log "filtered.json 不存在，跳過"
    exit 1
}

# 讀取 .env 環境變數
Get-Content "C:\Users\inice\claudeAgent\.env" | ForEach-Object {
    if ($_ -match "^\s*([^#][^=]+)=(.+)$") {
        [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim())
    }
}

# ── 階段一：評分（一次完成全部文章）─────────────────────────
$statusJson = python scripts/ai_score.py status $today | ConvertFrom-Json
if ($null -eq $statusJson) {
    Log "錯誤：無法取得狀態，中止"
    exit 1
}

if ($statusJson.phase -eq "scoring") {
    Log "階段一：評分 $($statusJson.pending_count) 篇文章"

    $prompt = python scripts/ai_score.py scoring-prompt $today
    if (-not $prompt) {
        Log "錯誤：無法生成評分 prompt，中止"
        exit 1
    }

    Log "呼叫 claude -p 進行評分..."
    $output = $prompt | claude --dangerously-skip-permissions -p

    $json = Extract-Result $output
    if ($json) {
        $json | Out-File -Encoding utf8 "data\_scores_temp.json"
        python scripts/ai_score.py save-scores $today data\_scores_temp.json
        Remove-Item "data\_scores_temp.json" -ErrorAction SilentlyContinue
        Log "評分完成，已儲存"
    } else {
        Log "錯誤：評分輸出中找不到 <result> 標籤，中止"
        Log "claude 原始輸出前 500 字：$($output.Substring(0, [Math]::Min(500, $output.Length)))"
        exit 1
    }
}

# ── 階段二：翻譯（分批循環）─────────────────────────────────
$maxBatches = 15
$batchCount = 0

while ($batchCount -lt $maxBatches) {
    $statusJson = python scripts/ai_score.py status $today | ConvertFrom-Json

    if ($statusJson.phase -eq "done" -or $statusJson.phase -ne "translating") { break }

    $batchCount++
    Log "翻譯第 $batchCount 批（剩餘 $($statusJson.pending_count) 篇）"

    $prompt = python scripts/ai_score.py translation-prompt $today
    if (-not $prompt) {
        Log "翻譯 prompt 為空，可能已全部完成"
        break
    }

    Log "呼叫 claude -p 進行翻譯..."
    $output = $prompt | claude --dangerously-skip-permissions -p

    $json = Extract-Result $output
    if ($json) {
        $json | Out-File -Encoding utf8 "data\_batch_temp.json"
        python scripts/ai_score.py save-batch $today data\_batch_temp.json
        Remove-Item "data\_batch_temp.json" -ErrorAction SilentlyContinue
        Log "第 $batchCount 批儲存完成"
    } else {
        Log "警告：第 $batchCount 批輸出中找不到 <result> 標籤，跳過"
        Log "claude 原始輸出前 500 字：$($output.Substring(0, [Math]::Min(500, $output.Length)))"
        break
    }
}

# ── 階段三：Finalize ─────────────────────────────────────────
Log "執行 finalize"
python scripts/ai_score.py finalize $today

# 確認最終文件生成
if (-not (Test-Path $weekFile)) {
    Log "錯誤：finalize 後 $today.json 不存在，中止 git push"
    exit 1
}

# ── Git push ──────────────────────────────────────────────────
Log "git commit + push"
git add "data\$today.json" "data\index.json" "data\search_index.json"
git commit -m "weekly: $today 週報發布"
git push
Log "git push 完成"

# ── 發送郵件（等待 GitHub Pages 部署，2 分鐘後）──────────────
Log "等待 2 分鐘後發送郵件..."
Start-Sleep -Seconds 120
python scripts/send_email.py $today
Log "郵件發送完成"

Log "=== 週報處理完成（共 $batchCount 批翻譯）==="
