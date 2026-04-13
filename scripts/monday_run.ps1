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

# 載入郵件相關環境變數（GMAIL_SENDER, GMAIL_APP_PASSWORD, NOTIFY_EMAILS）
$envFile = "C:\Users\inice\claudeAgent\.env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
        }
    }
    Log "已載入 .env 環境變數"
}

# ── 階段一：評分（分批循環，每批 SCORING_BATCH_SIZE 篇，避免輸出截斷）───────────
$scoringBatch = 0
$scoringFails = 0
$maxScoringFails = 3

while ($true) {
    $statusJson = python scripts/ai_score.py status $today | ConvertFrom-Json
    if ($null -eq $statusJson) {
        Log "錯誤：無法取得狀態，中止"
        exit 1
    }
    if ($statusJson.phase -ne "scoring") { break }
    if ($statusJson.pending_count -eq 0) { break }

    $scoringBatch++
    Log "評分第 $scoringBatch 批（剩餘 $($statusJson.pending_count) 篇未評分）"

    $prompt = python scripts/ai_score.py scoring-batch-prompt $today
    if (-not $prompt) {
        Log "評分 prompt 為空，評分完成"
        break
    }

    Log "呼叫 claude -p 進行評分..."
    $output = $prompt | claude --dangerously-skip-permissions -p

    $json = Extract-Result $output
    if ($json) {
        $json | Out-File -Encoding utf8 "data\_scores_temp.json"
        python scripts/ai_score.py save-scores $today data\_scores_temp.json
        Remove-Item "data\_scores_temp.json" -ErrorAction SilentlyContinue
        Log "第 $scoringBatch 批評分完成"
        $scoringFails = 0
    } else {
        $scoringFails++
        $outputText = if ($output -is [array]) { $output -join "`n" } else { "$output" }
        Log "警告：第 $scoringBatch 批評分輸出中找不到 <result> 標籤（連續失敗 $scoringFails 次）"
        if ($outputText) {
            $preview = $outputText.Substring(0, [Math]::Min(500, $outputText.Length))
            Log "claude 原始輸出前 500 字：$preview"
        }
        if ($scoringFails -ge $maxScoringFails) {
            Log "錯誤：評分連續失敗 $maxScoringFails 次，中止"
            exit 1
        }
    }
}
Log "評分階段完成，進入翻譯"

# ── 階段二：翻譯（逐篇循環，避免 claude -p 輸出截斷）─────────
$maxBatches = 30
$batchCount = 0
$failCount = 0
$maxFails = 3           # 連續「非限流」失敗超過此數則中止
$rateLimitRetries = 0
$maxRateLimitRetries = 3  # 限流最多重試 3 次（每次等待後重試）

while ($batchCount -lt $maxBatches) {
    $statusJson = python scripts/ai_score.py status $today | ConvertFrom-Json

    if ($statusJson.phase -eq "done" -or $statusJson.phase -ne "translating") { break }

    $batchCount++
    Log "翻譯第 $batchCount 篇（剩餘 $($statusJson.pending_count) 篇）"

    # 使用 single-translation-prompt：每次只翻譯 1 篇
    $prompt = python scripts/ai_score.py single-translation-prompt $today
    if (-not $prompt) {
        Log "翻譯 prompt 為空，可能已全部完成"
        break
    }

    # 翻譯使用 Sonnet 模型（降低撞限風險，翻譯品質足夠）
    Log "呼叫 claude -p --model sonnet 進行翻譯..."
    $output = $prompt | claude --dangerously-skip-permissions -p --model sonnet

    $json = Extract-Result $output
    if ($json) {
        $json | Out-File -Encoding utf8 "data\_batch_temp.json"
        python scripts/ai_score.py save-batch $today data\_batch_temp.json
        Remove-Item "data\_batch_temp.json" -ErrorAction SilentlyContinue
        Log "第 $batchCount 篇翻譯完成"
        $failCount = 0
        $rateLimitRetries = 0
    } else {
        # 判斷是否為限流錯誤
        $outputText = if ($output -is [array]) { $output -join "`n" } else { "$output" }
        $isRateLimit = $outputText -match "hit your limit|rate.?limit|resets \d"

        if ($isRateLimit) {
            $rateLimitRetries++
            Log "限流：第 $rateLimitRetries 次（上限 $maxRateLimitRetries 次）"

            if ($rateLimitRetries -ge $maxRateLimitRetries) {
                Log "錯誤：限流重試已達上限，中止翻譯"
                break
            }

            # 嘗試解析重置時間，否則遞增回退（10m / 20m / 30m）
            $waitMinutes = $rateLimitRetries * 10
            if ($outputText -match "resets (\d{1,2})(am|pm)") {
                $resetHour = [int]$matches[1]
                if ($matches[2] -eq "pm" -and $resetHour -ne 12) { $resetHour += 12 }
                $nowJst = Get-JstNow
                $resetTime = $nowJst.Date.AddHours($resetHour)
                if ($resetTime -gt $nowJst) {
                    $waitMinutes = [Math]::Ceiling(($resetTime - $nowJst).TotalMinutes) + 2
                }
            }

            Log "等待 $waitMinutes 分鐘後重試..."
            Start-Sleep -Seconds ($waitMinutes * 60)
            $batchCount--  # 不計入本次，重新翻譯同一篇
        } else {
            $failCount++
            Log "警告：第 $batchCount 篇輸出中找不到 <result> 標籤（連續失敗 $failCount 次）"
            if ($outputText) {
                $preview = $outputText.Substring(0, [Math]::Min(500, $outputText.Length))
                Log "claude 原始輸出前 500 字：$preview"
            }
            if ($failCount -ge $maxFails) {
                Log "錯誤：連續失敗 $maxFails 次，中止翻譯"
                break
            }
        }
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
