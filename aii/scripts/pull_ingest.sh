#!/usr/bin/env bash
# ★统一"主动拉料": D盘书源同步 + 本地新投PDF转换 + stratum分类池分拣, 一次做全.
# feeder 和三个业务飞轮(econ-zh/misc/math-prog)都调这一个脚本(而非各自重复逻辑),
# 外层调用者负责用 flock 互斥(同时挪/转同一文件会炸), 见 .locks/classify_md.lock。
set -uo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python

# 书源切换为 GDrive 只读挂载时：源文件只从 /home/soffy/books 读取，
# 转换产物写入项目内 gdrive_staging，绝不向 FUSE 源目录写入/删除。
GDRIVE_MOUNT_ACTIVE=0
if mountpoint -q /home/soffy/books && findmnt -T /home/soffy/books -no source 2>/dev/null | grep -Eq '^gdrive(-rw)?:'; then
  GDRIVE_MOUNT_ACTIVE=1
  echo "  GDrive 只读书源已挂载：源文件直读，转换产物写入 gdrive_staging"
fi

# 0. D盘下载位置(/mnt/d/books/{数学,Economic}) → 真正被飞轮监听的 /home/soffy/books/{数学,Economic}
#    (下载完成的才同步; .crdownload/.part/.tmp 是浏览器还没下完的, 跳过)
if [ "$GDRIVE_MOUNT_ACTIVE" -eq 0 ]; then
for sub in 数学 Economic; do
    SRC_D="/mnt/d/books/$sub" DST_D="/home/soffy/books/$sub" $PY - << 'PYEOF'
import os, shutil
src_dir, dst_dir = os.environ["SRC_D"], os.environ["DST_D"]
if not os.path.isdir(src_dir):
    raise SystemExit(0)
os.makedirs(dst_dir, exist_ok=True)


def safe_name(n):
    # ext4 单文件名上限255字节; 中文长书名常见超限(实测撞过300字节的). 原逻辑先按原名试
    # copy2, 失败(OSError)才截断重试落盘——但下一轮 src-dst diff 仍按"原名"比对, 截断后
    # 的文件名永远对不上原名, 于是这本书每轮都被判定成"新文件"重新拷贝一遍, 从不消失。
    # 改成入口处就统一算好目标名(超限则预先截断), diff 和实际落盘用同一个名字, 幂等。
    if len(n.encode("utf-8")) <= 255:
        return n
    base, ext = os.path.splitext(n)
    return base.encode("utf-8")[:200].decode("utf-8", errors="ignore") + ext


dst = set(os.listdir(dst_dir))
new = sorted(n for n in os.listdir(src_dir) if safe_name(n) not in dst)
copied = 0
for n in new:
    if n.endswith((".crdownload", ".part", ".tmp")):
        continue
    sp = os.path.join(src_dir, n)
    if not os.path.isfile(sp):
        continue  # 子文件夹(如按书名建的目录)不是待投书, 跳过
    try:
        shutil.copy2(sp, os.path.join(dst_dir, safe_name(n)))
        copied += 1
    except OSError:
        continue
if copied:
    print(f"  D盘同步[{dst_dir}]: {copied} 本新增")
PYEOF
done

# 0a. USB 移动硬盘书源同步(替代 D 盘, 2026-08-22) — 挂载点: /run/media/soffy/<UUID>/books
#     可覆写 USB_SRC 指向其它挂载点; 未挂载时静默跳过。
timeout 1800 bash scripts/usb_drive_sync.sh 2>&1 | sed 's/^/  /' || true

