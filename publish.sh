#!/bin/bash
# 每日报告站自动发布：重建全站 -> 有变更才提交推送
set -e
cd /home/hatch/workspace/dailystocks
/home/hatch/workspace/.venv-stocks/bin/python build.py
git add -A
if git diff --cached --quiet; then
  echo "no changes, skip push"
else
  git commit -qm "reports: $(date +%F) 自动更新"
  git push origin main
  echo "pushed"
fi
