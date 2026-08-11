#!/usr/bin/env bash
# econ_drive_sync.sh — 把 Google Drive 上 books/经济金融(由 auto_classify_books.py 分类落地)
# 的经济源文件同步到本地 books/Economic, 供 econ_convert.py 转换消费。
# 仿 math_drive_sync.sh, 区别: 按路径寻址(该目录由分类脚本持续写入, 不是固定文件夹, 不用硬编码ID)。
#
# 用法:  ./econ_drive_sync.sh            # 拉新文件
#        DRIVE_DRY=1 ./econ_drive_sync.sh  # 只看会拉哪些, 不下载
# 触发:  挂在 pull_ingest.sh

set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"

: "${RCLONE_PROXY=http://127.0.0.1:7890}"
if [ -n "${RCLONE_PROXY}" ] && [ -z "${HTTPS_PROXY:-}" ]; then
  export HTTPS_PROXY="${RCLONE_PROXY}" HTTP_PROXY="${RCLONE_PROXY}"
  export NO_PROXY="localhost,127.0.0.1,::1,192.168.0.0/24,100.64.0.0/10,.local"
  export no_proxy="${NO_PROXY}"
fi

RCLONE_REMOTE="${RCLONE_REMOTE:-gdrive}"
DRIVE_PATH="${DRIVE_PATH:-books/经济金融}"
DEST="${DEST:-/home/soffy/books/Economic}"

command -v rclone >/dev/null || { echo "[econ_drive_sync] rclone 未安装 (~/.local/bin/rclone)"; exit 1; }
if ! rclone listremotes 2>/dev/null | grep -qx "${RCLONE_REMOTE}:"; then
  echo "[econ_drive_sync] remote '${RCLONE_REMOTE}:' 未配置"
  exit 2
fi

mkdir -p "${DEST}"

FLAGS=(--include "*.pdf" --include "*.epub")
if [ "${DRIVE_DRY:-0}" = "1" ]; then
  echo "[econ_drive_sync] DRY: 将要拉取的新文件:"
  rclone copy "${RCLONE_REMOTE}:${DRIVE_PATH}" "${DEST}" "${FLAGS[@]}" --dry-run 2>&1 | grep -iE "copy|transfer" | head -50 || true
else
  echo "[econ_drive_sync] 拉取新文件 ${RCLONE_REMOTE}:${DRIVE_PATH} → ${DEST} …"
  rclone copy "${RCLONE_REMOTE}:${DRIVE_PATH}" "${DEST}" "${FLAGS[@]}" --stats-one-line
fi
echo "[econ_drive_sync] 完成。"
