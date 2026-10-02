#!/usr/bin/env bash
# ★断料主动补料: 飞轮 discover 到无新书(空转)时, 主动触发 Google Drive 同步一轮.
#   2026-08-29 改造: gdrive 已有 1800+ 本新书(PDF/EPUB), 不必再走夸克;
#   夸克老 token 持续 412 Precondition Failed, 改用 rclone 拉 gdrive.
#   与 pull_ingest.sh 内嵌的 0b gdrive 同步构成双保险: 定时拉 + 断料即时拉.
#   幂等: rclone copy 按文件名去重, 重复触发不会重复下载.
set -uo pipefail
cd "$(dirname "$0")/.."
# systemd --user 的精简 PATH 不包含 ~/.local/bin；rclone 安装在这里。
# 子脚本里的 PATH 设置不会回传给父进程。
export PATH="$HOME/.local/bin:$PATH"
# GDrive API 在当前网络环境需要走本机代理；各 drive_sync 子脚本已有同样设置，
# 这里的直接 rclone 路径也必须显式继承，否则会直连 SYN-SENT 并耗尽超时。
: "${RCLONE_PROXY=http://127.0.0.1:7890}"
if [ -n "${RCLONE_PROXY}" ] && [ -z "${HTTPS_PROXY:-}" ]; then
  export HTTPS_PROXY="${RCLONE_PROXY}" HTTP_PROXY="${RCLONE_PROXY}"
  export NO_PROXY="localhost,127.0.0.1,192.168.80.1,::1,192.168.0.0/24,100.64.0.0/10,.local"
export no_proxy="${NO_PROXY}"
fi

# /home/soffy/books 已经是 aii-books 的只读 GDrive 挂载时，飞轮直接消费挂载内容。
# 禁止旧的 gdrive:books/* copy 链路反复列举/写入只读挂载，避免 Drive API 配额风暴。
if mountpoint -q /home/soffy/books && findmnt -T /home/soffy/books -no source 2>/dev/null | grep -Eq '^gdrive(-rw)?:'; then
  echo "  [refill] aii-books GDrive 只读挂载已就绪：跳过旧补料 copy，飞轮直接读取 /home/soffy/books"
  exit 0
fi

LOCK=.locks/gdrive_refill.lock
mkdir -p .locks
exec 9>"$LOCK"
flock -n 9 || { echo "  [refill] gdrive 同步已在跑(跳过本轮)"; exit 0; }

# 探测 gdrive 远端是否可用(避免在 token 失效时对每个学科目录都等待 900s 超时)
if ! timeout 5 rclone lsd gdrive: >/dev/null 2>&1; then
  echo "  [refill] gdrive 远端不可用(鉴权失效或网络不可达)，跳过本次补料"
  exit 0
fi

echo "  [refill] $(date '+%F %H:%M') 空转触发 gdrive 补料..."
# 大目录用 fast-list；每个目录独立超时，单个远端异常不拖死后续学科。
RCLONE_MAX_TRANSFER="${RCLONE_MAX_TRANSFER:-2G}"
RCLONE_COPY_FLAGS=(--fast-list --transfers 8 --checkers 8 --max-transfer "$RCLONE_MAX_TRANSFER" --cutoff-mode SOFT --include "*.pdf" --include "*.epub" --stats-one-line)
REFILL_FAIL=0
sync_one() {
  local remote="$1" dest="$2" rc
  mkdir -p "$dest"
  echo "  [refill] $remote → $dest"
  timeout 900 rclone copy "$remote" "$dest" "${RCLONE_COPY_FLAGS[@]}" 2>&1 | tail -3
  rc=${PIPESTATUS[0]}
  if [ "$rc" -eq 8 ]; then
    # rclone 用 8 表示 --max-transfer 达到本轮预算；不是同步故障，下一轮续传。
    echo "  [refill] 本轮达到 ${RCLONE_MAX_TRANSFER} 上限，下一轮续传"
  elif [ "$rc" -ne 0 ]; then
    echo "  [refill] 该目录失败 rc=$rc，继续下一个"
    REFILL_FAIL=1
  fi
}

sync_one gdrive:books/教辅 /home/soffy/books/教辅
sync_one gdrive:books/计算机 /home/soffy/books/计算机
sync_one gdrive:books/经济金融 /home/soffy/books/Economic
sync_one gdrive:books/Economic /home/soffy/books/Economic
sync_one gdrive:books/数学 /home/soffy/books/数学
sync_one gdrive:books/论文 /home/soffy/books/论文
echo "  [refill] $(date '+%H:%M') gdrive 补料结束 rc=$REFILL_FAIL"

# 同步完立即触发 pull_ingest (flock 互斥), 让 feeder 看到新 PDF 调度转换
mkdir -p .locks
GDRIVE_LOCK_HELD=1 flock -n .locks/classify_md.lock -c "timeout --kill-after=30s 600 bash scripts/pull_ingest.sh" > .logs/pull_ingest_refill.out 2>&1 || true
echo "  [refill] $(date '+%H:%M') pull_ingest 调度完成"
exit 0
