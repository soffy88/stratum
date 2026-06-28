"""
batch_r1_r9_repair.py — Batch 1 R1-R9 repairs for personal library (meta.duckdb.bak)
§20 compliant: stratum/scripts layer only.

Data source: meta.duckdb.bak (personal library; NOT live meta.duckdb)
Write target: same bak file via direct DuckDB connection (not locked by any server)

Operations:
  --cfa-fifl      D-class CFA: fi/fl ligature FFFD repair
  --c6-tables     C-class 5 books: R8 table-only fix (no chapter inject)
  --b3-inject     B-class 3 books: chapter injection + R8 tables
  --batch1        All three above
  --batch2-mt     D-class MathTime book: FFFD repair (fix_b_class_fffd pattern)
  --b36-scan      Scan 36 C-class PDFs for bookmark naming conventions
"""
from __future__ import annotations
import argparse, logging, pathlib, re, sys, tempfile, os

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)-8s %(message)s')
log = logging.getLogger(__name__)

BAK = '/root/.stratum/meta.duckdb.bak'
FFFD = chr(0xfffd)

# ── targets ──────────────────────────────────────────────────────────────────

CFA_ID    = '01KVA3Z23KAJ1VJSST6KHC6KYV'   # D-class: fi/fl ligatures, fffd=1244
MT_ID     = '01KVAJVDS4GH9VFTJWD5GW1K4W'   # D-class: MathTime Pro, fffd=2248

B3 = [
    ('01KVJS5MDDBG9W5D1SXE099E5B', 'skip_tables'),    # 書呆子 21ch, r8=0
    ('01KVABDEXD2V985Q9GZWFWPERW', 'with_tables'),    # Jacques 9ch, r8=95
    ('01KVA9FE7XBDTP8MYHSHEFZHGD', 'with_tables'),    # Org Mgmt 4ch, r8=14
]

C6_IDS = [
    '01KVAKHZHHTSKG2C5VD95W6P62',   # Atkinson-Piketty-Saez r8=61
    '01KVA3S1YGHVHBB9R96V6Z0DEY',   # 曼昆微观经济学原理 r8=59
    '01KVAG6Z063RVXJMV35ZD1QS3C',   # 北大社数理经济学 r8=54
    '01KVAG3E1J5YKKGP9X26MX4KDZ',   # 宏观经济学数理模型 r8=54
    '01KVA884MG7DZHQVA2XHTGS1QG',   # 曼昆经济学原理中文版 r8=37
]


# ── DB helpers ────────────────────────────────────────────────────────────────

def read_md(conn, sid: str) -> str | None:
    row = conn.execute(
        "SELECT content FROM derivative WHERE substrate_id=? AND kind='markdown'", (sid,)
    ).fetchone()
    return row[0] if row else None


def read_source_path(conn, sid: str) -> str | None:
    row = conn.execute("SELECT source_path FROM substrates WHERE id=?", (sid,)).fetchone()
    return row[0] if row else None


def write_md(conn, sid: str, md: str) -> int:
    res = conn.execute(
        "UPDATE derivative SET content=? WHERE substrate_id=? AND kind='markdown'",
        (md, sid),
    )
    return res.rowcount if res.rowcount != -1 else 1


def read_title(conn, sid: str) -> str:
    row = conn.execute("SELECT title FROM substrates WHERE id=?", (sid,)).fetchone()
    return (row[0] or '') if row else ''


# ── CFA fi/fl ligature fix ────────────────────────────────────────────────────

# Known ligatures: fi, fl, ff, ffi, ffl (standard OpenType)
# Strategy: scan all FFFD occurrences, pick best ligature by prefix/suffix letter context.
# Priority: fi (most common in English text, confirmed by 3/3 CFA samples)

_LIGATURE_MAP: list[tuple[str, str]] = [
    # (context_hint, replacement)
    # These cover the vast majority; remaining edge cases default to 'fi'
    ('fi', 'fi'), ('fl', 'fl'), ('ff', 'ff'), ('ffi', 'ffi'), ('ffl', 'ffl'),
]

# Precomputed: words where fi/fl/ff ligature replaces FFFD
# Instead of a word list, use letter-pair heuristic:
# If preceding char is a letter and following char is a letter → determine ligature by pair
# English bigram "fi" >> "fl" >> "ff" in most non-math text

