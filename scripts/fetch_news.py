"""
Step 1: 抓取新闻
- NewsAPI 抓取英文新闻
- RSS 抓取中文新闻（量子位、36kr、机器之心）
- RSS 抓取日文新闻（Gigazine、ITmedia、ASCII.jp）
"""

import os
import json
import feedparser
import requests
from datetime import datetime, timedelta, timezone

NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "")

# RSS 来源
RSS_SOURCES = [
    # 中文
    {"url": "https://www.qbitai.com/feed", "lang": "zh", "name": "量子位"},
    {"url": "https://36kr.com/feed", "lang": "zh", "name": "36kr"},
    {"url": "https://www.jiqizhixin.com/rss", "lang": "zh", "name": "机器之心"},
    # 日文
    {"url": "https://gigazine.net/news/rss_2.0/", "lang": "ja", "name": "Gigazine"},
    {"url": "https://rss.itmedia.co.jp/rss/2.0/ait.xml", "lang": "ja", "name": "ITmedia AI"},
    {"url": "https://ascii.jp/rss.xml", "lang": "ja", "name": "ASCII.jp"},
]

# NewsAPI 搜索关键词（英文）
EN_KEYWORDS = [
    "artificial intelligence",
    "AI 3D generation",
    "generative AI",
    "large language model",
    "AI tools",
    "NeRF 3D",
    "AI image generation",
    "AI agent",
    "prompt engineering",
    "AI workflow automation",
]


def fetch_newsapi(keyword: str, from_date: str) -> list[dict]:
    """从 NewsAPI 抓取单个关键词的新闻"""
    if not NEWS_API_KEY:
        print("[警告] NEWS_API_KEY 未设置，跳过 NewsAPI")
        return []
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": keyword,
        "from": from_date,
        "language": "en",
        "sortBy": "popularity",
        "pageSize": 20,
        "apiKey": NEWS_API_KEY,
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        articles = resp.json().get("articles", [])
        result = []
        for a in articles:
            result.append({
                "title": a.get("title", ""),
                "url": a.get("url", ""),
                "source": a.get("source", {}).get("name", ""),
                "language": "en",
                "summary_original": a.get("description", "") or a.get("content", "") or "",
                "summary": "",
                "published_at": a.get("publishedAt", ""),
                "category": "",
                "score": 0,
            })
        return result
    except Exception as e:
        print(f"[错误] NewsAPI 关键词「{keyword}」抓取失败: {e}")
        return []


def fetch_rss(source: dict, from_date: datetime) -> list[dict]:
    """从 RSS 抓取新闻"""
    try:
        feed = feedparser.parse(source["url"])
        result = []
        for entry in feed.entries:
            # 发布时间过滤
            pub = entry.get("published_parsed") or entry.get("updated_parsed")
            if pub:
                pub_dt = datetime(*pub[:6], tzinfo=timezone.utc)
                if pub_dt < from_date:
                    continue
            summary = entry.get("summary", "") or entry.get("description", "")
            # 去除 HTML 标签
            import re
            summary = re.sub(r"<[^>]+>", "", summary).strip()
            result.append({
                "title": entry.get("title", ""),
                "url": entry.get("link", ""),
                "source": source["name"],
                "language": source["lang"],
                "summary_original": summary[:500],
                "summary": "",
                "published_at": entry.get("published", "") or entry.get("updated", ""),
                "category": "",
                "score": 0,
            })
        return result
    except Exception as e:
        print(f"[错误] RSS 来源「{source['name']}」抓取失败: {e}")
        return []


def fetch_all() -> list[dict]:
    """抓取所有来源，返回原始新闻列表"""
    # 抓取过去 7 天的新闻
    from_dt = datetime.now(timezone.utc) - timedelta(days=7)
    from_date_str = from_dt.strftime("%Y-%m-%d")

    all_articles = []

    # NewsAPI 英文
    print("抓取 NewsAPI 英文新闻...")
    for kw in EN_KEYWORDS:
        articles = fetch_newsapi(kw, from_date_str)
        all_articles.extend(articles)
        print(f"  [{kw}] {len(articles)} 条")

    # RSS 中日文
    print("抓取 RSS 新闻...")
    for source in RSS_SOURCES:
        articles = fetch_rss(source, from_dt)
        all_articles.extend(articles)
        print(f"  [{source['name']}] {len(articles)} 条")

    print(f"\n原始抓取总计: {len(all_articles)} 条")
    return all_articles


if __name__ == "__main__":
    articles = fetch_all()
    # 临时保存，供下一步处理
    with open("data/raw.json", "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    print("已保存到 data/raw.json")
