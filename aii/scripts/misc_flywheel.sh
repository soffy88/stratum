#!/usr/bin/env bash
# ★程序化其它飞轮 — 自动循环: 发现书→检MD→反馈Stratum→跑管道→入库/隔离
# ★程序化 = WHAT 部分由【程序】抽取(_extract_skeleton: 定义框/例子/公式/图表标题/表格数据),
#   不是 LLM 抽 WHAT; LLM 只负责【规划知识点】+ 补【WHY/HOW】。这是本飞轮的根本标识。
# (复制自 econ_flywheel.sh，待升级为英文经济学专用；原始 econ_flywheel.sh 不动)
#
# 流程:
#   econ_discover.py 找到未处理的经济书 →
#   econ_batch_run.sh 逐本: R1-R9预检(失败→反馈Stratum) → 管道 → 质量门 → 入库/隔离 →
#   更新 flywheel_state.json → 生成飞轮报告
#
# Optional env vars:
#   ECON_LIMIT=N        每次最多处理N本(默认20; 0=无限)
#   ECON_DRY_RUN=1      仅预检,不跑管道
#   ECON_FORCE=1        已入库的书也重跑
#   ECON_STRATUM_FEEDBACK=1  预检失败时反馈Stratum(默认1=开)
#
# Usage:
#   bash scripts/econ_flywheel.sh               # 正常跑
#   ECON_DRY_RUN=1 ECON_LIMIT=3 bash scripts/econ_flywheel.sh  # 小批干跑
#   # 夜间定时(加到 crontab):
#   # 0 2 * * * cd /home/soffy/projects/AII && bash scripts/econ_flywheel.sh >> econ_pipeline/flywheel.log 2>&1
set -euo pipefail
cd "$(dirname "$0")/.."

PY=.venv/bin/python
# ★英文经济学飞轮: 独立 _en 状态/书单/报告(与原始 econ_flywheel 不冲突)
FLYWHEEL_STATE="misc_pipeline/flywheel_misc_state.json"
FLYWHEEL_BOOK_LIST="misc_pipeline/flywheel_misc_booklist.txt"
FLYWHEEL_REPORT="misc_pipeline/flywheel_misc_report.json"
FLYWHEEL_LOG="misc_pipeline/flywheel_misc.log"
ECON_LIMIT="${ECON_LIMIT:-20}"
STRATUM_FEEDBACK="${ECON_STRATUM_FEEDBACK:-0}"   # 英文书来自本地文件夹, 默认不反馈Stratum

# ★NIM key(免费) + DB + BGE-M3跑CPU(不抢aii-api的GPU)
export NVIDIA_NIM_API_KEY="$($PY -c "import json;print(json.load(open('.pipeline_keys.json')).get('econ',''))" 2>/dev/null)"
# ★模型选型: 同 advmath/math_prog(2026-07-07实测对比) — 默认 meta/llama-3.1-70b-instruct 讲得干,
#   nemotron-super-49b 明显更好, _plan() 规划知识点这步换掉默认档.
export NIM_MODEL="${NIM_MODEL:-nvidia/llama-3.3-nemotron-super-49b-v1.5}"
export AII_SYNTH_CONCURRENCY="${AII_SYNTH_CONCURRENCY:-4}"   # ★并发度=4(测试定论: 4-5低偶发超时, 6+持续过载)
export DATABASE_URL="${DATABASE_URL:-postgresql://aii:aii_safe_pass@localhost:5435/aii_kg}"
export CUDA_VISIBLE_DEVICES=""          # 嵌入走 CPU(GPU 让给 math-prog, 防 OOM)
export HF_HUB_OFFLINE=1                 # ★用本地缓存 BGE-M3, 不连 huggingface(直连超时→卡死)
export TRANSFORMERS_OFFLINE=1
export AII_EMBED_URL="${AII_EMBED_URL:-http://100.68.226.13:8102}"   # ★嵌入走共享 aii-embed 微服务(已迁笔记本GPU, 禁止用本机GPU)
# ★忠实模式(同中文版): 只忠实呈现原书内容, 不过度LLM判断/why-how; section 默认13000
export ECON_FAITHFUL=1
export ECON_QUARANTINE_JSON="misc_pipeline/quarantine.json"
export ECON_BATCH_REPORT="misc_pipeline/batch_report.json"
export ECON_QUAL_DIR="misc_pipeline/qual"
export ECON_CKPT_DIR="misc_pipeline/ckpts"
# ★质量门密度基准: econ_quality_gate.py 默认按经济学教材(~15KU/章)校准, "其它"学科
#   (哲学/通识等)天然密度更低, 套经济学基准会把正常书误判隔离 → 降基准, 非放水
export QGATE_KU_PER_CHAPTER="${QGATE_KU_PER_CHAPTER:-8}"
export QGATE_CHAPTER_FLOOR="${QGATE_CHAPTER_FLOOR:-3}"

mkdir -p misc_pipeline misc_pipeline/qual misc_pipeline/ckpts

# ── 初始化 state ──
if [ ! -f "$FLYWHEEL_STATE" ]; then
    echo '{"processed":{}}' > "$FLYWHEEL_STATE"
