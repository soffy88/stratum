#!/usr/bin/env bash
# ★喂书守护进程 — 持续把"书源产出 + 本地投书"转成 MD 并分类进 /books/MD/, 喂给四个飞轮.
#
# 四条进书渠道(scripts/pull_ingest.sh, 每轮都跑, 都幂等, 已转/已存在则跳过):
#   0. D盘同步       : /mnt/d/books/{数学,Economic} → /home/soffy/books/{数学,Economic}
#   1. classify_md.py  : stratum 抓书转好的 MD (/shared/stratum-to-aii) → 分类 → /books/MD/{经济学|中英文数学}
#   2. math_convert.py : 本地投的数学 PDF (/books/数学)    → 转MD → /books/MD/{中文数学|英文数学}
#   3. econ_convert.py : 本地投的经济 PDF (/books/Economic) → 转MD → /books/MD/经济学
# 之后四个飞轮的 discover 自动发现新书. 任何人丢本教材 PDF 进 /books/{数学|Economic} 或 D盘对应目录就全自动入库.
# 三个业务飞轮(econ-zh/misc/math-prog)自己每轮也会主动调 pull_ingest.sh, 不必等这里的定时器.
#
# 注: 需OCR(无文字层)的扫描版不在此循环(GPU重), 单独跑 `python ocr_batch.py`.
# 注: classify 用宽松间隔, 让 AII background_flywheel(60s轮询/shared)先处理完再搬文件, 避免漏书.
#
# 用法:  nohup bash scripts/feeder_run.sh >> econ_pipeline/feeder.log 2>&1 &
# 可选:  FEEDER_IDLE=600 (每轮间隔秒, 默认600)
set -uo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
IDLE="${FEEDER_IDLE:-600}"

echo "════════════════════════════════════════════════════"
echo "★ 喂书守护启动 $(date '+%Y-%m-%d %H:%M')  (每 ${IDLE}s 一轮)"
echo "  渠道: classify(stratum-to-aii) + math_convert(/books/数学) + econ_convert(/books/Economic)"
echo "════════════════════════════════════════════════════"

while true; do
    echo "── [喂书] $(date '+%H:%M') 开始一轮 ──"
    before=$(ls /home/soffy/books/MD/经济学/*.md /home/soffy/books/MD/中文数学/*.md /home/soffy/books/MD/英文数学/*.md 2>/dev/null | wc -l)

    # D盘同步 + math_convert + econ_convert + classify_md, 一次做全
    # (flock: 三个飞轮各自也会主动拉料, 防撞车挪同一文件)
    mkdir -p .locks
    flock -w 120 .locks/classify_md.lock -c "timeout 600 bash scripts/pull_ingest.sh" 2>&1

    after=$(ls /home/soffy/books/MD/经济学/*.md /home/soffy/books/MD/中文数学/*.md /home/soffy/books/MD/英文数学/*.md 2>/dev/null | wc -l)
    echo "── [喂书] $(date '+%H:%M') /books/MD 教材: ${before}→${after}; sleep ${IDLE}s ──"
    sleep "$IDLE"
done
