#!/usr/bin/env bash
# ★经济学批量管道 — 夜里能跑, 一批书全自动(入库+拦截)
#
# 流程(每本书):
#   md先过R1-R9(不合格不进管道) → econ_pipeline.sh →
#   质量门通过 → econ_register.py(自动入正式库) → batch_report
#   质量门报警 → 隔离到 quarantine.json, 记录原因 → batch_report
#
# ★不合格的md 和 质量门报警的书, 都只隔离、不删除数据, 等人工review.
#
# Required:
#   ECON_MD_LIST  文件路径, 每行一条: "<md绝对路径>|<substrate_id>|<title>"
#                 OR 每行只写 md 路径(自动从 sidecar.json 读 id/title)
# Optional:
#   ECON_QUAL_DIR       质量报告目录(默认 econ_pipeline/qual/)
#   ECON_CKPT_DIR       checkpoint目录(默认 econ_pipeline/ckpts/)
#   ECON_DRY_RUN=1      只做预检(R1-R9+是否已入库), 不跑管道
#   ECON_FORCE=1        已入库的也重跑(默认跳过)
#
# Usage:
#   ECON_MD_LIST=econ_pipeline/test_books.txt bash scripts/econ_batch_run.sh
#   ECON_MD_LIST=... ECON_DRY_RUN=1 bash scripts/econ_batch_run.sh  # 只预检
set -euo pipefail
cd "$(dirname "$0")/.."

: "${RCLONE_PROXY=http://127.0.0.1:7890}"
if [ -n "${RCLONE_PROXY}" ] && [ -z "${HTTPS_PROXY:-}" ]; then
  export HTTPS_PROXY="${RCLONE_PROXY}" HTTP_PROXY="${RCLONE_PROXY}"
  # ★本地/tailscale 服务(embed 100.68.226.13:8102 / postgres)必须直连:
  #   缺 NO_PROXY 会让 embed 请求也走代理 → sing-box 拨号回环/内网失败
  #   → "aii-embed unreachable ... 502" 整章 FAILED(2026-08-09 事故根因)
  export NO_PROXY="localhost,127.0.0.1,::1,192.168.0.0/24,100.64.0.0/10,.local"
  export no_proxy="${NO_PROXY}"
fi

PY=.venv/bin/python
ECON_QUAL_DIR="${ECON_QUAL_DIR:-econ_pipeline/qual}"
ECON_CKPT_DIR="${ECON_CKPT_DIR:-econ_pipeline/ckpts}"
QUARANTINE_JSON="${ECON_QUARANTINE_JSON:-econ_pipeline/quarantine.json}"
BATCH_REPORT="${ECON_BATCH_REPORT:-econ_pipeline/batch_report.json}"
DRY_RUN="${ECON_DRY_RUN:-0}"
FORCE="${ECON_FORCE:-0}"
STRATUM_FEEDBACK="${ECON_STRATUM_FEEDBACK:-0}"  # 1=预检失败时反馈Stratum

: "${ECON_MD_LIST:?必须设置 ECON_MD_LIST (书单文件路径)}"
if [ ! -f "$ECON_MD_LIST" ]; then
    echo "❌ 书单文件不存在: $ECON_MD_LIST"; exit 1
fi

mkdir -p "$ECON_QUAL_DIR" "$ECON_CKPT_DIR" "econ_pipeline"

echo "════════════════════════════════════════════════════"
echo "★ 经济学批量管道 $(date '+%Y-%m-%d %H:%M')"
echo "  书单: $ECON_MD_LIST"
echo "  DRY_RUN=$DRY_RUN  FORCE=$FORCE"
echo "════════════════════════════════════════════════════"
echo ""

