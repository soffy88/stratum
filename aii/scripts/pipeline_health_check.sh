#!/usr/bin/env bash
# ★全链路体检 — 从源文件到KU的每一环都过一遍, 一条命令看清"哪里在断料/哪里卡死".
# 覆盖: 5个systemd常驻服务 / aii-embed真调用(已迁笔记本GPU) / 关键docker容器 / D盘挂载 /
#       各阶段积压深度(PDF待转/MD待分类/各飞轮消费队列) / 隔离积压 / 有没有卡住的拉料进程.
#
# Usage: bash scripts/pipeline_health_check.sh
# Exit: 0=全绿, 1=有🚨项(自动化场景可用来判断要不要报警)
set -uo pipefail
cd "$(dirname "$0")/.."

BAD=0
ok()   { echo "  ✅ $1"; }
warn() { echo "  ⚠️  $1"; }
bad()  { echo "  🚨 $1"; BAD=1; }

echo "════════════════════════════════════════════════════"
echo "★ AII 全链路体检 $(date '+%Y-%m-%d %H:%M:%S')"
echo "════════════════════════════════════════════════════"

echo
echo "[1/6] 常驻服务(systemd --user)"
for svc in aii-backend aii-feeder aii-flywheel-econ-zh aii-flywheel-math-prog aii-flywheel-misc; do
    if systemctl --user is-active --quiet "$svc"; then
        ok "$svc: active"
    else
        bad "$svc: $(systemctl --user is-active "$svc" 2>&1) — 需要 systemctl --user start $svc"
    fi
done

echo
echo "[2/6] aii-embed 真调用(★已迁笔记本GTX1050Ti, 禁止用本机GPU; 走tailscale, 不只看进程活着, 实际打一次embed)"
AII_EMBED_URL_CHECK="${AII_EMBED_URL:-http://100.68.226.13:8102}"
if curl -s -m 10 -o /dev/null -w "" "$AII_EMBED_URL_CHECK/health" 2>/dev/null; then
    EMBED_OUT=$(curl -s -m 30 -X POST "$AII_EMBED_URL_CHECK/embed" -H "Content-Type: application/json" -d '{"texts":["体检"]}' 2>&1)
    if echo "$EMBED_OUT" | grep -q '"embeddings"'; then
        ok "aii-embed /embed 调用成功"
    else
        bad "aii-embed /health通但/embed调用失败: ${EMBED_OUT:0:100}"
    fi
else
    bad "aii-embed($AII_EMBED_URL_CHECK) 无响应 — 三个飞轮的入库都会失败(err=N ok=0), 检查笔记本WSL的aii-embed.service"
fi

echo
echo "[3/6] 关键docker容器"
for c in aii-postgres ocr-vllm; do
    st=$(docker inspect -f '{{.State.Status}}' "$c" 2>/dev/null || echo "不存在")
    [ "$st" = "running" ] && ok "$c: running" || bad "$c: $st"
done

echo
echo "[4/6] D盘/网盘挂载"
if mountpoint -q /mnt/d; then
    ok "/mnt/d 已挂载"
else
    bad "/mnt/d 未挂载 — D盘书源同步这条进料渠道会静默失效(pull_ingest.sh对missing目录直接跳过,不报错)"
fi

echo
echo "[5/6] 各阶段积压深度(仅供参考, 不是越少越好——只看有没有异常暴涨/长期为0说明断料)"
echo "  待转PDF: 数学=$(find /home/soffy/books/数学 -maxdepth 1 -iname '*.pdf' 2>/dev/null | wc -l)  Economic=$(find /home/soffy/books/Economic -maxdepth 1 -iname '*.pdf' 2>/dev/null | wc -l)"
echo "  stratum已抓待分类MD: $(find /home/soffy/shared/stratum-to-aii -maxdepth 1 -iname '*.md' 2>/dev/null | wc -l)"
for d in 经济学 中文数学 英文数学 其它; do
    echo "  books/MD/$d 待飞轮消费: $(find "/home/soffy/books/MD/$d" -maxdepth 1 -iname '*.md' 2>/dev/null | wc -l)"
done
for q in econ_pipeline/quarantine.json misc_pipeline/quarantine.json math_pipeline/quarantine.json; do
    [ -f "$q" ] && n=$(.venv/bin/python -c "import json;print(len(json.load(open('$q'))['quarantined']))" 2>/dev/null) && echo "  隔离积压 $q: ${n:-?}"
done

echo
echo "[6/6] 有没有卡住的拉料进程(正常一轮<3分钟, 超过15分钟=可疑, 结合今天真实发生过9小时卡死的教训)"
STUCK=0
while read -r pid etimes cmd; do
    [ -z "$pid" ] && continue
    if [ "$etimes" -gt 900 ]; then
        bad "疑似卡住: pid=$pid 已跑${etimes}s(>15min) — $cmd"
        STUCK=1
    fi
done < <(ps -eo pid,etimes,cmd | grep -E "pull_ingest\.sh|math_convert\.py|econ_convert\.py|classify_md\.py" | grep -v grep)
[ "$STUCK" -eq 0 ] && ok "没有发现卡住超15分钟的拉料进程"

echo
echo "════════════════════════════════════════════════════"
if [ "$BAD" -eq 0 ]; then
    echo "★ 体检结论: 全绿 ✅"
else
    echo "★ 体检结论: 发现 🚨 项, 见上"
fi
echo "════════════════════════════════════════════════════"
exit $BAD
