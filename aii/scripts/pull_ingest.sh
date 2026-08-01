#!/usr/bin/env bash
# ★统一"主动拉料": D盘书源同步 + 本地新投PDF转换 + stratum分类池分拣, 一次做全.
# feeder 和三个业务飞轮(econ-zh/misc/math-prog)都调这一个脚本(而非各自重复逻辑),
# 外层调用者负责用 flock 互斥(同时挪/转同一文件会炸), 见 .locks/classify_md.lock。
set -uo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python

# 0. D盘下载位置(/mnt/d/books/{数学,Economic}) → 真正被飞轮监听的 /home/soffy/books/{数学,Economic}
#    (下载完成的才同步; .crdownload/.part/.tmp 是浏览器还没下完的, 跳过)
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

# 0b. Google Drive 书源同步(由 auto_classify_books.py 分类落地的学科夹) → 本地对应待转目录
#     独立超时+||true: 代理挂/无网/未授权都不许拖垮或中断飞轮; 未同步文件照常转。
timeout 300 bash scripts/math_drive_sync.sh 2>&1 | sed 's/^/  /' || true
timeout 300 bash scripts/econ_drive_sync.sh 2>&1 | sed 's/^/  /' || true
timeout 300 bash scripts/misc_drive_sync.sh 2>&1 | sed 's/^/  /' || true

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

# 1. 本地新投PDF(含刚从D盘/Drive同步来的) → MD
$PY math_convert.py --do 2>&1 | grep -cE '✓ \[' | sed 's/^/  math_convert 新转: /'
$PY econ_convert.py --do 2>&1 | grep -cE '✓ \[' | sed 's/^/  econ_convert 新转: /'
$PY misc_convert.py --do 2>&1 | grep -cE '✓ \[' | sed 's/^/  misc_convert 新转: /'

# 2. stratum 抓好的 MD(/shared/stratum-to-aii) → 分类入 books/MD/{经济学|中英文数学|其它}
$PY classify_md.py --do 2>&1 | tail -1