# 0b. Google Drive 书源同步(由 auto_classify_books.py 分类落地的学科夹) → 本地对应待转目录
#     独立超时+||true: 代理挂/无网/未授权都不许拖垮或中断飞轮; 未同步文件照常转。
#     ★与 refill_feed 共用同一把锁：空转补料可能和本脚本同时被多个飞轮唤起，
#     不锁会让两个 rclone 同时写同一目录、重复消耗 Drive 配额并制造半成品。
run_gdrive_sync() {
  # Drive 上的教辅/计算机/论文是独立源目录，原先只同步 math/econ/misc，
  # 导致这三条飞轮长期看到空书单，GDrive 新书一直留在远端。
  # 和其它同步脚本共用同一预算、过滤器与超时；只增量 copy，不删除本地文件。
  # 多个飞轮都会触发 pull_ingest；不能每 60s 对 Drive 做一次全量目录列举，
  # 否则共享 Google API client 很快撞 Queries/min quota，反而让新书同步失败。
  local sync_stamp=".locks/.last_gdrive_sync"
  local sync_interval="${GDRIVE_SYNC_INTERVAL:-300}"
  local now="$(date +%s)" last=0
  if [ -f "$sync_stamp" ]; then
    last="$(stat -c %Y "$sync_stamp" 2>/dev/null || echo 0)"
  fi
  if [ "${GDRIVE_FORCE_SYNC:-0}" != "1" ] && [ $((now - last)) -lt "$sync_interval" ]; then
    echo "  GDrive 同步限频：距上次不足 ${sync_interval}s，跳过远端列举"
    return 0
  fi
  local rclone_bin="${RCLONE_BIN:-$HOME/.local/bin/rclone}"
  if [ ! -x "$rclone_bin" ]; then
    echo "  GDrive 同步跳过：未找到 $rclone_bin"
    return 0
  fi
  if ! timeout 5 "$rclone_bin" lsd gdrive: >/dev/null 2>&1; then
    echo "  GDrive 远端不可用(鉴权失效或网络不可达)，跳过本次同步"
    return 0
  fi
  # math/econ/misc 的专用同步脚本从环境读取该值；必须 export，
  # 仅在此处声明 local 会让它们悄悄退回各自的 256M 默认值。
  export RCLONE_MAX_TRANSFER="${RCLONE_MAX_TRANSFER:-2G}"
  local max_transfer="$RCLONE_MAX_TRANSFER"
  local -a flags=(--fast-list --transfers 8 --checkers 8 --max-transfer "$max_transfer"
                  --cutoff-mode SOFT --include '*.pdf' --include '*.epub')
  sync_drive_bucket() {
    local remote_path="$1" dest="$2"
    if [ ! -x "$rclone_bin" ]; then
      echo "  GDrive 同步跳过：未找到 $rclone_bin"
      return 0
    fi
    echo "  GDrive 补料: gdrive:$remote_path → $dest"
    timeout 600 "$rclone_bin" copy "gdrive:$remote_path" "$dest" "${flags[@]}" --stats-one-line 2>&1 \
      | tail -n 5 || true
  }

  timeout 300 bash scripts/math_drive_sync.sh 2>&1 | sed 's/^/  /' || true
  timeout 300 bash scripts/econ_drive_sync.sh 2>&1 | sed 's/^/  /' || true
  timeout 300 bash scripts/misc_drive_sync.sh 2>&1 | sed 's/^/  /' || true
  sync_drive_bucket 'books/教辅' '/home/soffy/books/教辅'
  sync_drive_bucket 'books/计算机' '/home/soffy/books/计算机'
  sync_drive_bucket 'books/论文' '/home/soffy/books/论文'
  touch "$sync_stamp"
}
mkdir -p .locks
if [ "${GDRIVE_LOCK_HELD:-0}" = "1" ]; then
  run_gdrive_sync
else
  exec 8>.locks/gdrive_refill.lock
  if flock -n 8; then
    run_gdrive_sync
  else
    echo "  GDrive 同步已在运行，本轮跳过同步，继续转换已有源文件"
  fi
fi

# 0c. 合集本 epub 自动拆分 (每天最多跑一次, 避免每轮 10min 重复扫描大 epub)
#     检测 >20MB + 文件名含"套装/全集/共N册"等关键词的 epub → 拆成单本 MD → 分类入库。
SPLIT_STAMP="context_pipeline/.last_split_epub"
SPLIT_INTERVAL=86400  # 24h
if [ -f "$SPLIT_STAMP" ]; then
  LAST_SPLIT=$(stat -c %Y "$SPLIT_STAMP" 2>/dev/null || echo 0)
  NOW=$(date +%s)
  ELAPSED=$(( NOW - LAST_SPLIT ))
else
  ELAPSED=999999
fi
if [ "$ELAPSED" -ge "$SPLIT_INTERVAL" ]; then
  echo "★ 合集本拆分 (每日一次) $(date '+%H:%M')"
  timeout 600 $PY scripts/split_collection_epub.py --do 2>&1 | grep -E '✅|合集|拆分完成|跳过' | sed 's/^/  /' || true
  touch "$SPLIT_STAMP"
fi
fi

