#!/usr/bin/env python3
"""batch_enrich_metadata.py — 批量给 MD 文件注入元数据前置。

用法:
  python3 scripts/batch_enrich_metadata.py [--dir MD_DIR] [--dry-run] [--limit N]

- 遍历 MD_DIR 下所有 .md 文件
- 从文件名/frontmatter 提取 title/author
- 调用 oskill.book_metadata.pipeline.run()
- 将结果 merge 进 frontmatter
- 统计成功/失败/跳过数

可作为 pull_ingest.sh 的 step 1b 执行（classify_md 之后）。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from oskill.book_metadata.pipeline import create_default_pipeline, ResolvedMetadataFields
from oskill.book_metadata.types import MetadataSearchParams

FRONTMATTER_RE = __import__("re").compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", __import__("re").DOTALL)


def parse_frontmatter(md_text: str) -> tuple[dict[str, str], str]:
    m = FRONTMATTER_RE.match(md_text.strip())
    if not m:
        return {}, md_text
    fm_text = m.group(1)
    body = m.group(2)
    fm_dict = {}
    for line in fm_text.strip().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fm_dict[k.strip()] = v.strip().strip('"').strip("'")
    return fm_dict, body


def build_frontmatter(fm_dict: dict[str, str], resolved: ResolvedMetadataFields) -> str:
    lines = ["---"]
    # 优先保留现有非空字段
    for k in ["title", "source_file", "source_url", "lang", "converter"]:
        if k in fm_dict and fm_dict[k]:
            lines.append(f"{k}: {fm_dict[k]}")
    resolved_dict = resolved.to_dict()
    for k, v in resolved_dict.items():
        if k not in fm_dict or not fm_dict[k]:
            if k == "seriesMemberships" and v:
                val = "; ".join(f"{m['seriesName']}@{m.get('seriesIndex', '')}" for m in v)
            elif k == "genres" and v:
                val = "; ".join(v)
            elif k == "authors" and v:
                val = ", ".join(v)
            else:
                val = v if not isinstance(v, list) else ", ".join(str(x) for x in v)
            lines.append(f"{k}: {val}")
    for k, v in fm_dict.items():
        if k not in {"title", "source_file", "source_url", "lang", "converter"}:
            lines.append(f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines)


def extract_title_from_filename(path: Path) -> str:
    """从文件名推导书名（去掉 z-lib 等后缀）。"""
    name = path.stem
    # 去掉常见后缀
    import re

    name = re.sub(r"\s*\([^)]*(?:z-lib|z-library|1lib|zlibrary)[^)]*\)", "", name)
    name = re.sub(r"\s*\([^)]*\)", "", name)  # 去掉括号内容
    name = re.sub(r"\s*[-_]{2,}\s*", " ", name)  # 多个分隔符
    name = name.replace("_", " ").replace("-", " ")
    return name.strip()


def enrich_file(filepath: Path, pipeline, dry_run: bool = False) -> tuple[bool, str]:
    """处理单个文件。返回 (成功?, 消息)。"""
    md_text = filepath.read_text(encoding="utf-8")
    fm_dict, body = parse_frontmatter(md_text)

    # 提取已有 title
    existing_title = fm_dict.get("title", "")
    fname_title = extract_title_from_filename(filepath)
    title = existing_title or fname_title

    # 尝试从现有 frontmatter 读取 author（如有）
    author = fm_dict.get("author", None) or fm_dict.get("authors", None)

    # 运行 pipeline
    params = MetadataSearchParams(title=title, author=author)
    result = pipeline.run(params)

    if not result.resolved.title and not result.resolved.authors:
        return False, f"无元数据结果: {title[:50]}"

    new_fm = build_frontmatter(fm_dict, result.resolved)
    new_md = new_fm + "\n" + body if body else new_fm + "\n"

    if not dry_run:
        filepath.write_text(new_md, encoding="utf-8")

    fields = [k for k, v in result.resolved.to_dict().items() if v]
    return True, f"OK: {filepath.name} | 新增: {', '.join(fields)[:60]}"


def main():
    parser = argparse.ArgumentParser(description="批量 MD 元数据注入")
    parser.add_argument(
        "--dir", default="/data/soffy/books/MD", help="MD 根目录 (默认 /data/soffy/books/MD)"
    )
    parser.add_argument("--dry-run", action="store_true", help="只打印不写入")
    parser.add_argument("--limit", type=int, default=0, help="限制处理文件数 (0=不限)")
    parser.add_argument(
        "--skip-unchanged", action="store_true", help="跳过已有 coverUrl/author/publisher 的文件"
    )
    args = parser.parse_args()

    md_root = Path(args.dir)
    if not md_root.exists():
        print(f"✗ 目录不存在: {md_root}", file=sys.stderr)
        sys.exit(1)

    # 收集所有 .md 文件
    md_files = list(md_root.rglob("*.md"))
    if not md_files:
        print(f"✗ 目录下无 .md 文件: {md_root}", file=sys.stderr)
        sys.exit(1)

    if args.limit:
        md_files = md_files[: args.limit]

    print(f"发现 {len(md_files)} 个 MD 文件")
    if args.dry_run:
        print("🔍 DRY RUN 模式 - 不写入文件")

    pipeline = create_default_pipeline()

    ok_count = 0
    skip_count = 0
    fail_count = 0

    for i, f in enumerate(md_files, 1):
        success, msg = enrich_file(f, pipeline, dry_run=args.dry_run)
        if success:
            ok_count += 1
            print(f"  [{i}/{len(md_files)}] ✓ {msg}")
        else:
            fail_count += 1
            print(f"  [{i}/{len(md_files)}] ⚠ {msg}")

    print("\n=== 统计 ===")
    print(f"成功: {ok_count}")
    print(f"跳过: {skip_count}")
    print(f"失败: {fail_count}")
    print(f"总计: {len(md_files)}")


if __name__ == "__main__":
    main()
