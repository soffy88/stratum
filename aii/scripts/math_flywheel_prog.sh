#!/usr/bin/env bash
# ★数学程序化飞轮(B 范式): 程序从原文抠"陈述+证明"(0 LLM) + 程序命名(书自带名→标记).
# 取代旧 math_pipeline 的 LLM synth(费钱且抽成 blob). 全本地: BGE-M3 嵌入, 内容抽取本身无 LLM 调用.
# 单轮: 扫 /books/MD/{英文,中文}数学 → 未 B 过的逐本:
#   math_program_ingest.py 抽取(内含规划审核: 每章1次LLM筛掉交叉引用/半截碎片/重复候选,
#     只做留弃取舍不碰内容, 见该文件说明) → math_ingest.py 落库 →
#   math_prog_verify.py 质检(抓PDF转换污染/type误判, 只标记不拦截, 见该文件说明).
#   规划审核+质检共用同一个独立key(math_prog_verify), 无key则两步都fail-open跳过.
set -uo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
export DATABASE_URL="${DATABASE_URL:-postgresql://aii:aii_safe_pass@localhost:5435/aii_kg}"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1   # 用本地缓存 BGE-M3, 不连 huggingface
export AII_EMBED_URL="${AII_EMBED_URL:-http://100.68.226.13:8102}"   # ★嵌入走共享 aii-embed 微服务(已迁笔记本GPU, 禁止用本机GPU); 本进程不再加载 BGE-M3
export CUDA_VISIBLE_DEVICES=""   # ★嵌入已外包给服务, 本飞轮彻底不碰 GPU(抽取0-LLM纯CPU)
# ★规划审核用key。原来只取 'math_prog_verify' —— 该键在 .pipeline_keys.json 里【不存在】
# (实有 econ/math_en/econ_zh/math_zh/advmath_2/advmath_3/advmath_verify/learning),
# 取到空串后 math_program_ingest 静默 fail-open, 规划审核②从未跑过, 14919 条 KU 的命名
# 全部掉到③摘首句 —— 这就是 title 是陈述原文而非概念名的根因(2026-07-20 查实)。
# 改为按优先级回退到确实存在的键; 全找不到时下游会大声报警(不再静默)。
export NVIDIA_NIM_API_KEY="$($PY -c "
import json
d = json.load(open('.pipeline_keys.json'))
for k in ('math_prog_verify', 'advmath_verify', 'math_zh', 'math_en'):
    if d.get(k):
        print(d[k]); break
" 2>/dev/null)"
export NIM_MODEL="${NIM_MODEL:-nvidia/llama-3.3-nemotron-super-49b-v1.5}"
STAGING_BASE="scripts/_staging/math_prog"
MIN_KU="${MATH_PROG_MIN_KU:-30}"        # DB 已有 >MIN_KU 视为已 B 过(小书靠下面的 .done 标记判断)

# ★主动拉料: 别等 feeder 独立时钟才有新书: D盘同步+本地PDF转换+stratum分类一次做全
# (flock 防和其他飞轮/feeder撞车挪同一文件)
mkdir -p .locks
flock -w 120 .locks/classify_md.lock -c "timeout 600 bash scripts/pull_ingest.sh" || true

echo "════ 数学程序化飞轮 B (0 LLM) $(date '+%Y-%m-%d %H:%M') ════"
processed=0
for f in /home/soffy/books/MD/英文数学/*.md /home/soffy/books/MD/中文数学/*.md; do
    [ -f "$f" ] || continue
    # ★门禁: 数学密度/章节结构够≠能被B范式抽取(靠MARK正则找带编号的"定理N/定义N").
    # 叙事类数学科普书从不编号, 抽出0KU白跑一轮; 不可抽的直接挪 其它/ 给misc飞轮接手.
    if ! $PY scripts/math_route_or_skip.py "$f"; then
        continue
    fi
    stem="$(basename "$f" .md)"
    sub="math_prog_$(printf '%s' "$stem" | md5sum | cut -c1-10)"
    # ★粘连门(2026-07-20): OCR 抹掉空格的书, ①抠出记号、②大规模误判, 且过滤器无法
    # 察觉自己失败(粘连整句会被当成概念名放行)。实测 76% 粘连的书 ①②双双归零。
    # 不抽, 退回 Stratum 返工——粘连是上游 PDF→MD 的病, 自弃等于替上游背账。
    # 卡在②【之前】, 顺带省下 ~240s/章 的 49B 成本。阈值 MD_GLUE_THRESHOLD 可调。
    if ! $PY scripts/md_glue_gate.py "$f" --substrate "$sub" --title "$stem" --report; then
        echo "  ⏭ 粘连超阈值, 跳过并已反馈 Stratum: $stem"
        continue
    fi
    # ★已成功入库过的标记(即便书本身 KU 数<MIN_KU, 也不再永远重跑, 见下方 .done 写入)
    [ -f "$STAGING_BASE/$sub/.done" ] && continue
    cnt=$(docker exec aii-postgres psql -U aii -d aii_kg -tAc \
          "SELECT count(*) FROM aii.ku_onto WHERE substrate_id='$sub'" 2>/dev/null | tr -d '[:space:]')
    [ "${cnt:-0}" -gt "$MIN_KU" ] && continue
    echo "── 抽取: ${stem:0:50} (sub=$sub) ──"
    $PY scripts/math_program_ingest.py "$f" "$sub" 2>&1 | tail -2
    ingest_out=$($PY scripts/math_ingest.py --substrate "$sub" --staging "$STAGING_BASE/$sub" 2>&1)
    echo "$ingest_out" | grep -E '入库完成|准备入库' || true
    echo "$ingest_out" | grep -qE '入库完成: ok=[0-9]+ skip=[0-9]+ err=0$' && touch "$STAGING_BASE/$sub/.done"
    SUBSTRATE="$sub" $PY scripts/math_prog_verify.py 2>&1 || echo "  ⚠ 判官调用异常(非致命, 继续)"
    processed=$((processed + 1))
done
echo "── 本轮处理 $processed 本 ──"
if [ "$processed" -eq 0 ]; then
    echo "飞轮完成: 无新书"
fi
exit 0
