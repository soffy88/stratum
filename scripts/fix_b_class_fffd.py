#!/usr/bin/env python3
"""
fix_b_class_fffd.py — Context-based FFFD repair for B-class math books.

§20: stratum/scripts layer only — does NOT modify oprim/oskill/omodul/obase/oservi

Applies pure markdown context patterns to fix known encoding artifacts.
Does NOT need PDF access (complement to math_font_repair.py which does).

Books and fixes:
  essential_maths (01KVA4754)
      Essential Mathematics for Economic Analysis (Jacques, 5e)
      373 FFFDs: Δ (delta, U+0394) before variable + Ω (omega, U+03A9) isolated
      _□letter → _Δletter  (italic delta-t/r/y/b/p etc., 32+26+18+12+9 = ~100x)
      _□_ → _Ω_            (universal set symbol, 23x)
      Remaining ~250 standalone □ need font analysis (MathPi or similar font TBD)

  math_analysis (01KVAJVD)
      An Introduction to Mathematical Analysis for Economics
      2248 FFFDs: □→ = ↦ (maps-to, U+21A6, 297x)
      Remaining ~1950 FFFDs are [Σ]/[∫] in subscript notation + standalone ops
      → need font analysis to identify safely

  micro_calculus (01KVA59X)
      Microeconomics: An Intuitive Approach with Calculus
      7 FFFDs: fi/ti ligature artifacts
      31 CHAPTER noise: C H A P T E R N running page headers (R9 violations)

Usage (inside Docker container):
    python3 fix_b_class_fffd.py --book essential_maths \\
        --md /data/shared/stratum-to-aii/01KVA4754S7Q5SJY3PF9Y2HPR5.md [--dry-run]
"""
from __future__ import annotations
import re, sys, argparse, logging, pathlib

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)-8s %(message)s')
log = logging.getLogger(__name__)

FFFD = '�'


# ─────────────────────────────────────────────────────────────────────────────
# Per-book fix functions
# ─────────────────────────────────────────────────────────────────────────────

def fix_essential_maths_econ(md: str) -> tuple[str, int, int]:
    """
    Jacques 'Essential Mathematics for Economic Analysis'.
    Two safe patterns:
      1. _□_           → _Ω_   (universal set symbol, isolated italic FFFD)
      2. _□[a-zA-Z]   → _Δ[letter]  (delta prefix in italic: Δt, Δr, Δy, Δb, Δp ...)
    Order matters: Ω rule first so _□_ is not mismatched by Δ rule.
    """
    before = md.count(FFFD)

    # Rule 1: isolated italic FFFD (_□_) → Ω
    md = md.replace(f'_{FFFD}_', '_Ω_')

    # Rule 2: delta prefix in italic (_□letter) → _Δletter
    md = re.sub(f'_{FFFD}([a-zA-Z])', lambda m: f'_Δ{m.group(1)}', md)

    after = md.count(FFFD)
    return md, before - after, after


def fix_math_analysis_econtheory(md: str) -> tuple[str, int, int]:
    """
    'An Introduction to Mathematical Analysis for Economics'.
    Safe pattern: □→ = ↦ (maps-to, U+21A6).
    Context: 'a □→ f(a)' i.e. function mapping notation — 297 occurrences.
    """
    before = md.count(FFFD)

    # □→ (FFFD + right-arrow U+2192) → ↦ (maps-to U+21A6)
    md = md.replace(f'{FFFD}→', '↦')

    after = md.count(FFFD)
    return md, before - after, after


def fix_micro_calculus(md: str) -> tuple[str, int, int, int]:
    """
    'Microeconomics: An Intuitive Approach with Calculus'.
    Two operations:
      A. fi/ti ligature FFFDs (7x) — direct word-context replacements
      B. C H A P T E R N noise strip (31x) — running page header removal (R9)
    """
    fffd_before = md.count(FFFD)
    ch_before = len(re.findall(r'C\s+H\s+A\s+P\s+T\s+E\s+R', md))

    # A. Ligature fixes: □ = 'fi' or 'ti' ligature glyph
    SUBS: list[tuple[str, str]] = [
        # ti ligature (3 occurrences)
        (f'Discrimina{FFFD}on',  'Discrimination'),
        (f'Op{FFFD}mal',         'Optimal'),
        (f'nega{FFFD}ve',        'negative'),
        # fi ligature (4 occurrences)
        (f'Pro **{FFFD}** it',   'Profit'),   # bold fi ligature formatting artifact
        (f'pro{FFFD}it',         'profit'),
        (f'Pro{FFFD}it',         'Profit'),
    ]
    for old, new in SUBS:
        md = md.replace(old, new)

    # B. Strip CHAPTER noise — two passes:
    # Pass 1: standalone "C H A P T E R N" lines (numbered, no title text) → delete line
    md = re.sub(
        r'^(?:## )?C\s+H\s+A\s+P\s+T\s+E\s+R\s+\d+[ \t]*$\n?',
        '',
        md,
        flags=re.MULTILINE,
    )
    # Pass 2: CHAPTER prefix merged into a heading/paragraph with title text
    # "## C H A P T E R Title..." → "## Title..." (strip prefix, keep title)
    # "C H A P T E R Title..." → "Title..." (no ## prefix case)
    md = re.sub(
        r'^(## )?C\s+H\s+A\s+P\s+T\s+E\s+R\s+(?!\d+[ \t]*$)',
        r'\1',
        md,
        flags=re.MULTILINE,
    )

    fffd_after = md.count(FFFD)
    ch_after = len(re.findall(r'C\s+H\s+A\s+P\s+T\s+E\s+R', md))
    return md, fffd_before - fffd_after, fffd_after, ch_before - ch_after


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

BOOK_CHOICES = ('essential_maths', 'math_analysis', 'micro_calculus')


def main() -> int:
    p = argparse.ArgumentParser(
        description='Context-based FFFD repair for B-class math books'
    )
    p.add_argument(
        '--book', required=True, choices=BOOK_CHOICES,
        help='Which book to fix',
    )
    p.add_argument('--md', required=True, help='Markdown file to fix in-place')
    p.add_argument('--dry-run', action='store_true', help='Report only, do not write')
    args = p.parse_args()

    md_path = pathlib.Path(args.md)
    if not md_path.exists():
        log.error('MD not found: %s', md_path)
        return 1

    log.info('Reading %s', md_path)
    md = md_path.read_text(encoding='utf-8')
    fffd_before = md.count(FFFD)
    log.info('Before: FFFD=%d  chars=%d', fffd_before, len(md))

    if args.book == 'essential_maths':
        new_md, fixed, remaining = fix_essential_maths_econ(md)
        log.info('essential_maths: fixed=%d  remaining=%d', fixed, remaining)

    elif args.book == 'math_analysis':
        new_md, fixed, remaining = fix_math_analysis_econtheory(md)
        log.info('math_analysis: fixed=%d  remaining=%d', fixed, remaining)

    elif args.book == 'micro_calculus':
        new_md, fffd_fixed, fffd_remaining, ch_fixed = fix_micro_calculus(md)
        log.info(
            'micro_calculus: FFFD fixed=%d remaining=%d  CHAPTER noise stripped=%d',
            fffd_fixed, fffd_remaining, ch_fixed,
        )
        fixed = fffd_fixed
        remaining = fffd_remaining

    if args.dry_run:
        log.info('DRY-RUN: no files written')
        return 0

    log.info('Writing %d chars to %s', len(new_md), md_path)
    md_path.write_text(new_md, encoding='utf-8')
    log.info('Done.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
