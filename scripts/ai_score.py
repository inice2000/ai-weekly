"""
Step 4: 由澄澄手動執行 — 打分篩選 + 翻譯入選文章

【兩階段流程】

階段一：評分篩選（一次完成，全部 N 篇）
  python scripts/ai_score.py [date]
  → 澄澄對所有文章做：score + title_cht + title_ja + tags + summary_points
  → 呼叫 save_scores(date, results) 儲存評分
  → 系統自動篩選 score >= MIN_SCORE 的文章進入翻譯階段

階段二：全文翻譯（分批，僅限入選文章）
  python scripts/ai_score.py [date]
  → 系統顯示下一批待翻譯文章（依 content_original 字元數自動分批）
  → 澄澄翻譯 content_cht + content_ja
  → 呼叫 save_batch(date, results) 儲存進度
  → 重複直到全部完成，執行 finalize(date)

【批次大小邏輯】
- 以 content_original 總字元數為依據（目標每批 ≤ TARGET_CHARS）
- 自動適應文章數量多少
- 單篇超長文章（> LONG_ARTICLE_CHARS）單獨成一批

此腳本不會自動執行，由澄澄在 Claude Code 對話中調用。
"""

import json
import os
from datetime import datetime, timezone

# 入選最低分數（低於此分數不翻譯，不進入週報）
MIN_SCORE = 6

# 每批 content_original 字元數上限（約 3,000 input tokens）
TARGET_CHARS = 12000

# 超過此長度的單篇文章獨立成一批
LONG_ARTICLE_CHARS = 10000

# 進度檔路徑
def _progress_path(date: str) -> str:
    return f"data/_progress_{date}.json"


def load_filtered() -> dict:
    with open("data/filtered.json", encoding="utf-8") as f:
        return json.load(f)


def _load_progress(date: str) -> dict:
    path = _progress_path(date)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {
        "date": date,
        "phase": "scoring",       # "scoring" | "translating" | "done"
        "scores": {},              # key -> score 結果（階段一）
        "selected_keys": [],       # score >= MIN_SCORE 的文章 key 列表
        "translated_keys": [],     # 已完成翻譯的 key 列表
        "translations": {},        # key -> 翻譯結果（階段二）
    }


def _save_progress(date: str, progress: dict):
    path = _progress_path(date)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def show_next_batch(date: str = None) -> dict:
    """
    顯示當前階段應處理的內容。
    - 階段一（scoring）：列出所有待評分文章
    - 階段二（translating）：列出下一批待翻譯文章
    - 完成時提示執行 finalize()
    回傳 {"phase": ..., "items": [...]}
    """
    if not date:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    filtered = load_filtered()
    progress = _load_progress(date)
    phase = progress["phase"]

    total_filtered = sum(len(v) for v in filtered.values())

    # ── 階段一：評分 ──────────────────────────────────────
    if phase == "scoring":
        all_articles = []
        for cat, articles in filtered.items():
            for idx, a in enumerate(articles):
                all_articles.append({
                    "key": f"{cat}/{idx}",
                    "cat": cat,
                    "idx": idx,
                    "article": a,
                })
        print(f"【階段一：評分篩選】共 {total_filtered} 篇")
        print(f"請對每篇給出：score, title_cht, title_ja, tags,")
        print(f"summary_points_cht, summary_points_ja（無需翻譯全文）")
        print(f"score < {MIN_SCORE} 的文章將不進入週報，不需要翻譯。")
        print()
        for item in all_articles:
            a = item["article"]
            print(f"  [{item['key']}][{a['language']}] {a['title'][:65]}")
        print()
        print(f"完成後呼叫 save_scores('{date}', results)")
        return {"phase": "scoring", "items": all_articles}

    # ── 階段二：翻譯 ──────────────────────────────────────
    if phase == "translating":
        selected = progress["selected_keys"]
        translated = set(progress["translated_keys"])
        pending_keys = [k for k in selected if k not in translated]

        if not pending_keys:
            print(f"✅ 全文翻譯完成！可執行 finalize('{date}')")
            return {"phase": "done", "items": []}

        # 還原 key → article 映射
        article_map = {}
        for cat, articles in filtered.items():
            for idx, a in enumerate(articles):
                article_map[f"{cat}/{idx}"] = {"cat": cat, "idx": idx, "article": a}

        # 組成本批（依字元數）
        batch = []
        accumulated = 0
        for key in pending_keys:
            item = article_map[key]
            a = item["article"]
            orig_len = len(a.get("content_original", ""))
            if orig_len > LONG_ARTICLE_CHARS and batch:
                break
            batch.append({"key": key, **item, "orig_len": orig_len})
            accumulated += orig_len
            if orig_len > LONG_ARTICLE_CHARS:
                break
            if accumulated >= TARGET_CHARS:
                break

        done_count = len(translated)
        total_selected = len(selected)
        print(f"【階段二：全文翻譯】進度 {done_count}/{total_selected} 篇已完成")
        print(f"本批：{len(batch)} 篇，content_original 合計 {accumulated:,} 字元")
        print()
        for item in batch:
            a = item["article"]
            score = progress["scores"].get(item["key"], {}).get("score", "?")
            print(f"  [{item['key']}][score:{score}][{a['language']}] {a['title'][:55]}")
            print(f"    orig: {item['orig_len']:,} chars")
        print()
        print(f"完成後呼叫 save_batch('{date}', results)")
        return {"phase": "translating", "items": batch}

    # ── 完成 ──────────────────────────────────────────────
    print(f"✅ 所有工作完成，可執行 finalize('{date}')")
    return {"phase": "done", "items": []}


