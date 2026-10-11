#!/bin/bash
# 每日报告站自动发布：同步远端 -> 重建全站 -> 有变更才提交推送
set -e
cd /home/hatch/workspace/dailystocks
# 用户可能直接在 GitHub 上传文章/图片，先拉下来；失败不中断（推送时再报错）
git pull --rebase origin main 2>&1 | tail -1 || true
/home/hatch/workspace/.venv-stocks/bin/python build.py
git add -A
if git diff --cached --quiet; then
  echo "no changes, skip push"
else
  git commit -qm "reports: $(date +%F) 自动更新"
  git push origin main
  echo "pushed"
fi
