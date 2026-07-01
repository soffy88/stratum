#!/usr/bin/env bash
# ★OAPEN 开放教材抓取守护(主机侧) — 定期从 OAPEN 拉开放书 → /books/{Economic|数学} → feeder 转MD → 飞轮.
#
# 为何主机侧: 容器到不了 library.oapen.org(路由), 主机直连可达; 历史的 8766 代理已弃.
# 为何长间隔: OAPEN 内容静态, 抓完可得的就够了; 去重(对齐已入库)让重跑几乎0新增, 偶尔补新书.
# 多级过滤保证质量: oapen_fetch(只取真PDF) → econ/math_convert(教材门) → 飞轮预检 → A仓质量门.
#
# 用法: nohup bash scripts/oapen_fetch_run.sh >> econ_pipeline/oapen.log 2>&1 &
# 可选: OAPEN_IDLE=21600(间隔秒,默认6h)  OAPEN_MAX=3(每主题每轮最多下,默认3)
set -uo pipefail
cd "$(dirname "$0")/.."
IDLE="${OAPEN_IDLE:-21600}"
MAX="${OAPEN_MAX:-3}"

echo "════════ ★OAPEN 抓取守护启动 $(date '+%F %H:%M')  (每 ${IDLE}s, 每主题≤${MAX}本) ════════"
while true; do
    echo "── [OAPEN] $(date '+%F %H:%M') 抓一轮 ──"
    python3 oapen_fetch.py --do --max "$MAX" 2>&1 | grep -E "✓ 存|✓ 共下载|搜索失败|✗" | tail -20
    echo "── [OAPEN] sleep ${IDLE}s ──"
    sleep "$IDLE"
done
