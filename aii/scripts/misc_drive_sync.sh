#!/usr/bin/env bash
# misc_drive_sync.sh — 把 Google Drive 上 books/{哲学,社科心理,科学,量化与AI}
# (由 auto_classify_books.py 分类落地, 4个学科夹合并进misc飞轮同一个消费池)
# 的源文件同步到本地 books/其它, 供 misc_convert.py 转换消费。
# 仿 math_drive_sync.sh, 区别: 四个Drive源文件夹 → 一个本地目录。
#
# 用法:  ./misc_drive_sync.sh            # 拉新文件
#        DRIVE_DRY=1 ./misc_drive_sync.sh  # 只看会拉哪些, 不下载
# 触发:  挂在 pull_ingest.sh

set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"

: "${RCLONE_PROXY=http://127.0.0.1:7890}"
if [ -n "${RCLONE_PROXY}" ] && [ -z "${HTTPS_PROXY:-}" ]; then
  export HTTPS_PROXY="${RCLONE_PROXY}" HTTP_PROXY="${RCLONE_PROXY}"
fi

RCLONE_REMOTE="${RCLONE_REMOTE:-gdrive}"
DEST="${DEST:-/home/soffy/books/其它}"
SUBFOLDERS=(哲学 社科心理 科学 量化与AI all)

command -v rclone >/dev/null || { echo "[misc_drive_sync] rclone 未安装 (~/.local/bin/rclone)"; exit 1; }
if ! rclone listremotes 2>/dev/null | grep -qx "${RCLONE_REMOTE}:"; then
  echo "[misc_drive_sync] remote '${RCLONE_REMOTE}:' 未配置"
  exit 2
fi

mkdir -p "${DEST}"

FLAGS=(--include "*.pdf" --include "*.epub")
for sub in "${SUBFOLDERS[@]}"; do
  if [ "${DRIVE_DRY:-0}" = "1" ]; then
    echo "[misc_drive_sync] DRY(${sub}): 将要拉取的新文件:"
    rclone copy "${RCLONE_REMOTE}:books/${sub}" "${DEST}" "${FLAGS[@]}" --dry-run 2>&1 | grep -iE "copy|transfer" | head -50 || true
  else
    echo "[misc_drive_sync] 拉取新文件 ${RCLONE_REMOTE}:books/${sub} → ${DEST} …"
    rclone copy "${RCLONE_REMOTE}:books/${sub}" "${DEST}" "${FLAGS[@]}" --stats-one-line
  fi
done
echo "[misc_drive_sync] 完成。"