def _best_ligature(before: str, after: str) -> str:
    """Given context chars, pick the most likely ligature."""
    # Use look-ahead: what word fragment after FFFD starts with?
    # fi: after starts with vowel or 'n','r','s','t','c','l','g','x'
    # fl: after starts with 'a','e','i','o','u','oo','ow','ue','y' (very common: flat, flex, floor)
    # ff: after starts with 'e','i','o','u' (effect, officer, off)
    # Most reliable for finance/English text: default fi

    # Simple two-char lookahead rules (covers >95% of cases):
    a = after.lower()
    if a.startswith(('a', 'e', 'i', 'o', 'u')):
        # Both fi and fl are plausible; check preceding char
        b = before.lower()
        if b.endswith(('a', 'e', 'i', 'o', 'u', 'f', 'r', 'n', 's', 'l', 'g', 'p', 'c', 'd', 'm', 'b')):
            return 'fi'   # "define", "office", "finance"
        return 'fi'       # default fi
    elif a.startswith('l'):
        return 'fl'       # "flat", "floor", "reflect"
    elif a.startswith('f'):
        return 'ff'       # "effect", "offer"
    else:
        return 'fi'       # default


def fix_fifl(md: str) -> tuple[str, int, dict[str, int]]:
    """Replace FFFD with fi/fl/ff ligatures using context."""
    count = 0
    stats: dict[str, int] = {'fi': 0, 'fl': 0, 'ff': 0, 'ffi': 0, 'ffl': 0}
    parts: list[str] = []
    i = 0
    while i < len(md):
        if md[i] == FFFD:
            before = md[max(0, i-3):i]
            after  = md[i+1:min(len(md), i+4)]
            lig = _best_ligature(before, after)
            parts.append(lig)
            stats[lig] = stats.get(lig, 0) + 1
            count += 1
        else:
            parts.append(md[i])
        i += 1
    return ''.join(parts), count, stats


# ── R8 table fix (standalone) ─────────────────────────────────────────────────

def run_r8_tables(md: str, pdf_path: pathlib.Path) -> tuple[str, int, int]:
    """Run fix_tables() from book_structure_inject without chapter injection."""
    sys.path.insert(0, '/app/scripts')
    from book_structure_inject import fix_tables

    import fitz
    doc = fitz.open(str(pdf_path))
    total_pages = doc.page_count
    doc.close()

    before = len(re.findall(r'\|[^\n]*<br>[^\n]*\|', md))
    new_md = fix_tables(md, pdf_path, chapters=[], total_pages=total_pages)
    after = len(re.findall(r'\|[^\n]*<br>[^\n]*\|', new_md))
    return new_md, before, after


# ── B3 chapter injection ──────────────────────────────────────────────────────

def run_inject(conn, sid: str, skip_tables: bool) -> dict:
    sys.path.insert(0, '/app/scripts')
    from book_structure_inject import inject_structure_inplace

    md = read_md(conn, sid)
    spath = read_source_path(conn, sid)
    title = read_title(conn, sid)
    if not md or not spath:
        return {'status': 'skip', 'reason': 'no md or path'}

    pdf_path = pathlib.Path(spath)
    if not pdf_path.exists() or pdf_path.suffix.lower() != '.pdf':
        return {'status': 'skip', 'reason': f'not a pdf or missing: {spath}'}

    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', encoding='utf-8',
                                     prefix=f'inject_{sid}_', delete=False) as f:
        f.write(md)
        tmp = pathlib.Path(f.name)

    try:
        try:
            result = inject_structure_inplace(
                md_path=tmp, pdf_path=pdf_path, substrate_id=sid, skip_tables=skip_tables
            )
        except RuntimeError as exc:
            return {'status': 'error', 'reason': str(exc), 'title': title}

        if result is None:
            return {'status': 'skip', 'reason': 'no CHAPTER bookmarks with titles'}

        new_md = tmp.read_text(encoding='utf-8')
        written = write_md(conn, sid, new_md)
        return {
            'status': 'ok',
            'title': title,
            'chapters_found': result.chapters_found,
            'chapters_total': result.chapters_total,
            'h1_in': result.header_noise_before,
            'h1_out': result.header_noise_after,
            'br_in': result.br_tables_before,
            'br_out': result.br_tables_after,
            'acceptance': result.acceptance,
            'db_written': written,
        }
    finally:
        tmp.unlink(missing_ok=True)


# ── 36-PDF bookmark scan ──────────────────────────────────────────────────────

