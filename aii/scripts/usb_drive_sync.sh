#!/usr/bin/env bash
# ★USB 移动硬盘书源同步 — 把 /run/media/soffy/6A0C01100C00D8C9/books/ 下的书
#   同步到本地 /home/soffy/books/{数学,Economic,其它} 待转目录。
# 挂载点: 移动硬盘通常是 /run/media/soffy/<UUID>/books/
# 用法:  ./usb_drive_sync.sh           # 同步新文件
#        USB_DRY=1 ./usb_drive_sync.sh  # 只看不拷
# 触发: 挂在 pull_ingest.sh 第 0d 步
set -uo pipefail
cd "$(dirname "$0")/.."

USB_SRC="${USB_SRC:-/run/media/soffy/6A0C01100C00D8C9/books}"
DRY="${USB_DRY:-0}"

if [ ! -d "$USB_SRC" ]; then
    echo "[usb_drive_sync] USB 移动硬盘未挂载: $USB_SRC"
    exit 0
fi

echo "★ USB 移动硬盘书源同步 $(date '+%H:%M')"
echo "  源: $USB_SRC"

mkdir -p /home/soffy/books/数学 /home/soffy/books/Economic /home/soffy/books/其它

# ─── 按学科分类拷入本地待转目录 ───
# 规则: 文件名含关键词决定目标目录; 未知的归"其它"
# ext4 单文件名上限255字节; 中文长书名常见超限(实测 创业工作室手册 超限拷不进去)。
# 超限时截断 base 到 200 字节再落盘, 存在性检查与落盘用同一个名字, 保持幂等。
safe_name() {
    local n="$1"
    if [ "$(printf '%s' "$n" | wc -c)" -le 255 ]; then
        printf '%s' "$n"
        return
    fi
    local base ext
    if printf '%s' "$n" | grep -q '\\.'; then
        ext=".${n##*.}"
        base="${n%.*}"
    else
        base="$n"
        ext=""
    fi
    printf '%s%s' "$(printf '%s' "$base" | head -c 200)" "$ext"
}

sync_file() {
    local f="$1"
    local base
    base=$(basename "$f")
    local low
    low=$(echo "$base" | tr '[:upper:]' '[:lower:]')

    local dst=""
    if echo "$low" | grep -qiE "algebraic|geometry|calculus|实分析|复分析|拓扑|概率|统计|微分|积分|线性代数|mathematics|math_|数理|数学"; then
        dst=数学
    elif echo "$low" | grep -qiE "经济|金融|投资|宏观|微观|市场|贸易|竞争均衡|创业|副业|搞钱|赚钱|商业|财富|公司|startup|business|money|wealth|side hustle|economics|finance|econom|trade|market|invest|entrepreneur|start.?up"; then
        dst=Economic
    else
        dst=其它
    fi

    local target_name
    target_name=$(safe_name "$base")
    local target="/home/soffy/books/$dst/$target_name"
    [ -f "$target" ] && return 0  # 已同步过
    echo "  $base → $dst"
    if [ "$DRY" = "0" ]; then
        cp -n "$f" "$target" || echo "  ⚠ 拷贝失败: $base"
    fi
}

copy_dir() {
    local src_dir="$1"
    local label="$2"
    local count=0
    echo "── $label ──"
    while IFS= read -r f; do
        sync_file "$f"
        count=$((count+1))
    done < <(find "$src_dir" -type f \( -name "*.pdf" -o -name "*.epub" -o -name "*.mobi" \) 2>/dev/null | sort)
    echo "  扫描 $count 文件"
}

# 根目录学术书(只扫顶层文件, 不递归进子目录)
while IFS= read -r f; do
    sync_file "$f"
done < <(find "$USB_SRC" -maxdepth 1 -type f \( -name "*.pdf" -o -name "*.epub" -o -name "*.mobi" \) 2>/dev/null | sort)
# 110本精选搞钱好书(经管/创业类) — 全部归 Economic
copy_dir "$USB_SRC/110本精选搞钱好书" "110本精选搞钱好书"
# 中信见识丛书(历史/社科) — 归 其它
copy_dir "$USB_SRC/中信见识丛书（1-52册）" "中信见识丛书"

echo "✓ USB 同步完成"