#!/bin/bash
# 重跑 3 本"容量悬崖受害书"(分片改造之前跑的, 命名率被 max_tokens 截断压到 4-34%)。
# ★在你自己的持久会话里前台跑(用 ! 前缀), 别经 agent —— agent 环境杀长后台任务。
# 预计 40-75 分钟(3本约30章 × ~150s/章 串行)。跑完概念自动可入库。
set -e
cd /data/soffy/projects/stratum/aii
export NVIDIA_NIM_API_KEY=$(.venv/bin/python -c "
import json;d=json.load(open('.pipeline_keys.json'))
for k in ('math_prog_verify','advmath_verify','math_zh','math_en'):
    if d.get(k): print(d[k]); break")
# 这3本的 .done 已删, --rest 只会挑它们
.venv/bin/python scripts/math_prog_rename_batch.py --rest --tag reflow
echo "── 重跑完成, 补入库(幂等) ──"
.venv/bin/python scripts/math_concept_ingest_dryrun.py --apply
