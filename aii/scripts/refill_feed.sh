#!/usr/bin/env bash
# ★断料主动补料: 飞轮 discover 到无新书(空转)时, 主动触发夸克盘同步一轮.
#   与 aii-quark-sync.timer(每2h固定节奏)构成双保险: 定时补 + 断料即时补.
#   flock 与 timer 共用同一锁文件: 任一方在跑, 另一方直接跳过(防双实例同写 .part).
#   幂等: quark_drive_sync.py 按 .quarkid.json 去重, 重复触发不会重复下载.
set -uo pipefail
cd "$(dirname "$0")/.."

LOCK=.locks/quark_refill.lock
mkdir -p .locks
exec 9>"$LOCK"
flock -n 9 || { echo "  [refill] 夸克同步已在跑(跳过本轮)"; exit 0; }

echo "  [refill] $(date '+%F %H:%M') 空转触发夸克补料(--limit 10)..."
timeout 1200 .venv/bin/python scripts/quark_drive_sync.py --limit 10 2>&1 | tail -6
RC=${PIPESTATUS[0]}
echo "  [refill] $(date '+%H:%M') 夸克补料结束 rc=$RC"
exit 0
