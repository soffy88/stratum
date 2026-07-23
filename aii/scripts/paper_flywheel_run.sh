#!/usr/bin/env bash
# ★论文飞轮 — 连续运行(不停, 非定时). 同 advmath_flywheel_run.sh / misc_flywheel_run.sh 的模式.
# 用法:  nohup bash scripts/paper_flywheel_run.sh >> paper_pipeline/flywheel.log 2>&1 &
# 可选:  PAPER_IDLE_SLEEP=600(无新论文时sleep秒, 默认600)
set -uo pipefail
cd "$(dirname "$0")/.."
IDLE="${PAPER_IDLE_SLEEP:-600}"
BOOKLIST="paper_pipeline/flywheel_booklist.txt"

echo "════════════════════════════════════════════════════"
echo "★ 论文飞轮 — 连续运行启动 $(date '+%Y-%m-%d %H:%M')"
echo "  模式: 不停(处理完一批→下一批; 无新论文sleep ${IDLE}s 再查)"
echo "════════════════════════════════════════════════════"

while true; do
    bash scripts/paper_flywheel.sh || echo "  ⚠️ 本轮飞轮异常(继续循环) $(date '+%H:%M')"
    if [ ! -s "$BOOKLIST" ]; then
        echo "── [连续] 无新论文, sleep ${IDLE}s 后再发现… $(date '+%H:%M') ──"
        sleep "$IDLE"
    fi
done