def save_scores(date: str, results: list):
    """
    儲存階段一的評分結果，並自動篩選入選文章進入翻譯階段。

    results: list of dict，每項必須包含：
      key, score, title_cht, title_ja, tags,
      summary_points_cht, summary_points_ja
    """
    progress = _load_progress(date)

    for r in results:
        progress["scores"][r["key"]] = r

    # 篩選入選文章（score >= MIN_SCORE），維持原始順序
    selected = [r["key"] for r in results if r.get("score", 0) >= MIN_SCORE]
    progress["selected_keys"] = selected
    progress["phase"] = "translating"

    _save_progress(date, progress)

    total = len(results)
    selected_count = len(selected)
    skipped = total - selected_count
    print(f"✅ 評分完成：{total} 篇中 {selected_count} 篇入選（score ≥ {MIN_SCORE}），{skipped} 篇略過")
    print(f"接下來執行 show_next_batch('{date}') 開始翻譯")


def save_batch(date: str, results: list):
    """
    儲存階段二的一批翻譯結果。

    results: list of dict，每項必須包含：
      key, content_cht, content_ja
    """
    progress = _load_progress(date)

    for r in results:
        key = r["key"]
        progress["translated_keys"].append(key)
        progress["translations"][key] = r

    # 全部翻譯完成時更新狀態
    if set(progress["translated_keys"]) >= set(progress["selected_keys"]):
        progress["phase"] = "done"

    _save_progress(date, progress)
    done = len(progress["translated_keys"])
    total = len(progress["selected_keys"])
    print(f"✅ 已儲存 {len(results)} 篇，翻譯進度 {done}/{total}")


def finalize(date: str = None):
    """
    合併評分 + 翻譯結果，生成最終 data/{date}.json。
    只有 selected_keys 中的文章才會出現在週報中。
    """
    if not date:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    filtered = load_filtered()
    progress = _load_progress(date)

    if progress["phase"] != "done":
        print(f"⚠️  尚未完成所有工作（目前階段：{progress['phase']}），請先完成再執行 finalize。")
        return

    scores = progress["scores"]
    translations = progress["translations"]
    selected_set = set(progress["selected_keys"])

    # 合併資料，只保留入選文章
    categories = {cat: [] for cat in filtered}
    for cat, articles in filtered.items():
        for idx, a in enumerate(articles):
            key = f"{cat}/{idx}"
            if key not in selected_set:
                continue
            score_data = scores.get(key, {})
            trans_data = translations.get(key, {})
            merged = {**a, **{k: v for k, v in score_data.items() if k != "key"},
                           **{k: v for k, v in trans_data.items() if k != "key"}}
            categories[cat].append(merged)

        # 按 score 降序排列
        categories[cat].sort(key=lambda x: x.get("score", 0), reverse=True)

    save_weekly(categories, date)

    # 清理進度檔
    os.remove(_progress_path(date))
    print(f"✅ 已生成 data/{date}.json，進度檔已清除。")


def save_weekly(categories: dict, date: str = None):
    if not date:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    weekly_data = {"date": date, "articles": categories}

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

    _update_search_index(date, categories)
    return output_path


