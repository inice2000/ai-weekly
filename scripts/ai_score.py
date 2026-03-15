"""
Step 4: AI 打分 + 摘要翻译成中文
- 用 Claude API 对每条新闻打分（0~10）
- 将摘要翻译为中文
- 按分数重新排序
"""

import os
import json
import anthropic

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

SCORE_PROMPT = """你是一位 AI 科技新闻编辑，专注于 AI 行业动态和 3D AI 技术。

请对以下新闻进行评分和处理，返回 JSON 格式。

评分标准（0~10分）：
- 9~10：重大突破、重要产品发布、行业里程碑事件
- 7~8：有实质内容的新产品/功能/研究成果
- 5~6：一般性行业动态、值得关注但不紧迫
- 3~4：信息量少、重复报道
- 1~2：软文、营销内容、泛泛而谈

新闻列表：
{articles}

请返回以下 JSON 格式（数组，与输入顺序一致）：
[
  {{
    "score": 8.5,
    "summary": "用简洁中文写50字以内的摘要，准确概括核心内容"
  }},
  ...
]

只返回 JSON，不要其他内容。"""


def score_batch(articles: list[dict]) -> list[dict]:
    """对一批新闻打分并翻译摘要（每次最多10条）"""
    articles_text = json.dumps(
        [{"title": a["title"], "summary_original": a["summary_original"][:300]} for a in articles],
        ensure_ascii=False,
        indent=2,
    )
    prompt = SCORE_PROMPT.format(articles=articles_text)

    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = message.content[0].text.strip()
        # 去除可能的 markdown 代码块
        if text.startswith("```"):
            text = "\n".join(text.split("\n")[1:-1])
        results = json.loads(text)
        for i, article in enumerate(articles):
            if i < len(results):
                article["score"] = results[i].get("score", 0)
                article["summary"] = results[i].get("summary", "")
        return articles
    except Exception as e:
        print(f"[错误] AI 打分失败: {e}")
        # 失败时保留原始摘要
        for article in articles:
            article["score"] = 5
            article["summary"] = article.get("summary_original", "")[:100]
        return articles


def score_all(categories: dict) -> dict:
    """对所有分类的新闻打分"""
    for cat, articles in categories.items():
        print(f"AI 打分: [{cat}] {len(articles)} 条...")
        # 每批 10 条
        for i in range(0, len(articles), 10):
            batch = articles[i:i+10]
            score_batch(batch)

        # 按分数降序排列
        categories[cat] = sorted(articles, key=lambda x: x.get("score", 0), reverse=True)
        print(f"  完成，最高分: {categories[cat][0]['score'] if categories[cat] else 'N/A'}")

    return categories


if __name__ == "__main__":
    with open("data/filtered.json", encoding="utf-8") as f:
        categories = json.load(f)

    categories = score_all(categories)

    with open("data/scored.json", "w", encoding="utf-8") as f:
        json.dump(categories, f, ensure_ascii=False, indent=2)
    print("已保存到 data/scored.json")
