"""
Step 4: 由澄澄手动执行 — 打分 + 翻譯繁體中文 + 生成日語摘要
用法：直接告訴澄澄「幫我處理本週新聞」，澄澄會讀取 data/filtered.json，
打分並翻譯後寫入 data/YYYY-MM-DD.json，再更新 index.json。

此腳本不會自動執行，由澄澄在 Claude Code 對話中調用。
"""

import json
import os
from datetime import datetime, timezone


def load_filtered() -> dict:
    with open("data/filtered.json", encoding="utf-8") as f:
        return json.load(f)


def save_weekly(categories: dict, date: str = None):
    if not date:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    weekly_data = {
        "date": date,
        "articles": categories,
    }

    output_path = f"data/{date}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(weekly_data, f, ensure_ascii=False, indent=2)
    print(f"已儲存: {output_path}")

    # 更新 index.json
    index_path = "data/index.json"
    if os.path.exists(index_path):
        with open(index_path, encoding="utf-8") as f:
            index = json.load(f)
    else:
        index = {"weeks": []}

    if date not in index["weeks"]:
        index["weeks"].insert(0, date)
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
        print(f"已更新: {index_path}")

    return output_path


# 打分格式說明（給澄澄參考）
SCORING_GUIDE = """
請對每條新聞完成以下處理：

1. score（0~10）：
   - 9~10：重大突破、重要產品發布、行業里程碑
   - 7~8：有實質內容的新產品/功能/研究成果
   - 5~6：一般性動態，值得關注但不緊迫
   - 3~4：信息量少、重複報道
   - 1~2：軟文、泛泛而談

   斌斌是3D手辦原型師，使用ZBrush，3D AI相關新聞優先給高分。

2. summary_cht（繁體中文，50字以內）：準確概括核心內容

3. summary_ja（日語，50字以內）：準確概括核心內容

4. summary_en（英文，若原文是英文則直接用原始摘要的精簡版，50字以內）
"""


if __name__ == "__main__":
    print(SCORING_GUIDE)
    data = load_filtered()
    total = sum(len(v) for v in data.values())
    print(f"\n待處理：{total} 條新聞")
    for cat, articles in data.items():
        print(f"\n=== {cat} ({len(articles)}條) ===")
        for i, a in enumerate(articles):
            print(f"{i+1}. [{a['language']}] {a['source']}: {a['title']}")
            if a.get("summary_original"):
                print(f"   摘要: {a['summary_original'][:100]}")
