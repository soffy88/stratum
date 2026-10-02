#!/usr/bin/env bash
# ★ 夸克网盘 [2.BBC纪录片] & [4.教辅与外语] & [B站付费课程] 流式迁移守护脚本
# 零磁盘直连 Google Drive，边上传边校验边删除夸克原文件，直至达到减负目标。
set -euo pipefail
cd "$(dirname "$0")/.."

ulimit -n 65535 2>/dev/null || true

export http_proxy="http://127.0.0.1:7890"
export https_proxy="http://127.0.0.1:7890"
export no_proxy="localhost,127.0.0.1,::1,192.168.0.0/24,192.168.1.0/24,100.64.0.0/10,.local,.quark.cn,quark.cn"

mkdir -p .locks quark_pipeline
exec 8>.locks/quark_streamer.lock
if ! flock -n 8; then
    echo "  [quark_streamer] 已有流式转移守护进程在运行中，跳过"
    exit 0
fi

echo "════════════════════════════════════════════════════"
echo "★ 启动夸克网盘流式转移守护任务 $(date '+%Y-%m-%d %H:%M:%S')"
echo "════════════════════════════════════════════════════"

while true; do
    if python3 -u scripts/quark_to_gdrive_streamer.py >> quark_pipeline/quark_transfer_2_4.log 2>&1; then
        echo "  [quark_streamer] 任务达标正常结束。" >> quark_pipeline/quark_transfer_2_4.log
        break
    fi
    echo "  [quark_streamer] 进程异常退出，10秒后自动重试续传..." >> quark_pipeline/quark_transfer_2_4.log
    sleep 10
done
