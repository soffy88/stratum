#!/usr/bin/env bash
# ★单本飞轮 pipeline(第一本微观经济学验证过的流程固化). 一键跑单本.
# ★只含【书内】机制; 【跨书】机制(谱社区跨书增长/概念复用/本性同一)不在此 pipeline,
#   单本跑完后单独验(那些第一本没验证过). 见末尾 EXCLUDED.
# 产出落 substrate-scoped 数据 = 暂存区; 末尾质量自检报告 + 报警 → 人工确认才算入正式库.
# Usage: SUBSTRATE=<id> flywheel_single_book.sh   (脚本目前 hardcode microecon, book2 需参数化)
set -e
cd "$(dirname "$0")/.."
PY=.venv/bin/python
echo "════ 单本飞轮: ${SUBSTRATE:-microecon_en_full_v2} ════"
echo "[1/8] 逐章讲透 KU + 完整性校验防漏 + KU打磨(clean整合)"; $PY scripts/synthesize_book.py
echo "[2/8] 概念抽取 + 共现联结(纯计算, 书内)";              $PY scripts/materialize_links.py
echo "[3/8] 有向关系读出(讲透KU读出, 非N²judge)";           $PY scripts/readout_all.py
echo "[4/8] 节点归一: 概念级有向→图 / KU内部逻辑→留KU";      $PY scripts/normalize_readout.py
echo "[5/8] KU内部逻辑结构化(因果链+分解树) + 节点归一";      $PY scripts/structure_logic.py && $PY scripts/normalize_ku_logic_nodes.py
echo "[6/8] 按章KC(中文主题名) + 双语簇摘要";                $PY scripts/persist_chapter_kc.py && $PY scripts/fix_kc_labels_summaries.py
echo "[7/8] BU 书级理解(七项 + 忠实校验) 入库";              $PY scripts/generate_bu.py && $PY scripts/persist_bu.py
echo "[8/8] ★质量自检报告 + 报警阈值(→人工确认入正式库)";   $PY scripts/quality_report.py "${SUBSTRATE:-microecon_en_full_v2}"
echo "════ 完成. 看质量自检报告: 0报警→人工确认; 有报警→人工核查 ════"
# ───────────────────────────────────────────────────────────────────────
# ★EXCLUDED(跨书机制, 不在单本 pipeline, 单本跑完单独验):
#   - 谱社区KC(laplacian_job.py + name_communities.py): 跨书主题增长, 第一本只是intra-book聚类
#   - 持续Laplacian谱演化: 跨书图增长追踪
#   - 概念复用/本性同一(extract_essence.py): 跨学科不变内核(导数↔边际), 要≥2本书才能验
#   这些等第二本(数学书)跑完单本后, 再单独接入 + 验证.
