#!/usr/bin/env bash
# ★高级数学经济专用管道 — 单本全自动. 克隆自 econ_pipeline.sh, 两处实质改动:
#   [1/6]换成 synthesize_book_advmath.py(真LLM讲透, 高中生讲解桥梁版, 见
#   chapter_synthesize_advmath.py), 不是econ_zh/misc用的0LLM程序抠版 synthesize_book.py
#   ——这批书(高级微观/代数几何/拓扑/递归宏观理论等)术语抽象度高, 用户明确要求"讲解到
#   高中生能看懂但不降原书深度", 0LLM逐字抠办不到(不改写语言)。
#   [2/6]新增讲透质量判官(advmath_verify.py, 独立key), 现有econ_quality_gate.py全是
#   确定性规则检查, 没有LLM去判断"是否保留了原书的严谨性/中文是否纯净"。
# 其余步骤(概念抽取/按章KC/BU/质量门)跟econ_zh完全一致, 原样复用.
#
# Required env vars:
#   SUBSTRATE     DB唯一键 (advmath_zh_xxx / advmath_en_xxx)
#   AII_MD_FILE   书的 MD 文件绝对路径(在 /mnt/d/books/高级数学经济专用/ 下)
# Optional:
#   ECON_TITLE    显示名(默认=SUBSTRATE)
#   QUAL_DIR      质量报告输出目录(默认 advmath_pipeline/qual/)
#   PIPELINE_CKPT_DIR  断点续跑checkpoint目录(默认 advmath_pipeline/ckpts/)
#
# Exit: 0=质量门通过, 1=质量门报警, 2=管道步骤失败
set -euo pipefail
cd "$(dirname "$0")/.."

: "${SUBSTRATE:?必须设置 SUBSTRATE (DB唯一键)}"
: "${AII_MD_FILE:?必须设置 AII_MD_FILE (md文件绝对路径)}"

ECON_TITLE="${ECON_TITLE:-$SUBSTRATE}"
QUAL_DIR="${QUAL_DIR:-advmath_pipeline/qual}"
PIPELINE_CKPT_DIR="${PIPELINE_CKPT_DIR:-advmath_pipeline/ckpts}"

mkdir -p "$QUAL_DIR" "$PIPELINE_CKPT_DIR"
QUAL_JSON="$QUAL_DIR/${SUBSTRATE}.json"

ADVMATH_PIPELINE_VERSION="advmath-A仓-v1.0(高中生讲透版)"
export SUBSTRATE AII_MD_FILE PIPELINE_CKPT_DIR

PY=.venv/bin/python

echo "════════════════════════════════════════════"
echo "★ 高级数学经济管道 [$ADVMATH_PIPELINE_VERSION]: $ECON_TITLE"
echo "  SUBSTRATE=$SUBSTRATE"
echo "  AII_MD_FILE=$AII_MD_FILE"
echo "  QUAL=$QUAL_JSON"
echo "════════════════════════════════════════════"

echo ""
echo "[1/6] 逐章讲透(高中生可懂桥梁+原书深度不减) + ★完整性校验严(不能遗漏) + 打磨"
$PY scripts/synthesize_book_advmath.py || { echo "❌ [1/6] 失败"; exit 2; }
$PY scripts/dedup_within_book.py "$SUBSTRATE" 2>/dev/null || echo "  ⚠ 书内去重跳过(非致命)"

echo ""
echo "[2/6] ★讲透质量判官(LLM查保留严谨/中文纯净, 不合格只记录不拦截——见advmath_verify.py)"
$PY scripts/advmath_verify.py 2>&1 || echo "  ⚠ 判官调用异常(非致命, 继续)"

echo ""
echo "[2b/6] ★论文召回审计(observe-only: 摘要自称贡献 vs KU覆盖, 漏项记录; 仅doc_type=paper生效, 不拦截——见advmath_recall_audit.py)"
$PY scripts/advmath_recall_audit.py 2>&1 || echo "  ⚠ 召回审计异常(非致命, 继续)"

echo ""
echo "[3/6] 概念抽取(单本KU涉及哪些概念; ★只概念不共现, 共现=B仓)"
$PY scripts/materialize_links.py || { echo "❌ [3/6] 失败"; exit 2; }

echo ""
echo "[4/6] 按章KC(书内结构, 给人按书读) + 双语簇摘要"
$PY scripts/persist_chapter_kc.py && $PY scripts/fix_kc_labels_summaries.py || { echo "❌ [4/6] 失败"; exit 2; }

echo ""
echo "[5/6] BU 书级理解(七项) 入库"
NIM_BU_KEY="$($PY -c "import json;print(json.load(open('.pipeline_keys.json')).get('math_zh',''))" 2>/dev/null)"
NVIDIA_NIM_API_KEY="$NIM_BU_KEY" $PY scripts/generate_bu.py \
  && NVIDIA_NIM_API_KEY="$NIM_BU_KEY" $PY scripts/persist_bu.py \
  || { echo "❌ [5/6] 失败"; exit 2; }

echo ""
echo "[5b/6] ★论文V3排他性门(observe-only: 只给非常识建技能, 逐条筛findings, 仅doc_type=paper生效, 不拦截)"
$PY scripts/paper_v3_gate.py 2>&1 || echo "  ⚠ V3门异常(非致命, 继续)"

echo ""
echo "[6/6] ★KU质量门(complete严=100%/残留/空壳/双语/讲浅/密度/章) → $QUAL_JSON"
$PY scripts/econ_quality_gate.py "$SUBSTRATE" --json "$QUAL_JSON"
GATE_EXIT=$?

echo ""
if [ $GATE_EXIT -eq 0 ]; then
    echo "✅ 质量门通过 → 待自动入库 (advmath_register.py)"
else
    echo "🚨 质量门报警($GATE_EXIT) → 隔离等人工. 详见 $QUAL_JSON"
fi

exit $GATE_EXIT
