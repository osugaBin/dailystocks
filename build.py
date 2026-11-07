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
import json
from datetime import date as _date, datetime as _datetime

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
html{-webkit-text-size-adjust:100%;background:var(--bg);color-scheme:light}
body{
  font-family:"Noto Serif CJK SC","Songti SC",Georgia,serif;
  color:var(--ink); background:var(--bg);
  margin:0; line-height:1.7; font-size:16px;
}
.wrap{max-width:860px;margin:0 auto;padding:24px 18px 64px}
.site-head{border-bottom:2px solid #111;padding-bottom:14px;margin-bottom:20px}
.site-head h1{font-size:1.5rem;margin:0}
.site-head p{color:var(--muted);margin:6px 0 0;font-size:.9rem}
.sub-row{display:flex;justify-content:space-between;align-items:center;margin-top:6px}
.sub-row p{margin:0}
.msg-btn{display:inline-block;background:#1a3a6b;color:#fff;text-decoration:none;
  border-radius:20px;padding:6px 18px;font-size:.85rem;white-space:nowrap;
  font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif}
.msg-btn:hover{background:#24487f;color:#fff}
.head-btns{display:flex;gap:8px;align-items:center}
.theme-toggle{display:inline-block;background:var(--card);color:var(--ink);
  border:1px solid var(--line);border-radius:20px;padding:6px 14px;font-size:.85rem;
  cursor:pointer;font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;white-space:nowrap}
.theme-toggle:hover{border-color:var(--accent)}
.actions .theme-toggle{border-radius:8px}
.le{display:none}
html[data-lang="en"] .le{display:inline}
html[data-lang="en"] .lz{display:none}
.abstract{border:1px solid var(--line);border-left:3px solid var(--accent);
  background:var(--card);border-radius:8px;padding:12px 16px;margin:16px 0 20px}
.abstract h3{margin:0 0 6px;font-size:.95rem;border:none;padding:0}
.abstract p{margin:0;font-size:.92rem}
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
.badge.update{background:#ccfbf1;color:#0f766e}
.badge.data{background:#e0f2fe;color:#0369a1}
.badge.model{background:#fef9c3;color:#a16207}
/* tabs */
.tabs{display:flex;gap:8px;margin:20px 0 18px}
.tab{flex:1 1 0;min-width:0;border:1px solid var(--line);background:#fff;border-radius:12px;
  padding:12px 4px;cursor:pointer;text-align:center;
  font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif}
.tab .t{display:block;font-size:clamp(.85rem,4.5vw,1rem);font-weight:600;color:var(--ink);white-space:nowrap}
.tab .count{display:block;font-size:.75rem;color:var(--muted);margin-top:2px;white-space:nowrap}
.tab.active{background:#1a3a6b;border-color:#1a3a6b}
.tab.active .t{color:#fff}
.tab.active .count{color:#cbd5e1}
section[hidden]{display:none!important}
.empty{color:var(--muted);background:var(--card);border:1px dashed var(--line);
  border-radius:10px;padding:28px;text-align:center;font-size:.9rem}
.card h2{font-size:1.12rem;margin:0 0 6px}
.card p.excerpt{margin:0;color:#4b5563;font-size:.92rem}
.more{text-align:center;margin:4px 0 18px;
  font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;font-size:.9rem}
.meta{color:var(--muted);font-size:.8rem;margin-top:8px}
.back{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;font-size:.9rem}
.head-row{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}
.head-row .lang-toggle{flex:none;margin-top:4px}
.top-row{display:flex;justify-content:space-between;align-items:center;gap:12px}
.top-row .back{margin:0}
.top-row .lang-toggle{flex:none}
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
details.older-records{border:1px solid var(--line);border-radius:10px;background:var(--card);padding:8px 16px;margin:12px 0 20px}
details.older-records summary{cursor:pointer;font-weight:600;color:var(--accent);padding:6px 0}
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
.msgfloat-list .s{display:block;font-size:.8rem;color:#4b5563;margin-top:4px;line-height:1.5}
.msgfloat-list .d{display:block;font-size:.75rem;color:var(--muted);margin-top:2px}
/* 打赏浮窗（仅首页，位于快讯浮窗上方，可关闭；配色跟随全站变量、随系统自适应） */
#donatefloat{position:fixed;right:16px;bottom:70px;z-index:59;
  font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif}
#donatefloat-panel{position:relative;width:188px;max-width:calc(100vw - 24px);
  max-height:calc(100vh - 92px);overflow-y:auto;background:var(--bg);color:var(--ink);
  border:1px solid var(--line);border-radius:14px;padding:10px 12px 8px;
  box-shadow:0 8px 28px rgba(0,0,0,.16);text-align:center}
#donatefloat-panel[hidden],#donatefloat-open[hidden]{display:none!important}
#donatefloat-close{position:absolute;top:5px;right:6px;width:26px;height:26px;
  border:none;border-radius:50%;background:#eef2f7;color:#334155;
  font-size:1.05rem;line-height:1;cursor:pointer;padding:0}
#donatefloat-close:hover{background:#e2e8f0}
.donate-title{color:#e05d52;font-size:.98rem;font-weight:700;margin:2px 22px 8px}
#donatefloat img{margin:0 auto}
.donate-coffee{display:block;width:100%;border-radius:6px;margin-bottom:8px}
.donate-qr{display:block;width:100%;border-radius:8px}
.donate-label{font-size:.8rem;color:#4b5563;margin:3px 0 8px}
.donate-label:last-child{margin-bottom:2px}
#donatefloat-open{border:1px solid #1a3a6b;background:#1a3a6b;color:#fff;
  border-radius:24px;padding:9px 16px;font-size:.88rem;cursor:pointer;
  box-shadow:0 4px 16px rgba(0,0,0,.18)}
#donatefloat-open:hover{background:#24487f}
@media(max-width:600px){
  #donatefloat{right:12px;bottom:70px}
}
/* 快讯存档页 */
.msg{border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin:0 0 16px;background:#fff}
.msg-meta{color:var(--muted);font-size:.8rem;margin-bottom:6px;
  font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif}
.msg h2{border:none;padding:0;margin:0 0 8px;font-size:1.15rem}
footer.site-foot{border-top:1px solid var(--line);margin-top:40px;padding-top:14px;color:var(--muted);font-size:.8rem}
.actions{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;margin:0 0 6px}
.actions button{border:1px solid var(--line);background:#fff;border-radius:8px;
  padding:6px 14px;font-size:.85rem;cursor:pointer;color:var(--accent)}
.actions button:hover{border-color:var(--accent)}
.actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.prevnext{margin-left:auto;display:flex;gap:8px}
.prevnext a{border:1px solid var(--line);background:#fff;border-radius:8px;
  padding:5px 12px;font-size:.85rem;color:var(--ink);text-decoration:none;white-space:nowrap}
.prevnext a:hover{border-color:var(--accent)}
/* 深色配色：系统自适应 + 手动切换（data-theme 由切换按钮写入、优先于系统；两组规则内容相同，改一处须同步另一组） */
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){--ink:#e2e8f0;--muted:#94a3b8;--accent:#7db8f7;--line:#2b3648;--card:#151d2b;--bg:#0f141d;color-scheme:dark}
  :root:not([data-theme="light"]) .site-head{border-bottom-color:#e2e8f0}
  :root:not([data-theme="light"]) h1{color:#f1f5f9;border-bottom-color:#64748b}
  :root:not([data-theme="light"]) h2{color:#f1f5f9}
  :root:not([data-theme="light"]) th{background:#1c2739}
  :root:not([data-theme="light"]) th, :root:not([data-theme="light"]) td{border-color:#475569}
  :root:not([data-theme="light"]) tr:nth-child(even) td{background:#131a26}
  :root:not([data-theme="light"]) blockquote{background:#16202f;color:#cbd5e1;border-left-color:#475569}
  :root:not([data-theme="light"]) .section-hint code{background:#1e293b}
  :root:not([data-theme="light"]) .card p.excerpt{color:#a5b0bf}
  :root:not([data-theme="light"]) .tab{background:var(--bg)}
  :root:not([data-theme="light"]) .actions button{background:var(--bg)}
  :root:not([data-theme="light"]) .prevnext a{background:var(--bg);color:var(--ink)}
  :root:not([data-theme="light"]) #msgfloat-panel{background:var(--bg)}
  :root:not([data-theme="light"]) .msgfloat-list a:hover{background:#1a2436}
  :root:not([data-theme="light"]) .msgfloat-list .t{color:var(--ink)}
  :root:not([data-theme="light"]) .msgfloat-list .s{color:#a5b0bf}
  :root:not([data-theme="light"]) .msg{background:var(--bg)}
  :root:not([data-theme="light"]) .donate-title{color:#f28b82}
  :root:not([data-theme="light"]) .donate-label{color:#cbd5e1}
  :root:not([data-theme="light"]) #donatefloat-close{background:rgba(255,255,255,.14);color:#fff}
  :root:not([data-theme="light"]) #donatefloat-close:hover{background:rgba(255,255,255,.28)}
}
:root[data-theme="dark"]{--ink:#e2e8f0;--muted:#94a3b8;--accent:#7db8f7;--line:#2b3648;--card:#151d2b;--bg:#0f141d;color-scheme:dark}
:root[data-theme="dark"] .site-head{border-bottom-color:#e2e8f0}
:root[data-theme="dark"] h1{color:#f1f5f9;border-bottom-color:#64748b}
:root[data-theme="dark"] h2{color:#f1f5f9}
:root[data-theme="dark"] th{background:#1c2739}
:root[data-theme="dark"] th, :root[data-theme="dark"] td{border-color:#475569}
:root[data-theme="dark"] tr:nth-child(even) td{background:#131a26}
:root[data-theme="dark"] blockquote{background:#16202f;color:#cbd5e1;border-left-color:#475569}
:root[data-theme="dark"] .section-hint code{background:#1e293b}
:root[data-theme="dark"] .card p.excerpt{color:#a5b0bf}
:root[data-theme="dark"] .tab{background:var(--bg)}
:root[data-theme="dark"] .actions button{background:var(--bg)}
:root[data-theme="dark"] .prevnext a{background:var(--bg);color:var(--ink)}
:root[data-theme="dark"] #msgfloat-panel{background:var(--bg)}
:root[data-theme="dark"] .msgfloat-list a:hover{background:#1a2436}
:root[data-theme="dark"] .msgfloat-list .t{color:var(--ink)}
:root[data-theme="dark"] .msgfloat-list .s{color:#a5b0bf}
:root[data-theme="dark"] .msg{background:var(--bg)}
:root[data-theme="dark"] .donate-title{color:#f28b82}
:root[data-theme="dark"] .donate-label{color:#cbd5e1}
:root[data-theme="dark"] #donatefloat-close{background:rgba(255,255,255,.14);color:#fff}
:root[data-theme="dark"] #donatefloat-close:hover{background:rgba(255,255,255,.28)}
@page{size:A4;margin:18mm 15mm}
@media print{
  .back,.actions,footer.site-foot,#msgfloat,#donatefloat{display:none!important}
  :root[data-theme="dark"],:root:not([data-theme="light"]){--ink:#222;--muted:#666;--accent:#2a6cb6;--line:#e5e7eb;--card:#f8fafc;--bg:#fff}
  [data-theme="dark"] h1,:root:not([data-theme="light"]) h1{color:#111;border-bottom-color:#333}
  [data-theme="dark"] h2,:root:not([data-theme="light"]) h2{color:#1a1a1a}
  [data-theme="dark"] th,:root:not([data-theme="light"]) th{background:#eef2f7}
  [data-theme="dark"] tr:nth-child(even) td,:root:not([data-theme="light"]) tr:nth-child(even) td{background:#fafbfc}
  [data-theme="dark"] blockquote,:root:not([data-theme="light"]) blockquote{background:#f7f7f7;color:#555;border-left-color:#ccc}
  :root{--ink:#222;--muted:#666;--accent:#2a6cb6;--line:#e5e7eb;--card:#f8fafc;--bg:#fff}
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
<link rel="stylesheet" href="assets/style.css?v=20261107a">
{themeinit}
</head>
<body>
<div class="wrap">
<header class="site-head">
<div class="head-row"><h1>DrX Daily · <span class="lz">每日市场洞察</span><span class="le">Daily Market Insights</span></h1><button type="button" class="theme-toggle lang-toggle">EN</button></div>
<div class="sub-row">
<p><span class="lz">数据驱动 · 行情复盘 · 金融建模</span><span class="le">Data-Driven · Market Review · Financial Modeling</span></p>
<div class="head-btns"><button type="button" class="theme-toggle">深色模式</button><a class="msg-btn" href="messages.html"><span class="lz">及时快讯</span><span class="le">Market Alerts</span></a></div>
</div>
</header>
{content}
<footer class="site-foot"><span class="lz">本站内容由定时任务自动生成，仅供学习参考，不构成投资建议。</span><span class="le">Content on this site is generated automatically on a schedule, for study and reference only. Not investment advice.</span></footer>
</div>
<script>
(function(){
  var tabs=document.querySelectorAll('.tab');
  function show(name){
    tabs.forEach(function(b){b.classList.toggle('active',b.dataset.tab===name)});
    ['daily','data','model'].forEach(function(n){
      document.getElementById('tab-'+n).hidden=(n!==name);
    });
    try{localStorage.setItem('drx_tab',name)}catch(e){}
    try{history.replaceState(null,'','#'+name)}catch(e){}
  }
  tabs.forEach(function(b){b.addEventListener('click',function(){show(b.dataset.tab)})});
  var h=(location.hash||'').replace('#','');
  var saved='';
  try{saved=localStorage.getItem('drx_tab')||''}catch(e){}
  if(h==='daily'||h==='data'||h==='model') show(h);
  else if(saved==='data'||saved==='model') show(saved);
})();
</script>
{msgfloat}
{donatefloat}
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
<link rel="stylesheet" href="{root}assets/style.css?v=20261107a">
{mathjax}
{themeinit}
</head>
<body>
<div class="wrap">
<div class="top-row"><p class="back"><a href="{root}index.html{backhash}">← <span class="lz">全部报告</span><span class="le">All Reports</span></a></p><button type="button" class="theme-toggle lang-toggle">EN</button></div>
<p class="actions"><button type="button" onclick="window.print()"><span class="lz">下载 PDF / 打印</span><span class="le">Download PDF / Print</span></button> <button type="button" class="theme-toggle">深色模式</button><span class="prevnext">{prevnext}</span></p>
{body}
<p class="meta">{meta_line}</p>
<footer class="site-foot"><span class="lz">本站内容由定时任务自动生成，仅供学习参考，不构成投资建议。</span><span class="le">Content on this site is generated automatically on a schedule, for study and reference only. Not investment advice.</span></footer>
</div>
{donatefloat}
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


def collapse_daily_records(body, keep_days=3):
    """「三、每日记录」小节只展开最近 keep_days 天，更早条目折叠进 <details>。

    条目以 <h3>YYYY-MM-DD 开头；按不同日期计天数（同一天多条一并展开）。
    md 源文件保持全量，只改页面呈现；每日追加新条目后自动滚动折叠。
    """
    marker = "<h2>三、每日记录</h2>"
    idx = body.find(marker)
    if idx < 0:
        return body
    head, rest = body[:idx + len(marker)], body[idx + len(marker):]
    entries = list(re.finditer(r"<h3>(\d{4}-\d{2}-\d{2})", rest))
    if not entries:
        return body
    dates = []
    for m in entries:
        if m.group(1) not in dates:
            dates.append(m.group(1))
    if len(dates) <= keep_days:
        return body
    keep = set(dates[-keep_days:])
    split = next(m.start() for m in entries if m.group(1) in keep)
    older, recent = rest[:split], rest[split:]
    n_old = sum(1 for m in entries if m.start() < split)
    details = (f'<details class="older-records"><summary>'
               f'更早的记录（共 {n_old} 条 · {dates[0]} 至 '
               f'{dates[-keep_days - 1]}，点击展开）</summary>\n'
               + older + "</details>\n")
    return head + details + recent


def extract_h1(text):
    m = re.search(r"^#\s+(.+)$", text, re.M)
    return m.group(1).strip() if m else "(无标题)"


def last_update_date(src, text, pub_date):
    """文章最近更新日期：正文中最晚的日期（ISO 与中文格式）与源文件
    修改日期取最大者，且不早于发布日期、不晚于构建当天。
    每日追加条目的博客正文含当日日期，更新日期随之自动滚动。"""
    today = _date.today().isoformat()
    upd = pub_date
    for pat in (r"(20\d{2})-(\d{1,2})-(\d{1,2})",
                r"(20\d{2})年(\d{1,2})月(\d{1,2})日"):
        for y, m, d in re.findall(pat, text):
            ds = f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
            if upd < ds <= today:
                upd = ds
    try:
        mt = _datetime.fromtimestamp(os.path.getmtime(src)).strftime("%Y-%m-%d")
        if upd < mt <= today:
            upd = mt
    except OSError:
        pass
    return upd


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
    in_card = False
    for line in text.splitlines()[:120]:
        if "DAILY-CARD:START" in line:
            in_card = True
            continue
        if "DAILY-CARD:END" in line:
            in_card = False
            continue
        if in_card:
            continue
        s = re.sub(r"<!--.*?-->", "", line).strip()
        if not s or s[0] in "#>|`-" or s[0] == "<":
            continue
        if s.startswith("!["):
            continue  # 图片行不是正文，不能当摘要
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
TYPE_LABEL_EN = {"morning": "Morning", "evening": "Evening", "custom": "Other",
                 "data": "Data Mining", "model": "Financial Modeling"}
TAB_LABELS_EN = {"daily": "Daily Reports", "data": "Data Mining",
                 "model": "Financial Modeling"}
DAILY_TITLE_EN = {
    "美股A股对标映射分析": "US-China Cross-Market Mapping Analysis",
    "A股收盘技术分析报告": "A-Share Close Technical Analysis Report",
}

def bi(zh, en):
    """双语 span：默认中文，html[data-lang="en"] 时显示英文（CSS + LANG_SCRIPT）。"""
    return f'<span class="lz">{zh}</span><span class="le">{en}</span>'

ABSTRACTS = {}
_abs_file = os.path.join(SITE, "abstracts.json")
if os.path.exists(_abs_file):
    with open(_abs_file, encoding="utf-8") as _f:
        ABSTRACTS = json.load(_f)
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
    content = "\n".join(blocks) if blocks else f'<p class="empty">{bi("暂无快讯", "No alerts yet")}</p>'
    page = PAGE_TMPL.format(
        title="及时快讯", body=content,
        meta_line=bi(f"共 {len(messages)} 条 · 按时间倒序",
                     f"{len(messages)} alerts - newest first"), root="", mathjax="",
        themeinit=THEME_INIT, donatefloat=donatefloat_html(""),
        backhash="", prevnext="")
    with open(os.path.join(SITE, "messages.html"), "w",
              encoding="utf-8") as f:
        f.write(page)
    print(f"page: messages.html ({len(messages)} 条快讯)")


def build_msgfloat(messages):
    """首页右下角浮窗：只显示最新1条快讯（含摘要）+ 未读红点（localStorage 记忆）。"""
    if not messages:
        return ""
    sortkey, date, hm, title, src = messages[0]
    anchor = f"m-{date}-{hm.replace(':', '')}"
    excerpt = extract_excerpt(open(src, encoding="utf-8").read(), limit=150)
    latest_id = anchor
    item = (f'<a href="messages.html#{anchor}">'
            f'<span class="t">{htmlmod.escape(title)}</span>'
            + (f'<span class="s">{htmlmod.escape(excerpt)}</span>'
               if excerpt else "")
            + f'<span class="d">{date} {hm}</span></a>')
    return f"""<div id="msgfloat">
  <button id="msgfloat-btn" type="button"><span><span class="lz">及时快讯</span><span class="le">Market Alerts</span></span><span class="msgfloat-dot" id="msgfloat-dot"></span></button>
  <div id="msgfloat-panel" hidden>
    <div class="msgfloat-head"><b><span class="lz">及时快讯</span><span class="le">Market Alerts</span></b><a href="messages.html"><span class="lz">全部存档 →</span><span class="le">All Alerts →</span></a></div>
    <div class="msgfloat-list">{item}</div>
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



DONATEFLOAT_HTML = """<div id="donatefloat">
  <button id="donatefloat-open" type="button" hidden><span class="lz">赞赏我的开发</span><span class="le">Buy me a coffee</span></button>
  <div id="donatefloat-panel">
    <button id="donatefloat-close" type="button" aria-label="关闭打赏窗口">&times;</button>
    <div class="donate-title"><span class="lz">赞赏我的开发</span><span class="le">Buy me a coffee</span></div>
    <img class="donate-coffee" src="assets/donate-coffee.jpg" alt="Buy me a coffee">
    <img class="donate-qr" src="assets/donate-wechat2.png" alt="微信支付收款码">
    <div class="donate-label"><span class="lz">微信</span><span class="le">WeChat</span></div>
    <img class="donate-qr" src="assets/donate-alipay2.png" alt="支付宝收款码">
    <div class="donate-label"><span class="lz">支付宝</span><span class="le">Alipay</span></div>
  </div>
</div>
<script>
(function(){
  var panel=document.getElementById('donatefloat-panel'),
      openBtn=document.getElementById('donatefloat-open'),
      closeBtn=document.getElementById('donatefloat-close');
  function setClosed(closed,save){
    panel.hidden=closed;
    openBtn.hidden=!closed;
    if(save){try{localStorage.setItem('drx_donate_closed',closed?'1':'0');}catch(e){}}
  }
  var wasClosed=false;
  try{wasClosed=localStorage.getItem('drx_donate_closed')==='1';}catch(e){}
  if(window.matchMedia&&matchMedia('(max-width:600px)').matches){wasClosed=true;}
  setClosed(wasClosed,false);
  closeBtn.addEventListener('click',function(){setClosed(true,true);});
  openBtn.addEventListener('click',function(){setClosed(false,true);});
})();
</script>"""



THEME_INIT = """<script>(function(){try{var t=localStorage.getItem('drx_theme');if(t==='dark'||t==='light'){document.documentElement.setAttribute('data-theme',t);}}catch(e){}})();</script>"""

LANG_INIT = """<script>(function(){try{var l=localStorage.getItem('drx_lang');if(l==='en'){document.documentElement.setAttribute('data-lang','en');document.documentElement.lang='en';}}catch(e){}})();</script>"""
THEME_INIT = THEME_INIT + LANG_INIT

LANG_SCRIPT = """<script>
(function(){
  function paint(){
    var en=document.documentElement.getAttribute('data-lang')==='en';
    document.querySelectorAll('.lang-toggle').forEach(function(b){b.textContent=en?'\u4e2d\u6587':'EN';});
    if(window.drxPaintTheme)window.drxPaintTheme();
  }
  document.querySelectorAll('.lang-toggle').forEach(function(b){
    b.addEventListener('click',function(){
      var en=document.documentElement.getAttribute('data-lang')==='en';
      if(en){document.documentElement.removeAttribute('data-lang');document.documentElement.lang='zh-CN';try{localStorage.setItem('drx_lang','zh');}catch(e){}}
      else{document.documentElement.setAttribute('data-lang','en');document.documentElement.lang='en';try{localStorage.setItem('drx_lang','en');}catch(e){}}
      paint();
    });
  });
  paint();
})();
</script>"""

THEME_SCRIPT = """<script>
(function(){
  function effective(){
    var t=document.documentElement.getAttribute('data-theme');
    if(t==='dark'||t==='light') return t;
    return (window.matchMedia&&matchMedia('(prefers-color-scheme: dark)').matches)?'dark':'light';
  }
  function paint(){
    var en=document.documentElement.getAttribute('data-lang')==='en';
    var label=effective()==='dark'?(en?'Light Mode':'\u6d45\u8272\u6a21\u5f0f'):(en?'Dark Mode':'\u6df1\u8272\u6a21\u5f0f');
    document.querySelectorAll('.theme-toggle:not(.lang-toggle)').forEach(function(b){b.textContent=label;});
  }
  window.drxPaintTheme=paint;
  document.querySelectorAll('.theme-toggle:not(.lang-toggle)').forEach(function(b){
    b.addEventListener('click',function(){
      var nxt=effective()==='dark'?'light':'dark';
      document.documentElement.setAttribute('data-theme',nxt);
      try{localStorage.setItem('drx_theme',nxt);}catch(e){}
      paint();
    });
  });
  paint();
})();
</script>"""


def donatefloat_html(root=""):
    """donate float + theme script; subpages prefix image paths with root, close state shared site-wide."""
    return DONATEFLOAT_HTML.replace('src="assets/', 'src="' + root + 'assets/') + THEME_SCRIPT + LANG_SCRIPT


_CN_DIGITS = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
              "六": 6, "七": 7, "八": 8, "九": 9}


def _cn_num(s):
    if s == "十":
        return 10
    if "十" in s:
        tens, _, ones = s.partition("十")
        return (_CN_DIGITS.get(tens, 1) if tens else 1) * 10 + _CN_DIGITS.get(ones, 0)
    return _CN_DIGITS.get(s, -1)


def _custom_sort_key(fname):
    """同日文章按文件名倒序；带「第X讲」的系列文章先按讲次倒序（新讲在前）。"""
    m = re.match(r"(\d{4}-\d{2}-\d{2})-(.+)\.(md|html)$", fname)
    if not m:
        return ("", -1, fname)
    lm = re.search(r"第([一二三四五六七八九十两]+|\d+)讲", m.group(2))
    if not lm:
        n = -1
    elif lm.group(1).isdigit():
        n = int(lm.group(1))
    else:
        n = _cn_num(lm.group(1))
    return (m.group(1), n, fname)


def collect_custom():
    items = []  # (tab_id, subdir, date, name, ext, src_path)
    for subdir, tab_id in CUSTOM_DIRS.items():
        d = os.path.join(CUSTOM_DIR, subdir)
        if not os.path.isdir(d):
            continue
        names = set(os.listdir(d))
        for fname in sorted(names, key=_custom_sort_key, reverse=True):
            m = re.match(r"(\d{4}-\d{2}-\d{2})-(.+)\.(md|html)$", fname)
            if not m:
                continue
            # 跳过由 .md 生成的同名 .html，避免重复卡片
            if m.group(3) == "html" and f"{m.group(1)}-{m.group(2)}.md" in names:
                continue
            items.append((tab_id, subdir, m.group(1), m.group(2),
                          m.group(3), os.path.join(d, fname)))
    return items


def card(href, rtype, pub_date, title, excerpt, data_date, news_note="",
         update_date="", title_html=""):
    badges = (f'<span class="badge {rtype}">{bi(TYPE_LABEL[rtype], TYPE_LABEL_EN[rtype])}</span>'
              f'<span class="badge date">{bi(pub_date + " 发布", "Published " + pub_date)}</span>')
    if update_date and update_date > pub_date:
        badges += f'<span class="badge update">{bi(update_date + " 更新", "Updated " + update_date)}</span>' 
    if news_note:
        badges += f'<span class="badge news">{bi("新闻版", "News Edition")}</span>'
        meta = bi("本期为新闻版", "News edition")
    else:
        meta = bi(f"数据基准 {data_date}", f"Data as of {data_date}")
    excerpt_html = (f'<p class="excerpt">{htmlmod.escape(excerpt)}</p>'
                    if excerpt else "")
    return CARD_TMPL.format(
        href=href, badges=badges,
        title=title_html if title_html else htmlmod.escape(title),
        excerpt_html=excerpt_html, meta=meta)


def prevnext_html(order, idx, root):
    """文章页打印行右侧的前一篇/后一篇按钮。order 为栏目内展示顺序
    （新→旧）的 (href, title) 列表：前一篇=时间上的前一篇（更旧，idx+1），
    后一篇=时间上的后一篇（更新，idx-1）。列表竖排、新在上旧在下，故
    前一篇向下 ↓、后一篇向上 ↑；按钮左→右为[后一篇][前一篇]，前一篇
    固定在最右端，单按钮时位置不跳。"""
    parts = []
    if 0 <= idx - 1 < len(order):
        href, title = order[idx - 1]
        parts.append(f'<a href="{root}{href}" title="{htmlmod.escape(title)}">'
                     + bi("后一篇 ↑", "Next ↑") + "</a>")
    if 0 <= idx + 1 < len(order):
        href, title = order[idx + 1]
        parts.append(f'<a href="{root}{href}" title="{htmlmod.escape(title)}">'
                     + bi("前一篇 ↓", "Prev ↓") + "</a>")
    return "".join(parts)


def build():
    messages = collect_messages()
    build_messages_page(messages)
    os.makedirs(os.path.join(SITE, "reports"), exist_ok=True)
    os.makedirs(os.path.join(SITE, "assets"), exist_ok=True)
    with open(os.path.join(SITE, "assets", "style.css"), "w",
              encoding="utf-8") as f:
        f.write(CSS)

    daily_cards = []
    daily_pages = []  # 待写页面（先收集，齐全后按栏目顺序补前一篇/后一篇再写）
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
            meta_line = bi(f"发布日期：{pub_date} · 类型：{TYPE_LABEL[rtype]} · 本期为新闻版",
                           f"Published {pub_date} · {TYPE_LABEL_EN[rtype]} · News edition")
        else:
            body_md = re.sub(r"^#\s+.+$", "# " + title, text,
                             count=1, flags=re.M)
            excerpt = extract_excerpt(text)
            meta_line = bi(f"发布日期：{pub_date} · 数据基准：{data_date} · 类型：{TYPE_LABEL[rtype]}",
                           f"Published {pub_date} · Data as of {data_date} · {TYPE_LABEL_EN[rtype]}")
        body = md_to_html(body_md)
        title_html = ""
        _ten = DAILY_TITLE_EN.get(title)
        if _ten:
            title_html = bi(htmlmod.escape(title), htmlmod.escape(_ten))
            body = re.sub(
                r"<h1>(.*?)</h1>",
                lambda m: "<h1>" + bi(m.group(1),
                                      htmlmod.escape(_ten)) + "</h1>",
                body, count=1, flags=re.S)
        daily_pages.append({
            "slug": slug, "title": title, "body": body,
            "meta_line": meta_line, "src": src})
        daily_cards.append((pub_date, card(
            f"reports/{slug}.html", rtype, pub_date, title,
            excerpt, data_date, news_cfg["note"] if news_cfg else "",
            title_html=title_html)))

    _daily_order = [(f"reports/{p['slug']}.html", p["title"])
                    for p in daily_pages]
    for _i, p in enumerate(daily_pages):
        page = PAGE_TMPL.format(
            title=htmlmod.escape(p["title"]), body=p["body"],
            meta_line=p["meta_line"],
            root="../", mathjax=MATHJAX if "$" in p["body"] else "",
            themeinit=THEME_INIT, donatefloat=donatefloat_html("../"),
            backhash="#daily",
            prevnext=prevnext_html(_daily_order, _i, "../"))
        with open(os.path.join(SITE, "reports", p["slug"] + ".html"), "w",
                  encoding="utf-8") as f:
            f.write(page)
        print(f"page: reports/{p['slug']}.html  <- {os.path.basename(p['src'])}")

    tab_cards = {"data": [], "model": []}
    data_cards_keyed = []  # (slug, card_html)，用于数据掘金置顶排序
    data_order_keyed = []  # (slug, (href, title))，与 data_cards_keyed 同步置顶
    tab_order = {"data": [], "model": []}  # 各栏目展示顺序 (href, title)
    custom_pages = []  # md 文章页先收集，齐全后补前一篇/后一篇再写
    for tab_id, subdir, date, name, ext, src in collect_custom():
        if ext == "md":
            text = open(src, encoding="utf-8").read()
            title = extract_h1(text)
            excerpt = extract_excerpt(text)
            slug = f"{date}-{name}"
            upd = last_update_date(src, text, date)
            body = collapse_daily_records(md_to_html(text))
            _entry = ABSTRACTS.get(slug) or {}
            if isinstance(_entry, str):
                _entry = {"abstract": _entry}
            title_en = _entry.get("title", "")
            title_html = ""
            if title_en:
                title_html = bi(htmlmod.escape(title),
                                htmlmod.escape(title_en))
                body = re.sub(
                    r"<h1>(.*?)</h1>",
                    lambda m: "<h1>" + bi(m.group(1),
                                          htmlmod.escape(title_en)) + "</h1>",
                    body, count=1, flags=re.S)
            abs_text = _entry.get("abstract", "")
            if abs_text:
                _box = ('<div class="abstract"><h3>'
                        + bi("英文摘要", "Abstract")
                        + f'</h3><p>{htmlmod.escape(abs_text)}</p></div>')
                body = (body.replace("</h1>", "</h1>" + _box, 1)
                        if "</h1>" in body else _box + body)
            meta_line = bi(f"{date} 发布 · 类型：{TAB_LABELS[tab_id]}",
                           f"Published {date} · {TAB_LABELS_EN[tab_id]}")
            if upd > date:
                meta_line = bi(f"{date} 发布 · {upd} 更新 · 类型：{TAB_LABELS[tab_id]}",
                               f"Published {date} · Updated {upd} · {TAB_LABELS_EN[tab_id]}")
            href = f"custom/{subdir}/{slug}.html"
            custom_pages.append({
                "tab_id": tab_id, "href": href, "title": title,
                "body": body, "meta_line": meta_line,
                "out": os.path.join(CUSTOM_DIR, subdir, slug + ".html"),
                "src": src})
        else:  # html：自带样式，原样上架
            text = open(src, encoding="utf-8").read()
            title = extract_html_title(text) or name
            excerpt = ""
            upd = last_update_date(src, text, date)
            href = f"custom/{subdir}/{os.path.basename(src)}"
            print(f"file: {href}")
        _card_html = card(href, tab_id, date, title, excerpt, date,
                          update_date=upd,
                          title_html=title_html if ext == "md" else "")
        tab_cards[tab_id].append(_card_html)
        tab_order[tab_id].append((href, title))
        if tab_id == "data":
            data_cards_keyed.append((f"{date}-{name}", _card_html))
            data_order_keyed.append((f"{date}-{name}", (href, title)))

    # 数据掘金置顶：两个每日更新的模拟交易博客固定排在最前（新金路 → 100万组合）
    if data_cards_keyed:
        _pinned = ["2026-10-14-DrX-新金路箱体回归模拟交易",
                   "2026-10-14-DrX-100万组合模拟仓",
                   "2026-11-06-SGu-双基金核心卫星模拟仓"]
        _map = dict(data_cards_keyed)
        tab_cards["data"] = ([_map[k] for k in _pinned if k in _map]
                             + [h for k, h in data_cards_keyed
                                if k not in _pinned])
        _omap = dict(data_order_keyed)
        tab_order["data"] = ([_omap[k] for k in _pinned if k in _omap]
                             + [h for k, h in data_order_keyed
                                if k not in _pinned])

    for p in custom_pages:
        _order = tab_order[p["tab_id"]]
        _idx = [h for h, _ in _order].index(p["href"])
        page = PAGE_TMPL.format(
            title=htmlmod.escape(p["title"]), body=p["body"],
            meta_line=p["meta_line"],
            root="../../", mathjax=MATHJAX if "$" in p["body"] else "",
            themeinit=THEME_INIT, donatefloat=donatefloat_html("../../"),
            backhash="#" + p["tab_id"],
            prevnext=prevnext_html(_order, _idx, "../../"))
        with open(p["out"], "w", encoding="utf-8") as f:
            f.write(page)
        print(f"page: {p['href']}  <- {os.path.basename(p['src'])}")

    panels = {
        "daily": (bi("早盘 · 美股A股对标映射分析 ／ 晚间 · A股收盘技术分析 — 定时任务自动更新",
                     "Morning · US-China cross-market mapping / Evening · A-share close technical analysis - updated automatically on schedule"),
                  [c for _, c in daily_cards],
                  f"archive-{daily_cards[0][0][:7]}.html" if daily_cards else ""),
        "data": (bi("量化分析与数据挖掘 — 把 .md / .html 按 <code>YYYY-MM-DD-标题</code> 命名放入 custom/数据掘金/ 重新构建",
                    "Quantitative analysis and data mining - research notes and reproducible strategy studies"),
                 tab_cards["data"], "archive-data.html"),
        "model": (bi("金融建模相关报告 — 把 .md / .html 按 <code>YYYY-MM-DD-标题</code> 命名放入 custom/金融建模/ 重新构建",
                     "Financial modeling - paper studies and derivations in stochastic control, variational methods and derivatives pricing"),
                  tab_cards["model"], "archive-model.html"),
    }
    order = ["daily", "data", "model"]
    HOME_LIMIT = 10  # 首页每栏最多显示条数，超出进归档页
    tabbar = ['<div class="tabs" role="tablist">']
    for tid in order:
        n = len(panels[tid][1])
        active = " active" if tid == "daily" else ""
        tabbar.append(
            f'<button class="tab{active}" data-tab="{tid}" role="tab">'
            f'<span class="t">{bi(TAB_LABELS[tid], TAB_LABELS_EN[tid])}</span>'
            f'<span class="count">{bi(str(n) + " 篇", str(n) + " posts")}</span></button>')
    tabbar.append("</div>")
    parts = ["\n".join(tabbar)]
    for tid in order:
        hint, cards, archive_href = panels[tid]
        shown = cards[:HOME_LIMIT]
        inner = "\n".join(shown) if shown else f'<p class="empty">{bi("暂无内容", "No content yet")}</p>'
        if len(cards) > HOME_LIMIT and archive_href:
            inner += (f'<p class="more"><a href="{archive_href}">'
                      + bi(f"查看全部 {len(cards)} 篇 →", f"View all {len(cards)} →")
                      + "</a></p>")
        hid = "" if tid == "daily" else " hidden"
        parts.append(
            f'<section id="tab-{tid}"{hid}>\n'
            f'<p class="section-hint">{hint}</p>\n{inner}\n</section>')
    content = "\n".join(parts)

    with open(os.path.join(SITE, "index.html"), "w",
              encoding="utf-8") as f:
        f.write(INDEX_TMPL.replace("{content}", content)
                .replace("{msgfloat}", build_msgfloat(messages))
                .replace("{donatefloat}", donatefloat_html(""))
                .replace("{themeinit}", THEME_INIT))
    print(f"index: {len(daily_cards)} daily + {len(tab_cards['data'])} data"
          f" + {len(tab_cards['model'])} model")

    build_archives(daily_cards, tab_cards)


def build_archives(daily_cards, tab_cards):
    """归档页：每日报告按月（archive-YYYY-MM.html），数据掘金/金融建模各一页全量。"""
    # 每日报告按月分组
    months = {}
    for pub_date, html in daily_cards:
        months.setdefault(pub_date[:7], []).append(html)
    month_list = sorted(months.keys(), reverse=True)
    for ym in month_list:
        nav = " · ".join(
            f'<a href="archive-{m}.html">{m}</a>' if m != ym else f"<b>{m}</b>"
            for m in month_list)
        body = (f'<p class="section-hint">{bi("按月归档", "Monthly archive")} · {nav}</p>\n'
                + "\n".join(months[ym]))
        page = PAGE_TMPL.format(
            title=f"每日报告归档 {ym}", body=body,
            meta_line=bi(f"{ym} · 共 {len(months[ym])} 篇",
                         f"{ym} - {len(months[ym])} reports"), root="",
            mathjax="", themeinit=THEME_INIT, donatefloat=donatefloat_html(""),
            backhash="#daily", prevnext="")
        with open(os.path.join(SITE, f"archive-{ym}.html"), "w",
                  encoding="utf-8") as f:
            f.write(page)
        print(f"page: archive-{ym}.html ({len(months[ym])} 篇)")
    # 数据掘金 / 金融建模全量归档
    for tab_id, fname in (("data", "archive-data.html"),
                          ("model", "archive-model.html")):
        cards = tab_cards[tab_id]
        body = "\n".join(cards) if cards else f'<p class="empty">{bi("暂无内容", "No content yet")}</p>'
        page = PAGE_TMPL.format(
            title=f"{TAB_LABELS[tab_id]}全部存档", body=body,
            meta_line=bi(f"共 {len(cards)} 篇", f"{len(cards)} posts"), root="", mathjax="",
            themeinit=THEME_INIT, donatefloat=donatefloat_html(""),
            backhash="#" + tab_id, prevnext="")
        with open(os.path.join(SITE, fname), "w",
                  encoding="utf-8") as f:
            f.write(page)
        print(f"page: {fname} ({len(cards)} 篇)")


if __name__ == "__main__":
    build()