# 1. 本地新投PDF(含刚从D盘/Drive同步来的) → MD 转换
# ★2026-08-27 限流: 5 并发曾把 stratum-docs 容器 CPU 727% 拉爆, 改 2 并发(misc/edu/cs
# 这 3 串行目录不并发, 由独立的 scripts/bulk_convert.sh 后台跑, 避免和主飞轮抢资源).
# 主飞轮关心 math/econ 新书, 2 并发 math+econ 完全够; misc/edu/cs 走全量脚本, 不阻塞主线.
if [ "$GDRIVE_MOUNT_ACTIVE" -eq 1 ]; then
  STAGE_ROOT="${GDRIVE_STAGE_ROOT:-/data/soffy/projects/stratum/aii/gdrive_staging/MD}"
  mkdir -p "$STAGE_ROOT"/{中文数学,英文数学,经济学,其它,教辅,计算机,论文}
  KEEP_SRC=1 CONVERT_SRC=/home/soffy/books/数学 CONVERT_DST_ROOT="$STAGE_ROOT" \
    $PY math_convert.py --do 2>&1 | grep -cE '✓ \[' | sed 's/^/  gdrive math_convert 新转: /' &
  KEEP_SRC=1 CONVERT_SRC=/home/soffy/books/Economic CONVERT_DST="$STAGE_ROOT/经济学" \
    $PY econ_convert.py --do 2>&1 | grep -cE '✓ \[' | sed 's/^/  gdrive econ_convert 新转: /' &
  wait
  timeout --kill-after=30s 3600 env DOCS_TIMEOUT=300 KEEP_SRC=1 CONVERT_SRC=/home/soffy/books/其它 CONVERT_DST="$STAGE_ROOT/其它" CONVERT_TAG=其它 $PY misc_convert.py --do 2>&1 | grep -cE '✓ \[' | sed 's/^/  gdrive misc_convert 新转: /' || true
  timeout --kill-after=30s 3600 env DOCS_TIMEOUT=300 KEEP_SRC=1 CONVERT_SRC=/home/soffy/books/教辅 CONVERT_DST="$STAGE_ROOT/教辅" CONVERT_TAG=教辅 $PY misc_convert.py --do 2>&1 | grep -cE '✓ \[' | sed 's/^/  gdrive edu_convert 新转: /' || true
  timeout --kill-after=30s 3600 env DOCS_TIMEOUT=300 KEEP_SRC=1 CONVERT_SRC=/home/soffy/books/计算机 CONVERT_DST="$STAGE_ROOT/计算机" CONVERT_TAG=计算机 $PY misc_convert.py --do 2>&1 | grep -cE '✓ \[' | sed 's/^/  gdrive cs_convert 新转: /' || true
  timeout --kill-after=30s 3600 env DOCS_TIMEOUT=300 KEEP_SRC=1 CONVERT_SRC=/home/soffy/books/论文 CONVERT_DST="$STAGE_ROOT/论文" CONVERT_TAG=论文 $PY misc_convert.py --do 2>&1 | grep -cE '✓ \[' | sed 's/^/  gdrive paper_convert 新转: /' || true
else
  $PY math_convert.py --do 2>&1 | grep -cE '✓ \[' | sed 's/^/  math_convert 新转: /' &
  $PY econ_convert.py --do 2>&1 | grep -cE '✓ \[' | sed 's/^/  econ_convert 新转: /' &
  wait
  timeout --kill-after=30s 600 $PY misc_convert.py --do 2>&1 | grep -cE '✓ \[' | sed 's/^/  misc_convert 新转: /' || true
  timeout --kill-after=30s 600 env CONVERT_SRC=/home/soffy/books/教辅 CONVERT_DST=/home/soffy/books/MD/教辅 CONVERT_TAG=教辅 $PY misc_convert.py --do 2>&1 | grep -cE '✓ \[' | sed 's/^/  edu_convert 新转: /' || true
  timeout --kill-after=30s 600 env CONVERT_SRC=/home/soffy/books/计算机 CONVERT_DST=/home/soffy/books/MD/计算机 CONVERT_TAG=计算机 $PY misc_convert.py --do 2>&1 | grep -cE '✓ \[' | sed 's/^/  cs_convert 新转: /' || true
  timeout --kill-after=30s 600 env CONVERT_SRC=/home/soffy/books/论文 CONVERT_DST=/home/soffy/books/MD/论文 CONVERT_TAG=论文 $PY misc_convert.py --do 2>&1 | grep -cE '✓ \[' | sed 's/^/  paper_convert 新转: /' || true
fi
echo "  ★ convert 完成 (2 并发主线 + 3 串行备用)"

# 2. stratum 抓好的 MD(/shared/stratum-to-aii) → 分类入 books/MD/{经济学|中英文数学|其它}
if [ "$GDRIVE_MOUNT_ACTIVE" -eq 0 ]; then
  $PY classify_md.py --do 2>&1 | tail -1
else
  echo "  GDrive 只读书源模式：跳过 classify_md 写入挂载目录"
fi

# 2b. 元数据增强：给生成的 MD 注入 author/publisher/coverUrl/ISBN 等前置字段
#     仅依赖 OpenLibrary+iTunes(无 key), 有 Google Books key 时自动加入 google provider
#     耗时 ~1-3s/本, 对 1000 本约 10-30min, 可设 DRY_RUN=1 测试
if command -v $PY >/dev/null; then
  echo "★ 元数据增强 (batch_enrich_metadata.py) $(date '+%H:%M')"
  # ★2026-08-27 路径修复: 该脚本在 stratum/scripts/ 不在 aii/scripts/, 改用绝对路径.
  # 当前 AII 虚拟环境可能没有可选的 oskill.book_metadata 插件；不能让每轮刷 Traceback。
  if $PY -c 'import oskill.book_metadata.pipeline' >/dev/null 2>&1; then
    DRY_RUN=${DRY_RUN:-0} $PY /data/soffy/projects/stratum/scripts/batch_enrich_metadata.py --dir /data/soffy/books/MD 2>&1 \
      | tail -20 | sed 's/^/  /'
  else
    echo "  元数据增强跳过：当前 AII 环境未安装 oskill.book_metadata（可选插件）"
  fi
fi