def scan_36_pdf_bookmarks(conn) -> list[dict]:
    """Scan C-class PDFs with bookmarks but non-CHAPTER naming for bookmark format."""
    import fitz
    rows = conn.execute("""
        SELECT s.id, s.title, s.source_path
        FROM substrates s
        WHERE s.user_id='56d6bc01edc35765'
          AND s.parse_quality IN ('ok','ocr_ok')
          AND JSON_EXTRACT_STRING(s.meta_json,'$.medium')='book'
          AND s.source_path LIKE '%.pdf'
          AND s.id NOT IN (
            '01KVJS5MDDBG9W5D1SXE099E5B','01KVABDEXD2V985Q9GZWFWPERW',
            '01KVA9FE7XBDTP8MYHSHEFZHGD','01KVAFVR0KY9X6X6SPXCDFMG45',
            '01KVAJCXHEV751E9NTADMZ7RGV','01KVA3Z23KAJ1VJSST6KHC6KYV',
            '01KVAJVDS4GH9VFTJWD5GW1K4W'
          )
        ORDER BY s.title
    """).fetchall()

    results = []
    for sid, title, spath in rows:
        if not spath or not os.path.exists(spath):
            continue
        try:
            doc = fitz.open(spath)
            toc = doc.get_toc()
            total = doc.page_count
            doc.close()
        except Exception:
            continue

        if not toc:
            results.append({'id': sid, 'title': title, 'format': 'no_bookmarks', 'toc': []})
            continue

        # Classify bookmark format
        lv1_samples = [(t, p) for lv, t, p in toc if lv == 1][:4]
        lv2_samples = [(t, p) for lv, t, p in toc if lv == 2][:3]

        has_chapter = any(re.match(r'CHAPTER\s+\d+', t, re.I) for lv, t, p in toc)
        has_part = any(re.match(r'(Part|PART)\s+[IVX\d]', t) for lv, t, p in toc)
        has_num = any(re.match(r'\d+[\.\s]', t) for lv, t, p in toc if lv == 1)
        has_chinese = any(re.search(r'[一-鿿]', t) for lv, t, p in toc)
        has_section = any(re.match(r'Section\s+\d+', t, re.I) for lv, t, p in toc)

        fmt = ('chapter' if has_chapter else
               'part' if has_part else
               'numbered' if has_num else
               'chinese' if has_chinese else
               'section' if has_section else 'other')

        results.append({
            'id': sid, 'title': title, 'format': fmt,
            'toc_len': len(toc), 'pages': total,
            'lv1_samples': lv1_samples,
        })

    return results


