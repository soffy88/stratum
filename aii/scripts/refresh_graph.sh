#!/usr/bin/env bash
# 摄取后钩子: 重建概念图 + Laplacian快照(谱演化) + 谱社区KC. 使 Laplacian 真持续(图增长时增量追踪).
# synthesize_book 摄取/改动 KU 后调用; 也可手动/排程跑. LLM 重步骤(readout)~10min.
set -e
cd "$(dirname "$0")/.."
PY=.venv/bin/python
echo "[refresh] 1/6 concepts + co-occurrence";   $PY scripts/materialize_links.py
echo "[refresh] 2/6 read out directed relations"; $PY scripts/readout_all.py
echo "[refresh] 3/6 split concept-level / KU-internal"; $PY scripts/normalize_readout.py
echo "[refresh] 4/6 structure KU-internal logic";  $PY scripts/structure_logic.py
echo "[refresh] 5/6 normalize logic nodes";         $PY scripts/normalize_ku_logic_nodes.py
echo "[refresh] 6/6 Laplacian snapshot + spectral KC"; $PY scripts/laplacian_job.py && $PY scripts/name_communities.py
echo "[refresh] done — concept graph + Laplacian + spectral KC updated"
