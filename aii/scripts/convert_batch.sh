#!/usr/bin/env bash
# ★串行批量 PDF→MD 转换(每个分类一个独立目标目录)。
# 源是 gdrive:aii-books 的只读 FUSE 挂载, 产物必须写本地 gdrive_staging(挂载只读写不进去)。
# 串行而非并发: 单本 analyze 就要读整本 PDF 过 FUSE, 并发只会互相抢带宽。
# KEEP_SRC=1: 源在云端, 不删。
set -uo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
ROOT=$PWD
mkdir -p .logs

run_one() {
  local cat="$1"
  local dst="$ROOT/gdrive_staging/MD/$cat"
  mkdir -p "$dst"
  echo "════════════════════════════════════════════════════"
  echo "★ [$cat] 转换启动 $(date '+%Y-%m-%d %H:%M')"
  echo "════════════════════════════════════════════════════"
  CONVERT_SRC="/home/soffy/books/$cat" CONVERT_DST="$dst" CONVERT_TAG="$cat" KEEP_SRC=1 \
    timeout 21600 "$PY" -u misc_convert.py --do 2>&1 | tee -a ".logs/convert_$cat.out" | \
    grep -aE "^=== |✅|⚠ |✗ |📗|📕"
  echo "★ [$cat] 结束 $(date '+%Y-%m-%d %H:%M')"
}

for c in "$@"; do
  run_one "$c"
done
echo "全部指定分类处理完毕 $(date '+%Y-%m-%d %H:%M')"
