#!/usr/bin/env bash
# math_drive_sync.sh — 把 Google Drive 上的数学源文件同步到本地 books/数学,
# 并写出 基名→Drive直链 映射(.driveid.json), 供 math_convert.py 写进 MD frontmatter 的 source_url。
#
# 前置(一次性): 配好一个名为 gdrive 的 rclone Drive remote(见本仓 aii/deploy/ 或 README 里的 OAuth 步骤)。
#   rclone config create gdrive drive scope=drive.readonly   # 走一次浏览器授权
#
# 用法:  ./math_drive_sync.sh            # 拉新文件 + 刷新 .driveid.json
#        DRIVE_DRY=1 ./math_drive_sync.sh  # 只看会拉哪些, 不下载
# 触发:  可挂到 math 飞轮每轮开头, 或单独 cron/systemd timer。
#
# 环境变量:
#   RCLONE_REMOTE   remote 名           (默认 gdrive)
#   DRIVE_FOLDER_ID Drive 文件夹 ID     (默认下方常量, 来自用户给的文件夹链接)
#   DEST            本地落地目录         (默认 /home/soffy/books/数学)

set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"

RCLONE_REMOTE="${RCLONE_REMOTE:-gdrive}"
DRIVE_FOLDER_ID="${DRIVE_FOLDER_ID:-1tbxwprHUfM0rjaCtTJGdGah70Pk2Wt-k}"
DEST="${DEST:-/home/soffy/books/数学}"
MAP="${DEST}/.driveid.json"

command -v rclone >/dev/null || { echo "[drive_sync] rclone 未安装 (~/.local/bin/rclone)"; exit 1; }
if ! rclone listremotes 2>/dev/null | grep -qx "${RCLONE_REMOTE}:"; then
  echo "[drive_sync] remote '${RCLONE_REMOTE}:' 未配置 — 先跑一次 OAuth:"
  echo "             rclone config create ${RCLONE_REMOTE} drive scope=drive.readonly"
  exit 2
fi

mkdir -p "${DEST}"

# 1) 列目录(递归, 只文件), 拿到每个文件的 Drive ID → 写 基名→直链 映射
echo "[drive_sync] 列举 Drive 文件夹 ${DRIVE_FOLDER_ID} …"
LSJSON=$(rclone lsjson --drive-root-folder-id "${DRIVE_FOLDER_ID}" "${RCLONE_REMOTE}:" --files-only -R)
python3 - "$MAP" <<PY
import json, sys
rows = json.loads('''${LSJSON}''')
m = {}
for r in rows:
    name = r.get("Name", "")
    if not name.lower().endswith((".pdf", ".epub")):
        continue
    fid = r.get("ID")
    if not fid:
        continue
    # 同名(不同子目录)后者覆盖前者 — 数学书基名基本唯一, 够用
    m[name] = f"https://drive.google.com/file/d/{fid}/view"
json.dump(m, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print(f"[drive_sync] 写映射 {sys.argv[1]}: {len(m)} 个文件")
PY

# 2) 拉取(copy=只增不删; 已存在的按大小/校验跳过)
FLAGS=(--include "*.pdf" --include "*.epub")
if [ "${DRIVE_DRY:-0}" = "1" ]; then
  echo "[drive_sync] DRY: 将要拉取的新文件:"
  rclone copy --drive-root-folder-id "${DRIVE_FOLDER_ID}" "${RCLONE_REMOTE}:" "${DEST}" "${FLAGS[@]}" --dry-run 2>&1 | grep -iE "copy|transfer" | head -50 || true
else
  echo "[drive_sync] 拉取新文件到 ${DEST} …"
  rclone copy --drive-root-folder-id "${DRIVE_FOLDER_ID}" "${RCLONE_REMOTE}:" "${DEST}" "${FLAGS[@]}" --stats-one-line
fi
echo "[drive_sync] 完成。"
