#!/usr/bin/env python3
"""enrich_metadata.py — 将 Phase 1 oskill/book_metadata pipeline 的结果注入 MD 前置。

用法:
  python3 scripts/enrich_metadata.py [--title "书名"] [--author "作者"] [--isbn "xxx"]
  或: python3 scripts/enrich_metadata.py --file /home/soffy/books/数学/微积分.pdf

该脚本:
1. 从文件名/路径提取书名
2. 调用 oskill.book_metadata.pipeline.run() 获取元数据
3. 解析现有 MD 的 frontmatter
4. 用 pipeline 结果覆盖/补充字段
5. 把 enriched frontmatter + 内容 写回原文件

Priority: existing frontmatter fields kept unless pipeline provides a non-empty value.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from oskill.book_metadata.pipeline import create_default_pipeline, ResolvedMetadataFields
from oskill.book_metadata.types import MetadataSearchParams

# frontmatter 正则（与 math_convert.py _frontmatter 兼容）
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def parse_frontmatter(md_text: str) -> tuple[dict[str, str], str]:
    """返回 (frontmatter_dict, body_text)。"""
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
    """把 resolved 字段合并到现有 frontmatter；不覆盖空值。"""
    lines = ["---"]
    # 优先保留现有非空字段
    for k in ["title", "source_file", "source_url", "lang", "converter"]:
        if k in fm_dict and fm_dict[k]:
            lines.append(f"{k}: {fm_dict[k]}")
    # pipeline 结果补充
    resolved_dict = resolved.to_dict()
    for k, v in resolved_dict.items():
        # 只在现有为空时填充
        if k not in fm_dict or not fm_dict[k]:
            # seriesMemberships 需要特殊处理
            if k == "seriesMemberships" and v:
                val = "; ".join(f"{m['seriesName']}@{m.get('seriesIndex', '')}" for m in v)
            elif k == "genres" and v:
                val = "; ".join(v)
            elif k == "authors" and v:
                val = ", ".join(v)
            else:
                val = v if not isinstance(v, list) else ", ".join(str(x) for x in v)
            lines.append(f"{k}: {val}")
    # 其它现有字段保持不变
    for k, v in fm_dict.items():
        if k not in {"title", "source_file", "source_url", "lang", "converter"}:
            lines.append(f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines)


def enrich_file(
    filepath: str, title: str | None = None, author: str | None = None, isbn: str | None = None
) -> bool:
    """丰富单个 MD 文件的前置。返回 True 表示成功。"""
    p = Path(filepath)
    if not p.exists():
        print(f"✗ 文件不存在: {filepath}")
        return False

    # 读取现有 MD
    md_text = p.read_text(encoding="utf-8")
    fm_dict, body = parse_frontmatter(md_text)

    # 提取已有 title (若未传参)
    if not title:
        existing_title = fm_dict.get("title", "")
        # 从文件名倒推 (去后缀 .md)
        fname_title = p.stem.replace("_", " ").replace("-", " ")
        title = existing_title or fname_title

    # 运行 metadata pipeline
    pipeline = create_default_pipeline(google_api_key=None)
    params = MetadataSearchParams(title=title, author=author, isbn=isbn)
    result = pipeline.run(params)

    if not result.resolved.title and not result.resolved.authors:
        print(f"⚠ Pipeline 未返回有效元数据: {title or p.name}")
        # 保持原样
        return True

    # 合并 frontmatter
    new_fm = build_frontmatter(fm_dict, result.resolved)
    new_md = new_fm + "\n" + body if body else new_fm + "\n"

    # 写回
    p.write_text(new_md, encoding="utf-8")
    fields = [k for k, v in result.resolved.to_dict().items() if v]
    print(f"✓ 丰富: {p.name} — 新增/更新字段: {', '.join(fields)[:80]}")
    return True


def main():
    args = sys.argv[1:]
    filepath = None
    title = None
    author = None
    isbn = None

    i = 0
    while i < len(args):
        if args[i] == "--file" and i + 1 < len(args):
            filepath = args[i + 1]
            i += 2
        elif args[i] == "--title" and i + 1 < len(args):
            title = args[i + 1]
            i += 2
        elif args[i] == "--author" and i + 1 < len(args):
            author = args[i + 1]
            i += 2
        elif args[i] == "--isbn" and i + 1 < len(args):
            isbn = args[i + 1]
            i += 2
        else:
            i += 1

    if not filepath:
        print(
            "用法: python3 scripts/enrich_metadata.py --file <md-path> [--title <书名>] [--author <作者>] [--isbn <isbn>]"
        )
        sys.exit(1)

    enrich_file(filepath, title=title, author=author, isbn=isbn)


if __name__ == "__main__":
    main()
