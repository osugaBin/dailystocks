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

TYPE_LABEL = {"morning": "早盘", "evening": "晚间", "custom": "其他",
             "data": "数据掘金", "model": "金融建模"}
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
.badge.news{background:#dcfce7;color:#15803d}
.badge.data{background:#e0f2fe;color:#0369a1}
.badge.model{background:#fef9c3;color:#a16207}
/* tabs */
.tabs{display:flex;gap:10px;margin:20px 0 18px;flex-wrap:wrap}
.tab{flex:1;min-width:130px;border:1px solid var(--line);background:#fff;border-radius:12px;
  padding:12px 8px;cursor:pointer;text-align:center;
  font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif}
.tab .t{display:block;font-size:1rem;font-weight:600;color:var(--ink)}
.tab .count{display:block;font-size:.75rem;color:var(--muted);margin-top:2px}
.tab.active{background:#1a3a6b;border-color:#1a3a6b}
.tab.active .t{color:#fff}
.tab.active .count{color:#cbd5e1}
section[hidden]{display:none!important}
.empty{color:var(--muted);background:var(--card);border:1px dashed var(--line);
  border-radius:10px;padding:28px;text-align:center;font-size:.9rem}
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
img{max-width:100%;height:auto;display:block;margin:14px auto}
figcaption,.imgcap{text-align:center;color:var(--muted);font-size:.82rem;margin:-6px 0 14px}
/* 及时快讯浮窗 */
#msgfloat{position:fixed;right:16px;bottom:16px;z-index:60;
  font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif}
#msgfloat-btn{position:relative;display:flex;align-items:center;border:1px solid #1a3a6b;
  background:#1a3a6b;color:#fff;border-radius:24px;padding:10px 18px;font-size:.9rem;
  cursor:pointer;box-shadow:0 4px 16px rgba(0,0,0,.18)}
#msgfloat-btn:hover{background:#24487f}
.msgfloat-dot{position:absolute;top:5px;right:7px;width:9px;height:9px;border-radius:50%;
  background:#ef4444;display:none}
#msgfloat-panel{position:absolute;right:0;bottom:58px;width:340px;max-width:calc(100vw - 32px);
  background:#fff;border:1px solid var(--line);border-radius:12px;
  box-shadow:0 8px 28px rgba(0,0,0,.16);overflow:hidden;text-align:left}
.msgfloat-head{display:flex;justify-content:space-between;align-items:center;
  padding:10px 14px;border-bottom:1px solid var(--line)}
.msgfloat-head b{font-size:.95rem}
.msgfloat-head a{font-size:.8rem}
.msgfloat-list a{display:block;padding:10px 14px;border-bottom:1px solid var(--line);
  text-decoration:none;color:inherit}
.msgfloat-list a:last-child{border-bottom:none}
.msgfloat-list a:hover{background:#f8fafc}
.msgfloat-list .t{display:block;font-size:.88rem;color:var(--ink)}
.msgfloat-list .d{display:block;font-size:.75rem;color:var(--muted);margin-top:2px}
/* 快讯存档页 */
.msg{border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin:0 0 16px;background:#fff}
.msg-meta{color:var(--muted);font-size:.8rem;margin-bottom:6px;
  font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif}
.msg h2{border:none;padding:0;margin:0 0 8px;font-size:1.15rem}
.site-nav{margin-top:10px;font-size:.85rem;
  font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif}
.site-nav a{margin-right:14px}
footer.site-foot{border-top:1px solid var(--line);margin-top:40px;padding-top:14px;color:var(--muted);font-size:.8rem}
.actions{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;margin:0 0 6px}
.actions button{border:1px solid var(--line);background:#fff;border-radius:8px;
  padding:6px 14px;font-size:.85rem;cursor:pointer;color:var(--accent)}
.actions button:hover{border-color:var(--accent)}
@page{size:A4;margin:18mm 15mm}
@media print{
  .back,.actions,footer.site-foot,#msgfloat{display:none!important}
  body{background:#fff;color:#222;font-size:10.5pt;line-height:1.7}
  .wrap{max-width:none;margin:0;padding:0}
  h1{font-size:17pt;border-bottom:2px solid #333;padding-bottom:8px}
  h2{font-size:13pt;color:#1a3a6b;border-left:4px solid #2a6cb6;padding-left:10px;margin-top:1.4em}
  h3{font-size:11pt;color:#2a6cb6}
  table{display:table;font-size:8.2pt;border-collapse:collapse;width:100%;margin:.6em 0;overflow:visible}
  th,td{border:1px solid #999;padding:4px 6px;white-space:normal;text-align:left}
  th{background:#eef2f7}
  blockquote{border-left:3px solid #2a6cb6;background:#f2f6fb;padding:8px 12px;color:#444;font-size:9.5pt}
  a{color:#1a3a6b;text-decoration:none}
  .meta{color:#666;font-size:9pt}
  .badge{font-size:8pt}
}
@media(max-width:600px){body{font-size:15px}.wrap{padding:16px 14px 48px}}
"""

INDEX_TMPL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DrX Daily · 每日市场洞察</title>
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
<div class="wrap">
<header class="site-head">
<h1>DrX Daily · 每日市场洞察</h1>
<p>数据驱动 · 行情复盘 · 金融建模</p>
<nav class="site-nav"><a href="messages.html">及时快讯</a></nav>
</header>
{content}
<footer class="site-foot">本站内容由定时任务自动生成，仅供学习参考，不构成投资建议。</footer>
</div>
<script>
(function(){
  var tabs=document.querySelectorAll('.tab');
  function show(name){
    tabs.forEach(function(b){b.classList.toggle('active',b.dataset.tab===name)});
    ['daily','data','model'].forEach(function(n){
      document.getElementById('tab-'+n).hidden=(n!==name);
    });
    try{history.replaceState(null,'','#'+name)}catch(e){}
  }
  tabs.forEach(function(b){b.addEventListener('click',function(){show(b.dataset.tab)})});
  var h=(location.hash||'').replace('#','');
  if(h==='data'||h==='model') show(h);
})();
</script>
{msgfloat}
</body>
</html>
"""

CARD_TMPL = """<a class="card" href="{href}">
<div class="badges">{badges}</div>
<h2>{title}</h2>
{excerpt_html}
<div class="meta">{meta}</div>
</a>
"""

PAGE_TMPL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · DrX Daily</title>
<link rel="stylesheet" href="{root}assets/style.css">
{mathjax}
</head>
<body>
<div class="wrap">
<p class="back"><a href="{root}index.html">← 全部报告</a></p>
<p class="actions"><button type="button" onclick="window.print()">下载 PDF / 打印</button></p>
{body}
<p class="meta">{meta_line}</p>
<footer class="site-foot">本站内容由定时任务自动生成，仅供学习参考，不构成投资建议。</footer>
</div>
</body>
</html>
"""


def fix_list_spacing(text):
    """Python-Markdown 要求列表前有空行：给直接跟在段落后的列表项补空行，
    否则 `- ` 会被当成段落文字原样输出。"""
    lines = text.split("\n")
    out = []
    prev_is_list = False
    prev_blank = True
    for ln in lines:
        is_list = bool(re.match(r"^[ \t]*([-*]|\d+\.)\s", ln))
        is_blank = not ln.strip()
        if is_list and not prev_blank and not prev_is_list:
            out.append("")
        out.append(ln)
        prev_is_list = is_list
        prev_blank = is_blank
    return "\n".join(out)


# MathJax：只有正文含 $...$ / $$...$$ 时才加载（行内公式 $...$，行间 $$...$$；
# 注意金额不要写 $ 符号，写"美元"，否则会被误判为公式定界符）
MATHJAX = """<script>
window.MathJax={tex:{inlineMath:[['$','$']],displayMath:[['$$','$$']]},options:{skipHtmlTags:['script','noscript','style','textarea','pre','code']}};
</script>
<script async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js"></script>"""


def md_to_html(text):
    text = text.replace("- [ ]", "- □")  # 与 md2pdf 保持一致的缺字处理
    text = fix_list_spacing(text)
    return markdown.markdown(text, extensions=["tables", "fenced_code"])


def extract_h1(text):
    m = re.search(r"^#\s+(.+)$", text, re.M)
    return m.group(1).strip() if m else "(无标题)"


def extract_data_date(h1):
    m = re.search(r"（(\d{4})年(\d{1,2})月(\d{1,2})日", h1)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return ""


def clean_title(h1):
    """去掉标题括号内的日期（如 “（2026年10月9日，周五）”），避免与发布日期混淆。"""
    return re.sub(r"（[^）]*[年月日][^）]*）", "", h1).strip()


# 历史周末补发报告：数据与上一份同类型报告重复，网站按“新闻版”展示（只留新闻/前瞻章节）
NEWS_EDITION = {
    ("evening", "2026-10-10"): {
        "keep": ["新闻汇总", "关注"],
        "note": "A股休市，本期为新闻版：数据分析见 2026-10-09 晚间报告。",
        "summary": "10月9日A股深V反转收红、成交1.9万亿；中央印发新质生产力意见；"
                   "OpenAI营收不及预期拖累半导体，黄金原油齐涨。",
    },
    ("evening", "2026-10-11"): {
        "keep": ["新闻汇总", "关注"],
        "note": "A股休市，本期为新闻版：数据分析见 2026-10-09 晚间报告。",
        "summary": "证监会座谈释放稳市信号、公募新规征求意见；沙特机场遇袭，"
                   "布伦特原油大涨超5%逼近105美元；美联储纪要现加息分歧。",
    },
    ("morning", "2026-10-11"): {
        "drop": ["隔夜美股关键指标"],
        "note": "美股休市，本期为新闻版：数据指标见 2026-10-10 早盘报告。",
        "summary": "美股周五普涨反弹，光通信领涨；沙特机场遇袭油价冲高，人民币走强；"
                   "下周一A股或温和高开，光模块链领涨。",
    },
}


def news_edition_body(md_text, cfg):
    """只保留新闻版章节，去掉重复的数据分析与文末 footer。"""
    chunks = re.split(r"(?m)^(?=##\s)", md_text)
    out = []
    for ch in chunks:
        m = re.match(r"##\s+([^\n]+)", ch)
        if not m:
            continue  # 丢掉开头的引用说明等前言
        head = m.group(1)
        if "keep" in cfg:
            if not any(k in head for k in cfg["keep"]):
                continue
        elif any(k in head for k in cfg.get("drop", [])):
            continue
        out.append(ch.strip())
    text = "\n\n".join(out)
    text = re.sub(r"\n---\n[\s\S]*$", "", text).strip()  # 去掉文末 footer
    return text


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


CUSTOM_DIRS = {"数据掘金": "data", "金融建模": "model"}  # custom/ 子目录 -> tab id
TAB_LABELS = {"daily": "每日报告", "data": "数据掘金", "model": "金融建模"}
MSG_DIR = os.path.join(CUSTOM_DIR, "快讯")  # 及时消息：YYYY-MM-DD-HHMM-标题.md


def collect_messages():
    items = []  # (sortkey, date, hm, title, src_path)
    if not os.path.isdir(MSG_DIR):
        return items
    for fname in sorted(os.listdir(MSG_DIR), reverse=True):
        m = re.match(r"(\d{4}-\d{2}-\d{2})-(\d{4})-(.+)\.md$", fname)
        if not m:
            continue
        date, hm, title = m.group(1), m.group(2), m.group(3)
        items.append((f"{date} {hm}", date, f"{hm[:2]}:{hm[2:]}", title,
                      os.path.join(MSG_DIR, fname)))
    return items


def build_messages_page(messages):
    """快讯存档页 messages.html（全文，按时间倒序）。"""
    blocks = []
    for sortkey, date, hm, title, src in messages:
        body = md_to_html(open(src, encoding="utf-8").read())
        body = re.sub(r"^<h1>.*?</h1>", "", body, count=1,
                      flags=re.S).strip()  # 去正文H1，页面单独渲染标题
        anchor = f"m-{date}-{hm.replace(':', '')}"
        blocks.append(
            f'<article class="msg" id="{anchor}">'
            f'<div class="msg-meta">{date} {hm}</div>'
            f"<h2>{htmlmod.escape(title)}</h2>{body}</article>")
    content = "\n".join(blocks) if blocks else '<p class="empty">暂无快讯</p>'
    page = PAGE_TMPL.format(
        title="及时快讯", body=content,
        meta_line=f"共 {len(messages)} 条 · 按时间倒序", root="", mathjax="")
    with open(os.path.join(SITE, "messages.html"), "w",
              encoding="utf-8") as f:
        f.write(page)
    print(f"page: messages.html ({len(messages)} 条快讯)")


def build_msgfloat(messages):
    """首页右下角浮窗：最新3条快讯 + 未读红点（localStorage 记忆）。"""
    if not messages:
        return ""
    lis = []
    for sortkey, date, hm, title, src in messages[:3]:
        anchor = f"m-{date}-{hm.replace(':', '')}"
        lis.append(
            f'<a href="messages.html#{anchor}">'
            f'<span class="t">{htmlmod.escape(title)}</span>'
            f'<span class="d">{date} {hm}</span></a>')
    latest_id = f"m-{messages[0][1]}-{messages[0][2].replace(':', '')}"
    return f"""<div id="msgfloat">
  <button id="msgfloat-btn" type="button"><span>及时快讯</span><span class="msgfloat-dot" id="msgfloat-dot"></span></button>
  <div id="msgfloat-panel" hidden>
    <div class="msgfloat-head"><b>及时快讯</b><a href="messages.html">全部存档 →</a></div>
    <div class="msgfloat-list">{''.join(lis)}</div>
  </div>
</div>
<script>
(function(){{
  var btn=document.getElementById('msgfloat-btn'),
      panel=document.getElementById('msgfloat-panel'),
      dot=document.getElementById('msgfloat-dot'),
      latest='{latest_id}';
  function seen(){{try{{return localStorage.getItem('drx_msg_seen')===latest;}}catch(e){{return true;}}}}
  dot.style.display=seen()?'none':'block';
  btn.addEventListener('click',function(){{
    panel.hidden=!panel.hidden;
    if(!panel.hidden){{try{{localStorage.setItem('drx_msg_seen',latest);}}catch(e){{}}dot.style.display='none';}}
  }});
}})();
</script>"""


def collect_custom():
    items = []  # (tab_id, subdir, date, name, ext, src_path)
    for subdir, tab_id in CUSTOM_DIRS.items():
        d = os.path.join(CUSTOM_DIR, subdir)
        if not os.path.isdir(d):
            continue
        names = set(os.listdir(d))
        for fname in sorted(names, reverse=True):
            m = re.match(r"(\d{4}-\d{2}-\d{2})-(.+)\.(md|html)$", fname)
            if not m:
                continue
            # 跳过由 .md 生成的同名 .html，避免重复卡片
            if m.group(3) == "html" and f"{m.group(1)}-{m.group(2)}.md" in names:
                continue
            items.append((tab_id, subdir, m.group(1), m.group(2),
                          m.group(3), os.path.join(d, fname)))
    return items


def card(href, rtype, pub_date, title, excerpt, data_date, news_note=""):
    badges = (f'<span class="badge {rtype}">{TYPE_LABEL[rtype]}</span>'
              f'<span class="badge date">{pub_date} 发布</span>')
    if news_note:
        badges += '<span class="badge news">新闻版</span>'
        meta = "本期为新闻版"
    else:
        meta = f"数据基准 {data_date}"
    excerpt_html = (f'<p class="excerpt">{htmlmod.escape(excerpt)}</p>'
                    if excerpt else "")
    return CARD_TMPL.format(
        href=href, badges=badges, title=htmlmod.escape(title),
        excerpt_html=excerpt_html, meta=meta)


def build():
    messages = collect_messages()
    build_messages_page(messages)
    os.makedirs(os.path.join(SITE, "reports"), exist_ok=True)
    os.makedirs(os.path.join(SITE, "assets"), exist_ok=True)
    with open(os.path.join(SITE, "assets", "style.css"), "w",
              encoding="utf-8") as f:
        f.write(CSS)

    daily_cards = []
    for rtype, pub_date, src in collect_daily():
        text = open(src, encoding="utf-8").read()
        h1 = extract_h1(text)
        title = clean_title(h1)
        data_date = extract_data_date(h1) or pub_date
        slug = f"{pub_date}-{rtype}"
        news_cfg = NEWS_EDITION.get((rtype, pub_date))
        if news_cfg:
            note = news_cfg["note"]
            body_md = ("# " + title + "\n\n> " + note + "\n\n"
                       + news_edition_body(text, news_cfg))
            excerpt = news_cfg["summary"]
            meta_line = (f"发布日期：{pub_date} · 类型：{TYPE_LABEL[rtype]}"
                         f" · 本期为新闻版")
        else:
            body_md = re.sub(r"^#\s+.+$", "# " + title, text,
                             count=1, flags=re.M)
            excerpt = extract_excerpt(text)
            meta_line = (f"发布日期：{pub_date} · 数据基准：{data_date}"
                         f" · 类型：{TYPE_LABEL[rtype]}")
        body = md_to_html(body_md)
        page = PAGE_TMPL.format(
            title=htmlmod.escape(title), body=body, meta_line=meta_line,
            root="../", mathjax=MATHJAX if "$" in body else "")
        with open(os.path.join(SITE, "reports", slug + ".html"), "w",
                  encoding="utf-8") as f:
            f.write(page)
        daily_cards.append(card(
            f"reports/{slug}.html", rtype, pub_date, title,
            excerpt, data_date, news_cfg["note"] if news_cfg else ""))
        print(f"page: reports/{slug}.html  <- {os.path.basename(src)}")

    tab_cards = {"data": [], "model": []}
    for tab_id, subdir, date, name, ext, src in collect_custom():
        if ext == "md":
            text = open(src, encoding="utf-8").read()
            title = extract_h1(text)
            excerpt = extract_excerpt(text)
            slug = f"{date}-{name}"
            body = md_to_html(text)
            page = PAGE_TMPL.format(
                title=htmlmod.escape(title), body=body,
                meta_line=f"发布日期：{date} · 类型：{TAB_LABELS[tab_id]}",
                root="../../", mathjax=MATHJAX if "$" in body else "")
            with open(os.path.join(CUSTOM_DIR, subdir, slug + ".html"), "w",
                      encoding="utf-8") as f:
                f.write(page)
            href = f"custom/{subdir}/{slug}.html"
            print(f"page: custom/{subdir}/{slug}.html"
                  f"  <- {os.path.basename(src)}")
        else:  # html：自带样式，原样上架
            text = open(src, encoding="utf-8").read()
            title = extract_html_title(text) or name
            excerpt = ""
            href = f"custom/{subdir}/{os.path.basename(src)}"
            print(f"file: {href}")
        tab_cards[tab_id].append(
            card(href, tab_id, date, title, excerpt, date))

    panels = {
        "daily": ("早盘 · 美股A股对标映射分析 ／ 晚间 · A股收盘技术分析"
                  " — 定时任务自动更新", daily_cards),
        "data": ("量化分析与数据挖掘 — 把 .md / .html 按 "
                 "<code>YYYY-MM-DD-标题</code> 命名放入 custom/数据掘金/ 重新构建",
                 tab_cards["data"]),
        "model": ("金融建模相关报告 — 把 .md / .html 按 "
                  "<code>YYYY-MM-DD-标题</code> 命名放入 custom/金融建模/ 重新构建",
                  tab_cards["model"]),
    }
    order = ["daily", "data", "model"]
    tabbar = ['<div class="tabs" role="tablist">']
    for tid in order:
        n = len(panels[tid][1])
        active = " active" if tid == "daily" else ""
        tabbar.append(
            f'<button class="tab{active}" data-tab="{tid}" role="tab">'
            f'<span class="t">{TAB_LABELS[tid]}</span>'
            f'<span class="count">{n} 篇</span></button>')
    tabbar.append("</div>")
    parts = ["\n".join(tabbar)]
    for tid in order:
        hint, cards = panels[tid]
        inner = "\n".join(cards) if cards else '<p class="empty">暂无内容</p>'
        hid = "" if tid == "daily" else " hidden"
        parts.append(
            f'<section id="tab-{tid}"{hid}>\n'
            f'<p class="section-hint">{hint}</p>\n{inner}\n</section>')
    content = "\n".join(parts)

    with open(os.path.join(SITE, "index.html"), "w",
              encoding="utf-8") as f:
        f.write(INDEX_TMPL.replace("{content}", content)
                .replace("{msgfloat}", build_msgfloat(messages)))
    print(f"index: {len(daily_cards)} daily + {len(tab_cards['data'])} data"
          f" + {len(tab_cards['model'])} model")


if __name__ == "__main__":
    build()
