"""
Step 2 & 3: 主题分类 + 规则过滤 + 数量控制
- 分类：3D AI / AI行业
- 去重（标题相似度 > 80%）
- 关键词黑名单去软文
- 各分类取前 15 条
"""

import json
import re
from difflib import SequenceMatcher

# 3D AI 关键词（命中任意一个即归为 3D AI 分类）
KEYWORDS_3D_AI = [
    "3d", "3d ai", "3d generation", "nerf", "zbrush", "meshy", "tripo",
    "luma ai", "3d diffusion", "generative 3d", "point cloud", "mesh",
    "sculpt", "3d model", "photogrammetry", "gaussian splatting",
    "三维", "3d生成", "三维生成", "建模", "雕刻",
    "3Dモデル", "3D生成", "三次元",
]

# 软文黑名单关键词（命中即丢弃）
BLACKLIST_KEYWORDS = [
    "限时优惠", "折扣", "促销", "赞助", "广告", "affiliate",
    "buy now", "discount", "sponsored", "subscribe now",
    "セール", "割引", "PR",
]

# 泛泛标题黑名单（过于空洞的文章）
VAGUE_PATTERNS = [
    r"将(彻底)?改变(世界|未来|行业)",
    r"AI的未来",
    r"你不得不知道的",
    r"everything you need to know",
    r"will change the world",
    r"the future of AI",
]


def is_3d_ai(article: dict) -> bool:
    text = (article.get("title", "") + " " + article.get("summary_original", "")).lower()
    return any(kw.lower() in text for kw in KEYWORDS_3D_AI)


def is_blacklisted(article: dict) -> bool:
    text = article.get("title", "") + " " + article.get("summary_original", "")
    # 黑名单关键词
    if any(kw.lower() in text.lower() for kw in BLACKLIST_KEYWORDS):
        return True
    # 泛泛标题
    if any(re.search(p, text) for p in VAGUE_PATTERNS):
        return True
    return False


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def deduplicate(articles: list[dict], threshold: float = 0.8) -> list[dict]:
    """去除标题相似度超过阈值的重复文章"""
    result = []
    for article in articles:
        title = article.get("title", "")
        if not title:
            continue
        is_dup = any(similarity(title, kept.get("title", "")) > threshold for kept in result)
        if not is_dup:
            result.append(article)
    return result


def filter_and_classify(articles: list[dict]) -> dict:
    """
    主流程：
    1. 分类（3D AI / AI行业）
    2. 黑名单过滤
    3. 去重
    4. 各取前 15 条
    """
    categories = {"3d_ai": [], "ai_industry": []}

    for article in articles:
        if not article.get("title"):
            continue
        if is_blacklisted(article):
            continue
        if is_3d_ai(article):
            article["category"] = "3d_ai"
            categories["3d_ai"].append(article)
        else:
            article["category"] = "ai_industry"
            categories["ai_industry"].append(article)

    # 去重
    for cat in categories:
        categories[cat] = deduplicate(categories[cat])

    # 数量控制：各取前 15 条（已按 popularity 排序，直接截取）
    for cat in categories:
        categories[cat] = categories[cat][:15]
        print(f"  [{cat}] 过滤后: {len(categories[cat])} 条")

    return categories


if __name__ == "__main__":
    with open("data/raw.json", encoding="utf-8") as f:
        articles = json.load(f)

    print(f"原始: {len(articles)} 条")
    categories = filter_and_classify(articles)

    with open("data/filtered.json", "w", encoding="utf-8") as f:
        json.dump(categories, f, ensure_ascii=False, indent=2)
    print("已保存到 data/filtered.json")
