"""
发送周报邮件通知
收件人：斌斌 + myu
内容：本周新闻标题 + 链接 + 网页入口
"""

import json
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def load_weekly(date: str) -> dict:
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), f"data/{date}.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_html(data: dict, site_url: str) -> str:
    date = data["date"]
    articles = data["articles"]
    cat_labels = {
        "ai_industry": "🌐 AI 行業",
        "ai_agent":    "🤖 AI Agent・使用技巧",
        "3d_ai":       "🧊 3D AI",
    }

    sections = ""
    for cat, label in cat_labels.items():
        items = articles.get(cat, [])
        if not items:
            continue
        rows = ""
        for a in items:
            title = a.get("title_cht") or a.get("title", "")
            url = a.get("url", "#")
            points = a.get("summary_points_cht") or []
            source = a.get("source", "")
            score = a.get("score", "")
            score_str = f"⭐ {score}" if score else ""
            tags = " ".join(a.get("tags", []))
            # 子弹摘要
            if points:
                bullets = "".join(
                    f'<li style="margin:2px 0;font-size:13px;color:#555;">{p}</li>'
                    for p in points
                )
                summary_html = f'<ul style="margin:6px 0 0 16px;padding:0;">{bullets}</ul>'
            else:
                fallback = a.get("summary_cht") or a.get("summary", "")
                summary_html = f'<div style="margin-top:4px;font-size:13px;color:#666;">{fallback}</div>'

            rows += f"""
            <tr>
              <td style="padding:12px 0;border-bottom:1px solid #f0f0f0;">
                <a href="{url}" style="font-size:15px;font-weight:600;color:#1a1a1a;text-decoration:none;">{title}</a>
                {summary_html}
                <div style="margin-top:6px;font-size:11px;color:#aaa;">{source} {score_str} {tags}</div>
              </td>
            </tr>"""
        sections += f"""
        <tr><td style="padding:20px 0 8px;">
          <div style="font-size:18px;font-weight:700;color:#333;">{label}</div>
        </td></tr>
        {rows}"""

    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <div style="max-width:600px;margin:30px auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
    <div style="background:linear-gradient(135deg,#667eea,#764ba2);padding:30px;color:#fff;">
      <div style="font-size:22px;font-weight:700;">🌿🍵 AI 新聞週報</div>
      <div style="font-size:14px;margin-top:6px;opacity:0.85;">{date} 週報</div>
    </div>
    <div style="padding:20px 30px;">
      <table width="100%" cellpadding="0" cellspacing="0">
        {sections}
      </table>
    </div>
    <div style="padding:20px 30px;background:#f9f9f9;text-align:center;">
      <a href="{site_url}" style="display:inline-block;padding:10px 24px;background:#667eea;color:#fff;border-radius:6px;text-decoration:none;font-size:14px;font-weight:600;">
        查看完整週報 →
      </a>
    </div>
  </div>
</body>
</html>"""


SITE_ACCESS_KEY = "Chen9ch!nga1"


def send(date: str, site_url: str = "https://inice2000.github.io/ai-weekly"):
    sender = os.environ.get("GMAIL_SENDER", "")
    password = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "")
    recipients = os.environ.get("NOTIFY_EMAILS", "").split(",")
    recipients = [r.strip() for r in recipients if r.strip()]

    if not sender or not password:
        print("[邮件] 未配置 GMAIL_SENDER / GMAIL_APP_PASSWORD，跳过")
        return

    data = load_weekly(date)
    total = sum(len(v) for v in data["articles"].values())
    # 邮件按钮链接带 key，收件人点击后自动解锁全文
    keyed_url = f"{site_url}?key={SITE_ACCESS_KEY}"
    html_body = build_html(data, keyed_url)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🌿🍵 {date} AI新聞週報"
    msg["From"] = f"澄澄 AI週報 <{sender}>"
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, recipients, msg.as_string())
        print(f"[邮件] 已发送至 {recipients}")
    except Exception as e:
        print(f"[邮件] 发送失败: {e}")


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    test_mode = "--test" in args
    args = [a for a in args if a != "--test"]
    date = args[0] if args else datetime.now().strftime("%Y-%m-%d")
    if test_mode:
        # 测试模式：只发给 NOTIFY_EMAILS 中的第一个地址
        recipients = os.environ.get("NOTIFY_EMAILS", "").split(",")
        recipients = [r.strip() for r in recipients if r.strip()]
        os.environ["NOTIFY_EMAILS"] = recipients[0] if recipients else ""
        print(f"[邮件] 测试模式，仅发送至 {os.environ['NOTIFY_EMAILS']}")
    send(date)
