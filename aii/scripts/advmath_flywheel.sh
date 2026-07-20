#!/usr/bin/env bash
# ★高级数学经济专用飞轮 — 自动循环: 转换→发现→跑管道(高中生讲透版)→入库/隔离
# 克隆自 misc_flywheel.sh, 核心区别:
#   - 书源是用户自己维护的单一文件夹 /mnt/d/books/高级数学经济专用/(源PDF+转换出的MD
#     都在这一个文件夹, 方便用户自己抽查转换质量), 不是 books/MD/{学科} 那套多文件夹.
#   - Step 0 用 advmath_convert.py(markitdown) 代替 pull_ingest.sh(D盘同步+math/econ_convert
#     +classify_md, 那一套是给 books/{数学,Economic} 用的, 跟这个专用文件夹无关).
#   - 管道用 advmath_pipeline.sh(真LLM"讲解到高中生能懂但不降深度"版), 见
#     chapter_synthesize_advmath.py; 不是econ_zh/misc共用的0LLM程序抠版.
#   - 独立NIM key(math_en, 闲置未用的旧key——旧math_flywheel_en.sh已废弃, 见pipelines.py
#     注释), 避免和econ_zh(econ_zh key)/misc(econ key)共享限流.
#
# Optional env vars:
#   ADVMATH_LIMIT=N        每次最多处理N本(默认10; 0=无限——这批书讲透版比0LLM版慢得多,
#                           默认给个更小的批次, 避免一轮陷进单本大书跑几十分钟)
#   ADVMATH_DRY_RUN=1      仅预检,不跑管道
#   ADVMATH_FORCE=1        已入库的书也重跑
set -euo pipefail
cd "$(dirname "$0")/.."

PY=.venv/bin/python
FLYWHEEL_STATE="advmath_pipeline/flywheel_state.json"
FLYWHEEL_BOOK_LIST="advmath_pipeline/flywheel_booklist.txt"
FLYWHEEL_REPORT="advmath_pipeline/flywheel_report.json"
FLYWHEEL_LOG="advmath_pipeline/flywheel.log"
ADVMATH_LIMIT="${ADVMATH_LIMIT:-10}"

# ★NIM key(math_en, 闲置——旧math_flywheel_en.sh已废弃, 见pipelines.py CHANNELS注释)
export NVIDIA_NIM_API_KEY="$($PY -c "import json;print(json.load(open('.pipeline_keys.json')).get('math_en',''))" 2>/dev/null)"
# ★模型选型(2026-07-07实测对比, 见记忆/对话记录): 默认 meta/llama-3.1-70b-instruct 讲透
# 内容干; nvidia/llama-3.3-nemotron-super-49b-v1.5 明显更好(讲解更充分, 公式/引用一个
# 不少)——只对本频道生效(NIM_MODEL是per-process env, 不影响econ_zh/misc/math_prog各自
# 进程的默认模型选择)。
export NIM_MODEL="${NIM_MODEL:-nvidia/llama-3.3-nemotron-super-49b-v1.5}"
export AII_SYNTH_CONCURRENCY="${AII_SYNTH_CONCURRENCY:-4}"
export DATABASE_URL="${DATABASE_URL:-postgresql://aii:aii_safe_pass@localhost:5435/aii_kg}"
export CUDA_VISIBLE_DEVICES=""
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export AII_EMBED_URL="${AII_EMBED_URL:-http://100.68.226.13:8102}"   # ★嵌入走共享 aii-embed 微服务(已迁笔记本GPU, 禁止用本机GPU)
export ECON_QUARANTINE_JSON="advmath_pipeline/quarantine.json"
export ECON_BATCH_REPORT="advmath_pipeline/batch_report.json"
export ECON_QUAL_DIR="advmath_pipeline/qual"
export ECON_CKPT_DIR="advmath_pipeline/ckpts"
export ECON_PIPELINE_SCRIPT="scripts/advmath_pipeline.sh"
export ECON_RUN_LOG_DIR="advmath_pipeline"
export ECON_REGISTER_SUBJECT="高级数学经济"

mkdir -p advmath_pipeline advmath_pipeline/qual advmath_pipeline/ckpts

