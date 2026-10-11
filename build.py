# -*- coding: utf-8 -*-
"""把 stocks/ 下的 md 报告 + custom/ 下的手动报告转成静态网站（Cloudflare Pages 用）。

用法：python build.py            # 全量重建本站点目录
输出：index.html（按发布时间倒序，分"每日报告"/"其他报告"两栏）
     + reports/<date>-<morning|evening>.html + custom/* + assets/style.css

手动加报告：把 .md / .html 按 `YYYY-MM-DD-标题` 命名放入 custom/ 目录即可，
.md 会渲染成正文页，.html 原样上架（需自带样式）。
"""
import os
import re
import html as htmlmod

import markdown

HOME = os.path.expanduser("~")
STOCKS = os.path.join(HOME, "workspace", "stocks")
SITE = os.path.join(HOME, "workspace", "dailystocks")
CUSTOM_DIR = os.path.join(SITE, "custom")

TYPE_LABEL = {"morning": "早盘", "evening": "晚间", "custom": "其他"}
TYPE_ORDER = {"morning": 0, "evening": 1}  # 同一天：晚间(20:00)比早盘(09:00)新

CSS = """/* dailystocks site */
:root{
  --ink:#222; --muted:#6b7280; --accent:#2a6cb6; --line:#e5e7eb;
  --card:#f8fafc; --bg:#fff;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{
  font-family:"Noto Serif CJK SC","Songti SC",Georgia,serif;
  color:var(--ink); background:var(--bg);
  margin:0; line-height:1.7; font-size:16px;
}
.wrap{max-width:860px;margin:0 auto;padding:24px 18px 64px}
.site-head{border-bottom:2px solid #111;padding-bottom:14px;margin-bottom:20px}
.site-head h1{font-size:1.5rem;margin:0}
.site-head p{color:var(--muted);margin:6px 0 0;font-size:.9rem}
a{color:var(--accent)}
.section-title{font-size:1.15rem;margin:26px 0 4px;border:none;padding:0}
.section-hint{color:var(--muted);font-size:.82rem;margin:0 0 14px;
  font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif}
.section-hint code{background:#f1f5f9;padding:1px 6px;border-radius:4px;font-size:.78rem}
.card{display:block;text-decoration:none;color:inherit;background:var(--card);
  border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin:0 0 14px}
.card:hover{border-color:var(--accent)}
.badges{margin-bottom:8px}
.badge{display:inline-block;font-size:.75rem;border-radius:20px;padding:2px 10px;margin-right:8px;
  font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif}
.badge.morning{background:#e8f1fd;color:#1d4ed8}
.badge.evening{background:#fef3e2;color:#b45309}
.badge.custom{background:#ede9fe;color:#6d28d9}
.badge.date{background:#f1f5f9;color:#475569}
.card h2{font-size:1.12rem;margin:0 0 6px}
.card p.excerpt{margin:0;color:#4b5563;font-size:.92rem}
.meta{color:var(--muted);font-size:.8rem;margin-top:8px}
.back{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;font-size:.9rem}
/* report body */
h1{font-size:1.45rem;border-bottom:2px solid #333;padding-bottom:8px}
h2{font-size:1.2rem;color:#1a1a1a;margin-top:1.4em;border-left:4px solid var(--accent);padding-left:10px}
h2.section-title{border:none;padding:0;margin:26px 0 4px;font-size:1.15rem}
h3{font-size:1.05rem;color:var(--accent)}
table{border-collapse:collapse;width:100%;margin:.7em 0;font-size:.82rem;display:block;overflow-x:auto}
th,td{border:1px solid #999;padding:4px 6px;text-align:center;white-space:nowrap}
th{background:#eef2f7}
tr:nth-child(even) td{background:#fafbfc}
blockquote{border-left:3px solid #ccc;margin:.7em 0;padding:6px 12px;color:#555;background:#f7f7f7;font-size:.88rem}
ul,ol{padding-left:1.4em}
footer.site-foot{border-top:1px solid var(--line);margin-top:40px;padding-top:14px;color:var(--muted);font-size:.8rem}
.actions{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;margin:0 0 6px}
.actions button{border:1px solid var(--line);background:#fff;border-radius:8px;
  padding:6px 14px;font-size:.85rem;cursor:pointer;color:var(--accent)}
.actions button:hover{border-color:var(--accent)}
@media print{
  .back,.actions,footer.site-foot{display:none!important}
  body{font-size:11pt}
  .wrap{max-width:none;padding:0 4px}
  a{color:#111;text-decoration:none}
}
@media(max-width:600px){body{font-size:15px}.wrap{padding:16px 14px 48px}}
"""

