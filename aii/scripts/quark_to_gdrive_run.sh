#!/usr/bin/env bash
# ★夸克网盘 → GDrive 流式同步守护脚本
# 持续把夸克新增书籍流式转移到 GDrive，上传成功后即刻删除本地缓存与夸克源文件。
#
# 用法:
#   nohup bash scripts/quark_to_gdrive_run.sh >> quark_pipeline/quark_gdrive_sync.log 2>&1 &
set -uo pipefail
cd "$(dirname "$0")/.."

mkdir -p .locks quark_pipeline /data/soffy/scratch/quark_transit
exec 9>.locks/quark_sync.lock
if ! flock -n 9; then
    echo "  [quark_sync] 已有同步进程在跑(锁存在)，跳过"
    exit 0
fi

echo "════════════════════════════════════════════════════"
echo "★ 夸克网盘 → GDrive 持续流式同步 $(date '+%Y-%m-%d %H:%M:%S')"
echo "════════════════════════════════════════════════════"

# 夸克 API 国内直连，避免被本地代理阻断或风控
# rclone 会自动尊重系统的 HTTPS_PROXY (7890) 连接 Google Drive
.venv/bin/python scripts/quark_to_gdrive_sync.py --sync-only
EXIT_CODE=$?

echo "════════════════════════════════════════════════════"
echo "★ 夸克同步结束 ($(date '+%Y-%m-%d %H:%M:%S')), exit code: $EXIT_CODE"
echo "════════════════════════════════════════════════════"
exit $EXIT_CODE
