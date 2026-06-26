#!/usr/bin/env python3
"""
book_reclassify.py — 修复扫描版误判 + 为无 markdown 书补跑 parse_pdf

问题: oprim.detect_pdf_features 只看前 3 页判断 is_scanned。
教材封面/版权页常为图片或空白 → 前3页 < 150 chars → 误判 is_scanned=True
→ 走 marker 路径 → marker 未安装 → fallback pymupdf4llm（输出质量同文字版）。
但中间仍然走了错误路径，未来可能引入 marker 后行为改变。

§20: 只改 stratum/scripts/ 层。
- 调用 oprim.parser.parse_pdf(path, provider='pymupdf4llm') 显式指定（绕过误判）
- 把 markdown/chapters 存入 DuckDB derivative 表（通过 stratum.db）
- 不改 oprim/oskill/omodul 源码

用法:
  # 1. 报告: 195本书里多少是文字版被误判
  docker stop stratum-sl
  python3 book_reclassify.py --report

  # 2. 补跑文字版 md（service 停时跑，需 DuckDB 写权）
  python3 book_reclassify.py --run

  # 3. 只补单本
  python3 book_reclassify.py --run --substrate 01KVAJCXHEV751E9NTADMZ7RGV
"""
from __future__ import annotations
import sys, os, re, json, time, logging, argparse, pathlib

sys.path.insert(0, '/app/src')
os.environ.setdefault('STRATUM_ENV', 'prod')

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)-8s %(message)s')
log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# 改进的 PDF 类型检测（stratum 层，不改 oprim）
# ──────────────────────────────────────────────────────────────────────────────

def is_text_pdf(pdf_path: pathlib.Path, sample_pages: int = 10) -> tuple[bool, int, int]:
    """判断 PDF 是否有文本层。跳过前2页（封面/版权），采样后续页。

    Returns: (is_text, total_text_chars, pages_sampled)
    """
    import fitz
    doc = fitz.open(str(pdf_path))
    total_pages = doc.page_count
    text_chars = 0
    pages_checked = 0

    # 跳过第1-2页（封面、扉页），从第3页开始
    start_page = min(2, total_pages - 1)  # 0-indexed → page 3
    end_page = min(start_page + sample_pages, total_pages)

    for i in range(start_page, end_page):
        t = doc[i].get_text().strip()
        text_chars += len(t)
        pages_checked += 1

    doc.close()
    # 判定: 每页平均 > 100 chars → 文字版
    avg = text_chars / max(pages_checked, 1)
    return avg > 100, text_chars, pages_checked


def has_bookmarks(pdf_path: pathlib.Path) -> int:
    """返回书签数量（>0 意味着有 chapter 结构）。"""
    import fitz
    doc = fitz.open(str(pdf_path))
    n = len(doc.get_toc())
    doc.close()
    return n


# ──────────────────────────────────────────────────────────────────────────────
# 找没有 markdown derivative 的 book 基底
# ──────────────────────────────────────────────────────────────────────────────

