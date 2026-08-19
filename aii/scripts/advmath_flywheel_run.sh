#!/usr/bin/env bash
# ★高级数学经济专用飞轮 — 连续运行(不停, 非定时). 同 econ_flywheel_zh_run.sh 的模式.
# 用法:  nohup bash scripts/advmath_flywheel_run.sh >> advmath_pipeline/flywheel.log 2>&1 &
# 可选:  ADVMATH_IDLE_SLEEP=600(无书时sleep秒, 默认600)
set -uo pipefail
cd "$(dirname "$0")/.."
# ★单实例锁: 防止 systemd 服务 + 手动 nohup 双跑(实测双实例同 key 打 NIM → 限流风暴
# → ReadTimeout 重试地狱 → 整批隔离, 零入库)。已持锁实例正常跑, 新实例立即退出。
mkdir -p .locks
exec 9>.locks/advmath_flywheel.lock
flock -n 9 || { echo "⚠ 已有实例在运行({lock}), 本次启动退出"; exit 0; }

IDLE="${ADVMATH_IDLE_SLEEP:-600}"
BOOKLIST="advmath_pipeline/flywheel_booklist.txt"

echo "════════════════════════════════════════════════════"
echo "★ 高级数学经济专用飞轮 — 连续运行启动 $(date '+%Y-%m-%d %H:%M')"
echo "  模式: 不停(处理完一本质量门确认→下一本; 无书sleep ${IDLE}s 再查)"
echo "════════════════════════════════════════════════════"

while true; do
    bash scripts/advmath_flywheel.sh || echo "  ⚠️ 本轮飞轮异常(继续循环) $(date '+%H:%M')"
    if [ ! -s "$BOOKLIST" ]; then
        echo "── [连续] 无新书, sleep ${IDLE}s 后再发现… $(date '+%H:%M') ──"
        sleep "$IDLE"
    fi
done
