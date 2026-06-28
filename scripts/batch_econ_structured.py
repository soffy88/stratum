#!/usr/bin/env python3
"""
batch_econ_structured.py — 批量为经济书生成 _structured.md

逻辑:
  1. 扫描 stratum-to-aii/ 中的经济书（按 title 关键词匹配）
  2. 跳过已有 _structured.md 的
  3. 有 PDF + 章节书签 → inject_structure → _structured.md + .sidecar.json
  4. 有 PDF 但无书签 → json 标记 needs_pdf_reextract
  5. 无 PDF         → json 标记 needs_better_source

§20: 只读/写 scripts 层 + shared 目录，不改主库。

用法:
  python3 scripts/batch_econ_structured.py [--shared-dir /home/soffy/shared/stratum-to-aii] \
      [--pdf-dir /root/.stratum/data/substrate/book] [--dry-run]
"""

import argparse
import json
import logging
import pathlib
import re
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)-7s %(message)s',
    datefmt='%H:%M:%S',
)
log = logging.getLogger('batch_econ')

ECON_KEYWORDS = [
    '经济', 'econom', 'finance', '金融', 'micro', 'macro', '宏观', '微观',
    'money', 'banking', 'invest', '投资', '贸易', 'trade', '价格', 'fiscal',
    'monetary', '货币', 'market', '市场', 'business', '商', 'accounting',
    '会计', '统计', 'statistic', 'management', 'mba', 'gdp', 'labor', '劳动',
    'inequality', '不平等', 'poverty', '贫困', 'development', '发展',
]

CN_CH_RE = re.compile(
    r'^第\s*([零一二三四五六七八九十百千\d]+)\s*章[：:、\s]+(.*)',
    re.UNICODE,
)


def is_econ_book(title: str) -> bool:
    t = title.lower()
    return any(k in t for k in ECON_KEYWORDS)


def check_pdf_structure(pdf_path: pathlib.Path) -> str:
    """返回 'chapter', 'chinese', 'h2_only', 'none'"""
    try:
        import fitz
        doc = fitz.open(str(pdf_path))
        toc = doc.get_toc()
        doc.close()
    except Exception as e:
        log.debug("check_pdf_structure: fitz error %s: %s", pdf_path.name, e)
        return 'none'

    # CHAPTER-style 英文书签 (lv1 or lv2)
    ch_marks = [t for t in toc
                if t[0] in (1, 2) and re.match(r'CHAPTER\s+\d+', t[1], re.I)
                and not re.match(r'CHAPTER\s+\d+\s*$', t[1], re.I)]
    if len(ch_marks) >= 2:
        return 'chapter'

    # 中文第N章 书签
    cn_marks = [t for t in toc
                if t[0] in (1, 2) and CN_CH_RE.match(t[1].strip())
                and CN_CH_RE.match(t[1].strip()).group(2).strip()]
    if len(cn_marks) >= 2:
        return 'chinese'

    # 有书签但不是章节格式
    if toc:
        return 'h2_only'

    return 'none'


def mark_json(json_path: pathlib.Path, key: str, value: str, dry_run: bool) -> None:
    """在.json文件里加标记字段"""
    try:
        data = json.loads(json_path.read_text(encoding='utf-8'))
    except Exception:
        data = {}
    if data.get(key) == value:
        return  # 已有相同标记，跳过
    data[key] = value
    if not dry_run:
        json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    log.info("  mark: %s = %s → %s", key, value, json_path.name)


def find_pdf(pdf_dir: pathlib.Path, stem: str) -> pathlib.Path | None:
    """从 stem（ULID 前缀或完整 ULID）找对应 PDF"""
    # 完整 ULID（26字符，纯 md 文件名）
    if re.match(r'^[0-9A-Z]{26}$', stem):
        cands = list(pdf_dir.glob(f'{stem}*.pdf'))
        if cands:
            return cands[0]
        short = stem[:8]
    else:
        # _XXXX 短后缀（Title_XXXX.md 格式）
        m = re.search(r'_([0-9A-Z]{8,})$', stem)
        short = m.group(1) if m else stem[:8]

    cands = list(pdf_dir.glob(f'{short}*.pdf'))
    return cands[0] if cands else None