def find_books_without_markdown() -> list[dict]:
    """查 DuckDB: book 类基底里没有 markdown derivative 的。"""
    from stratum.db import get_conn
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT s.id, s.file_path
            FROM substrates s
            WHERE json_extract_string(s.meta_json, '$.medium') = 'book'
              AND s.file_path LIKE '%.pdf'
              AND NOT EXISTS (
                SELECT 1 FROM derivative d
                WHERE d.substrate_id = s.id AND d.kind = 'markdown'
              )
            ORDER BY s.id
        """).fetchall()
    return [{'id': r[0], 'file_path': r[1]} for r in rows]


# ──────────────────────────────────────────────────────────────────────────────
# 补跑 parse_pdf + 存 derivative
# ──────────────────────────────────────────────────────────────────────────────

def parse_and_store(substrate_id: str, pdf_path: pathlib.Path) -> bool:
    """用 pymupdf4llm 解析 PDF，存 markdown+chapters+plaintext derivative。"""
    from oprim.parser.parse_pdf import parse_pdf
    from stratum.db import get_conn

    log.info("  Parsing %s ...", pdf_path.name[-50:])
    try:
        parsed = parse_pdf(pdf_path, provider='pymupdf4llm')
    except Exception as e:
        log.error("  parse_pdf failed: %s", e)
        return False

    if not parsed.markdown or len(parsed.markdown) < 500:
        log.warning("  Empty or tiny markdown (%d chars)", len(parsed.markdown))
        return False

    with get_conn() as conn:
        for kind, content in [
            ('markdown', parsed.markdown),
            ('plaintext', parsed.plaintext or ''),
            ('chapters', json.dumps(parsed.chapters) if parsed.chapters else '[]'),
        ]:
            if not content:
                continue
            conn.execute("""
                INSERT OR REPLACE INTO derivative (substrate_id, kind, content, updated_at)
                VALUES (?, ?, ?, NOW())
            """, (substrate_id, kind, content))

    log.info("  Stored markdown (%d chars), chapters (%d)", len(parsed.markdown),
             len(parsed.chapters))
    return True


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main() -> int:
    p = argparse.ArgumentParser(description='Fix PDF scanned misclassification + generate md')
    p.add_argument('--report', action='store_true',
                   help='Only report: how many books are text-PDF vs truly scanned')
    p.add_argument('--run', action='store_true',
                   help='Parse text-PDFs and store markdown derivatives')
    p.add_argument('--substrate', default='',
                   help='Single substrate ID (optional, for targeted run)')
    p.add_argument('--limit', type=int, default=0, help='Max books to process (0=all)')
    args = p.parse_args()

    if not args.report and not args.run:
        p.print_help()
        return 0

    log.info("Finding books without markdown derivative...")
    books = find_books_without_markdown()
    if args.substrate:
        books = [b for b in books if b['id'] == args.substrate]
    log.info("Found %d books without markdown", len(books))

    if args.limit:
        books = books[:args.limit]

    text_pdfs, scanned_pdfs, missing_files, errors = [], [], [], []

    for i, book in enumerate(books, 1):
        sid = book['id']
        fp = pathlib.Path(book['file_path']) if book['file_path'] else None

        if fp is None or not fp.exists():
            # 文件路径可能是相对于 data 目录的
            # 尝试从 substrate 目录查找
            candidates = list(pathlib.Path('/root/.stratum/data/substrate/book').glob(f'{sid}*'))
            if candidates:
                fp = candidates[0]
            else:
                log.warning("[%d/%d] %s: file not found", i, len(books), sid)
                missing_files.append(sid)
                continue

        is_text, text_chars, pages_checked = is_text_pdf(fp)
        bookmarks = has_bookmarks(fp)

        status = 'TEXT_PDF' if is_text else 'SCANNED'
        log.info("[%d/%d] %s: %s (text_chars=%d over %d pages, bookmarks=%d)",
                 i, len(books), sid[:12], status, text_chars, pages_checked, bookmarks)

        if is_text:
            text_pdfs.append({'id': sid, 'path': str(fp), 'bookmarks': bookmarks})
        else:
            scanned_pdfs.append({'id': sid, 'path': str(fp)})

        if args.run and is_text:
            ok = parse_and_store(sid, fp)
            if not ok:
                errors.append(sid)
            time.sleep(0.2)

    # 汇总
    log.info("")
    log.info("=== Summary ===")
    log.info("Total books without markdown : %d", len(books))
    log.info("Text PDF (misdetected)       : %d (→ can use pymupdf4llm)", len(text_pdfs))
    log.info("  With bookmarks (has TOC)   : %d", sum(1 for b in text_pdfs if b['bookmarks'] > 0))
    log.info("Truly scanned                : %d (→ needs Unlimited-OCR)", len(scanned_pdfs))
    log.info("File missing                 : %d", len(missing_files))
    if args.run:
        log.info("Markdown generated (errors)  : %d (%d)", len(text_pdfs) - len(errors), len(errors))

    return 0


if __name__ == '__main__':
    sys.exit(main())
