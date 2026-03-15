"""
主入口：每周一由 GitHub Actions 自动运行
步骤：抓取 → 过滤 → 保存 filtered.json
打分和翻译由澄澄手动完成（告诉澄澄「帮我处理本周新闻」）
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


def run():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"=== AI Weekly 抓取 {today} ===\n")

    # Step 1: 抓取
    print("Step 1: 抓取新闻")
    articles = fetch_all()

    # Step 2 & 3: 分类 + 过滤 + 数量控制
    print("\nStep 2&3: 分类 + 规则过滤")
    categories = filter_and_classify(articles)

    # 保存 filtered.json，等待澄澄手动打分翻译
    with open("data/filtered.json", "w", encoding="utf-8") as f:
        json.dump(categories, f, ensure_ascii=False, indent=2)

    total = sum(len(v) for v in categories.values())
    print(f"\n已保存 data/filtered.json（共 {total} 条）")
    print("下一步：告诉澄澄「帮我处理本周新闻」，澄澄会完成打分和翻译。")


if __name__ == "__main__":
    run()
