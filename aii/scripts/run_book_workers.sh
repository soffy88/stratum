#!/usr/bin/env bash
# ★多 worker 并行跑书单 — 供各飞轮 source 复用(2026-09-27)。
#
# 背景: econ_batch_run.sh 的书循环是串行 `while read`(见该文件 ~97 行), 一本一本处理。
# 单本逐章 LLM 合成 + 质检实测 ~30 分钟, 于是单飞轮上限约 2 本/小时, 而队列常有几��本,
# 根本消化不完。这里把书单轮转拆成 N 份, 每份一个独立 NIM key, 后台并行跑。
#
# 模式来自 advmath_flywheel.sh 里已验证的实现; 抽成共享函数是为了避免 4 个飞轮各抄一份
# 之后字段名/合并逻辑漂移(合并 summary 时踩过一次 skipped vs skipped(已入库) 的坑)。
#
# 用法:
#   bash scripts/run_book_workers.sh <pipeline_dir> <book_list> <flywheel_log> <key1> [key2 ...]
#
#   pipeline_dir  形如 cs_pipeline / econ_pipeline, worker 产物写在它下面
#   book_list     书单文件(md_path|substrate_id|title)
#   flywheel_log  各 worker 的输出汇总追加到这里
#   key1..keyN    .pipeline_keys.json 里的槽位名; 自动跳过空槽位
#
# 环境变量:
#   <PREFIX>_WORKERS=N          限制并发数(≤ 可用 key 数); 未设则用全部可用 key
#   ECON_DRY_RUN / ECON_FORCE / STRATUM_FEEDBACK / ECON_PIPELINE_TIMEOUT  透传给 worker
#
# 退出码: 0 = 至少一个 worker 跑完; 3 = 无可用 key(调用方应退回单进程)
set -uo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python

PIPE_DIR="${1:?用法: run_book_workers.sh <pipeline_dir> <book_list> <log> <key...>}"
BOOK_LIST="${2:?}"
FLYWHEEL_LOG="${3:?}"
shift 3
REQUESTED_KEYS=("$@")

# 过滤空槽位(某个 key 可能被腾空)
AVAILABLE=()
for _k in "${REQUESTED_KEYS[@]}"; do
    if [ -n "$($PY -c "import json,sys;print(json.load(open('.pipeline_keys.json')).get(sys.argv[1],''))" "$_k" 2>/dev/null)" ]; then
        AVAILABLE+=("$_k")
    fi
done
NW=${#AVAILABLE[@]}

# 并发上限: 取 <PREFIX>_WORKERS(用 PIPE_DIR 的 basename 去掉 _pipeline 推出的前缀)
PREFIX="$(basename "$PIPE_DIR" _pipeline)"
PREFIX="${PREFIX^^}"
MAXW="${PREFIX}_WORKERS:-"
if [[ ! "$MAXW" =~ ^[0-9]+$ ]]; then
    MAXW="$NW"
fi
if (( MAXW > 0 && MAXW < NW )); then
    AVAILABLE=("${AVAILABLE[@]:0:MAXW}")
    NW=$MAXW
fi

if (( NW == 0 )); then
    echo "  ⚠ 没有可用 worker key (请求: ${REQUESTED_KEYS[*]})"
    exit 3
fi

# ★2026-10-01 必须在上面 rm 之前抓: 持久的历史隔离台账。主 quarantine.json
#   跨轮累积(worker 级的 quarantine_worker*.json 每轮被删), 重试判定要读它 ——
#   读刚清空的 worker 文件永远查不到上一轮的隔离记录。
QUARANTINE_HISTORY="${ECON_QUARANTINE_HISTORY:-$PIPE_DIR/quarantine.json}"

rm -f "$PIPE_DIR"/booklist_worker*.txt "$PIPE_DIR"/quarantine_worker*.json \
      "$PIPE_DIR"/batch_report_worker*.json "$PIPE_DIR"/worker*.log
for i in "${!AVAILABLE[@]}"; do : > "$PIPE_DIR/booklist_worker${i}.txt"; done

_i=0
while IFS= read -r line; do
    [ -z "$line" ] && continue
    echo "$line" >> "$PIPE_DIR/booklist_worker$((_i % NW)).txt"
    _i=$((_i + 1))
done < "$BOOK_LIST"

PIDS=()
for i in "${!AVAILABLE[@]}"; do
    WL="$PIPE_DIR/booklist_worker${i}.txt"
    [ -s "$WL" ] || continue
    KEY_ID="${AVAILABLE[$i]}"
    KEY="$($PY -c "import json,sys;print(json.load(open('.pipeline_keys.json')).get(sys.argv[1],''))" "$KEY_ID" 2>/dev/null)"
    (
        ECON_MD_LIST="$WL" \
        NVIDIA_NIM_API_KEY="$KEY" \
        ECON_QUARANTINE_JSON="$PIPE_DIR/quarantine_worker${i}.json" \
        ECON_QUARANTINE_HISTORY="$QUARANTINE_HISTORY" \
        ECON_BATCH_REPORT="$PIPE_DIR/batch_report_worker${i}.json" \
        ECON_STRATUM_FEEDBACK="${STRATUM_FEEDBACK:-0}" \
        ECON_DRY_RUN="${ECON_DRY_RUN:-0}" \
        ECON_FORCE="${ECON_FORCE:-0}" \
        bash scripts/econ_batch_run.sh > "$PIPE_DIR/worker${i}.log" 2>&1
    ) &
    PIDS+=($!)
    echo "  worker$i(key=$KEY_ID) 启动, 处理 $(wc -l < "$WL" | tr -d ' ') 本, pid=$!"
done
for pid in "${PIDS[@]}"; do wait "$pid" || true; done
cat "$PIPE_DIR"/worker*.log >> "$FLYWHEEL_LOG" 2>/dev/null || true

# 合并各 worker 的 quarantine / batch_report 到主文件(供调用方后续 Step 3/4 读)
PIPE_DIR="$PIPE_DIR" $PY - << 'PYEOF'
import glob
import json
import os
from datetime import datetime
from pathlib import Path

pipe_dir = Path(os.environ["PIPE_DIR"])

merged_q = {"quarantined": []}
for f in sorted(glob.glob(str(pipe_dir / "quarantine_worker*.json"))):
    try:
        d = json.loads(Path(f).read_text(encoding="utf-8"))
    except Exception:
        continue
    merged_q["quarantined"].extend(d.get("quarantined", []))
(pipe_dir / "quarantine.json").write_text(
    json.dumps(merged_q, ensure_ascii=False, indent=2), encoding="utf-8"
)

# 遍历实际 key 求和, 不硬编码字段名 —— 各 worker 与主报告的 summary 结构可能演进
summary = {}
reports = sorted(glob.glob(str(pipe_dir / "batch_report_worker*.json")))
for f in reports:
    try:
        s = json.loads(Path(f).read_text(encoding="utf-8")).get("summary", {})
    except Exception:
        continue
    for k, v in s.items():
        summary[k] = summary.get(k, 0) + v
(pipe_dir / "batch_report.json").write_text(
    json.dumps(
        {
            "generated_at": datetime.now().isoformat(),
            "dry_run": False,
            "summary": summary,
            "quarantine_file": str(pipe_dir / "quarantine.json"),
            "workers": len(reports),
        },
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)
print(f"  合并 {len(reports)} 个 worker 报告: {summary}")
PYEOF