# ── 辅助函数: 写 quarantine (定义必须在 while 循环之前) ──
_quarantine_add_json() {
    local sid="$1" title="$2" md="$3" reason_type="$4" reason_detail="$5"
    $PY - <<PYEOF 2>/dev/null || true
import json, datetime
from pathlib import Path
qf = Path('$QUARANTINE_JSON')
d = json.loads(qf.read_text(encoding='utf-8')) if qf.exists() else {"quarantined": []}
d["quarantined"] = [x for x in d["quarantined"] if x.get("substrate_id") != "$sid"]
d["quarantined"].append({
    "substrate_id": "$sid",
    "title": "$title",
    "md_path": "$md",
    "reason_type": "$reason_type",
    "reason_detail": "$reason_detail",
    "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "qual_json": "econ_pipeline/qual/$sid.json",
    "status": "pending_review",
})
qf.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
PYEOF
}

# ── 初始化结果计数 ──
N_TOTAL=0; N_SKIP=0; N_PRECHECK_FAIL=0; N_PIPELINE_OK=0; N_ALARM=0; N_FAIL=0
declare -A RESULTS  # substrate_id → status

# ── 初始化/加载 quarantine ──
if [ ! -f "$QUARANTINE_JSON" ]; then
    echo '{"quarantined":[]}' > "$QUARANTINE_JSON"
fi