if [ ! -f "$FLYWHEEL_STATE" ]; then
    echo '{"processed":{}}' > "$FLYWHEEL_STATE"
fi

echo "════════════════════════════════════════════════════"
echo "★ 高级数学经济知识飞轮 $(date '+%Y-%m-%d %H:%M')"
echo "  LIMIT=$ADVMATH_LIMIT  DRY_RUN=${ADVMATH_DRY_RUN:-0}"
echo "════════════════════════════════════════════════════"
echo ""

# ── Step 0: 转换(不含OCR, 快路径; 需OCR的书交给 ocr_daemon.sh 慢循环) ──
echo "[0/4] 转换可转的源文件(markitdown, 不含OCR)..."
$PY scripts/advmath_convert.py --do 2>&1 | grep -vE "^MuPDF error"

echo ""
echo "[1/4] 发现未处理的书(/mnt/d/books/高级数学经济专用/)..."
LIMIT_ARG=""
[ "$ADVMATH_LIMIT" -gt 0 ] 2>/dev/null && LIMIT_ARG="--limit $ADVMATH_LIMIT"
$PY scripts/advmath_discover.py \
    --out "$FLYWHEEL_BOOK_LIST" \
    --state "$FLYWHEEL_STATE" \
    --verbose \
    $LIMIT_ARG

if [ ! -s "$FLYWHEEL_BOOK_LIST" ]; then
    echo "  ✅ 没有新书需要处理(全部已处理或未发现候选书)"
    echo "════════════════════════════════════════════════════"
    echo "飞轮完成: 无新书"
    exit 0
fi

BOOK_COUNT=$(wc -l < "$FLYWHEEL_BOOK_LIST" | tr -d ' ')
echo "  发现 $BOOK_COUNT 本待处理书 → $FLYWHEEL_BOOK_LIST"
echo ""

