#!/usr/bin/env bash
# ★OCR自动化守护 — 扫描版/烂文本层的数学+经济PDF, 自动排队调用ocr-vllm转清再入常规流程.
#
# 为什么独立跑, 不塞进 pull_ingest.sh(三个KU飞轮+feeder每轮都调, 10-15min一轮):
#   OCR一本大书能到~80min(实测42min/767页), pull_ingest.sh里的每一步都要快, 之前
#   给它加了 timeout 600 防真卡死(见 PIPELINE_STATUS.md), 塞进去只会把没转完的OCR
#   任务腰斩。所以单独一条慢节奏常驻循环, 不设短超时, 让OCR任务自然跑完.
#
# GPU排队(不是"不空闲就放弃"): math_ocr_convert.ensure_container() 内部会先等
# aii-embed 空闲卸载显存(BGE-M3哪怕只占~2.4G也可能让只留75%显存的ocr-vllm启动失败,
# 2026-07-06 实测复现), 而不是一撞见占用就退出.
#
# 不走 .locks/classify_md.lock(三个飞轮+feeder共用的那把锁): 避免OCR长任务占着锁
# 把其它快周期进程卡住数小时; 常规转换部分(可转书)和其它进程的重叠窗口小且幂等
# (先查目标文件是否已存在), 接受这个小概率竞争.
#
# 用法:  nohup bash scripts/ocr_daemon.sh >> math_pipeline/ocr_daemon.log 2>&1 &
# 可选:  OCR_DAEMON_IDLE=1800 (每轮间隔秒, 默认1800=30min; 积压清完后才会真正睡这么久,
#        有积压时一次invocation本身就会跑很久, 循环体感知不到这个间隔)
set -uo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
IDLE="${OCR_DAEMON_IDLE:-1800}"

export MATH_CONVERT_AUTO_OCR=1
export ADVMATH_CONVERT_AUTO_OCR=1
export DATABASE_URL="${DATABASE_URL:-postgresql://aii:aii_safe_pass@localhost:5435/aii_kg}"

echo "════════════════════════════════════════════════════"
echo "★ OCR自动化守护启动 $(date '+%Y-%m-%d %H:%M')  (每 ${IDLE}s 一轮)"
echo "════════════════════════════════════════════════════"

while true; do
    echo "── [OCR守护] $(date '+%H:%M') 开始一轮(数学) ──"
    $PY math_convert.py --do 2>&1
    echo "── [OCR守护] $(date '+%H:%M') 开始一轮(经济) ──"
    $PY econ_convert.py --do 2>&1
    echo "── [OCR守护] $(date '+%H:%M') 开始一轮(高级数学经济专用) ──"
    $PY scripts/advmath_convert.py --do 2>&1 | grep -vE "^MuPDF error"
    echo "── [OCR守护] $(date '+%H:%M') 本轮完成; sleep ${IDLE}s ──"
    sleep "$IDLE"
done
