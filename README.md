# 每日市场报告 · 静态站

由 `build.py` 从 `~/workspace/stocks/` 的 Markdown 报告自动生成，部署在 Cloudflare Pages。

## 目录结构

```
index.html            # 首页：报告按发布时间倒序
assets/style.css      # 全站样式
reports/              # 每期报告页：<发布日期>-<morning|evening>.html
build.py              # 生成脚本（md → html + 首页）
```

## 本地重新生成

```bash
~/workspace/.venv-stocks/bin/python ~/workspace/dailystocks/build.py
```

## 发布流程（定时任务内）

1. 早盘 / 晚间 cron 生成 `.md` + `.pdf`（现有流程不变）
2. 运行 `build.py` 重新生成全站
3. `git add -A && git commit -m "reports: <日期>" && git push` → Cloudflare Pages 自动重新部署