INDEX_TMPL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>每日市场报告</title>
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
<div class="wrap">
<header class="site-head">
<h1>每日市场报告</h1>
<p>按发布时间倒序排列</p>
</header>
{sections}
<footer class="site-foot">本站内容由定时任务自动生成，仅供学习参考，不构成投资建议。</footer>
</div>
</body>
</html>
"""

CARD_TMPL = """<a class="card" href="{href}">
<div class="badges"><span class="badge {rtype}">{type_label}</span><span class="badge date">{pub_date} 发布</span></div>
<h2>{title}</h2>
{excerpt_html}
<div class="meta">数据基准 {data_date}</div>
</a>
"""

PAGE_TMPL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · 每日市场报告</title>
<link rel="stylesheet" href="../assets/style.css">
</head>
<body>
<div class="wrap">
<p class="back"><a href="../index.html">← 全部报告</a></p>
<p class="actions"><button type="button" onclick="window.print()">下载 PDF / 打印</button></p>
{body}
<p class="meta">发布日期：{pub_date} · 数据基准：{data_date} · 类型：{type_label}</p>
<footer class="site-foot">本站内容由定时任务自动生成，仅供学习参考，不构成投资建议。</footer>
</div>
</body>
</html>
"""


def md_to_html(text):
    text = text.replace("- [ ]", "- □")  # 与 md2pdf 保持一致的缺字处理
    return markdown.markdown(text, extensions=["tables", "fenced_code"])


def extract_h1(text):
    m = re.search(r"^#\s+(.+)$", text, re.M)
    return m.group(1).strip() if m else "(无标题)"


def extract_data_date(h1):
    m = re.search(r"（(\d{4})年(\d{1,2})月(\d{1,2})日", h1)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return ""


def extract_excerpt(text, limit=120):
    for line in text.splitlines()[:80]:
        s = line.strip()
        if not s or s[0] in "#>|`-":
            continue
        if s.startswith("**"):
            s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
            s = re.sub(r"[*_`]", "", s).strip()
            if s:
                return s[:limit] + ("…" if len(s) > limit else "")
    return ""


def collect_daily():
    items = []  # (rtype, pub_date, src_path)
    for fname in os.listdir(STOCKS):
        m = re.match(r"股票分析报告_(\d{8})\.md$", fname)
        if m:
            d = m.group(1)
            items.append(("evening", f"{d[:4]}-{d[4:6]}-{d[6:8]}",
                          os.path.join(STOCKS, fname)))
    comp = os.path.join(STOCKS, "comparison")
    if os.path.isdir(comp):
        for fname in os.listdir(comp):
            m = re.match(r"美股A股对标映射分析_(\d{8})\.md$", fname)
            if m:
                d = m.group(1)
                items.append(("morning", f"{d[:4]}-{d[4:6]}-{d[6:8]}",
                              os.path.join(comp, fname)))
    items.sort(key=lambda x: (x[1], TYPE_ORDER[x[0]]), reverse=True)
    return items


def extract_html_title(text):
    m = re.search(r"<title>(.*?)</title>", text, re.S | re.I)
    if m:
        return htmlmod.unescape(m.group(1).strip())
    m = re.search(r"<h1[^>]*>(.*?)</h1>", text, re.S | re.I)
    if m:
        return htmlmod.unescape(re.sub(r"<[^>]+>", "", m.group(1)).strip())
    return ""


