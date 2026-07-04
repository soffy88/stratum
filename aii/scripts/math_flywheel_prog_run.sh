#!/usr/bin/env bash
# ★数学程序化飞轮 B — 常驻循环. 处理完一轮无新书 sleep 后再发现. 永不退出.
# 用法: nohup bash scripts/math_flywheel_prog_run.sh >> math_pipeline/flywheel_prog.log 2>&1 &
set -uo pipefail
cd "$(dirname "$0")/.."
IDLE="${MATH_IDLE_SLEEP:-600}"

echo "════════════════════════════════════════════════════"
echo "★ 数学程序化飞轮 B (0 LLM) 常驻启动 $(date '+%Y-%m-%d %H:%M')"
echo "════════════════════════════════════════════════════"

while true; do
    bash scripts/math_flywheel_prog.sh || echo "  ⚠️ 本轮异常(继续循环) $(date '+%H:%M')"
    echo "── [连续] sleep ${IDLE}s 后再发现… $(date '+%H:%M') ──"
    sleep "$IDLE"
done
