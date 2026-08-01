#!/usr/bin/env bash
# backfill_md_archive.sh — 一次性回填: 把 books/MD/{经济学,中文数学,英文数学,其它}
# 里已经存在的所有MD文件, 补传一份到 gdrive-rw:aii-已入库源MD/<同名>/。
#
# 背景(2026-07-23 用户指令): 转好+抽完KU的源MD是资产, 不能只留本地一份——本地目录长期
# 累积却从没备份过, 今天起飞轮每本书成功入库后会自动归档(见 econ_batch_run.sh /
# math_flywheel_prog.sh), 但今天之前已经存在的这一批需要单独补一次。
# 只增不删(rclone copy), 不动本地文件。
#
# 用法: bash scripts/backfill_md_archive.sh
set -euo pipefail
cd "$(dirname "$0")/.."

: "${RCLONE_PROXY=http://127.0.0.1:7890}"
if [ -n "${RCLONE_PROXY}" ] && [ -z "${HTTPS_PROXY:-}" ]; then
  export HTTPS_PROXY="${RCLONE_PROXY}" HTTP_PROXY="${RCLONE_PROXY}"
fi

for sub in 经济学 中文数学 英文数学 其它; do
  SRC="/home/soffy/books/MD/$sub"
  [ -d "$SRC" ] || { echo "[backfill] 跳过(不存在): $SRC"; continue; }
  echo "[backfill] $SRC → gdrive-rw:aii-已入库源MD/$sub/ …"
  rclone copy "$SRC" "gdrive-rw:aii-已入库源MD/$sub/" --include "*.md" --stats-one-line
done
echo "[backfill] 完成。"