def collect_custom():
    items = []  # (date, name, ext, src_path)
    if not os.path.isdir(CUSTOM_DIR):
        return items
    for fname in sorted(os.listdir(CUSTOM_DIR)):
        m = re.match(r"(\d{4}-\d{2}-\d{2})-(.+)\.(md|pdf|html)$", fname)
        if m:
            items.append((m.group(1), m.group(2), m.group(3),
                          os.path.join(CUSTOM_DIR, fname)))
    items.sort(key=lambda x: x[0], reverse=True)
    return items


def card(href, rtype, pub_date, title, excerpt, data_date):
    excerpt_html = (f'<p class="excerpt">{htmlmod.escape(excerpt)}</p>'
                    if excerpt else "")
    return CARD_TMPL.format(
        href=href, rtype=rtype, type_label=TYPE_LABEL[rtype],
        pub_date=pub_date, title=htmlmod.escape(title),
        excerpt_html=excerpt_html, data_date=data_date)


def build():
    os.makedirs(os.path.join(SITE, "reports"), exist_ok=True)
    os.makedirs(os.path.join(SITE, "assets"), exist_ok=True)
    with open(os.path.join(SITE, "assets", "style.css"), "w",
              encoding="utf-8") as f:
        f.write(CSS)

    daily_cards = []
    for rtype, pub_date, src in collect_daily():
        text = open(src, encoding="utf-8").read()
        title = extract_h1(text)
        data_date = extract_data_date(title) or pub_date
        slug = f"{pub_date}-{rtype}"
        body = md_to_html(text)
        page = PAGE_TMPL.format(
            title=htmlmod.escape(title), body=body, pub_date=pub_date,
            data_date=data_date, type_label=TYPE_LABEL[rtype])
        with open(os.path.join(SITE, "reports", slug + ".html"), "w",
                  encoding="utf-8") as f:
            f.write(page)
        daily_cards.append(card(
            f"reports/{slug}.html", rtype, pub_date, title,
            extract_excerpt(text), data_date))
        print(f"page: reports/{slug}.html  <- {os.path.basename(src)}")

    custom_cards = []
    for date, name, ext, src in collect_custom():
        if ext == "md":
            text = open(src, encoding="utf-8").read()
            title = extract_h1(text)
            excerpt = extract_excerpt(text)
            slug = f"{date}-{name}"
            body = md_to_html(text)
            page = PAGE_TMPL.format(
                title=htmlmod.escape(title), body=body, pub_date=date,
                data_date=date, type_label="其他报告")
            with open(os.path.join(CUSTOM_DIR, slug + ".html"), "w",
                      encoding="utf-8") as f:
                f.write(page)
            href = f"custom/{slug}.html"
            print(f"page: custom/{slug}.html  <- {os.path.basename(src)}")
        elif ext == "html":
            text = open(src, encoding="utf-8").read()
            title = extract_html_title(text) or name
            href = f"custom/{os.path.basename(src)}"
            print(f"file: {href}")
            custom_cards.append(card(href, "custom", date, title, "", date))
        else:  # pdf（保留能力，默认不在仓库放 PDF）
            title, excerpt = name, ""
            href = f"custom/{os.path.basename(src)}"
            print(f"file: {href}")
            custom_cards.append(card(href, "custom", date, title, excerpt, date))

    sections = [
        f'<h2 class="section-title">每日报告</h2>\n'
        f'<p class="section-hint">早盘 · 美股A股对标映射分析 ／ 晚间 · A股收盘技术分析'
        f' — 定时任务自动更新，共 {len(daily_cards)} 期</p>\n'
        + "\n".join(daily_cards),
    ]
    if custom_cards:
        sections.append(
            f'<h2 class="section-title">其他报告</h2>\n'
            f'<p class="section-hint">手动添加：把 .md / .pdf 按 '
            f'<code>YYYY-MM-DD-标题</code> 命名放入 custom/ 目录，重新构建即上架</p>\n'
            + "\n".join(custom_cards))

    with open(os.path.join(SITE, "index.html"), "w",
              encoding="utf-8") as f:
        f.write(INDEX_TMPL.format(sections="\n".join(sections)))
    print(f"index: {len(daily_cards)} daily + {len(custom_cards)} custom")


if __name__ == "__main__":
    build()
