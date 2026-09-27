#!/usr/bin/env bash
# ★纯本地 convert — 跳过 stratum-docs 容器(单点瓶颈, 慢/挂会拖垮飞轮).
# 用本地 pdf_inspector(oprim) + markitdown 兜底, 速度 1-3s/本.
# 跑 3 个目录: 其它 427 + 教辅 808 + 计算机 149 = 约 1400 本
# 预期 30-60 分钟全跑完.
set -uo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python

# 强制跳过容器: DOCS_URL 指向 unreachable 端口, 任何 connect 立即失败
export DOCS_URL="http://127.0.0.1:1"     # 端口 1 不可达, connection refused 立即
export DOCS_TIMEOUT=2                     # 2s 连接超时

LOG=.logs/local_convert.out
mkdir -p .logs
echo "════════════════════════════════════════════════════" > $LOG
echo "★ 本地 convert 启动 $(date '+%Y-%m-%d %H:%M')  (跳过容器, 纯本地 pdf_inspector/markitdown)" >> $LOG
echo "  渠道: 其它 427 + 教辅 808 + 计算机 149  =  约 1400 本" >> $LOG
echo "════════════════════════════════════════════════════" >> $LOG

# 其它
echo "── [local] 其它 (start $(date '+%H:%M')) ──" >> $LOG
$PY misc_convert.py --do >> $LOG 2>&1
echo "  done $(date '+%H:%M')" >> $LOG

# 教辅
echo "── [local] 教辅 (start $(date '+%H:%M')) ──" >> $LOG
CONVERT_SRC=/home/soffy/books/教辅 CONVERT_DST=/home/soffy/books/MD/教辅 CONVERT_TAG=教辅 \
  $PY misc_convert.py --do >> $LOG 2>&1
echo "  done $(date '+%H:%M')" >> $LOG

# 计算机
echo "── [local] 计算机 (start $(date '+%H:%M')) ──" >> $LOG
CONVERT_SRC=/home/soffy/books/计算机 CONVERT_DST=/home/soffy/books/MD/计算机 CONVERT_TAG=计算机 \
  $PY misc_convert.py --do >> $LOG 2>&1
echo "  done $(date '+%H:%M')" >> $LOG

echo "════════════════════════════════════════════════════" >> $LOG
echo "★ 本地 convert 完成 $(date '+%Y-%m-%d %H:%M')" >> $LOG
echo "════════════════════════════════════════════════════" >> $LOG