fi

echo "════════════════════════════════════════════════════"
echo "★ 其它知识飞轮 $(date '+%Y-%m-%d %H:%M')"
echo "  LIMIT=$ECON_LIMIT  DRY_RUN=${ECON_DRY_RUN:-0}  STRATUM_FEEDBACK=$STRATUM_FEEDBACK"
echo "════════════════════════════════════════════════════"
echo ""

# ── Step 0: 主动拉料 ── 别等 feeder 独立时钟才有新书: D盘同步+本地PDF转换+stratum分类
# 一次做全 (flock 防和其他飞轮/feeder撞车挪同一文件)
mkdir -p .locks
flock -w 120 .locks/classify_md.lock -c "timeout 600 bash scripts/pull_ingest.sh" || true

# ── Step 1: 发现未处理的经济书 ──
echo "[1/4] 发现未处理的书(books/MD/其它, 全学科)..."
LIMIT_ARG=""
[ "$ECON_LIMIT" -gt 0 ] 2>/dev/null && LIMIT_ARG="--limit $ECON_LIMIT"
$PY scripts/misc_discover.py \
    --out "$FLYWHEEL_BOOK_LIST" \
    --state "$FLYWHEEL_STATE" \
    --verbose \
    $LIMIT_ARG

if [ ! -s "$FLYWHEEL_BOOK_LIST" ]; then
    echo "  ✅ 没有新书需要处理(全部已处理或未发现经济书)"
    echo "════════════════════════════════════════════════════"
    echo "飞轮完成: 无新书"
    exit 0
fi

BOOK_COUNT=$(wc -l < "$FLYWHEEL_BOOK_LIST" | tr -d ' ')
echo "  发现 $BOOK_COUNT 本待处理书 → $FLYWHEEL_BOOK_LIST"
echo ""

# ── Step 2: 批量预检+管道 ──
echo "[2/4] 批量预检 + 管道..."
ECON_MD_LIST="$FLYWHEEL_BOOK_LIST" \
ECON_STRATUM_FEEDBACK="$STRATUM_FEEDBACK" \
ECON_DRY_RUN="${ECON_DRY_RUN:-0}" \
ECON_FORCE="${ECON_FORCE:-0}" \
bash scripts/econ_batch_run.sh 2>&1 | tee -a "$FLYWHEEL_LOG"

echo ""

# ── Step 3: 更新 flywheel_state.json ──
echo "[3/4] 更新飞轮状态..."
$PY - << PYEOF
import json, datetime
from pathlib import Path

state_path = Path('$FLYWHEEL_STATE')
state = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {"processed": {}}

batch_report = Path('misc_pipeline/batch_report.json')
if not batch_report.exists():
    print("  批量报告不存在, 跳过状态更新")
    exit(0)

report = json.loads(batch_report.read_text(encoding='utf-8'))
quarantine_file = Path('misc_pipeline/quarantine.json')
quarantine = json.loads(quarantine_file.read_text(encoding='utf-8')) if quarantine_file.exists() else {"quarantined": []}
ts = datetime.datetime.now(datetime.timezone.utc).isoformat()

# 从 quarantine 里读失败原因, 更新 state
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

# ── Step 4: 飞轮报告 ──
echo "[4/4] 生成飞轮报告..."
$PY - << PYEOF
import json, datetime
from pathlib import Path

report = {
    "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "flywheel_run": True,
    "dry_run": "${ECON_DRY_RUN:-0}" == "1",
    "limit": $ECON_LIMIT,
    "stratum_feedback_enabled": "$STRATUM_FEEDBACK" == "1",
}

# 合并 batch_report
batch = Path('misc_pipeline/batch_report.json')
if batch.exists():
    report["batch_summary"] = json.loads(batch.read_text(encoding='utf-8')).get("summary", {})

# Stratum 反馈统计
feedback_queue = Path('/home/soffy/shared/aii-to-stratum/md_rework_queue.json')
if feedback_queue.exists():
    q = json.loads(feedback_queue.read_text(encoding='utf-8'))
    pending = [x for x in q.get('items', []) if x.get('status') == 'pending']
    report["stratum_feedback"] = {
        "queue_file": str(feedback_queue),
        "total_items": len(q.get('items', [])),
        "pending": len(pending),
    }

# 飞轮状态统计
state_file = Path('econ_pipeline/flywheel_state.json')
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
if "stratum_feedback" in report:
    sf = report["stratum_feedback"]
    print(f"  Stratum 反馈队列: {sf['pending']} pending / {sf['total_items']} 总计")
    print(f"    文件: {sf['queue_file']}")
PYEOF

echo ""
echo "════════════════════════════════════════════════════"
echo "★ 飞轮完成 $(date '+%Y-%m-%d %H:%M')"
echo "  书单 → $FLYWHEEL_BOOK_LIST"
echo "  状态 → $FLYWHEEL_STATE"
echo "  报告 → $FLYWHEEL_REPORT"
if [ "$STRATUM_FEEDBACK" = "1" ]; then
    echo "  Stratum反馈 → /home/soffy/shared/aii-to-stratum/md_rework_queue.json"
fi
echo "════════════════════════════════════════════════════"
