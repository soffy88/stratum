#!/usr/bin/env bash
# ★程序化中文经济学飞轮 — 连续运行(不停, 非定时)
# 处理完一本(econ_batch_run 自带 R1-R9预检 + A仓5步 + ★质量门抽查确认质量 → 入A仓/隔离)→ 下一本;
# 全部处理完(无新书)→ sleep 后再发现 → 继续. 永不退出(Ctrl-C / kill 才停).
#
# 用法:  nohup bash scripts/econ_flywheel_zh_run.sh >> econ_pipeline/flywheel_zh.log 2>&1 &
# 可选:  ECON_IDLE_SLEEP=600(无书时sleep秒, 默认600)
set -uo pipefail
cd "$(dirname "$0")/.."
# ★单实例锁: 防止 systemd 服务 + 手动 nohup 双跑(实测双实例同 key 打 NIM → 限流风暴
# → ReadTimeout 重试地狱 → 整批隔离, 零入库)。已持锁实例正常跑, 新实例立即退出。
mkdir -p .locks
exec 9>.locks/econ_flywheel_zh.lock
flock -n 9 || { echo "⚠ 已有实例在运行({lock}), 本次启动退出"; exit 0; }

IDLE="${ECON_IDLE_SLEEP:-600}"
BOOKLIST="econ_pipeline/flywheel_zh_booklist.txt"

echo "════════════════════════════════════════════════════"
echo "★ 程序化中文经济学飞轮 — 连续运行启动 $(date '+%Y-%m-%d %H:%M')"
echo "  模式: 不停(处理完一本质量门确认→下一本; 无书sleep ${IDLE}s 再查)"
echo "════════════════════════════════════════════════════"

while true; do
    bash scripts/econ_flywheel_zh.sh || echo "  ⚠️ 本轮飞轮异常(继续循环) $(date '+%H:%M')"
    if [ ! -s "$BOOKLIST" ]; then
        echo "── [连续] 无新中文经济书, sleep ${IDLE}s 后再发现… $(date '+%H:%M') ──"
        sleep "$IDLE"
    fi
done
