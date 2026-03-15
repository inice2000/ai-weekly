"""
主入口：每周一运行，串联完整流程
fetch → filter → score → 生成 JSON → 更新 index
"""

import json
import os
import sys
from datetime import datetime, timezone

# 切换到仓库根目录
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(repo_root)
sys.path.insert(0, os.path.join(repo_root, "scripts"))

from fetch_news import fetch_all
from filter_news import filter_and_classify
from ai_score import score_all


def run():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"=== AI Weekly {today} ===\n")

    # Step 1: 抓取
    print("Step 1: 抓取新闻")
    articles = fetch_all()

    # Step 2 & 3: 分类 + 过滤 + 数量控制
    print("\nStep 2&3: 分类 + 规则过滤")
    categories = filter_and_classify(articles)

    # Step 4: AI 打分 + 翻译
    print("\nStep 4: AI 打分 + 摘要翻译")
    categories = score_all(categories)

    # 生成周报 JSON
    weekly_data = {
        "date": today,
        "articles": categories,
    }
    output_path = f"data/{today}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(weekly_data, f, ensure_ascii=False, indent=2)
    print(f"\n已生成: {output_path}")

    # 更新 index.json
    index_path = "data/index.json"
    if os.path.exists(index_path):
        with open(index_path, encoding="utf-8") as f:
            index = json.load(f)
    else:
        index = {"weeks": []}

    if today not in index["weeks"]:
        index["weeks"].insert(0, today)  # 最新的放最前面

    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    print(f"已更新: {index_path}")

    # 清理临时文件
    for tmp in ["data/raw.json", "data/filtered.json", "data/scored.json"]:
        if os.path.exists(tmp):
            os.remove(tmp)

    print("\n=== 完成 ===")


if __name__ == "__main__":
    run()
