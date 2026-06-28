#!/usr/bin/env bash
# 华东师大数学分析第5版 上册 全书提取 + 质量报告
# Usage: bash scripts/run_shuxuefen.sh
set -e
cd "$(dirname "$0")/.."

UPPER="/home/soffy/shared/stratum-to-aii/数学分析(第5版)_上_(华东师范大学数学系)_(z-library.sk,_1_01KVQ2BQ.md"
OUTDIR="/tmp/claude-1000/-home-soffy-projects-AII/b59675af-3e38-4d3d-9fd3-e5fd9f2f3a03/scratchpad/math_full"
mkdir -p "$OUTDIR"

echo "════ 华东师大数学分析 上册 全书提取(断点续) ════"
echo "书: $UPPER"
echo "暂存: $OUTDIR"
echo ""

for ch in 1 2 3 4 5 6 7 8 9 10 11; do
    OUT="$OUTDIR/ch${ch}.json"
    if [ -f "$OUT" ] && [ "$(python3 -c "import json; d=json.load(open('$OUT')); print(len(d))" 2>/dev/null)" -gt 0 ]; then
        echo "[已有] 第${ch}章 ($(python3 -c "import json; print(len(json.load(open('$OUT'))))" 2>/dev/null) KU)"
    else
        echo "[抽取] 第${ch}章..."
        AII_MD_FILE="$UPPER" .venv/bin/python3 scripts/math_pipeline.py $ch 2>&1
    fi
done

echo ""
echo "════ 全书质量自检 ════"
.venv/bin/python3 - <<'PYEOF'
import json, glob, os
OUTDIR = "/tmp/claude-1000/-home-soffy-projects-AII/b59675af-3e38-4d3d-9fd3-e5fd9f2f3a03/scratchpad/math_full"
all_kus = []
for ch in range(1, 12):
    f = f"{OUTDIR}/ch{ch}.json"
    if os.path.exists(f):
        kus = json.load(open(f, encoding='utf-8'))
        for k in kus:
            k.setdefault('chapter', ch)
        all_kus.extend(kus)
print(f"总 KU: {len(all_kus)}")
complete = [k for k in all_kus if k.get('content_match')]
has_formula = [k for k in all_kus if k.get('has_formula')]
shallow = [k for k in all_kus if k.get('facet_issues')]
print(f"内容真覆盖: {len(complete)}/{len(all_kus)}")
print(f"含完整LaTeX公式: {len(has_formula)}/{len(all_kus)}")
print(f"讲浅/缺面: {len(shallow)}")
if shallow:
    for k in shallow[:5]:
        print(f"  [{k['point'][:30]}] 问题: {k['facet_issues']}")
print()
print("各章统计:")
for ch in range(1, 12):
    chs = [k for k in all_kus if k.get('chapter') == ch]
    if chs:
        cf = sum(1 for k in chs if k.get('has_formula'))
        cc = sum(1 for k in chs if k.get('content_match'))
        print(f"  Ch{ch}: {len(chs)} KU | 公式{cf} | 内容真覆盖{cc}")
PYEOF

echo ""
echo "════ 跨书对比: 数分 vs 同济高数 ════"
.venv/bin/python3 - <<'PYEOF'
import json, glob, os, asyncio, asyncpg
from dotenv import load_dotenv
load_dotenv('aii/.env', override=True)
DB = os.getenv('DATABASE_URL')

OUTDIR = "/tmp/claude-1000/-home-soffy-projects-AII/b59675af-3e38-4d3d-9fd3-e5fd9f2f3a03/scratchpad/math_full"
all_kus = []
for ch in range(1, 12):
    f = f"{OUTDIR}/ch{ch}.json"
    if os.path.exists(f):
        all_kus.extend(json.load(open(f, encoding='utf-8')))

shuxuefen_titles = {k['point'] for k in all_kus}

async def main():
    conn = await asyncpg.connect(DB)
    # 同济高数 KU titles
    tongji = await conn.fetch("SELECT title FROM aii.ku_onto WHERE substrate_id='advmath_tongji_full'")
    tongji_titles = {r['title'] for r in tongji}
    print(f"数分上册: {len(shuxuefen_titles)} KU点")
    print(f"同济高数: {len(tongji_titles)} KU")
    # 主题重叠(极限/导数/连续/积分)
    key_topics = ['极限', '导数', '连续', '积分', '微分', '收敛', '级数']
    print("\n★ 跨书概念对比:")
    for topic in key_topics:
        sxf = [t for t in shuxuefen_titles if topic in t]
        tj = [t for t in tongji_titles if topic in t]
        print(f"  [{topic}] 数分:{len(sxf)} | 同济:{len(tj)}")
        for t in sxf[:2]:
            print(f"    数分: {t}")
        for t in tj[:2]:
            print(f"    同济: {t}")
    # 名字完全相同的
    overlap = shuxuefen_titles & tongji_titles
    print(f"\n★ 完全同名概念(直接复用候选): {len(overlap)}")
    for t in sorted(overlap):
        print(f"  • {t}")
    await conn.close()

asyncio.run(main())
PYEOF

echo "════ 完成. 暂存在 $OUTDIR ════"
echo "★ 入正式库前需人工确认(Wiki)"
