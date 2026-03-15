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

    # 更新 search_index.json
    _update_search_index(date, categories)

    return output_path


def _update_search_index(date: str, categories: dict):
    """將本週文章追加/更新至 search_index.json，支援全語言檢索。"""
    search_path = "data/search_index.json"
    if os.path.exists(search_path):
        with open(search_path, encoding="utf-8") as f:
            index = json.load(f)
    else:
        index = []

    # 移除同一週的舊資料（重新處理時覆蓋）
    index = [a for a in index if a.get("date") != date]

    for cat, articles in categories.items():
        for idx, a in enumerate(articles):
            index.append({
                "date":               date,
                "category":           cat,
                "idx":                idx,
                "title":              a.get("title", ""),
                "title_cht":          a.get("title_cht", ""),
                "title_ja":           a.get("title_ja", ""),
                "url":                a.get("url", ""),
                "source":             a.get("source", ""),
                "language":           a.get("language", ""),
                "score":              a.get("score", 0),
                "tags":               a.get("tags", []),
                "summary_points_cht": a.get("summary_points_cht", []),
                "summary_points_ja":  a.get("summary_points_ja", []),
                "summary_cht":        a.get("summary_cht", ""),
                "summary_ja":         a.get("summary_ja", ""),
                "summary_en":         a.get("summary_en", ""),
            })

    # 按日期降序排列
    index.sort(key=lambda x: x.get("date", ""), reverse=True)

    with open(search_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    print(f"已更新: {search_path}（共 {len(index)} 條）")


# 打分格式說明（給澄澄參考）
SCORING_GUIDE = """
請對每條新聞完成以下處理：

1. score（0~10）：
   - 9~10：重大突破、重要產品發布、行業里程碑
   - 7~8：有實質內容的新產品/功能/研究成果
   - 5~6：一般性動態，值得關注但不緊迫
   - 3~4：信息量少、重複報道
   - 1~2：軟文、泛泛而談

   優先給高分的類型（AI 技術/產品向）：
   - 新模型發布、API 更新、基準測試突破
   - AI 工具新功能、開發框架、開源項目
   - 具體技術研究成果、架構創新
   - 3D AI 相關（斌斌是3D手辦原型師，使用ZBrush，此類別最高優先）
   - AI Agent / MCP / 工作流 / 提示詞工程 / 頂尖工程師的AI使用方式

   降低優先級的類型（社會/政治/消費向）：
   - 民調、輿論調查、公眾對AI的看法
   - 選舉、政策、監管草案（無具體技術內容）
   - 社群媒體平台的商業糾紛（無技術突破）
   - 名人觀點、社論評論性文章

2. title_cht（繁體中文標題）：
   - 原文為英文/日文 → 準確翻譯
   - 原文已是繁體中文 → 直接複製
   - 原文是簡體中文 → 轉換為繁體中文

3. title_ja（日語標題）：
   - 原文為英文/中文 → 準確翻譯成日語
   - 原文已是日語 → 直接複製

4. tags（標籤陣列，3~5個）：以 # 開頭，用繁體中文或英文，例如：["#GPT-5", "#OpenAI", "#LLM", "#AI推理"]
   - 使用具體名詞（產品名、公司名、技術術語），避免過於寬泛的標籤如 #AI

5. summary_points_cht（繁體中文重點，陣列，3~5條）：每條一句話，涵蓋關鍵數據、核心事件、影響意義
   範例：["GPT-5 在 MATH 測試達到 97.3 分", "支援 256K Token 上下文", "API 同步開放定價降低 20%"]

6. summary_points_ja（日語重點，陣列，3~5條）：同上，日語版本

7. content_cht（繁體中文全文翻譯）：
   - 原文是英文/日文，且有 content_original → 逐字逐句完整翻譯成繁體中文，保留所有段落與細節，不得刪減、不得總結歸納，1000字以上
   - 原文是英文/日文，無 content_original → 根據 title、summary_original 補充撰寫完整報導，300字以上
   - 原文是簡體/繁體中文（language="zh"） → 直接轉換為繁體中文，不需重新翻譯，直接複製 content_original 並轉繁體即可

8. content_ja（日語版全文）：
   - 原文是英文/中文，且有 content_original → 逐字逐句完整翻譯成日語，保留所有段落與細節，不得刪減
   - 原文已是日文（language="ja"） → 直接填入 content_original 原文，不需翻譯
   - 無 content_original → 根據 title、summary_original 補充撰寫完整日語報導
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