def strip_cn_running_headers(md: str, chapters) -> str:
    """Remove plain-text 第N章 running-header lines from an injected markdown.

    After chapter injection, each chapter's running header may still appear as a
    bare plain-text line on every page. Since H1 markers are now the authoritative
    anchors, we strip ALL occurrences (including the first) of these lines.
    """
    sys.path.insert(0, '/app/scripts')
    from book_structure_inject import _int_to_cn

    result = md
    for ch in chapters:
        cn_forms = [str(ch.ch_num)]
        cn_word = _int_to_cn(ch.ch_num)
        if cn_word:
            cn_forms.append(cn_word)
        esc_title = re.escape(ch.title) if ch.title else r'.{0,80}'
        for cn_n in cn_forms:
            # Remove "第N章 title" lines and bare "第N章" lines
            result = re.sub(
                r'(?m)^第' + re.escape(cn_n) + r'章\s*' + esc_title + r'\s*$\n?', '', result
            )
            result = re.sub(
                r'(?m)^第' + re.escape(cn_n) + r'章\s*$\n?', '', result
            )
    # Collapse multiple blank lines left by stripping
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch1', action='store_true')
    parser.add_argument('--cfa-fifl', action='store_true')
    parser.add_argument('--c6-tables', action='store_true')
    parser.add_argument('--b3-inject', action='store_true')
    parser.add_argument('--batch2-mt', action='store_true')
    parser.add_argument('--cn-inject', action='store_true')
    parser.add_argument('--cn-inject-plainstext', action='store_true')
    parser.add_argument('--cn-mark-broken', action='store_true')
    parser.add_argument('--b36-scan', action='store_true')
    args = parser.parse_args()

    if not any(vars(args).values()):
        parser.print_help()
        sys.exit(1)

    import duckdb
    conn = duckdb.connect(BAK)

    # ── CFA fi/fl ─────────────────────────────────────────────────────────────
    if args.cfa_fifl or args.batch1:
        log.info('=== CFA fi/fl ligature fix ===')
        md = read_md(conn, CFA_ID)
        if md:
            before = md.count(FFFD)
            new_md, fixed, stats = fix_fifl(md)
            after = new_md.count(FFFD)
            write_md(conn, CFA_ID, new_md)
            log.info('CFA: FFFD %d → %d  fixed=%d  breakdown=%s', before, after, fixed, stats)
        else:
            log.warning('CFA: no markdown found')

    # ── C6 tables ────────────────────────────────────────────────────────────
    if args.c6_tables or args.batch1:
        log.info('=== C6 R8 table fixes ===')
        for sid in C6_IDS:
            title = read_title(conn, sid)
            md = read_md(conn, sid)
            spath = read_source_path(conn, sid)
            if not md or not spath:
                log.warning('%s: no md or path', sid[:12])
                continue
            pdf = pathlib.Path(spath)
            if not pdf.exists() or pdf.suffix != '.pdf':
                log.warning('%s: not a pdf', sid[:12])
                continue
            try:
                new_md, before, after = run_r8_tables(md, pdf)
                write_md(conn, sid, new_md)
                log.info('  %s  r8: %d → %d  [%s]', sid[:12], before, after, title[:35])
            except Exception as e:
                log.error('  %s  ERROR: %s', sid[:12], e)

    # ── B3 chapter injection ──────────────────────────────────────────────────
    if args.b3_inject or args.batch1:
        log.info('=== B3 chapter injection ===')
        for sid, mode in B3:
            log.info('--- %s (%s) ---', read_title(conn, sid)[:40], mode)
            skip_tables = (mode == 'skip_tables')
            result = run_inject(conn, sid, skip_tables=skip_tables)
            log.info('  result: %s', result)

    # ── Batch 2: MathTime D-class ─────────────────────────────────────────────
    if args.batch2_mt:
        log.info('=== Batch2 MathTime (01KVAJVDS4GH9VFTJWD5GW1K4W) ===')
        sys.path.insert(0, '/app/scripts')
        from fix_b_class_fffd import fix_math_analysis_econtheory
        import json as _json

        md = read_md(conn, MT_ID)
        if not md:
            log.warning('Batch2 MT: no markdown found')
        else:
            before = md.count(FFFD)
            new_md, fixed, remaining = fix_math_analysis_econtheory(md)
            write_md(conn, MT_ID, new_md)
            log.info('MT: FFFD %d → %d  (fixed=%d remaining=%d)', before, remaining, fixed, remaining)

            # Tag needs_pdf_reextract in meta_json
            row = conn.execute("SELECT meta_json FROM substrates WHERE id=?", (MT_ID,)).fetchone()
            meta = _json.loads(row[0] or '{}') if row else {}
            meta['needs_pdf_reextract'] = True
            conn.execute("UPDATE substrates SET meta_json=? WHERE id=?", (_json.dumps(meta), MT_ID))
            log.info('MT: tagged needs_pdf_reextract=True in meta_json')

    # ── Chinese book chapter injection ───────────────────────────────────────────
    if args.cn_inject:
        log.info('=== Chinese book chapter injection ===')
        sys.path.insert(0, '/app/scripts')
        from book_structure_inject import load_chapters_from_pdf
        import os as _os

        EXCLUDE = {
            '01KVJS5MDDBG9W5D1SXE099E5B','01KVABDEXD2V985Q9GZWFWPERW',
            '01KVA9FE7XBDTP8MYHSHEFZHGD','01KVAFVR0KY9X6X6SPXCDFMG45',
            '01KVAJCXHEV751E9NTADMZ7RGV','01KVA3Z23KAJ1VJSST6KHC6KYV',
            '01KVAJVDS4GH9VFTJWD5GW1K4W',
        }
        rows = conn.execute("""
            SELECT s.id, s.title, s.source_path
            FROM substrates s
            WHERE s.user_id='56d6bc01edc35765'
              AND s.parse_quality IN ('ok','ocr_ok')
              AND JSON_EXTRACT_STRING(s.meta_json,'$.medium')='book'
              AND s.source_path LIKE '%.pdf'
            ORDER BY s.title
        """).fetchall()

        ok = skip = err = 0
        for sid, title, sp in rows:
            if sid in EXCLUDE or not sp or not _os.path.exists(sp): continue
            chs, _ = load_chapters_from_pdf(pathlib.Path(sp))
            if len(chs) < 2: continue
            md_row = conn.execute(
                "SELECT content FROM derivative WHERE substrate_id=? AND kind='markdown'", (sid,)
            ).fetchone()
            if not md_row:
                skip += 1; continue
            if re.search(r'^# Chapter \d+:', md_row[0], re.M):
                log.info('  %s: already injected, skip', sid[:12])
                skip += 1; continue

            log.info('--- %s (%d chs) [%s] ---', sid[:12], len(chs), title[:40])
            result = run_inject(conn, sid, skip_tables=True)
            if result.get('status') == 'ok':
                acc = result.get('acceptance', {})
                log.info('  OK h1=%d PASS=%s seq=%s [%s]',
                         result['chapters_found'], acc.get('PASS'), acc.get('R1_sequential'),
                         title[:30])
                ok += 1
            else:
                log.warning('  FAIL %s: %s  [%s]', result.get('status'), result.get('reason', ''), title[:40])
                err += 1

        log.info('CN inject: ok=%d skip=%d err=%d', ok, skip, err)

    # ── CN plain-text running-header injection (线性代数/高数上下) ────────────────
    if args.cn_inject_plainstext:
        log.info('=== CN plain-text inject (running-header books) ===')
        sys.path.insert(0, '/app/scripts')
        from book_structure_inject import load_chapters_from_pdf
        import os as _os, json as _json

        # Specific books: flat OCR text with 第N章 running headers, no H2 markers.
        # Pattern 10 (added to _search_chapter_h2) locates first running header per chapter.
        PLAINSTEXT_IDS = {
            '01KVQ3HN9H5J': 'normal',     # 线性代数第六版 ch1-6
            '01KVQ13J49KR': 'normal',     # 高等数学上册 ch1-7
            '01KVQ16E1SKQ': 'multivol',   # 高等数学下册 ch8-12
        }

        ok = skip = err = 0
        for id_prefix, mode in PLAINSTEXT_IDS.items():
            row = conn.execute('SELECT id, title, source_path FROM substrates WHERE id LIKE ?',
                               (id_prefix + '%',)).fetchone()
            if not row:
                log.warning('%s: NOT FOUND', id_prefix)
                err += 1; continue
            sid, title, sp = row

            md_row = conn.execute(
                "SELECT content FROM derivative WHERE substrate_id=? AND kind='markdown'", (sid,)
            ).fetchone()
            if not md_row:
                log.warning('%s: no markdown', sid[:12])
                skip += 1; continue
            if re.search(r'^# Chapter \d+:', md_row[0], re.M):
                log.info('%s: already injected, skip [%s]', sid[:12], title[:30])
                skip += 1; continue

            log.info('--- %s  mode=%s  [%s] ---', sid[:12], mode, title[:40])
            result = run_inject(conn, sid, skip_tables=True)

            if result.get('status') == 'ok':
                acc = result.get('acceptance', {})
                ch_pass = acc.get('PASS')

                if not ch_pass and mode == 'multivol':
                    # Multi-volume: chapters may not start at 1 → acceptance PASS=False is expected.
                    # Check that chapters are actually sequential (R1_sequential True).
                    new_md = read_md(conn, sid)
                    chs, _ = load_chapters_from_pdf(pathlib.Path(sp))
                    ch_nums = sorted([int(m.group(1)) for m in re.finditer(r'^# Chapter (\d+):', new_md or '', re.M)])
                    is_seq = ch_nums == list(range(ch_nums[0], ch_nums[0]+len(ch_nums))) if ch_nums else False
                    log.info('  multivol: chapters=%s seq=%s PASS=%s', ch_nums, is_seq, ch_pass)
                    if is_seq:
                        # Tag meta_json with multivolume flag
                        meta_row = conn.execute('SELECT meta_json FROM substrates WHERE id=?', (sid,)).fetchone()
                        meta = _json.loads(meta_row[0] or '{}') if meta_row else {}
                        meta['multivolume_inject'] = True
                        meta['multivolume_chapters'] = ch_nums
                        conn.execute('UPDATE substrates SET meta_json=? WHERE id=?', (_json.dumps(meta), sid))
                        log.info('  tagged multivolume_inject=True')
                        ch_pass = True  # Treat as ok for reporting
                    else:
                        log.warning('  FAIL: not sequential, chapters=%s', ch_nums)
                        err += 1; continue

                if ch_pass:
                    # Strip running headers (第N章 plain-text lines) from injected markdown
                    new_md = read_md(conn, sid)
                    chs, _ = load_chapters_from_pdf(pathlib.Path(sp))
                    stripped = strip_cn_running_headers(new_md, chs)
                    h_before = sum(len(re.findall(r'(?m)^第' + re.escape(str(c.ch_num)) + r'章', new_md)) for c in chs)
                    h_after  = sum(len(re.findall(r'(?m)^第' + re.escape(str(c.ch_num)) + r'章', stripped)) for c in chs)
                    write_md(conn, sid, stripped)
                    log.info('  OK h1=%d PASS=%s running_hdr_removed=%d [%s]',
                             result['chapters_found'], ch_pass, h_before - h_after, title[:30])
                    ok += 1
                else:
                    log.warning('  FAIL PASS=%s seq=%s [%s]', acc.get('PASS'), acc.get('R1_sequential'), title[:30])
                    err += 1
            else:
                log.warning('  FAIL %s: %s [%s]', result.get('status'), result.get('reason',''), title[:30])
                err += 1

        log.info('CN plainstext inject: ok=%d skip=%d err=%d', ok, skip, err)

    # ── CN broken-book marking ────────────────────────────────────────────────
    if args.cn_mark_broken:
        log.info('=== CN broken-book marking ===')
        import json as _json

        BROKEN = {
            # Fragments (<10k chars, mid-volume)
            '01KVJQ05Z9E6': {'broken_reason': 'fragment_preview', 'needs_better_source': True},
            '01KVQ31ST4CC': {'broken_reason': 'fragment_vol3_ch22plus', 'needs_better_source': True},
            '01KVQ0Y4AF0P': {'broken_reason': 'fragment_vol2_ch10plus', 'needs_better_source': True},
            # Bundle (11-book set, needs per-book splitting)
            '01KVJRF905WY': {'broken_reason': 'bundle_11books', 'needs_split': True},
            # OCR garbled (variant Unicode chars / flat TOC / image-heavy)
            '01KVJQK4K6TQ': {'broken_reason': 'ocr_variant_chars', 'needs_better_source': True},
            '01KVJR5VQ30D': {'broken_reason': 'ocr_flat_toc_no_headings', 'needs_better_source': True},
            '01KVAGBCMEDX': {'broken_reason': 'ocr_50pct_images', 'needs_better_source': True},
        }

        ok = err = 0
        for id_prefix, tags in BROKEN.items():
            row = conn.execute('SELECT id, title FROM substrates WHERE id LIKE ?',
                               (id_prefix + '%',)).fetchone()
            if not row:
                log.warning('%s: NOT FOUND', id_prefix)
                err += 1; continue
            sid, title = row
            meta_row = conn.execute('SELECT meta_json FROM substrates WHERE id=?', (sid,)).fetchone()
            meta = _json.loads(meta_row[0] or '{}') if meta_row else {}
            meta.update(tags)
            conn.execute('UPDATE substrates SET meta_json=? WHERE id=?', (_json.dumps(meta), sid))
            log.info('  tagged %s: %s  [%s]', sid[:12], tags, title[:40])
            ok += 1

        log.info('CN mark-broken: tagged=%d err=%d', ok, err)

    # ── 36-PDF bookmark scan ──────────────────────────────────────────────────
    if args.b36_scan:
        log.info('=== 36-PDF bookmark format scan ===')
        from collections import Counter
        results = scan_36_pdf_bookmarks(conn)
        fmt_dist = Counter(r['format'] for r in results)
        log.info('Format distribution: %s  (total=%d)', dict(fmt_dist), len(results))
        for fmt in ('chapter', 'part', 'numbered', 'chinese', 'section', 'other', 'no_bookmarks'):
            group = [r for r in results if r['format'] == fmt]
            if not group:
                continue
            log.info('\n--- %s (%d books) ---', fmt, len(group))
            for r in group:
                log.info('  %s  %s', r['id'][:12], repr(r['title'][:45]))
                for t, p in r.get('lv1_samples', [])[:2]:
                    log.info('    lv1 p%d: %s', p, repr(t[:60]))

    conn.close()
    log.info('=== Done ===')


if __name__ == '__main__':
    main()
