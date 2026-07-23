#!/usr/bin/env bash
# ★论文轻量管道 — 论文≠教材(见 docs/PAPER_BU_SCHEMA.md), 不套 advmath/econ 那套
# 逐章讲透+概念抽取+章节KC模板(约一半KU是概念,教材里都有,冗余; 论文低价值)。
# 只跑: BU两层理解(generate_bu.py 论文分支 + persist_bu.py) → skill抽取
# (paper_v3_gate.py, observe-only) → 登记入库(复用econ_register.py, 通用注册脚本)。
# ku_count=0 是正常状态——论文管道刻意不产 KU, 别当成"没处理"。
#
# Required env vars:
#   SUBSTRATE     DB唯一键 (paper_xxx, 见 paper_discover.py)
#   AII_MD_FILE   论文 MD 文件绝对路径(在 /home/soffy/books/MD/论文/ 下)
# Optional:
#   PAPER_TITLE   显示名(默认=SUBSTRATE)
#
# Exit: 0=已登记入库, 2=管道步骤失败
set -euo pipefail
cd "$(dirname "$0")/.."

: "${SUBSTRATE:?必须设置 SUBSTRATE (DB唯一键)}"
: "${AII_MD_FILE:?必须设置 AII_MD_FILE (论文md文件绝对路径)}"

PAPER_TITLE="${PAPER_TITLE:-$SUBSTRATE}"
PY=.venv/bin/python
export SUBSTRATE AII_MD_FILE
# ★嵌入走共享 aii-embed 微服务, 不占本机 GPU(同 misc/econ-zh/math-prog 飞轮的既有约定)。
# 2026-07-19 实测漏配这几个: persist_bu.py 的"技能检索向量"步骤会在 AII_EMBED_URL 未设时
# 回退进程内加载真实 BGE-M3(见 aii/api/_provider.py), 每篇论文都占用本机 GPU 显存,
# 且撞上过一次疑似卡死(单次调用挂了 1 小时, GPU 显存一直不释放)。
export CUDA_VISIBLE_DEVICES=""
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export AII_EMBED_URL="${AII_EMBED_URL:-http://100.68.226.13:8102}"

echo "════════════════════════════════════════════"
echo "★ 论文轻量管道: $PAPER_TITLE"
echo "  SUBSTRATE=$SUBSTRATE"
echo "  AII_MD_FILE=$AII_MD_FILE"
echo "════════════════════════════════════════════"

echo ""
echo "[1/3] BU 论文两层理解(generate_bu.py 论文分支自动触发, doc_type:paper frontmatter 早返回 + persist_bu.py)"
$PY scripts/generate_bu.py && $PY scripts/persist_bu.py || { echo "❌ [1/3] 失败"; exit 2; }

echo ""
echo "[2/3] ★论文V3排他性门(observe-only: 只给非常识建技能, 逐条筛findings——见paper_v3_gate.py)"
$PY scripts/paper_v3_gate.py 2>&1 || echo "  ⚠ V3门异常(非致命, 继续)"

echo ""
echo "[3/3] 登记入库(medium=paper, subject=论文; ku_count 从 ku_onto 数, 论文管道下应为0, 正常)"
$PY scripts/econ_register.py "$SUBSTRATE" "$PAPER_TITLE" --medium paper --subject 论文 || { echo "❌ [3/3] 失败"; exit 2; }

echo ""
echo "✅ 论文处理完成 → $SUBSTRATE"
