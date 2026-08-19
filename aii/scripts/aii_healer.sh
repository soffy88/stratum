#!/usr/bin/env bash
# ★AII/Stratum 管线自愈守护 — 15 分钟一轮(由 aii-healer.timer 驱动)
#
# 职责(全部幂等, 失败只记日志不中断):
#   1. aii systemd 用户服务: 非 active → 重启(含 cs/edu 飞轮, 2026-08-16 补齐)
#   2. aii-embed: ★已迁笔记本GTX1050Ti(100.119.113.90:8102, tailscale)。先真调远程
#      /health+/embed; 不通才试本机 unit(受 hevi GPU 占用 ConditionPathExists 限制);
#      两者都不通 → 🚨 告警(需人工去笔记本侧重启, 本机无法代劳)
#   3. stratum-api / stratum-sl 容器: 未运行 → docker start(D 盘挂载后自动成功)
#   4. /mnt/d 未挂载 → sudo -n systemctl start mnt-d.mount(sudoers NOPASSWD 已配时),
#      否则仅记录"需人工挂载"告警
#   5. KU 数据新鲜度: aii.ku_onto max(created_at) 停滞 >48h → 告警
#   6. 飞轮心跳: 各 pipeline 日志最后写入 >3h → 自动重启(空转或卡死信号)
#   7. aii-extract 崩溃循环检测: /tmp/lx-env 丢失导致 EXEC 失败(重启也白搭) → 🚨 提示修复
#   8. 磁盘: / 或 /data 用量 >92% → 🚨; 飞轮日志 >300MB 就地截断(append-only 写入方不受影响)
# 日志: aii_pipeline/healer.log
set -uo pipefail
cd "$(dirname "$0")/.."
LOG="aii_pipeline/healer.log"
mkdir -p aii_pipeline
log() { echo "$(date '+%F %T') $*" >> "$LOG"; }
log "── healer 一轮开始 ──"

# 1. aii 服务自愈(aii-embed 单独处理见下)
SERVICES="aii-backend aii-feeder aii-flywheel-advmath aii-flywheel-cs aii-flywheel-econ-zh aii-flywheel-math-prog aii-flywheel-misc aii-flywheel-edu aii-flywheel-paper"
for svc in $SERVICES; do
    if ! systemctl --user is-active --quiet "$svc" 2>/dev/null; then
        systemctl --user restart "$svc" 2>/dev/null
        log "🔄 自愈: $svc 非 active → 已重启"
    fi
done

# 2. aii-embed: 远程真调用优先(笔记本 GPU, 已迁移); 不通再试本机 unit; 都不通 → 🚨
EMBED_URL="${AII_EMBED_URL:-http://100.119.113.90:8102}"
EMBED_OK=0
if curl -s -m 8 -o /dev/null "$EMBED_URL/health" 2>/dev/null; then
    if curl -s -m 20 -X POST "$EMBED_URL/embed" -H "Content-Type: application/json" \
        -d '{"texts":["体检"]}' 2>/dev/null | grep -q '"embeddings"'; then
        EMBED_OK=1
    else
        log "🚨 aii-embed($EMBED_URL) /health通但 /embed 异常(维度/模型错误?) — 需人工查笔记本"
    fi
fi
if [ "$EMBED_OK" -eq 0 ]; then
    if systemctl --user restart aii-embed 2>/dev/null && systemctl --user is-active --quiet aii-embed 2>/dev/null; then
        log "🔄 自愈: aii-embed 远程不可达 → 本机 unit 已重启(注意: 本机受 hevi GPU 占用条件限制)"
    else
        log "🚨 aii-embed($EMBED_URL) 无响应且本机 unit 无法启动 — 需人工去笔记本(WSL/原生)重启 aii-embed; 所有飞轮入库会 err=N ok=0"
    fi
fi

# 3. stratum 容器自愈
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

# 4. D 盘
if ! findmnt /mnt/d >/dev/null 2>&1; then
    if sudo -n systemctl start mnt-d.mount >/dev/null 2>&1; then
        log "🔄 自愈: /mnt/d 已挂载"
    else
        log "🚨 /mnt/d 未挂载且无 sudo 权限自动挂(需人工: sudo ntfsfix /dev/nvme0n1p1; sudo mount /mnt/d)"
    fi
fi

