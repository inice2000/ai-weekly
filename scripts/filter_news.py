"""
Step 2 & 3: 主题分类 + 规则过滤 + 数量控制
- 分类：3D AI / AI Agent / AI行业
- 去重（标题相似度 > 80%）
- 关键词黑名单去软文
- 各分类取前 15 条
"""

import json
import re
from difflib import SequenceMatcher

# AI 基础关键词（文章必须包含其中之一才入选）
KEYWORDS_AI_BASE = [
    "ai", "artificial intelligence", "machine learning", "deep learning",
    "large language model", "llm", "generative", "neural", "diffusion",
    "人工智能", "机器学习", "大模型", "生成式", "神经网络",
    "AI", "人工知能", "機械学習", "生成AI",
]

# 3D AI 判断：文章中同时出现「3D相关词」和「AI相关词」
KEYWORDS_3D = [
    "3d", "nerf", "zbrush", "meshy", "tripo", "luma", "gaussian splatting",
    "photogrammetry", "point cloud", "sculpt", "voxel", "3d model",
    "三维", "建模", "雕刻", "3Dモデル", "三次元",
]

# AI Agent 关键词
KEYWORDS_AGENT = [
    "ai agent", "llm agent", "autonomous agent", "agentic", "multi-agent",
    "ai workflow", "ai automation", "claude agent", "gpt agent", "copilot",
    "mcp ", "model context protocol", "function calling", "tool use",
    "prompt engineering", "system prompt", "ai tips", "ai tricks",
    "how to use ai", "ai productivity", "ai assistant tips",
    "ai工作流", "ai自动化", "ai助手使用", "提示词", "智能体",
    "AIエージェント", "エージェント", "プロンプト",
]

# 技术/产品导向关键词 → 相关度加分
TECH_SCORE_KEYWORDS = [
    "model", "release", "launch", "api", "sdk", "open source", "benchmark",
    "architecture", "training", "inference", "fine-tuning", "multimodal",
    "reasoning", "framework", "dataset", "plugin", "feature", "update",
    "3d", "nerf", "diffusion", "agent", "workflow", "mcp", "copilot",
    "开源", "发布", "模型", "训练", "推理", "API", "工具", "功能",
    "モデル", "リリース", "オープンソース", "機能", "ツール",
]

# 社会/政治导向关键词 → 相关度减分
SOCIAL_SCORE_KEYWORDS = [
    "poll", "survey", "voters", "election", "fear", "anxiety", "oppose",
    "ban", "regulation", "congress", "senate", "government policy",
    "workers fear", "job loss", "protest", "union", "boycott",
    "民调", "选举", "监管", "禁止", "舆论",
]


def relevance_score(article: dict) -> int:
    """计算文章相关度分数：技术/产品类加分，社会/政治类减分"""
    text = (article.get("title", "") + " " + article.get("summary_original", "")).lower()
    score = 0
    for kw in TECH_SCORE_KEYWORDS:
        if kw.lower() in text:
            score += 1
    for kw in SOCIAL_SCORE_KEYWORDS:
        if kw.lower() in text:
            score -= 2
    return score


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


def is_ai_related(article: dict) -> bool:
    """文章必须包含 AI 基础关键词"""
    text = (article.get("title", "") + " " + article.get("summary_original", "")).lower()
    return any(kw.lower() in text for kw in KEYWORDS_AI_BASE)


def is_3d_ai(article: dict) -> bool:
    """同时包含3D相关词和AI相关词才归为 3D AI"""
    text = (article.get("title", "") + " " + article.get("summary_original", "")).lower()
    has_3d = any(kw.lower() in text for kw in KEYWORDS_3D)
    has_ai = is_ai_related(article)
    return has_3d and has_ai


def is_agent(article: dict) -> bool:
    """包含 AI Agent / 使用技巧相关词"""
    text = (article.get("title", "") + " " + article.get("summary_original", "")).lower()
    return any(kw.lower() in text for kw in KEYWORDS_AGENT)


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
    1. 分类（3D AI / AI Agent / AI行业）
    2. 黑名单过滤
    3. 去重
    4. 各取前 15 条
    """
    categories = {"3d_ai": [], "ai_agent": [], "ai_industry": []}

    for article in articles:
        if not article.get("title"):
            continue
        if not is_ai_related(article):
            continue
        if is_blacklisted(article):
            continue
        if is_3d_ai(article):
            article["category"] = "3d_ai"
            categories["3d_ai"].append(article)
        elif is_agent(article):
            article["category"] = "ai_agent"
            categories["ai_agent"].append(article)
        else:
            article["category"] = "ai_industry"
            categories["ai_industry"].append(article)

    # 去重
    for cat in categories:
        categories[cat] = deduplicate(categories[cat])

    # 按相关度排序（技术/产品类优先）后取前 15 条
    for cat in categories:
        categories[cat] = sorted(categories[cat], key=relevance_score, reverse=True)[:15]
        en = sum(1 for a in categories[cat] if a.get("language") == "en")
        zh = sum(1 for a in categories[cat] if a.get("language") == "zh")
        ja = sum(1 for a in categories[cat] if a.get("language") == "ja")
        print(f"  [{cat}] 过滤后: {len(categories[cat])} 条 (en:{en} zh:{zh} ja:{ja})")

    return categories


if __name__ == "__main__":
    with open("data/raw.json", encoding="utf-8") as f:
        articles = json.load(f)

    print(f"原始: {len(articles)} 条")
    categories = filter_and_classify(articles)

    with open("data/filtered.json", "w", encoding="utf-8") as f:
        json.dump(categories, f, ensure_ascii=False, indent=2)
    print("已保存到 data/filtered.json")
