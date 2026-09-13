#!/usr/bin/env python3
"""split_collection_epub.py — 把合集本 epub 拆分成单本 MD 文件。

用法:
  python split_collection_epub.py [--do] [--dry-run] [--output-dir DIR]
  
  --do        实际执行拆分+转换 (默认 dry-run)
  --dry-run   只列出会拆哪些, 不执行
  --output-dir  输出目录 (默认 books/MD/_split_staging/)

检测逻辑:
  1. 扫描 books/{数学,Economic,其它} 下所有 epub
  2. 解析 TOC, 识别顶层 Section/Link 为"子书"
  3. 如果 TOC 有 ≥2 个顶层 Section (每个有 ≥5 个子项), 判定为合集
  4. 按 spine 顺序切分每个子书的 HTML 范围, 合并转 MD
  5. 输出到 books/MD/_split_staging/子书名.md, 供 classify_md.py 分拣
"""

import argparse
import logging
import os
import re
import sys
import zipfile
from concurrent.futures import ProcessPoolExecutor, TimeoutError as FuturesTimeout
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("split_collection")

# ── 配置 ──────────────────────────────────────────────────────────────────
BOOK_DIRS = [
    "/home/soffy/books/数学",
    "/home/soffy/books/Economic",
    "/home/soffy/books/其它",
]
DEFAULT_OUTPUT = "/home/soffy/projects/stratum/aii/books/MD/_split_staging"

# 合集检测: TOC 顶层 Section 数 ≥ 此值 → 判定为合集
MIN_SECTIONS_FOR_COLLECTION = 2
# 每个 Section 至少有这么多子项才算"真子书"(排除封面/目录等短 section)
MIN_CHILDREN_PER_SECTION = 3
# 非内容页面关键词 (跳过这些章节)
SKIP_KEYWORDS = re.compile(
    r"^(扉页|版权|版权页|目录|致谢|后记|索引|参考文献|附录|Appendix|"
    r"Bibliography|Index|Acknowledgment|Copyright|Colophon|About)",
    re.I,
)


def is_collection_by_name(filename, title):
    """通过文件名/元数据标题判断是否为合集本。"""
    patterns = re.compile(
        r"套装|全集|全集.*共.*册|共\d+册|共\s*\d+\s*册|合[集辑]|"
        r"文[集库]|丛书.*\d+册|系列.*共|典藏版.*全|"
        r"Boxed\s*Set|Collection|Anthology|Complete\s*Works|"
        r"套装共|全\d+册|全\d+本|全\d+卷",
        re.I,
    )
    text = f"{filename} {title}"
    return bool(patterns.search(text))


def _read_epub_worker(path):
    """子进程里读 epub — 防止大合集在父进程里读挂(D状态不可杀, 拖死整轮 pull_ingest)."""
    import ebooklib
    from ebooklib import epub
    return epub.read_epub(path)


