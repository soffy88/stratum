#!/usr/bin/env bash
# ★数学程序化飞轮(B 范式): 程序从原文抠"陈述+证明"(0 LLM) + 程序命名(书自带名→标记).
# 取代旧 math_pipeline 的 LLM synth(费钱且抽成 blob). 全本地: BGE-M3 嵌入, 无 LLM 调用.
# 单轮: 扫 /books/MD/{英文,中文}数学 → 未 B 过的逐本 program_ingest + math_ingest 落库.
set -uo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
export DATABASE_URL="${DATABASE_URL:-postgresql://aii:aii_safe_pass@localhost:5435/aii_kg}"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1   # 用本地缓存 BGE-M3, 不连 huggingface
# 不设 CUDA_VISIBLE_DEVICES → BGE-M3(FlagEmbedding, fp16)自动用本地 GPU(RTX 3080)加速嵌入
STAGING_BASE="scripts/_staging/math_prog"
MIN_KU="${MATH_PROG_MIN_KU:-30}"        # DB 已有 >MIN_KU 视为已 B 过

echo "════ 数学程序化飞轮 B (0 LLM) $(date '+%Y-%m-%d %H:%M') ════"
processed=0
for f in /home/soffy/books/MD/英文数学/*.md /home/soffy/books/MD/中文数学/*.md; do
    [ -f "$f" ] || continue
    stem="$(basename "$f" .md)"
    sub="math_prog_$(printf '%s' "$stem" | md5sum | cut -c1-10)"
    cnt=$(docker exec aii-postgres psql -U aii -d aii_kg -tAc \
          "SELECT count(*) FROM aii.ku_onto WHERE substrate_id='$sub'" 2>/dev/null | tr -d '[:space:]')
    [ "${cnt:-0}" -gt "$MIN_KU" ] && continue
    echo "── 抽取: ${stem:0:50} (sub=$sub) ──"
    $PY scripts/math_program_ingest.py "$f" "$sub" 2>&1 | tail -2
    $PY scripts/math_ingest.py --substrate "$sub" --staging "$STAGING_BASE/$sub" 2>&1 | grep -E '入库完成|准备入库' || true
    processed=$((processed + 1))
done
echo "── 本轮处理 $processed 本 ──"
[ "$processed" -eq 0 ] && echo "飞轮完成: 无新书"