# ── 逐本处理 ──
while IFS='|' read -r MD_PATH SUBSTRATE ECON_TITLE || [ -n "$MD_PATH" ]; do
    MD_PATH="${MD_PATH//[$'\r\n']/}"
    [ -z "$MD_PATH" ] || [[ "$MD_PATH" == \#* ]] && continue  # 跳空行/注释

    N_TOTAL=$((N_TOTAL + 1))

    # ── 解析参数 ──
    if [ -z "$SUBSTRATE" ]; then
        # 从 sidecar JSON 自动读(同名 .json 文件)
        SIDECAR="${MD_PATH%.md}.json"
        if [ -f "$SIDECAR" ]; then
            SUBSTRATE=$($PY -c "import json; d=json.load(open('$SIDECAR')); print(d.get('id', ''))" 2>/dev/null || true)
            ECON_TITLE=$($PY -c "import json; d=json.load(open('$SIDECAR')); print(d.get('title', '')[:80])" 2>/dev/null || true)
        fi
        if [ -z "$SUBSTRATE" ]; then
            SUBSTRATE=$(basename "$MD_PATH" .md)
        fi
        if [ -z "$ECON_TITLE" ]; then
            ECON_TITLE="$SUBSTRATE"
        fi
    fi
    ECON_TITLE="${ECON_TITLE:-$SUBSTRATE}"

    echo "──────────────────────────────────────────"
    echo "[$N_TOTAL] $ECON_TITLE"
    echo "  SUBSTRATE=$SUBSTRATE"
    echo "  MD=$MD_PATH"

    # ── 检查 md 文件存在 ──
    if [ ! -f "$MD_PATH" ]; then
        echo "  ⚠️ MD文件不存在, 跳过"
        N_SKIP=$((N_SKIP + 1))
        RESULTS[$SUBSTRATE]="SKIP:md_not_found"
        continue
    fi

    # ── 检查是否已经入库(flywheel) ──
    if [ "$FORCE" != "1" ]; then
        ALREADY=$($PY -c "
import asyncio, asyncpg, os; from dotenv import load_dotenv; from pathlib import Path
load_dotenv(Path('aii/.env'))
async def chk():
    c = await asyncpg.connect(os.getenv('DATABASE_URL'))
    # 已完整入库: ingested_substrate 已登记(register.py 末端标记) 且 BU已生成
    # (KU>100 阈值只对经济学大书成立; misc书KU常<100 → 以登记表为准)
    r = await c.fetchrow('SELECT (SELECT count(*) FROM aii.ingested_substrate WHERE substrate_id=\$1) AS reg, (SELECT count(*) FROM aii.bu_onto WHERE substrate_id=\$1) AS bu', '$SUBSTRATE')
    await c.close()
    if r and (r['reg'] or 0) > 0 and (r['bu'] or 0) > 0:
        print('yes')
    else:
        print('no')
asyncio.run(chk())
" 2>/dev/null || echo "no")
        if [ "$ALREADY" = "yes" ]; then
            echo "  ✅ 已完整入库(已登记且BU已生成), 跳过(FORCE=0)"
            N_SKIP=$((N_SKIP + 1))
            RESULTS[$SUBSTRATE]="SKIP:already_ingested"
            continue
        fi
    fi

    # ── R1-R9 预检(md 结构质量门) ──
    echo "  [预检] R1-R9 章节结构检查..."
    PRECHECK_RESULT=$($PY scripts/misc_precheck.py "$MD_PATH" "$ECON_TITLE" 2>/dev/null || echo "FAIL:预检脚本错误")

    if [[ "$PRECHECK_RESULT" == FAIL* ]]; then
        echo "  ❌ 预检失败($PRECHECK_RESULT) → 不进管道"
        N_PRECHECK_FAIL=$((N_PRECHECK_FAIL + 1))
        RESULTS[$SUBSTRATE]="PRECHECK_FAIL:$PRECHECK_RESULT"
        _quarantine_add_json "$SUBSTRATE" "$ECON_TITLE" "$MD_PATH" "precheck" "$PRECHECK_RESULT"
        # ── 反馈 Stratum: MD 需重新输出 ──
        if [ "$STRATUM_FEEDBACK" = "1" ]; then
            $PY scripts/econ_stratum_feedback.py "$SUBSTRATE" "$ECON_TITLE" "$MD_PATH" "$PRECHECK_RESULT" \
                2>/dev/null && echo "  📤 已反馈 Stratum(md_rework_queue.json)" || true
        fi
        continue
    fi
    echo "  ✅ 预检通过($PRECHECK_RESULT)"

    if [ "$DRY_RUN" = "1" ]; then
        echo "  [DRY_RUN] 跳过管道执行"
        RESULTS[$SUBSTRATE]="DRY_RUN:precheck_ok"
        continue
    fi

    # ── 运行管道 ── ★PIPELINE_SCRIPT/RUN_LOG_DIR 可覆盖(默认走econ_zh/misc共用的econ_pipeline.sh
    # +econ_pipeline/, 不设就是原行为不变; advmath等新频道传自己的脚本+目录, 避免log混进econ_pipeline/)
    PIPELINE_SCRIPT="${ECON_PIPELINE_SCRIPT:-scripts/econ_pipeline.sh}"
    RUN_LOG_DIR="${ECON_RUN_LOG_DIR:-econ_pipeline}"
    mkdir -p "$RUN_LOG_DIR"
    echo "  [管道] 运行 $PIPELINE_SCRIPT..."
    QUAL_JSON="$ECON_QUAL_DIR/${SUBSTRATE}.json"
    export SUBSTRATE AII_MD_FILE="$MD_PATH" ECON_TITLE QUAL_DIR="$ECON_QUAL_DIR" PIPELINE_CKPT_DIR="$ECON_CKPT_DIR"

    PIPE_EXIT=0
    bash "$PIPELINE_SCRIPT" 2>&1 | tee "$RUN_LOG_DIR/${SUBSTRATE}_run.log" || PIPE_EXIT=$?

    if [ $PIPE_EXIT -eq 2 ]; then
        echo "  ❌ 管道步骤失败(exit=2) → 隔离"
        N_FAIL=$((N_FAIL + 1))
        RESULTS[$SUBSTRATE]="PIPELINE_FAIL"
        _quarantine_add_json "$SUBSTRATE" "$ECON_TITLE" "$MD_PATH" "pipeline_error" "管道步骤失败(exit 2)"
        continue
    fi

    if [ $PIPE_EXIT -eq 0 ]; then
        # ── 质量门通过 → 自动入库 ──
        echo "  ✅ 质量门通过 → 自动入库..."
        $PY scripts/econ_register.py "$SUBSTRATE" "$ECON_TITLE" --subject "${ECON_REGISTER_SUBJECT:-经济学}"
        N_PIPELINE_OK=$((N_PIPELINE_OK + 1))
        RESULTS[$SUBSTRATE]="PASS:registered"
        echo "  ✅ 已入正式库: $SUBSTRATE"
        # ★P2(2026-08-12): 生成 KU 证据审查 HTML(字符级高亮, 人工抽查 A 仓质量用)
        $PY scripts/ku_visualize.py --substrate "$SUBSTRATE" --limit 60 \
            --out "$(dirname "$QUAL_JSON" 2>/dev/null || echo econ_pipeline/qual)/${SUBSTRATE}_ku_review.html" 2>/dev/null \
            || echo "  ⚠ KU 审查 HTML 生成失败(非致命)"
        # ★用户指令(2026-07-23): 抽完KU的源MD是资产, 不能只留本地——按本地MD池子分类
        # (经济学/中文数学/英文数学/其它)同名归档到Drive。不删本地, 失败下轮 econ_register
        # 幂等重跑时不会再碰这段(只在本次成功分支跑一次), 但下次批量遇到同名文件 rclone
        # 会按checksum跳过, 不重复上传。
        MD_SUBJECT_DIR=$(basename "$(dirname "$MD_PATH")")
        if rclone copy "$MD_PATH" "gdrive-rw:aii-已入库源MD/$MD_SUBJECT_DIR/" --drive-chunk-size 64M 2>/dev/null; then
            echo "  📦 已归档源MD到 Drive(aii-已入库源MD/$MD_SUBJECT_DIR/)"
        else
            echo "  ⚠ 归档到 Drive 失败(本地MD保留, 不影响入库结果)"
        fi
    else
        # ── 质量门报警 → 隔离等人工 ──
        echo "  🚨 质量门报警(exit=$PIPE_EXIT) → 隔离等人工审查"
        ALARM_REASONS="see $QUAL_JSON"
        if [ -f "$QUAL_JSON" ]; then
            ALARM_REASONS=$($PY -c "import json; d=json.load(open('$QUAL_JSON')); print(' | '.join(d.get('alarms',[])[:3]))" 2>/dev/null || echo "see $QUAL_JSON")
        fi
        _quarantine_add_json "$SUBSTRATE" "$ECON_TITLE" "$MD_PATH" "quality_gate" "$ALARM_REASONS"
        N_ALARM=$((N_ALARM + 1))
        RESULTS[$SUBSTRATE]="ALARM:$ALARM_REASONS"
    fi

done < "$ECON_MD_LIST"

# ── 批量报告 ──
N_ALL_OK=$((N_TOTAL - N_SKIP - N_PRECHECK_FAIL - N_PIPELINE_OK - N_ALARM - N_FAIL))

$PY - <<PYEOF 2>/dev/null
import json, datetime
from pathlib import Path

report = {
    "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "book_list": "$ECON_MD_LIST",
    "dry_run": "$DRY_RUN" == "1",
    "summary": {
        "total": $N_TOTAL,
        "skipped(已入库)": $N_SKIP,
        "precheck_fail": $N_PRECHECK_FAIL,
        "pipeline_fail": $N_FAIL,
        "alarm_quarantined": $N_ALARM,
        "pass_registered": $N_PIPELINE_OK,
    },
    "quarantine_file": "$QUARANTINE_JSON",
    "qual_dir": "$ECON_QUAL_DIR",
}
Path("$BATCH_REPORT").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
PYEOF

echo ""
echo "════════════════════════════════════════════════════"
echo "★ 批量完成 $(date '+%Y-%m-%d %H:%M')"
echo "  总计=$N_TOTAL | 跳过=$N_SKIP | 预检失败=$N_PRECHECK_FAIL"
echo "  管道失败=$N_FAIL | 质量门拦截=$N_ALARM | 成功入库=$N_PIPELINE_OK"
echo ""
echo "  批量报告 → $BATCH_REPORT"
echo "  质量门拦截 → $QUARANTINE_JSON"
echo "════════════════════════════════════════════════════"