def detect_collections():
    """扫描本地书目录, 返回 (epub_path, title, sections) 列表。
    
    合集检测策略 (同时满足):
    1. 文件大小 > 20MB (普通教材很少这么大)
    2. 文件名/标题含合集关键词 (套装/全集/文集/共N册/Boxed Set等)
    3. TOC 有 ≥2 个顶层 Section (每个有 ≥3 个子项)
    
    ★2026-08-22 修复: epub.read_epub 在父进程里读大合集时曾卡入 D 状态
    (磁盘IO挂起, 连 SIGKILL 都杀不掉, 单轮 pull_ingest 拖死 55 分钟)。
    改到独立子进程读 + 120s 超时, 超时直接跳过该书(下轮 24h 后再试)。
    """
    try:
        import ebooklib
        from ebooklib import epub
    except ImportError:
        log.error("ebooklib 未安装, 请运行: uv pip install ebooklib")
        return []

    results = []
    pool = ProcessPoolExecutor(max_workers=1)
    for book_dir in BOOK_DIRS:
        if not os.path.isdir(book_dir):
            continue
        for f in sorted(Path(book_dir).glob("*.epub")):
            # Gate 1: file size > 20MB
            fsize = f.stat().st_size
            if fsize < 20 * 1024 * 1024:
                continue

            try:
                fut = pool.submit(_read_epub_worker, str(f))
                book = fut.result(timeout=120)
            except FuturesTimeout:
                # 子进程可能已卡 D 状态(磁盘IO挂起, SIGKILL 也杀不掉), 直接换新池:
                # shutdown(wait=False) 立刻返回, 遗留的 D 状态子进程由内核在 I/O 恢复后自己结束。
                log.warning("超时跳过(读epub>120s): %s", f.name[:50])
                pool.shutdown(wait=False, cancel_futures=True)
                pool = ProcessPoolExecutor(max_workers=1)
                continue
            except Exception as e:
                log.warning("读取失败 %s: %s", f.name[:50], e)
                continue

            title_meta = book.get_metadata("DC", "title")
            title = title_meta[0][0] if title_meta else f.stem[:60]

            # Gate 2: name/title contains collection keywords
            if not is_collection_by_name(f.name, title):
                continue

            toc = book.toc
            # Count top-level sections (tuples with children)
            sections = [
                (sec, children)
                for sec, children in (
                    item if isinstance(item, tuple) else (None, [])
                    for item in toc
                )
                if sec is not None and len(children) >= MIN_CHILDREN_PER_SECTION
            ]

            if len(sections) >= MIN_SECTIONS_FOR_COLLECTION:
                results.append((str(f), title, sections))
                log.info(
                    "合集: %s (%dMB) → %d 本子书",
                    f.name[:50], fsize // (1024 * 1024), len(sections),
                )
            else:
                # Flat structure: top-level Links are books
                # Only if there are few Links (2-50) AND they point to substantial content.
                # Many Links (e.g. 1322 for 阿来) = individual chapters, NOT books.
                top_links = [item for item in toc if not isinstance(item, tuple)]
                if 2 <= len(top_links) <= 50:
                    # Wrap flat links as a pseudo-section
                    results.append((str(f), title, [(None, top_links)]))
                    log.info(
                        "扁平合集: %s (%dMB) → %d 个Link子书",
                        f.name[:50], fsize // (1024 * 1024), len(top_links),
                    )
                elif len(top_links) > 50:
                    log.info(
                        "跳过: %s (%dMB, %d个顶层Link=章节非子书, 当整本处理)",
                        f.name[:50], fsize // (1024 * 1024), len(top_links),
                    )

    pool.shutdown(wait=False)
    return results


