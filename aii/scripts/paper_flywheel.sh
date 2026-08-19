#!/usr/bin/env bash
# ★论文飞轮 — 一轮: 拉料 → 发现未处理论文 → 逐篇跑轻量BU管道(paper_pipeline.sh) → 登记.
# 论文管道比教材管道轻得多(无逐章LLM讲透), 不需要 advmath 那种多worker并行,
# 顺序处理即可; PAPER_LIMIT 控制单轮上限, 防止一轮占用过多NIM配额/耗时过长.
#
# Optional env vars:
#   PAPER_LIMIT=20    每轮最多处理N篇(默认20; 0=无限)
#
# Usage: bash scripts/paper_flywheel.sh
set -uo pipefail
cd "$(dirname "$0")/.."

PY=.venv/bin/python
FLYWHEEL_STATE="paper_pipeline/flywheel_state.json"
FLYWHEEL_BOOK_LIST="paper_pipeline/flywheel_booklist.txt"
PAPER_LIMIT="${PAPER_LIMIT:-120}"         # 每轮上限(120: 摊薄每轮 Step0 pull_ingest 固定开销; 并发 6 下 120 篇≈7min/轮)
PAPER_WORKERS="${PAPER_WORKERS:-6}"   # ★2026-08-16 提速: 并发 worker 数(opencode-go 主 provider 无 rpm 限制; NIM 仅 fallback)

# ★2026-08-16 修复: 论文飞轮曾是唯一不带 NIM/opencode env 的飞轮 → generate_bu.py 落到
#   已失效的 DEEPSEEK_API_KEY(aii/aii/.env, 07-19 起 401/402) → 每篇论文都 "LLM 主 provider
#   失败且无 fallback" → 被永久标记 precheck_fail。现对齐 econ/cs 飞轮: opencode-go 主 +
#   NIM 兜底 + 本地服务 NO_PROXY(防 embed/postgres 502)。
export NVIDIA_NIM_API_KEY="$($PY -c "import json;print(json.load(open('.pipeline_keys.json')).get('econ_zh',''))" 2>/dev/null)"
export NIM_KEY_POOL="$($PY -c "import json;d=json.load(open('.pipeline_keys.json'));print(','.join(x for x in (d.get('econ_zh'),d.get('math_en'),d.get('advmath_verify')) if x))" 2>/dev/null)"
export NIM_MODEL="${NIM_MODEL:-nvidia/llama-3.3-nemotron-super-49b-v1.5}"
export OPENCODE_API_KEY=""  # 留空 → 读 ~/.pi/agent/opencode-keys.txt
export OPENCODE_MODEL="${OPENCODE_MODEL:-deepseek-v4-flash}"
export DATABASE_URL="${DATABASE_URL:-postgresql://aii:aii_safe_pass@localhost:5435/aii_kg}"
export NO_PROXY="localhost,127.0.0.1,::1,192.168.0.0/24,100.64.0.0/10,.local"
export no_proxy="${NO_PROXY}"
# ★opencode-go 直连偶发 PoolTimeout(实测 4-12s 抖动, 重试 5 次后 NIM fallback 才能救)
#   → 走本机 7890 代理(实测稳定 2-4s)。NO_PROXY 已排除本地/内网服务。代理挂了自动回落直连。
export http_proxy="${HTTP_PROXY:-http://127.0.0.1:7890}"
export https_proxy="${HTTPS_PROXY:-http://127.0.0.1:7890}"
export HTTP_PROXY="${http_proxy}"
export HTTPS_PROXY="${https_proxy}"
export CUDA_VISIBLE_DEVICES=""          # 嵌入走共享 aii-embed, 不占本机 GPU
# HF offline 由 aii/aii/.env 提供(HF_HUB_OFFLINE=1), 此处不重复设防覆盖

export AII_EMBED_URL="${AII_EMBED_URL:-http://100.119.113.90:8102}"

mkdir -p paper_pipeline

if [ ! -f "$FLYWHEEL_STATE" ]; then
    echo '{"processed":{}}' > "$FLYWHEEL_STATE"
fi

echo "════════════════════════════════════════════════════"
echo "★ 论文知识飞轮 $(date '+%Y-%m-%d %H:%M')"
echo "  LIMIT=$PAPER_LIMIT"
echo "════════════════════════════════════════════════════"
echo ""

