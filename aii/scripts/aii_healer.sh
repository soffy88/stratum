#!/usr/bin/env bash
# ★AII/Stratum 管线自愈守护 — 15 分钟一轮(由 aii-healer.timer 驱动)
#
# 职责(全部幂等, 失败只记日志不中断):
#   1. aii systemd 用户服务: 非 active → 重启
#   2. stratum-api / stratum-sl 容器: 未运行 → docker start(D 盘挂载后自动成功)
#   3. /mnt/d 未挂载 → sudo -n systemctl start mnt-d.mount(sudoers NOPASSWD 已配时),
#      否则仅记录"需人工挂载"告警
#   4. KU 数据新鲜度: aii.ku_onto max(created_at) 停滞 >48h → 告警
#   5. 飞轮心跳: 各 pipeline 日志最后写入 >3h → 告警(空转或卡死信号)
# 日志: aii_pipeline/healer.log
set -uo pipefail
cd "$(dirname "$0")/.."
LOG="aii_pipeline/healer.log"
mkdir -p aii_pipeline
log() { echo "$(date '+%F %T') $*" >> "$LOG"; }
log "── healer 一轮开始 ──"

# 1. aii 服务自愈
SERVICES="aii-backend aii-feeder aii-flywheel-advmath aii-flywheel-econ-zh aii-flywheel-math-prog aii-flywheel-misc aii-flywheel-paper aii-embed"
for svc in $SERVICES; do
    if ! systemctl --user is-active --quiet "$svc" 2>/dev/null; then
        systemctl --user restart "$svc" 2>/dev/null
        log "🔄 自愈: $svc 非 active → 已重启"
    fi
done

# 2. stratum 容器自愈
for c in stratum-api stratum-sl; do
    state=$(docker inspect -f '{{.State.Status}}' "$c" 2>/dev/null || echo missing)
    if [ "$state" != "running" ]; then
        if docker start "$c" >/dev/null 2>&1; then
            log "🔄 自愈: 容器 $c 已启动"
        else
            log "⚠ 容器 $c 启动失败(state=$state, 多半是 D 盘未挂载导致卷路径悬空)"
        fi
    fi
done

# 3. D 盘
if ! findmnt /mnt/d >/dev/null 2>&1; then
    if sudo -n systemctl start mnt-d.mount >/dev/null 2>&1; then
        log "🔄 自愈: /mnt/d 已挂载"
    else
        log "🚨 /mnt/d 未挂载且无 sudo 权限自动挂(需人工: sudo ntfsfix /dev/nvme0n1p1; sudo mount /mnt/d)"
    fi
fi

# 4. KU 数据新鲜度(需要 psql/psycopg, 用 aii venv python 查库)
FRESH=$(.venv/bin/python -c '
import asyncio, asyncpg, os, datetime
async def go():
    c = await asyncpg.connect(os.getenv("DATABASE_URL", "postgresql://aii:aii_safe_pass@localhost:5435/aii_kg"), timeout=10)
    v = await c.fetchval("SELECT max(created_at) FROM aii.ku_onto")
    await c.close()
    if v is None: print("empty")
    else: print(v.strftime("%m-%d %H:%M") + f" ({(datetime.datetime.now(datetime.timezone.utc)-v).total_seconds()/3600:.0f}h ago)")
asyncio.run(go())
' 2>/dev/null || echo unknown)
log "📊 KU 最新入库: $FRESH"

# 5. 飞轮心跳(日志最后修改时间 > 3h = 卡死 → 自动重启, 保飞轮不停工)
for p in misc_pipeline/flywheel_misc.log econ_pipeline/flywheel_zh.log advmath_pipeline/flywheel.log math_pipeline/flywheel_prog.log; do
    if [ -f "$p" ]; then
        age_min=$(( ($(date +%s) - $(stat -c %Y "$p")) / 60 ))
        if [ "$age_min" -gt 180 ]; then
            case "$p" in
                misc_pipeline/*) svc="aii-flywheel-misc" ;;
                econ_pipeline/*) svc="aii-flywheel-econ-zh" ;;
                advmath_pipeline/*) svc="aii-flywheel-advmath" ;;
                math_pipeline/*) svc="aii-flywheel-math-prog" ;;
            esac
            if systemctl --user restart "$svc" 2>/dev/null; then
                log "🔄 自愈: $svc 心跳停滞 ${age_min}min → 已重启"
            else
                log "🚨 心跳停滞: $p ${age_min}min, 重启 $svc 失败(需人工)"
            fi
        fi
    fi
done

# 6. B 仓体检 + 零风险修复(每轮都跑: 打标 → 修断链 → crit 告警)
B_LINT=$(.venv/bin/python scripts/ku_lint.py --fix-safe --json 2>/dev/null || echo '{"summary":{}}')
B_CRIT=$(echo "$B_LINT" | .venv/bin/python -c "import json,sys;d=json.load(sys.stdin);print(d.get('summary',{}).get('crit',0))" 2>/dev/null || echo 0)
B_FIXED=$(echo "$B_LINT" | .venv/bin/python -c "import json,sys;d=json.load(sys.stdin);print(d.get('summary',{}).get('fixed_rows',0))" 2>/dev/null || echo 0)
log "📊 B 仓体检: crit=$B_CRIT, 本轮修断链=$B_FIXED"
if [ "${B_CRIT:-0}" -gt 0 ] 2>/dev/null; then
    log "🚨 B 仓 crit 项 > 0: 查看 rf.ku_health_issues (status='open', severity='crit')"
fi

log "── healer 一轮完成 ──"
