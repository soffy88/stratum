#!/usr/bin/env bash
# ★论文单篇 worker — 由 paper_flywheel.sh Step 2 经 xargs -P 并发调用。
# 输入: 一行 TAB 分隔 "md_path<TAB>substrate<TAB>title"(与 paper_discover.py 的 TAB 协议对齐)。
# 输出: 进度走 stdout(经 xargs 汇入飞轮日志); 结果("OK|FAIL substrate")追加到 $PAPER_RESULTS
#       (每行小写原子, 飞轮汇总后统一写 flywheel_state, 避免并发写 state 损坏)。
#
# 并发安全(每篇按 SUBSTRATE 隔离, 互不共享写文件):
#   - generate_bu.py 写 econ_pipeline/bu_{SUB}.json(唯一)
#   - persist_bu.py 读同一文件、写 bu_onto 按 SUB
#   - paper_v3_gate.py 写 agent_skill 按 SUB
#   - econ_register.py 追加 run_log.jsonl(单行 write, O_APPEND 原子)
set -uo pipefail
cd "$(dirname "$0")/.."

line="${1:-}"
[ -z "$line" ] && exit 0
IFS=$'\t' read -r md_path substrate title <<< "$line"
[ -z "$substrate" ] && exit 0

echo "  → $substrate ($title)"
if SUBSTRATE="$substrate" AII_MD_FILE="$md_path" PAPER_TITLE="$title" \
    bash scripts/paper_pipeline.sh 2>&1 | sed 's/^/    /'; then
    echo "OK $substrate" >> "${PAPER_RESULTS:?}"
else
    echo "FAIL $substrate" >> "${PAPER_RESULTS:?}"
fi