# ── Step 0: 主动拉料(D盘同步+本地PDF转换+stratum分类, 含classify_md.py新分出的"论文"桶)──
mkdir -p .locks
flock -w 120 .locks/classify_md.lock -c "timeout 600 bash scripts/pull_ingest.sh" || true

# ── Step 1: 发现未处理论文 ──
echo "[1/2] 发现未处理的论文(books/MD/论文)..."
LIMIT_ARG=""
[ "$PAPER_LIMIT" -gt 0 ] 2>/dev/null && LIMIT_ARG="--limit $PAPER_LIMIT"
$PY scripts/paper_discover.py \
    --out "$FLYWHEEL_BOOK_LIST" \
    --state "$FLYWHEEL_STATE" \
    --verbose \
    $LIMIT_ARG

if [ ! -s "$FLYWHEEL_BOOK_LIST" ]; then
    echo "  ✅ 没有新论文需要处理"
    echo "════════════════════════════════════════════════════"
    echo "飞轮完成: 无新论文"
    exit 0
fi

PAPER_COUNT=$(wc -l < "$FLYWHEEL_BOOK_LIST" | tr -d ' ')
echo "  发现 $PAPER_COUNT 篇待处理论文 → $FLYWHEEL_BOOK_LIST"
echo ""

# ── Step 2: 并发跑轻量管道(★2026-08-16 提速: 原串行每篇~6-7min, 4387篇≈19天;
#    改 xargs -P 多 worker, 每篇产物按 SUBSTRATE 隔离可安全并行; 结果汇总后统一写 state) ──
echo "[2/2] 逐篇跑论文轻量管道(并发 $PAPER_WORKERS)..."
RESULTS="paper_pipeline/round_results.txt"
: > "$RESULTS"
PAPER_RESULTS="$RESULTS" timeout 3600 xargs -d '\n' -P "$PAPER_WORKERS" -n1 bash scripts/paper_worker.sh < "$FLYWHEEL_BOOK_LIST" || echo "  ⚠ 并发轮超时/中断(3600s) — 已完成结果仍会汇总"

ok=0; fail=0
while read -r status substrate; do  # worker 写 "OK|FAIL <substrate>"(空格分隔)
    [ -z "$substrate" ] && continue
    if [ "$status" = "OK" ]; then
        ok=$((ok + 1))
        $PY - "$FLYWHEEL_STATE" "$substrate" << 'PYEOF'
import json, sys, datetime
state_path, sid = sys.argv[1], sys.argv[2]
state = json.loads(open(state_path, encoding="utf-8").read())
state["processed"][sid] = {"status": "ingested", "ts": datetime.datetime.now(datetime.timezone.utc).isoformat()}
open(state_path, "w", encoding="utf-8").write(json.dumps(state, ensure_ascii=False, indent=2))
PYEOF
    else
        fail=$((fail + 1))
        echo "    ⚠ 失败, 跳过(下轮不重试——见flywheel_state标记precheck_fail)"
        $PY - "$FLYWHEEL_STATE" "$substrate" << 'PYEOF'
import json, sys, datetime
state_path, sid = sys.argv[1], sys.argv[2]
state = json.loads(open(state_path, encoding="utf-8").read())
state["processed"][sid] = {"status": "precheck_fail", "ts": datetime.datetime.now(datetime.timezone.utc).isoformat()}
open(state_path, "w", encoding="utf-8").write(json.dumps(state, ensure_ascii=False, indent=2))
PYEOF
    fi
done < "$RESULTS"

echo ""
echo "════════════════════════════════════════════════════"
echo "★ 论文飞轮完成 $(date '+%Y-%m-%d %H:%M') — 成功 $ok / 失败 $fail"
echo "════════════════════════════════════════════════════"

# ★2026-08-10 论文精髓 → Agent Skill 自动导出(book-to-skill + cangjie V3)
#   增量幂等: 只导出新入库的 worth_as_skill 论文到 ~/.agents/skills/
echo "[skill] 导出本轮新论文技能..."
$PY scripts/paper_skill_export.py 2>&1 | tail -2