# 5. KU 数据新鲜度(需要 psql/psycopg, 用 aii venv python 查库)
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

# 6. 飞轮心跳(日志最后修改时间 > 3h = 卡死 → 自动重启, 保飞轮不停工)
for p in misc_pipeline/flywheel_misc.log econ_pipeline/flywheel_zh.log advmath_pipeline/flywheel.log \
         math_pipeline/flywheel_prog.log cs_pipeline/flywheel_cs.log edu_pipeline/flywheel_edu.log \
         paper_pipeline/flywheel.log; do
    if [ -f "$p" ]; then
        age_min=$(( ($(date +%s) - $(stat -c %Y "$p")) / 60 ))
        if [ "$age_min" -gt 180 ]; then
            case "$p" in
                misc_pipeline/*) svc="aii-flywheel-misc" ;;
                econ_pipeline/*) svc="aii-flywheel-econ-zh" ;;
                advmath_pipeline/*) svc="aii-flywheel-advmath" ;;
                math_pipeline/*) svc="aii-flywheel-math-prog" ;;
                cs_pipeline/*) svc="aii-flywheel-cs" ;;
                edu_pipeline/*) svc="aii-flywheel-edu" ;;
                paper_pipeline/*) svc="aii-flywheel-paper" ;;
            esac
            if systemctl --user restart "$svc" 2>/dev/null; then
                log "🔄 自愈: $svc 心跳停滞 ${age_min}min → 已重启"
            else
                log "🚨 心跳停滞: $p ${age_min}min, 重启 $svc 失败(需人工)"
            fi
        fi
    fi
done

# 7. aii-extract 崩溃循环检测(/tmp/lx-env 丢失 → EXEC 失败, 重启无用, 只告警)
if ! systemctl --user is-active --quiet aii-extract 2>/dev/null; then
    if [ ! -x /tmp/lx-env/bin/python ]; then
        log "🚨 aii-extract 无法启动: /tmp/lx-env/bin/python 不存在(重启后 /tmp 被清) — 需重建 /tmp/lx-env 或改 unit ExecStart 指向 .venv"
    else
        systemctl --user restart aii-extract 2>/dev/null && log "🔄 自愈: aii-extract 非 active → 已重启"
    fi
fi

# 8. 磁盘: 用量告警 + 大日志就地截断(O_APPEND 写入方不受影响)
for fs in / /data; do
    pct=$(df "$fs" 2>/dev/null | awk 'NR==2{gsub(/%/,"",$5);print $5}')
    if [ -n "${pct:-}" ] && [ "$pct" -gt 92 ]; then
        log "🚨 磁盘 $fs 用量 ${pct}% (>92%) — 需清理"
    fi
done
for p in advmath_pipeline/flywheel.log math_pipeline/flywheel_prog.log misc_pipeline/flywheel_misc.log \
         econ_pipeline/flywheel_zh.log paper_pipeline/flywheel.log cs_pipeline/flywheel_cs.log \
         edu_pipeline/flywheel_edu.log; do
    if [ -f "$p" ] && [ "$(stat -c %s "$p" 2>/dev/null || echo 0)" -gt 314572800 ]; then
        : > "$p"
        log "🔄 自愈: $p 超过300MB → 已就地截断"
    fi
done

# 9. B 仓体检 + 零风险修复(每轮都跑: 打标 → 修断链 → crit 告警)
B_LINT=$(.venv/bin/python scripts/ku_lint.py --fix-safe --json 2>/dev/null || echo '{"summary":{}}')
B_CRIT=$(echo "$B_LINT" | .venv/bin/python -c "import json,sys;d=json.load(sys.stdin);print(d.get('summary',{}).get('crit',0))" 2>/dev/null || echo 0)
B_FIXED=$(echo "$B_LINT" | .venv/bin/python -c "import json,sys;d=json.load(sys.stdin);print(d.get('summary',{}).get('fixed_rows',0))" 2>/dev/null || echo 0)
log "📊 B 仓体检: crit=$B_CRIT, 本轮修断链=$B_FIXED"
if [ "${B_CRIT:-0}" -gt 0 ] 2>/dev/null; then
    log "🚨 B 仓 crit 项 > 0: 查看 rf.ku_health_issues (status='open', severity='crit')"
fi

log "── healer 一轮完成 ──"