def run(shared_dir: pathlib.Path, pdf_dir: pathlib.Path, dry_run: bool) -> dict:
    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    from book_structure_inject import inject_structure

    # 收集所有经济书 .md（排除 _structured.md）
    all_mds = [f for f in shared_dir.glob('*.md') if '_structured' not in f.name]
    econ_mds = []
    for md in sorted(all_mds):
        json_path = shared_dir / f'{md.stem}.json'
        title = md.stem
        if json_path.exists():
            try:
                d = json.loads(json_path.read_text(encoding='utf-8'))
                title = d.get('title', md.stem)
            except Exception:
                pass
        if is_econ_book(title):
            econ_mds.append((md, json_path, title))

    log.info("Found %d economics books in %s", len(econ_mds), shared_dir)

    stats = {
        'total': len(econ_mds),
        'already_done': 0,
        'injected': 0,
        'no_pdf': 0,
        'no_chapters': 0,
        'h2_only': 0,
        'failed': 0,
    }
    results = []

    for md_path, json_path, title in econ_mds:
        stem = md_path.stem
        structured_out = shared_dir / f'{stem}_structured.md'

        # 已有 _structured.md → 跳过
        if structured_out.exists():
            log.info("SKIP (done): %s", title[:60])
            stats['already_done'] += 1
            results.append({'id': stem, 'title': title, 'status': 'already_done'})
            continue

        # 也检查内容（inplace 模式可能已注入到原文件）
        content = md_path.read_text(encoding='utf-8', errors='replace')
        if '<!-- TOC START -->' in content or '# Chapter 1:' in content:
            log.info("SKIP (inplace done): %s", title[:60])
            stats['already_done'] += 1
            results.append({'id': stem, 'title': title, 'status': 'already_done'})
            continue

        # 找 PDF
        pdf_path = find_pdf(pdf_dir, stem)
        if not pdf_path:
            log.warning("NO_PDF: %s", title[:60])
            mark_json(json_path, 'inject_status', 'needs_better_source', dry_run)
            stats['no_pdf'] += 1
            results.append({'id': stem, 'title': title, 'status': 'no_pdf'})
            continue

        # 检查书签
        pdf_struct = check_pdf_structure(pdf_path)
        log.info("PDF_STRUCT=%s: %s", pdf_struct, title[:60])

        if pdf_struct == 'none':
            mark_json(json_path, 'inject_status', 'needs_pdf_reextract', dry_run)
            stats['no_chapters'] += 1
            results.append({'id': stem, 'title': title, 'status': 'no_chapters', 'pdf_struct': 'none'})
            continue

        if pdf_struct == 'h2_only':
            mark_json(json_path, 'inject_status', 'needs_pdf_reextract', dry_run)
            stats['h2_only'] += 1
            results.append({'id': stem, 'title': title, 'status': 'h2_only'})
            continue

        # 有章节书签 → 注入
        if dry_run:
            log.info("DRY_RUN: would inject → %s", structured_out.name)
            stats['injected'] += 1
            results.append({'id': stem, 'title': title, 'status': 'dry_run_inject', 'pdf_struct': pdf_struct})
            continue

        try:
            # 从stem提取ULID
            ulid_m = re.match(r'^([0-9A-Z]{26})', stem)
            substrate_id = ulid_m.group(1) if ulid_m else ''

            result = inject_structure(
                md_path=md_path,
                pdf_path=pdf_path,
                out_dir=shared_dir,   # → {stem}_structured.md
                substrate_id=substrate_id,
                skip_tables=True,
            )
            if result.acceptance.get('PASS'):
                log.info("OK chapters=%d: %s", result.chapters_found, title[:60])
                mark_json(json_path, 'inject_status', 'done', dry_run)
                stats['injected'] += 1
                results.append({
                    'id': stem, 'title': title, 'status': 'injected',
                    'chapters': result.chapters_found, 'pdf_struct': pdf_struct,
                })
            else:
                fails = {k: v for k, v in result.acceptance.items() if not v and k != 'chapters_found'}
                log.warning("FAIL acceptance=%s: %s", fails, title[:60])
                mark_json(json_path, 'inject_status', 'inject_failed', dry_run)
                stats['failed'] += 1
                results.append({'id': stem, 'title': title, 'status': 'failed', 'acceptance': fails})
        except RuntimeError as e:
            log.warning("SKIP runtime=%s: %s", e, title[:60])
            mark_json(json_path, 'inject_status', 'needs_pdf_reextract', dry_run)
            stats['no_chapters'] += 1
            results.append({'id': stem, 'title': title, 'status': 'no_chapters_runtime'})
        except Exception as e:
            log.error("ERROR: %s: %s", title[:60], e)
            stats['failed'] += 1
            results.append({'id': stem, 'title': title, 'status': 'error', 'error': str(e)})

    return {'stats': stats, 'results': results}


def main() -> int:
    p = argparse.ArgumentParser(description='Batch inject structure for economics books')
    p.add_argument('--shared-dir', default='/home/soffy/shared/stratum-to-aii',
                   help='stratum-to-aii 目录')
    p.add_argument('--pdf-dir', default='/root/.stratum/data/substrate/book',
                   help='PDF 文件根目录')
    p.add_argument('--dry-run', action='store_true',
                   help='只报告，不写文件')
    p.add_argument('--report', default='',
                   help='把结果 JSON 写到此文件')
    args = p.parse_args()

    shared_dir = pathlib.Path(args.shared_dir)
    pdf_dir = pathlib.Path(args.pdf_dir)

    if not shared_dir.exists():
        log.error("shared_dir not found: %s", shared_dir)
        return 1
    if not pdf_dir.exists():
        log.error("pdf_dir not found: %s", pdf_dir)
        return 1

    output = run(shared_dir, pdf_dir, dry_run=args.dry_run)
    s = output['stats']
    log.info("=== DONE ===")
    log.info("Total econ books : %d", s['total'])
    log.info("Already done     : %d", s['already_done'])
    log.info("Injected ✓       : %d", s['injected'])
    log.info("No PDF           : %d (marked needs_better_source)", s['no_pdf'])
    log.info("No chapters      : %d (marked needs_pdf_reextract)", s['no_chapters'])
    log.info("H2 only (no ch)  : %d (marked needs_pdf_reextract)", s['h2_only'])
    log.info("Failed inject    : %d", s['failed'])

    if args.report:
        rp = pathlib.Path(args.report)
        rp.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
        log.info("Report written to %s", rp)

    return 0


if __name__ == '__main__':
    sys.exit(main())