def _update_search_index(date: str, categories: dict):
    search_path = "data/search_index.json"
    if os.path.exists(search_path):
        with open(search_path, encoding="utf-8") as f:
            index = json.load(f)
    else:
        index = []

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

    index.sort(key=lambda x: x.get("date", ""), reverse=True)

    with open(search_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    print(f"已更新: {search_path}（共 {len(index)} 條）")


# ── 評分指南（給澄澄參考）────────────────────────────────
SCORING_GUIDE = """
【階段一：評分篩選】對每篇文章完成以下欄位（不需要翻譯全文）：

1. score（0~10）：
   - 9~10：重大突破、重要產品發布、行業里程碑
   - 7~8：有實質內容的新產品/功能/研究成果
   - 5~6：一般性動態，值得關注但不緊迫
   - 3~4：信息量少、重複報道
   - 1~2：軟文、泛泛而談
   score < 6 的文章不進入週報，不需要翻譯。

   優先給高分（AI 技術/產品向）：
   - 新模型發布、API 更新、基準測試突破
   - AI 工具新功能、開發框架、開源項目
   - 具體技術研究成果、架構創新
   - 3D AI（斌斌是3D手辦原型師，使用ZBrush，此類別最高優先）
   - AI Agent / MCP / 工作流 / 提示詞工程

   降低優先級（社會/政治/消費向，最高給 5 分）：
   - 民調、輿論調查、公眾對AI的看法
   - 選舉、政策、監管草案（無具體技術內容）
   - 社群媒體平台的商業糾紛
   - 名人觀點、社論評論性文章

2. title_cht：英文/日文 → 翻譯；繁中 → 直接複製；簡中 → 轉繁體

3. title_ja：英文/中文 → 翻譯成日語；日語 → 直接複製

4. tags（3~5個，# 開頭）：具體名詞，例如 ["#GPT-5", "#OpenAI", "#LLM"]

5. summary_points_cht（3~5條繁中重點）：每條一句話含關鍵數據

6. summary_points_ja（3~5條日語重點）：同上，日語版本


【階段二：全文翻譯】僅對入選文章（score ≥ 6）翻譯以下欄位：

7. content_cht（繁體中文全文）：
   - 英文/日文原文 → 逐字逐句完整翻譯，不得刪減或總結歸納，1000字以上
   - 簡/繁體中文原文（language="zh"）→ 直接轉繁體，複製 content_original
   - ⚠️ 若 content_original 結尾有 "[...（原文過長，已截斷）]"：
       只翻譯已有部分，結尾加「（原文過長，後續內容無法翻譯）」，不得推測補寫

8. content_ja（日語全文）：
   - 英文/中文原文 → 逐字逐句完整翻譯成日語
   - 日文原文（language="ja"）→ 直接填入 content_original，不需翻譯
   - ⚠️ 若 content_original 結尾有 "[...（原文過長，已截斷）]"：
       只翻譯已有部分，結尾加「（原文が長すぎるため、以降の翻訳は省略）」，不得推測補寫
"""


# ── 自動化用：生成給 claude -p 的 prompt ────────────────────

# 評分 prompt 中每篇文章的 content_original 截斷長度
SCORING_CONTENT_PREVIEW = 800


def build_scoring_prompt(date: str = None) -> str:
    """生成階段一評分的完整 prompt，供 claude -p 調用。"""
    if not date:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filtered = load_filtered()
    articles_list = []
    for cat, articles in filtered.items():
        for idx, a in enumerate(articles):
            preview = a.get("content_original", "")[:SCORING_CONTENT_PREVIEW]
            articles_list.append({
                "key": f"{cat}/{idx}",
                "category": cat,
                "language": a.get("language", ""),
                "title": a.get("title", ""),
                "source": a.get("source", ""),
                "content_preview": preview,
            })
    articles_json = json.dumps(articles_list, ensure_ascii=False, indent=2)
    return f"""你是澄澄，AI 新聞週報的評分助理。

{SCORING_GUIDE}

以下是本週所有待評分文章（JSON，content_preview 為正文前 {SCORING_CONTENT_PREVIEW} 字）：

{articles_json}

---
請對每篇文章完成評分，並在 <result></result> 標籤內輸出 JSON 陣列。
每個元素必須包含以下欄位：
  key, score, title_cht, title_ja, tags, summary_points_cht, summary_points_ja

⚠️ 嚴格要求：
- <result> 標籤外不得有任何文字或說明
- JSON 字符串值中若含引號，必須轉義為 \\\"（或改用「」代替）"""


def build_translation_prompt(date: str = None, single: bool = False) -> str:
    """生成階段二當前批次翻譯的完整 prompt，供 claude -p 調用。
    single=True 時只取 1 篇文章，避免 claude -p 輸出截斷。"""
    if not date:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filtered = load_filtered()
    progress = _load_progress(date)

    selected = progress["selected_keys"]
    translated = set(progress["translated_keys"])
    pending_keys = [k for k in selected if k not in translated]

    if not pending_keys:
        return ""

    article_map = {}
    for cat, articles in filtered.items():
        for idx, a in enumerate(articles):
            article_map[f"{cat}/{idx}"] = a

    # single 模式：只取第一篇待翻譯文章
    if single:
        key = pending_keys[0]
        a = article_map.get(key, {})
        batch = [{
            "key": key,
            "language": a.get("language", ""),
            "title": a.get("title", ""),
            "content_original": a.get("content_original", ""),
        }]
        accumulated = len(a.get("content_original", ""))
    else:
        # 與 show_next_batch 相同的分批邏輯
        batch = []
        accumulated = 0
        for key in pending_keys:
            a = article_map.get(key, {})
            orig_len = len(a.get("content_original", ""))
            if orig_len > LONG_ARTICLE_CHARS and batch:
                break
            batch.append({
                "key": key,
                "language": a.get("language", ""),
                "title": a.get("title", ""),
                "content_original": a.get("content_original", ""),
            })
            accumulated += orig_len
            if orig_len > LONG_ARTICLE_CHARS:
                break
            if accumulated >= TARGET_CHARS:
                break

    done = len(translated)
    total = len(selected)
    batch_json = json.dumps(batch, ensure_ascii=False, indent=2)

    translation_rules = """翻譯規則：
- content_cht（繁體中文全文）：英文/日文 → 逐字逐句完整翻譯；簡/繁中 → 轉繁體複製 content_original
- content_ja（日語全文）：英文/中文 → 逐字逐句翻譯成日語；日文 → 直接複製 content_original
- ⚠️ 若 content_original 結尾有 "[...（原文過長，已截斷）]"：
    只翻譯已有部分，content_cht 結尾加「（原文過長，後續內容無法翻譯）」
    content_ja 結尾加「（原文が長すぎるため、以降の翻訳は省略）」，不得推測補寫"""

    return f"""你是澄澄，AI 新聞週報的翻譯助理。

{translation_rules}

翻譯進度：{done}/{total} 篇已完成，本批 {len(batch)} 篇。

以下是本批待翻譯文章（JSON）：

{batch_json}

---
請翻譯每篇文章的全文，並在 <result></result> 標籤內輸出 JSON 陣列。
每個元素必須包含以下欄位：key, content_cht, content_ja

⚠️ 嚴格要求：
- <result> 標籤外不得有任何文字或說明
- JSON 字符串值中若含引號，必須轉義為 \\\"（或改用「」代替）"""


def get_status(date: str = None) -> dict:
    """回傳目前處理狀態的 dict（供 PowerShell 解析）。"""
    if not date:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    progress = _load_progress(date)
    phase = progress["phase"]
    if phase == "scoring":
        count = sum(len(v) for v in load_filtered().values())
    elif phase == "translating":
        pending = [k for k in progress["selected_keys"]
                   if k not in progress["translated_keys"]]
        count = len(pending)
    else:
        count = 0
    return {"phase": phase, "pending_count": count}


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        show_next_batch()
        sys.exit(0)

    cmd = sys.argv[1]
    date_arg = sys.argv[2] if len(sys.argv) > 2 else None

    if cmd == "status":
        print(json.dumps(get_status(date_arg)))

    elif cmd == "scoring-prompt":
        print(build_scoring_prompt(date_arg))

    elif cmd == "translation-prompt":
        print(build_translation_prompt(date_arg))

    elif cmd == "single-translation-prompt":
        print(build_translation_prompt(date_arg, single=True))

    elif cmd == "save-scores":
        json_file = sys.argv[3]
        with open(json_file, encoding="utf-8-sig") as f:
            raw = f.read()
        try:
            results = json.loads(raw)
        except json.JSONDecodeError:
            import json_repair
            results = json_repair.loads(raw)
            print(f"⚠️  JSON 自動修復（輕微格式錯誤）")
        save_scores(date_arg, results)

    elif cmd == "save-batch":
        json_file = sys.argv[3]
        with open(json_file, encoding="utf-8-sig") as f:
            raw = f.read()
        try:
            results = json.loads(raw)
        except json.JSONDecodeError:
            import json_repair
            results = json_repair.loads(raw)
            print(f"⚠️  JSON 自動修復（輕微格式錯誤）")
        save_batch(date_arg, results)

    elif cmd == "finalize":
        finalize(date_arg)

    else:
        # 向後相容：第一個參數視為日期
        show_next_batch(cmd)