def split_epub_to_md(epub_path, title, sections, output_dir, dry_run=False):
    """拆分单个合集 epub 为多个 MD 文件。"""
    import ebooklib
    from ebooklib import epub as epub_mod

    book = epub_mod.read_epub(epub_path)

    # Build spine order: item_id → position
    spine_ids = [item_id for item_id, _ in book.spine]
    id_to_item = {item.id: item for item in book.get_items()}
    spine_items = [id_to_item[sid] for sid in spine_ids if sid in id_to_item]
    item_to_pos = {item.id: i for i, item in enumerate(spine_items)}

    # Map href → spine position
    def href_to_pos(href):
        """Find the spine position for a given TOC href."""
        fname = href.split("#")[0]
        for item in spine_items:
            if item.get_name() == fname or item.file_name == fname:
                return item_to_pos[item.id]
        # Try basename match
        basename = os.path.basename(fname)
        for item in spine_items:
            if os.path.basename(item.get_name()) == basename:
                return item_to_pos[item.id]
        return None

    # Determine book boundaries from TOC
    books_data = []  # (book_title, start_pos, end_pos_or_None)

    for sec, children in sections:
        if sec is not None:
            # Section-based: this section = one book
            book_title = sec.title
            start_pos = href_to_pos(sec.href)
            if start_pos is None:
                log.warning("  跳过: %s (href=%s 不在 spine 中)", book_title[:40], sec.href[:30])
                continue
            books_data.append((book_title, start_pos, None))
        else:
            # Flat structure: each Link = one book
            for child in children:
                child_title = child.title if hasattr(child, "title") else str(child)
                href = child.href if hasattr(child, "href") else ""
                child_pos = href_to_pos(href)
                if child_pos is not None:
                    books_data.append((child_title, child_pos, None))
                else:
                    log.warning("  跳过: %s (href 不在 spine 中)", child_title[:40])

    if not books_data:
        log.warning("  无有效子书, 跳过")
        return

    # Fill end positions (sorted by start)
    sorted_books = sorted(books_data, key=lambda x: x[1])
    final_books = []
    for i, (btitle, start, _) in enumerate(sorted_books):
        if i + 1 < len(sorted_books):
            end = sorted_books[i + 1][1]
        else:
            end = len(spine_items)
        final_books.append((btitle, start, end))

    if dry_run:
        for btitle, start, end in final_books:
            n_files = end - start
            print(f"  [DRY] {btitle[:50]}  ({n_files} HTML文件)")
        return

    # Process each book
    os.makedirs(output_dir, exist_ok=True)
    safe_title = re.sub(r'[\\/:*?"<>|\n\r]', '_', title)[:40]

    for idx, (btitle, start, end) in enumerate(final_books):
        safe_btitle = re.sub(r'[\\/:*?"<>|\n\r]', '_', btitle)[:50]
        out_name = f"{safe_title}_{idx+1:02d}_{safe_btitle}.md"
        out_path = os.path.join(output_dir, out_name)

        if os.path.exists(out_path):
            log.info("  已存在, 跳过: %s", out_name)
            continue

        # Collect HTML content for this book's spine range
        html_parts = []
        for pos in range(start, end):
            item = spine_items[pos]
            try:
                content = item.get_body_content()
                if content:
                    html_parts.append(content.decode("utf-8", errors="replace"))
            except Exception:
                continue

        if not html_parts:
            log.warning("  无内容: %s", btitle[:40])
            continue

        # Merge HTML and convert to MD
        full_html = "\n".join(html_parts)
        try:
            from markitdown import MarkItDown
            import tempfile

            md = MarkItDown()
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".html", delete=False, encoding="utf-8"
            ) as tmp:
                tmp.write(f"<html><body>{full_html}</body></html>")
                tmp_path = tmp.name

            result = md.convert(tmp_path)
            md_text = result.text_content
            os.unlink(tmp_path)
        except Exception as e:
            log.error("  MD转换失败 %s: %s", btitle[:40], e)
            continue

        if len(md_text.strip()) < 200:
            log.warning("  MD太短 (%d字符), 跳过: %s", len(md_text), btitle[:40])
            continue

        # Add frontmatter
        frontmatter = f"""---
title: "{btitle}"
source_collection: "{title}"
source_epub: "{os.path.basename(epub_path)}"
book_index: {idx + 1}
total_books: {len(final_books)}
---

"""
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(frontmatter + md_text)

        log.info("  ✅ %s (%d字符, %d HTML)", out_name, len(md_text), len(html_parts))


def main():
    parser = argparse.ArgumentParser(description="拆分合集本 epub 为单本 MD")
    parser.add_argument("--do", action="store_true", help="实际执行")
    parser.add_argument("--dry-run", action="store_true", help="只列出不执行")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT, help="输出目录")
    parser.add_argument("--file", help="只处理指定文件")
    args = parser.parse_args()

    if not args.do and not args.dry_run:
        log.info("默认 dry-run 模式。加 --do 实际执行, --dry-run 显式 dry-run。")

    collections = detect_collections()
    if not collections:
        log.info("未发现合集本 epub。")
        return

    log.info("发现 %d 个合集本", len(collections))

    for epub_path, title, sections in collections:
        if args.file and args.file not in epub_path:
            continue
        log.info("━━━ %s ━━━", title[:60])
        log.info("  路径: %s", epub_path)
        log.info("  子书数: %d", len(sections))

        split_epub_to_md(
            epub_path,
            title,
            sections,
            args.output_dir,
            dry_run=not args.do,
        )

    if args.do:
        log.info("拆分完成。输出目录: %s", args.output_dir)
        log.info("下一步: 运行 classify_md.py --do 将 MD 分拣到对应学科目录。")


if __name__ == "__main__":
    main()
