#!/usr/bin/env bash
# ★全量重转脚本 — 把 gDrive 大量新书一次性 PDF→MD.
# 设计: 串行跑(避免 5 并发拉爆 stratum-docs), 单一后台长跑(7200s=2h 足够 1700+ PDF),
# 跑完自己退出, 不需要常驻. feeder_run.sh 主轮询仍负责新增.
# 用法: nohup bash scripts/bulk_convert.sh > .logs/bulk_convert.out 2>&1 &
set -uo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
LOG=.logs/bulk_convert.out
mkdir -p .logs

echo "════════════════════════════════════════════════════"
echo "★ 全量重转启动 $(date '+%Y-%m-%d %H:%M')  (timeout 7200s=2h)"
echo "  渠道: 其它 427 + 教辅 808 + 计算机 149  =  约 1400 本"
echo "════════════════════════════════════════════════════"

# 1. 其它 (最杂, 最先跑, 失败最不影响业务)
echo "── [bulk] 其它 (start $(date '+%H:%M')) ──"
$PY misc_convert.py --do 2>&1 | tail -3 | sed 's/^/  /'

# 2. 教辅
echo "── [bulk] 教辅 (start $(date '+%H:%M')) ──"
CONVERT_SRC=/home/soffy/books/教辅 CONVERT_DST=/home/soffy/books/MD/教辅 CONVERT_TAG=教辅 \
  timeout 3600 $PY misc_convert.py --do 2>&1 | tail -3 | sed 's/^/  /'

# 3. 计算机
echo "── [bulk] 计算机 (start $(date '+%H:%M')) ──"
CONVERT_SRC=/home/soffy/books/计算机 CONVERT_DST=/home/soffy/books/MD/计算机 CONVERT_TAG=计算机 \
  timeout 1800 $PY misc_convert.py --do 2>&1 | tail -3 | sed 's/^/  /'

echo "════════════════════════════════════════════════════"
echo "★ 全量重转完成 $(date '+%Y-%m-%d %H:%M')"
echo "════════════════════════════════════════════════════"
