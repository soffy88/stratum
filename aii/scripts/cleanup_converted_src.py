#!/usr/bin/env python3
"""★2026-08-10 清理已转 MD 的源文件(PDF/EPUB)省磁盘(94%满)。

安全规则:
  - 只删「对应 MD 已存在」的源文件(转换产物在, 源可弃)
  - 需OCR/打不开/无章节的源文件保留(将来可能重处理)
  - KEEP_SRC=1 环境变量 → 只统计不删(dry-run)

用法: .venv/bin/python scripts/cleanup_converted_src.py [--dry-run]
"""
import os
import re
import sys
from pathlib import Path

BOOKS = Path("/home/soffy/books")
MD = BOOKS / "MD"

# 源目录 → 对应 MD 目录(可多个)
SRC_TO_MD = {
    "数学": ["中文数学", "英文数学"],
    "Economic": ["经济学"],
    "其它": ["其它"],
    "教辅": ["教辅"],
    "计算机": ["计算机"],
}

EXT = (".pdf", ".epub")
DRY = "--dry-run" in sys.argv or os.getenv("KEEP_SRC") == "1"


def _norm(s: str) -> str:
    s = re.sub(r"\(z-lib[^)]*\)|\(z-library[^)]*\)|\([^)]*1lib[^)]*\)", "", s, flags=re.I)
    s = re.sub(r"\s*\([^)]*\)\s*$", "", s)  # 尾部作者括号
    s = re.sub(r"[^\w\u4e00-\u9fff-]+", "", s)
    return s.lower()


def main() -> int:
    md_names = {}
    for src_name, md_dirs in SRC_TO_MD.items():
        for md_dir in md_dirs:
            d = MD / md_dir
            if not d.exists():
                continue
            for md in d.glob("*.md"):
                md_names[_norm(md.stem)] = md
    print(f"已转 MD 索引: {len(md_names)} 个")

    removed = 0
    freed = 0
    for src_name, md_dirs in SRC_TO_MD.items():
        src_dir = BOOKS / src_name
        if not src_dir.exists():
            continue
        for f in list(src_dir.glob(f"*{EXT[0]}")) + list(src_dir.glob(f"*{EXT[1]}")):
            if _norm(f.stem) not in md_names:
                continue
            size = f.stat().st_size
            if DRY:
                print(f"  [dry] 可删: {f.name[:55]} ({size // 1048576}MB)")
                removed += 1
                freed += size
            else:
                try:
                    f.unlink()
                    removed += 1
                    freed += size
                except OSError as e:
                    print(f"  ⚠ 删失败 {f.name[:40]}: {e}")
    print(f"\n{'[dry-run] 可清理' if DRY else '已清理'}: {removed} 个, 释放 {freed // 1048576} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
