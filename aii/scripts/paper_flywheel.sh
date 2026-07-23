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
PAPER_LIMIT="${PAPER_LIMIT:-20}"

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

# ── Step 2: 逐篇跑轻量管道 ──
echo "[2/2] 逐篇跑论文轻量管道..."
ok=0; fail=0
while IFS='|' read -r md_path substrate title; do
    [ -z "$substrate" ] && continue
    echo "  → $substrate ($title)"
    if SUBSTRATE="$substrate" AII_MD_FILE="$md_path" PAPER_TITLE="$title" \
        bash scripts/paper_pipeline.sh 2>&1 | sed 's/^/    /'; then
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
done < "$FLYWHEEL_BOOK_LIST"

echo ""
echo "════════════════════════════════════════════════════"
echo "★ 论文飞轮完成 $(date '+%Y-%m-%d %H:%M') — 成功 $ok / 失败 $fail"
echo "════════════════════════════════════════════════════"