echo "[2/4] 批量预检 + 管道(讲透+完整性校验+概念/KC/BU/质量门) — 书级并行(3个worker各自独立NIM key)"
# ★2026-07-07: 3个key(math_en/advmath_2/advmath_3)round-robin分给并发跑的书, 每个worker
# 一份独立的书单/quarantine/batch_report(避免并发写同一个json互相覆盖——CKPT_DIR/QUAL_DIR
# /RUN_LOG_DIR按substrate命名天然不会撞, 可以共用), 跑完合并。econ_batch_run.sh本身不改
# (econ_zh/misc还在单进程顺序用它), 只是这里并行发起多份.
WORKER_KEYS=(math_en advmath_2 advmath_3)
NW=${#WORKER_KEYS[@]}
rm -f advmath_pipeline/booklist_worker*.txt advmath_pipeline/quarantine_worker*.json advmath_pipeline/batch_report_worker*.json
for i in "${!WORKER_KEYS[@]}"; do : > "advmath_pipeline/booklist_worker${i}.txt"; done
i=0
while IFS= read -r line; do
    [ -z "$line" ] && continue
    echo "$line" >> "advmath_pipeline/booklist_worker$((i % NW)).txt"
    i=$((i + 1))
done < "$FLYWHEEL_BOOK_LIST"

PIDS=()
for i in "${!WORKER_KEYS[@]}"; do
    WORKER_LIST="advmath_pipeline/booklist_worker${i}.txt"
    [ -s "$WORKER_LIST" ] || continue
    KEY_ID="${WORKER_KEYS[$i]}"
    WORKER_KEY="$($PY -c "import json;print(json.load(open('.pipeline_keys.json')).get('$KEY_ID',''))" 2>/dev/null)"
    (
        ECON_MD_LIST="$WORKER_LIST" \
        NVIDIA_NIM_API_KEY="$WORKER_KEY" \
        ECON_QUARANTINE_JSON="advmath_pipeline/quarantine_worker${i}.json" \
        ECON_BATCH_REPORT="advmath_pipeline/batch_report_worker${i}.json" \
        ECON_STRATUM_FEEDBACK=0 \
        ECON_DRY_RUN="${ADVMATH_DRY_RUN:-0}" \
        ECON_FORCE="${ADVMATH_FORCE:-0}" \
        bash scripts/econ_batch_run.sh > "advmath_pipeline/worker${i}.log" 2>&1
    ) &
    PIDS+=($!)
    echo "  worker$i(key=$KEY_ID) 启动, 处理 $(wc -l < "$WORKER_LIST" | tr -d ' ') 本, pid=$!"
done
for pid in "${PIDS[@]}"; do wait "$pid" || true; done
cat advmath_pipeline/worker*.log >> "$FLYWHEEL_LOG" 2>/dev/null || true

# ★合并各worker的quarantine/batch_report到主文件(供下面Step 3/4读)
$PY - << 'PYEOF'
import json, glob
from pathlib import Path

merged_q = {"quarantined": []}
for f in sorted(glob.glob("advmath_pipeline/quarantine_worker*.json")):
    try:
        d = json.loads(Path(f).read_text(encoding="utf-8"))
    except Exception:
        continue
    merged_q["quarantined"].extend(d.get("quarantined", []))
Path("advmath_pipeline/quarantine.json").write_text(
    json.dumps(merged_q, ensure_ascii=False, indent=2), encoding="utf-8"
)

summary = {"total": 0, "skipped(已入库)": 0, "precheck_fail": 0, "pipeline_fail": 0, "alarm_quarantined": 0, "pass_registered": 0}
for f in sorted(glob.glob("advmath_pipeline/batch_report_worker*.json")):
    try:
        d = json.loads(Path(f).read_text(encoding="utf-8"))
    except Exception:
        continue
    for k, v in d.get("summary", {}).items():
        summary[k] = summary.get(k, 0) + v
Path("advmath_pipeline/batch_report.json").write_text(
    json.dumps({"summary": summary}, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(f"  合并完成: {summary}")
PYEOF

echo ""
echo "[3/4] 更新飞轮状态..."
$PY - << PYEOF
import json, datetime
from pathlib import Path

state_path = Path('$FLYWHEEL_STATE')
state = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {"processed": {}}

batch_report = Path('advmath_pipeline/batch_report.json')
if not batch_report.exists():
    print("  批量报告不存在, 跳过状态更新")
    exit(0)

quarantine_file = Path('advmath_pipeline/quarantine.json')
quarantine = json.loads(quarantine_file.read_text(encoding='utf-8')) if quarantine_file.exists() else {"quarantined": []}
ts = datetime.datetime.now(datetime.timezone.utc).isoformat()

for item in quarantine.get('quarantined', []):
    sid = item.get('substrate_id', '')
    reason_type = item.get('reason_type', '')
    if sid:
        state['processed'][sid] = {
            'status': 'precheck_fail' if reason_type == 'precheck' else 'quarantine',
            'reason': item.get('reason_detail', '')[:200],
            'ts': item.get('ts', ts),
        }

state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
print(f"  飞轮状态已更新: {len(state['processed'])} 条记录")
PYEOF

echo ""
echo "[4/4] 生成飞轮报告..."
$PY - << PYEOF
import json, datetime
from pathlib import Path

report = {
    "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "flywheel_run": True,
    "dry_run": "${ADVMATH_DRY_RUN:-0}" == "1",
    "limit": $ADVMATH_LIMIT,
}
batch = Path('advmath_pipeline/batch_report.json')
if batch.exists():
    report["batch_summary"] = json.loads(batch.read_text(encoding='utf-8')).get("summary", {})

state_file = Path('$FLYWHEEL_STATE')
if state_file.exists():
    s = json.loads(state_file.read_text(encoding='utf-8'))
    by_status = {}
    for v in s.get('processed', {}).values():
        st = v.get('status', '?')
        by_status[st] = by_status.get(st, 0) + 1
    report["flywheel_state"] = by_status

Path('$FLYWHEEL_REPORT').write_text(
    json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

print(f"  飞轮报告 → {Path('$FLYWHEEL_REPORT')}")
print()
print("  批量摘要:")
for k, v in report.get("batch_summary", {}).items():
    print(f"    {k}: {v}")
PYEOF

echo ""
echo "════════════════════════════════════════════════════"
echo "★ 飞轮完成 $(date '+%Y-%m-%d %H:%M')"
echo "  书单 → $FLYWHEEL_BOOK_LIST"
echo "  状态 → $FLYWHEEL_STATE"
echo "  报告 → $FLYWHEEL_REPORT"
echo "════════════════════════════════════════════════════"
