"""
Step 2.5: 抓取新聞全文
在 filter_news.py（Step 3）之後、ai_score.py（Step 4）之前執行。

讀取 data/filtered.json，對每篇文章抓取原文全文，
將結果寫入 content_original 欄位，原地更新 filtered.json。

用法：
    cd ai-weekly
    python scripts/fetch_content.py
"""

import json
import time
import re

import requests
import trafilatura

# 每次請求間隔（秒），避免被封
REQUEST_DELAY = 1.2

# 單篇文章最大字元數（超過截斷）
MAX_CHARS = 8000

# 請求超時（秒）
TIMEOUT = 15

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,ja;q=0.8,en;q=0.7",
}

# 已知付費牆或無法抓取的域名，直接跳過
PAYWALL_DOMAINS = {
    "wsj.com", "nytimes.com", "ft.com", "bloomberg.com",
    "economist.com", "technologyreview.com",
}


def is_paywalled(url: str) -> bool:
    for domain in PAYWALL_DOMAINS:
        if domain in url:
            return True
    return False


def fetch_content(url: str) -> str:
    """
    使用 trafilatura 抓取文章正文。
    失敗時回傳空字串。
    """
    if is_paywalled(url):
        print(f"  [跳過 付費牆] {url[:60]}")
        return ""

    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()

        # trafilatura 提取正文（傳入 bytes 讓 trafilatura 自行偵測編碼，解決 Shift-JIS 亂碼）
        text = trafilatura.extract(
            resp.content,
            include_comments=False,
            include_tables=False,
            no_fallback=False,
        )

        if not text:
            print(f"  [無法提取] {url[:60]}")
            return ""

        # 清理多餘空白行
        text = re.sub(r"\n{3,}", "\n\n", text.strip())

        # 超長截斷
        if len(text) > MAX_CHARS:
            text = text[:MAX_CHARS] + "\n\n[...（原文過長，已截斷）]"

        return text

    except requests.exceptions.Timeout:
        print(f"  [逾時] {url[:60]}")
        return ""
    except requests.exceptions.HTTPError as e:
        print(f"  [HTTP {e.response.status_code}] {url[:60]}")
        return ""
    except Exception as e:
        print(f"  [錯誤] {url[:60]} — {e}")
        return ""


def run():
    with open("data/filtered.json", encoding="utf-8") as f:
        data = json.load(f)

    total = sum(len(v) for v in data.values())
    print(f"開始抓取全文，共 {total} 篇文章\n")

    fetched = 0
    skipped = 0

    for cat, articles in data.items():
        print(f"=== {cat} ({len(articles)} 篇) ===")
        for a in articles:
            url = a.get("url", "")
            if not url:
                skipped += 1
                continue

            # 已有內容則跳過（重跑時不重複抓）
            if a.get("content_original"):
                print(f"  [已有] {a['title'][:50]}")
                skipped += 1
                continue

            print(f"  抓取: {a['title'][:50]}")
            content = fetch_content(url)
            a["content_original"] = content

            if content:
                fetched += 1
                print(f"    ✓ {len(content)} 字元")
            else:
                skipped += 1

            time.sleep(REQUEST_DELAY)

        print()

    # 寫回 filtered.json
    with open("data/filtered.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"完成：成功 {fetched} 篇，跳過/失敗 {skipped} 篇")
    print("已更新 data/filtered.json")


if __name__ == "__main__":
    run()
