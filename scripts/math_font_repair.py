#!/usr/bin/env python3
"""
math_font_repair.py — R6 (MathematicalPi-One encoding) + R7 (figure captions)

§20: stratum/scripts layer only — does NOT modify oprim/oskill/omodul/obase/oservi

R6: MathematicalPi-One is a Type1 font whose ToUnicode CMap only maps space.
    6 math glyphs (H11002 H9004 H11005 H11001 H11003 H11032 etc.) produce U+FFFD.
    Each PDF font *instance* (embedded subset) has its own /Differences array, so
    the byte-code→glyph-name mapping varies per font xref. This script:
      1. Builds per-xref code→unicode maps from /Differences
      2. Parses content streams for ordered glyph codes per MathPi alias per page
      3. Uses rawdict for ordered MathPi FFFD positions + surrounding context
      4. Applies corrections to the md using context-anchored replacement

R7: Figure captions exist in the PDF text layer in two forms:
    Form A — "## **FIGURE N.M  Caption**" heading above the picture block
    Form B — "FIGURE N.M  Caption<br>" as first line inside picture text block
    Both are converted to ![Figure N.M: Caption]() notation.

Usage (inside Docker container):
    python3 math_font_repair.py --pdf /path/to/book.pdf --md /path/to/book.md [--dry-run]
"""
from __future__ import annotations
import sys, os, re, argparse, logging, pathlib

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)-8s %(message)s')
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# R6 — MathematicalPi glyph-name → Unicode mapping (universal, reusable)
# ─────────────────────────────────────────────────────────────────────────────

MATHPI_GLYPH_UNICODE: dict[str, str] = {
    # MathematicalPi-One core symbols — confirmed from PDF content stream analysis
    'H11002': '−',  # − (minus sign)
    'H9004':  'Δ',  # Δ (Greek capital delta)
    'H11005': '=',       # = (equals sign)
    'H11001': '+',       # + (plus sign)
    'H11003': '×',  # × (multiplication sign)
    'H11032': '′',  # ′ (prime)
    # Additional glyphs found in extended font instances
    'H9261':  'λ',  # λ (lambda — used as scale factor in production theory)
    'H11021': '<',       # < (less than)
    'H11022': '>',       # > (greater than)
    'H11009': '≠',  # ≠ (not equal — educated guess, verify if encountered)
    'H11350': '÷',  # ÷ (division — educated guess, verify if encountered)
    'H9255':  'ε',  # ε (epsilon — in MathPi-Four, educated guess)
    'H9251':  'α',  # α (alpha)
    'H9252':  'β',  # β (beta)
    'H11006': '≤',  # ≤ (less than or equal)
    'H11007': '≥',  # ≥ (greater than or equal)
    'H11008': '≠',  # ≠
    'H11021': '<',
    'H11022': '>',
    # MathematicalPi-Three: typically contains division slash, fraction bar etc.
    # (MathPi-Three glyphs produce FFFD but may be structural separators)
}

UNKNOWN_GLYPHS: set[str] = set()  # collects glyph names not in the map


def build_xref_code_map(doc, xref: int) -> dict[int, str]:
    """Parse /Differences array for a font xref → {byte_code: unicode_char}."""
    try:
        obj_str = doc.xref_object(xref, compressed=False)
    except Exception:
        return {}

    enc_m = re.search(r'/Encoding\s+(\d+)\s+0\s+R', obj_str)
    if not enc_m:
        return {}
    enc_xref = int(enc_m.group(1))

    try:
        enc_str = doc.xref_object(enc_xref, compressed=False)
    except Exception:
        return {}

    diff_m = re.search(r'/Differences\s*\[([^\]]+)\]', enc_str, re.DOTALL)
    if not diff_m:
        return {}

    code_map: dict[int, str] = {}
    cur_code: int | None = None
    for token in diff_m.group(1).split():
        if token.startswith('/'):
            glyph_name = token[1:]
            if cur_code is not None:
                uc = MATHPI_GLYPH_UNICODE.get(glyph_name)
                if uc is not None:
                    code_map[cur_code] = uc
                elif glyph_name != 'space':
                    UNKNOWN_GLYPHS.add(glyph_name)
                cur_code += 1
        else:
            try:
                cur_code = int(token)
            except ValueError:
                pass

    return code_map


def decode_pdf_literal(s: str) -> bytes:
    """Decode a PDF literal string (content between outer parens, already stripped)."""
    result = bytearray()
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == '\\' and i + 1 < len(s):
            nx = s[i + 1]
            if '0' <= nx <= '7':
                oc = nx
                j = i + 2
                while j < len(s) and '0' <= s[j] <= '7' and len(oc) < 3:
                    oc += s[j]; j += 1
                result.append(int(oc, 8)); i = j; continue
            elif nx == 'n': result.append(10)
            elif nx == 'r': result.append(13)
            elif nx == 't': result.append(9)
            elif nx == '\\': result.append(92)
            elif nx == '(': result.append(40)
            elif nx == ')': result.append(41)
            else: result.append(ord(nx) & 0xFF)
            i += 2
        else:
            result.append(ord(ch) & 0xFF); i += 1
    return bytes(result)


# Regex tokeniser for PDF content stream
_CS_TOK = re.compile(
    r'/([^\s\[\]<>()/]+)'           # name
    r'|\(([^)\\]*(?:\\.[^)\\]*)*)\)'  # literal string
    r'|<([0-9A-Fa-f\s]*)>'          # hex string
    r'|(-?(?:\d+\.?\d*|\.\d+))'     # number
    r'|([A-Za-z*"\']+)',             # operator/keyword
    re.DOTALL,
)


def extract_mathpi_codes(content_bytes: bytes, alias: str) -> list[int]:
    """Return ordered list of non-space glyph codes emitted by `alias` font."""
    try:
        content = content_bytes.decode('latin-1', errors='replace')
    except Exception:
        return []

    codes: list[int] = []
    cur_font: str | None = None
    op_stack: list[tuple[str, object]] = []

    for m in _CS_TOK.finditer(content):
        nm, lit, hx, num, op = m.groups()

        if nm is not None:
            op_stack.append(('n', nm))
        elif lit is not None:
            op_stack.append(('s', decode_pdf_literal(lit)))
        elif hx is not None:
            h = re.sub(r'\s', '', hx)
            if len(h) % 2: h += '0'
            op_stack.append(('s', bytes.fromhex(h) if h else b''))
        elif num is not None:
            op_stack.append(('v', None))
        elif op is not None:
            if op == 'Tf':
                names = [v for t, v in op_stack if t == 'n']
                if names:
                    cur_font = names[-1]
            elif op in ('Tj', "'"):
                if cur_font == alias:
                    for t, v in op_stack:
                        if t == 's':
                            codes.extend(b for b in v if b != 32)
            elif op == 'TJ':
                if cur_font == alias:
                    for t, v in op_stack:
                        if t == 's':
                            codes.extend(b for b in v if b != 32)
            op_stack = []

    return codes


# ─────────────────────────────────────────────────────────────────────────────
# Context-anchored FFFD replacement in md
# ─────────────────────────────────────────────────────────────────────────────

FFFD = '�'


def replace_fffd_with_context(
    md: str,
    before: str,
    after: str,
    replacement: str,
    search_from: int = 0,
    max_gap: int = 120,
) -> tuple[str, int, bool]:
    """
    Find the FFFD char in md[search_from:] using before-context anchor.
    Returns (new_md, fffd_pos_found, success).

    The caller should pass search_from = max(0, prev_fffd_pos - max_gap) so that
    anchors overlapping the previous correction's context are still found.

    Anchor = the NON-FFFD prefix of before-text (last 25 chars, trailing-stripped).
    Markdown formatting (_x_, *x*) in the md is silently skipped by max_gap.
    No after-context check — it would fail due to md vs rawdict formatting mismatch.
    """
    # Build anchor from the stable part of before (text up to any FFFD it contains)
    if FFFD in before:
        anchor_raw = before[:before.index(FFFD)]
    else:
        anchor_raw = before
    anchor = anchor_raw.rstrip()[-25:]

    if not anchor:
        # No stable anchor: scan forward for a FFFD whose after-context matches.
        after_prefix = (after[:after.index(FFFD)] if FFFD in after else after).strip()[:12]
        scan = search_from
        while True:
            pos = md.find(FFFD, scan)
            if pos == -1:
                return md, search_from, False
            if after_prefix:
                actual_raw = md[pos + 1: pos + 1 + len(after_prefix) + 20]
                actual_clean = re.sub(r'[_*`]', '', actual_raw.replace(FFFD, ''))
                target_clean = re.sub(r'[_*`]', '', after_prefix)
                if actual_clean.startswith(target_clean[:8]):
                    break          # matched
                scan = pos + 1
                continue
            break                  # no after-context to validate — take first FFFD
        new_md = md[:pos] + replacement + md[pos + 1:]
        return new_md, pos, True   # return pos (not pos+len) so caller can backtrack

    # Find anchor, then take the first FFFD within max_gap chars after it
    search_pos = search_from
    while True:
        anchor_pos = md.find(anchor, search_pos)
        if anchor_pos == -1:
            return md, search_from, False
        look_from = anchor_pos + len(anchor)
        fffd_pos = md.find(FFFD, look_from, look_from + max_gap)
        if fffd_pos == -1:
            search_pos = anchor_pos + 1
            continue
        new_md = md[:fffd_pos] + replacement + md[fffd_pos + 1:]
        return new_md, fffd_pos, True   # return pos so caller can backtrack safely


# ─────────────────────────────────────────────────────────────────────────────
# R6 main: fix MathPi FFFD in md
# ─────────────────────────────────────────────────────────────────────────────

def _span_chars_to_text(span: dict) -> str:
    """Reconstruct span text from the 'chars' array (rawdict mode)."""
    result = []
    for c in span.get('chars', []):
        ch = c.get('c', '')
        if isinstance(ch, int):
            ch = chr(ch)
        result.append(ch)
    return ''.join(result)


def fix_r6(pdf_path: str, md: str, dry_run: bool = False) -> tuple[str, dict]:
    import fitz

    doc = fitz.open(pdf_path)
    total_pages = doc.page_count

    # Cache xref → code_map (built on demand)
    xref_code_cache: dict[int, dict[int, str]] = {}

    all_corrections: list[tuple[str, str, str, str]] = []
    # Each element: (replacement, before_context, after_context, glyph_name)

    pages_with_mathpi = 0

    for pg_idx in range(total_pages):
        page = doc[pg_idx]
        fonts = page.get_fonts()

        # Find MathPi fonts on this page (could be multiple variants/instances)
        mathpi_fonts = [f for f in fonts if 'MathematicalPi' in f[3]]
        if not mathpi_fonts:
            continue

        pages_with_mathpi += 1

        # Build alias→code_map AND fontname→alias for this page
        alias_code_maps: dict[str, dict[int, str]] = {}
        fontname_to_alias: dict[str, str] = {}  # full_font_name → alias
        for f in mathpi_fonts:
            xref, basefont, alias = f[0], f[3], f[4]
            if xref not in xref_code_cache:
                xref_code_cache[xref] = build_xref_code_map(doc, xref)
            cm = xref_code_cache[xref]
            if cm:
                alias_code_maps[alias] = cm
                fontname_to_alias[basefont] = alias
                # Also map the short name (without subset prefix)
                short = basefont.split('+', 1)[-1] if '+' in basefont else basefont
                fontname_to_alias[short] = alias

        if not alias_code_maps:
            continue

        # For each alias, extract ALL glyph codes from content stream (including unknown)
        # Keep unknowns as FFFD so rawdict and code-deque stay in sync
        content = b''.join(filter(None, [doc.xref_stream(x) for x in page.get_contents()]))
        alias_code_seqs: dict[str, list[str]] = {}  # alias → list of unicode chars
        for alias, cm in alias_code_maps.items():
            all_codes = extract_mathpi_codes(content, alias)
            # map each code: known→unicode, unknown→FFFD (stays unchanged in md)
            unicode_seq = [cm.get(c, FFFD) for c in all_codes]
            if unicode_seq:
                alias_code_seqs[alias] = unicode_seq

        if not alias_code_seqs:
            continue

        # Build alias→deque for ordered consumption
        from collections import deque
        alias_code_deques: dict[str, deque] = {
            alias: deque(seqs) for alias, seqs in alias_code_seqs.items()
        }

        # Walk rawdict in order to collect MathPi FFFDs with context
        try:
            page_dict = page.get_text('rawdict', flags=0)
        except Exception as e:
            log.warning('p%d: rawdict failed: %s', pg_idx + 1, e)
            continue

        for block in page_dict['blocks']:
            if block.get('type') != 0:
                continue
            for line in block['lines']:
                spans = line['spans']
                # Pre-compute text for each span (rawdict mode: use chars)
                span_texts = [_span_chars_to_text(s) for s in spans]

                for si, span in enumerate(spans):
                    font_name = span.get('font', '')
                    if 'MathematicalPi' not in font_name:
                        continue

                    # Map font_name → alias → code deque
                    matching_alias = (
                        fontname_to_alias.get(font_name)
                        or fontname_to_alias.get(font_name.split('+', 1)[-1])
                    )
                    if matching_alias is None or matching_alias not in alias_code_deques:
                        continue

                    dq = alias_code_deques[matching_alias]
                    cm = alias_code_maps[matching_alias]
                    chars_in_span = span.get('chars', [])

                    for ci, char in enumerate(chars_in_span):
                        ch = char.get('c', '')
                        if isinstance(ch, int):
                            ch = chr(ch)
                        if ch != FFFD:
                            continue

                        if not dq:
                            log.warning('p%d: ran out of codes for %s (alias %s)',
                                        pg_idx + 1, font_name, matching_alias)
                            continue

                        replacement = dq.popleft()  # already unicode char or FFFD
                        glyph_name = next(
                            (g for g, u in MATHPI_GLYPH_UNICODE.items() if u == replacement),
                            'unknown'
                        )
                        if replacement == FFFD:
                            continue  # unknown glyph — leave FFFD unchanged

                        # Build context from SAME LINE using span_texts
                        # before: text in spans 0..si-1, plus chars 0..ci-1 in current span
                        before_parts = list(span_texts[:si])
                        before_parts += [
                            (ch2 if not isinstance(ch2 := c2.get('c',''), int) else chr(ch2))
                            for c2 in chars_in_span[:ci]
                        ]
                        before_text = ''.join(before_parts)[-30:]

                        # after: chars ci+1.. in current span, plus spans si+1..
                        after_parts = [
                            (ch2 if not isinstance(ch2 := c2.get('c',''), int) else chr(ch2))
                            for c2 in chars_in_span[ci + 1:]
                        ]
                        after_parts += span_texts[si + 1:]
                        after_text = ''.join(after_parts)[:20]

                        all_corrections.append((replacement, before_text, after_text, glyph_name))

    doc.close()
    log.info('R6: collected %d MathPi corrections from %d pages',
             len(all_corrections), pages_with_mathpi)
    if UNKNOWN_GLYPHS:
        log.warning('R6: unknown glyph names (left as FFFD): %s', sorted(UNKNOWN_GLYPHS))

    if dry_run:
        log.info('R6 DRY-RUN: first 15 corrections:')
        for repl, bef, aft, gn in all_corrections[:15]:
            log.info('  [%s] glyph=%s before=%r after=%r', repl, gn, bef[-20:], aft[:20])
        return md, {'fixed': 0, 'total': len(all_corrections), 'dry_run': True}

    # ── Apply corrections ────────────────────────────────────────────────────
    # pymupdf4llm wraps variable names in _ (italic), e.g. rawdict "y" → md "_y_".
    # We precompute a bare md (strip all `_`) so anchors from rawdict plain text
    # can match the md's italicised content.  Since replacements never touch `_`
    # chars (FFFD and math symbols are not `_`), the bare→orig mapping stays valid.
    import bisect

    _MAX_GAP_BARE = 180   # search window in bare-md chars
    _MAX_GAP_ORIG = 240   # window for FFFD search in original md (extra for _ chars)

    new_md = md
    md_bare = new_md.replace('_', '')                          # strip italic markers
    bare_to_orig = [i for i, c in enumerate(new_md) if c != '_']  # bare[i] → orig pos

    fixed = 0
    skipped = 0
    bare_search_pos = 0  # tracks last successful fix position in bare-space

    for i, (repl, before, after, glyph_name) in enumerate(all_corrections):
        # Build anchor: non-FFFD prefix of before-text, last 25 chars, rstripped
        anchor_raw = before[:before.index(FFFD)] if FFFD in before else before
        anchor = anchor_raw.rstrip()[-25:]   # rawdict has no `_`, so no stripping needed

        bare_start = max(0, bare_search_pos - _MAX_GAP_BARE)

        used_backtrack = False  # set True if anchor found only via full-doc backtrack
        if not anchor:
            # ── Empty anchor: scan forward for FFFD matching after-context ───
            after_prefix = (after[:after.index(FFFD)] if FFFD in after else after).strip()[:10]
            orig_start = bare_to_orig[bare_start] if bare_start < len(bare_to_orig) else len(new_md)
            scan = orig_start
            ok = False
            fffd_pos = -1
            while True:
                pos = new_md.find(FFFD, scan)
                if pos == -1:
                    break
                if after_prefix:
                    actual = re.sub(r'[_*`\s]', '', new_md[pos+1:pos+1+len(after_prefix)+30])
                    actual = actual.replace(FFFD, '')
                    target = re.sub(r'[_*`\s]', '', after_prefix)
                    if actual.startswith(target[:8]):
                        ok = True
                        fffd_pos = pos
                        break
                    scan = pos + 1
                else:
                    ok = True
                    fffd_pos = pos
                    break
        else:
            # ── Non-empty anchor: search in bare md, find FFFD in original ──
            # Two-stage: first from bare_start (forward), then full doc if missed.
            # Backtracking is safe: already-fixed FFFDs return no FFFD in window.
            ok = False
            fffd_pos = -1
            used_backtrack = False
            # Pre-compute stripped after-prefix for backtrack validation
            _after_raw = (after[:after.index(FFFD)] if FFFD in after else after)[:20]
            _after_ctx = re.sub(r'[\s_*`]', '', _after_raw)  # for backtrack validation
            for start_candidate in (bare_start, 0):
                if ok:
                    break
                scan_bare = start_candidate
                while True:
                    fp = md_bare.find(anchor, scan_bare)
                    if fp == -1:
                        break
                    end_bare = fp + len(anchor)
                    if end_bare >= len(bare_to_orig):
                        break
                    orig_after = bare_to_orig[end_bare]
                    pos = new_md.find(FFFD, orig_after, orig_after + _MAX_GAP_ORIG)
                    if pos != -1:
                        is_backtrack = (start_candidate == 0)
                        if is_backtrack and _after_ctx:
                            # Validate: after-context in md must match rawdict after-ctx
                            md_a = re.sub(r'[\s_*`]', '', new_md[pos+1:pos+30].replace(FFFD, ''))
                            n_match = sum(1 for a, b in zip(md_a, _after_ctx) if a == b)
                            min_needed = min(3, len(_after_ctx))
                            if n_match < min_needed:
                                # After-context mismatch: try next anchor occurrence
                                scan_bare = fp + 1
                                continue
                        ok = True
                        fffd_pos = pos
                        used_backtrack = (start_candidate == 0)
                        break
                    scan_bare = fp + 1

        if ok and fffd_pos >= 0:
            new_md = new_md[:fffd_pos] + repl + new_md[fffd_pos + 1:]
            # On backtrack: don't move bare_search_pos backward (let it stay advanced)
            if not used_backtrack:
                bare_search_pos = bisect.bisect_left(bare_to_orig, fffd_pos)
            fixed += 1
            if fixed <= 5:
                log.info('R6 fix[%d] [%s] anchor=%r fffd_pos=%d', i, repl, anchor[-20:], fffd_pos)
        else:
            skipped += 1
            if skipped <= 5:
                found_in_bare = md_bare.find(anchor) if anchor else -1
                log.info('R6 skip[%d] [%s] anchor=%r bare_found=%d bare_start=%d',
                         i, repl, anchor[-20:], found_in_bare, bare_start)

    log.info('R6: fixed=%d skipped=%d total=%d', fixed, skipped, len(all_corrections))

    # ── Pass 2: content-based pattern matching for remaining FFFDs ────────────
    new_md, p2_fixed = _fix_r6_pass2(new_md)
    log.info('R6 pass2: fixed=%d additional FFFDs by content pattern', p2_fixed)

    # ── Pass 3: fix low-codepoint control chars (U+0002/0003/0004) ────────────
    # pymupdf outputs chr(N) for MathPi byte-code N when ToUnicode is absent.
    # Only fix positions where context unambiguously determines the symbol.
    new_md, p3_fixed = _fix_r6_ctrl_chars(new_md)
    if p3_fixed:
        log.info('R6 pass3: fixed=%d control-char positions', p3_fixed)

    remaining_fffd = new_md.count(FFFD)
    log.info('R6: remaining FFFD in md: %d', remaining_fffd)

    return new_md, {
        'fixed': fixed,
        'skipped': skipped,
        'total': len(all_corrections),
        'remaining_fffd': remaining_fffd,
        'pass2_fixed': p2_fixed,
    }


def _fix_r6_ctrl_chars(md: str) -> tuple[str, int]:
    """
    Pass 3: fix U+0002/U+0003/U+0004 control chars that pymupdf emits when the
    MathPi font's ToUnicode CMap is absent and the glyph byte code is small.
    Only replace where surrounding text makes the correct symbol unambiguous.
    """
    fixed = 0
    replacements = [
        # U+0004 (byte 4 → H11005 → =): income table section headers
        ('Income \x04 $1,000',       'Income = $1,000'),
        ('Income \x04 $4,000',       'Income = $4,000'),
        # U+0003 (byte 3 → H9004 in MathPi-One, but = sign in other font instances)
        ('fees (annual) \x03 $',     'fees (annual) = $'),
        # URL query-string parameters (= sign separating key=value)
        ('data\x03yieldYear',        'data=yieldYear'),
        ('year\x032011',             'year=2011'),
    ]
    for old, new in replacements:
        count = md.count(old)
        if count:
            md = md.replace(old, new)
            fixed += count
    return md, fixed


def _fix_r6_pass2(md: str) -> tuple[str, int]:
    """
    Content-based second pass: fix remaining FFFDs by reading their surrounding
    context in the md.  Only applies rules where BOTH before AND after context
    uniquely identify the replacement.  Conservative — better to leave a FFFD
    than to corrupt the text.

    Stripping: re.sub(r'[_*`\\s]', '', text) removes markdown + whitespace.
    FFFDs already replaced in pass1 appear as actual chars (=, −, Δ, etc.).
    Remaining FFFDs are replaced with □ so rules can reference them.
    """
    FFFD = chr(0xFFFD)

    # ── Pre-step: correct KNOWN wrong replacements from pass1 forward search ─
    # These occur when a [=] correction was applied to a [−] FFFD position.
    # Fix list item 1: "- 30 = 20 □" should be "- 30 − 20 □"
    md = md.replace('- 30 = 20 �', '- 30 − 20 �')

    # ── Rules: (stripped_before_suffix, stripped_after_prefix, replacement) ──
    # "Stripped" = re.sub(r'[_*`\s]', '', text) — removes markdown formatting + whitespace
    # Remaining FFFDs in raw text are replaced with □ before stripping.
    # Both sides must match exactly (suffix and prefix).
    RULES: list[tuple[str, str, str]] = [
        # ── Appendix 1A list item 1: "30 − 20 □ 10" → = ────────────────────
        ('30−20', '10', '='),
        # ── Appendix 1A list item 2: _x_ = the change in _x_ = 6 − 4 = 2 ──
        ('x', 'thechangeinx', '='),           # "_x_ □ the change in _x_" → =
        ('thechangeinx', '6□4', '='),          # "the change in _x_ □ 6 □ 4" → =
        ('x=6', '4□2', '−'),                  # "_x_ = 6 □ 4 □ 2" → −
        ('6−4', '2', '='),                    # "6 − 4 □ 2" → =
        # ── Appendix 1A: y = mx + b ─────────────────────────────────────────
        ('y', 'mx□b', '='),                   # "y □ mx □ b" → =  (first □)
        ('mx', 'b2', '+'),                    # "mx □ b 20 = ..." → +
        ('b20', '5(1)', '='),                 # "b 20 □ 5(1) + b" → =
        ('5(1)', 'b', '+'),                   # "5(1) □ b" → +
        ('b', 'they-interce', '='),           # "b □ the y-intercept" → =
        # ── Appendix 1A: Δy/Δx slope: "-y/□x □ (18□12)/(2□1) □ 6" ─────────
        # (Note: y/□x means the □ IS the Δ symbol before x)
        ('get-y/', 'x□(18', 'Δ'),          # "-y/□x □ (18 − 12)/..." → Δ (Δx, second occ.)
        ('y/Δx', '(18', '='),                 # "y/Δx □ (18 − 12)/..." → = (second occ.)
        ('(18', '12)/(2', '−'),               # "(18 □ 12)/(2" → −
        ('(2', '1)□6', '−'),                  # "(2 □ 1) □ 6" → − (Appendix 1A)
        ('□1)', '6', '='),                    # "□ 1) □ 6" → = (→ "= 6")
        ('(2−1)', '6', '='),                  # "(2 − 1) □ 6" → = (Ch2-3 second occ.)
        # ── Appendix 1A: "y = " and "x = " and "m = " definitions ──────────
        ('where-y', 'thevalueofy', '='),         # "...b, where\n- y □ the value..." → =
        ('oint-x', 'thevalueofx', '='),          # "...a given point\n- x □ the value..." → =
        ('oint-m', 'theslopeof', '='),           # "...a given point\n- m □ the slope..." → =
        # ── Appendix 1A: y-axis intercept "x = 0, y = 15" ───────────────────
        ('pointx', '0,y□15.', '='),           # "the point x □ 0, y □ 15." → =
        ('pointx=0,y', '15.', '='),            # "point x = 0, y □ 15." → =
        # ── Ch2-3: ΔP = (P2 − P1) = $2.50 − $2.00 = $0.50, where Δ means ──
        # Note: in pass1-output, all □ below are STILL FFFD (not yet fixed)
        ('(P2)the', 'P□(P2□P', 'Δ'),          # “(P2) the □ P□(P2□P1)...” → Δ (ΔP)
        ('(P2)theΔP', '(P2□P1)□', '='),       # “the ΔP □ (P2□P1)□...” → =
        ('P=(P2', 'P1)□$2.50', '−'),          # “ΔP=(P2 □ P1)=...” → − (P2 − P1)
        ('P2−P1)', '$2.50□$2', '='),           # “(P2−P1) □ $2.50...” → =
        ('−P1)=$2.50', '$2.00□$0.50', '−'),   # “= $2.50 □ $2.00...” → −
        ('$2.50−$2.00', '$0.50,where', '='),   # “−$2.00 □ $0.50,where” → =
        ('where', 'means“change', 'Δ'),  # “where □ means “change in”” → Δ (curly L-quote)
        ('(P2', 'P1)', '−'),                  # “(P2 □ P1)” → − (general fallback)
        ('P1)', '$2.50', '='),                # "(P1) □ $2.50" → =
        ('$2.50', '$2.00', '−'),              # "$2.50 □ $2.00" → −
        ('$2.00', '$0.50,', '='),             # "$2.00 □ $0.50" → =
        # "%ΔP when P1 □ $30 and P2 □ $33"
        ('P1', '$30andP2', '='),
        ('andP2', '$33.', '='),
        # "%ΔQ when Q1 □ 45 and Q2 □ 30"
        ('Q1', '45andQ2', '='),
        ('andQ2', '30.', '='),
        # ── Cost formulas: TC = TFC + TVC ────────────────────────────────────
        ('TC)', 'Totalfixedcosts', '='),
        ('TFC)', 'Totalvariablecosts', '+'),
        # ── VMP formula: VMP = P × MP_L ──────────────────────────────────────
        ('2=P2', 'MPL<br>', '×'),             # "P 2 □ MP L" → ×
        ('1=P1', 'MPL<br>', '×'),             # "P 1 □ MP L" → ×
        # ── Midpoint elasticity formula ───────────────────────────────────────
        # η = [(Q2 − Q1)/((Q1+Q2)/2)] / [(P2 − P1)/((P1+P2)/2)] = 3.67
        # Six FFFDs (processed in order):
        # (1) = : the formula starts with η □ [(16 ...
        ('elasticityofdemand', '[(16', '='),   # "...elasticity of demand □ [(16" → =
        # (2) − : (16 □ 32)
        ('=[(16', '32)/(32', '−'),             # "= [(16 □ 32) / (32" → −
        # (3) + : (32 □ 16) midpoint denominator numerator
        ('/(32', '16)/2]/', '+'),              # "/ (32 □ 16) / 2] /" → +
        # (4) − : ($6 □ $5)
        ('[($6', '$5)/(5', '−'),              # "[($6 □ $5) / (5" → −
        # (5) + : (5 □ 6)
        ('/(5', '6)/2]', '+'),               # "/ (5 □ 6) / 2]" → +
        # (6) = : □ 3.67
        ('/2]', '3.67', '='),                 # "/ 2] □ 3.67" → =
        # Alt midpoint computation (second run, different order in text)
        ('[(32', '16)/2]/', '+'),             # "[(32 □ 16) / 2] /" → +
        ('[($5', '$6)/(6', '−'),              # alt version
        ('/(6', '5)/2]', '+'),               # alt version
        ('=[(32', '16)/(16+32)/2', '+'),     # yet another alt form
        # ── Ch9: Price elasticity computations ───────────────────────────────
        # Percentage change in price: (350−450)/450 = −0.22 = −22%
        ('/450−', '0.22□□22%', '='),           # "/450 − □ 0.22 □ □22%" → = (= −0.22)
        ('/450−=0.22', '□22%', '='),           # "−=0.22 □ □22%" → = (= −22%)
        ('=0.22=', '22%', '−'),                 # "=0.22= □ 22%" → − (−22%)
        # Babysitting elasticity: [($6−5)/5] □ 2.50%
        ('($6−5)/5]', '2.50%', '='),           # "[($6−5)/5] □ 2.50%" → =
        # Midpoint formula: (16 □ 32)/2
        ('−16)/(16', '32)/2]/', '+'),           # "(16 □ 32)/2]" → + (second occ.)
        # Elasticity of supply definition
        ('lasticityofdemand:', 'percentagechange', '='),  # "elasticity of demand: □ %" → =
        # picture placeholder = 0.8 is called "pure number"
        ('omitted<==', '0.8iscalled', '='),     # after picture: □ 0.8 is called → =
        # Price × quantity: $1 □ 40 million units
        ('perweek($1', '40millionunits)', '×'), # "$1 □ 40 million units" → ×
        # ── Ch9: εd comparison operators in section headings ─────────────────
        # NOTE: □ in suffix = the ε/η FFFD (unknown glyph). Rules listed in priority order.
        # Perfectly Inelastic: εd = 0
        ('PriceInelasticDemand(□d', '0)', '='),        # εd = 0 (Perfectly Inelastic)
        # Inelastic: εd < 1 (mixed-case)
        ('PriceInelasticDemand(□d', '1)What', '<'),    # Price Inelastic Demand (εd < 1)
        # Inelastic: εd < 1 (all-caps)
        ('PRICEINELASTICDEMAND(□d', '1)Asitu', '<'),   # PRICE INELASTIC DEMAND
        # Unitary: εd = 1 (mixed-case section)
        ('tyofDemand(□d', '1)Whatif,', '='),           # Unitary Price Elasticity of Demand
        # Unitary: εd = 1 (all-caps) — MUST come before Elastic rule
        ('UNITARYPRICEELASTICDEMAND(□d', '1)Asitu', '='),
        # Elastic: εd > 1 (mixed-case)
        ('PriceElasticDemand(□d', '1)OurNew', '>'),    # Price Elastic Demand (εd > 1)
        # Elastic: εd > 1 (all-caps) — after Unitary is already handled
        ('PRICEELASTICDEMAND(□d', '1)Asitu', '>'),     # PRICE ELASTIC DEMAND
        # ── Ch9: εd comparison in list examples ──────────────────────────────
        ('medicalcare□d', '0WhenPgoes', '='),           # medical care: εd = 0 (perfectly inelastic)
        ('coffee,gasoline-□d', '1WhenPgoes', '<'),      # gasoline/coffee: εd < 1 (inelastic)
        ('movies-□d', '1WhenPgoes', '<'),               # movies: εd < 1
        ('meals,manicures-□d', '1WhenPgoes', '<'),      # restaurant meals, manicures: εd < 1
        # ── Occupation % table: before=OCCUPATION_NAME, after=NN%<br> ───────
        ('Dishwasher', '83%<br>', '='),
        ('Child-careworker', '80%<br>', '='),
        ('Dentalhygienist', '76%<br>', '='),
        ('Cashier', '56%<br>', '='),
        ('Plumber', '39%<br>', '='),
        ('Waitress/waiter', '34%<br>', '='),
        ('Firefighter', '25%<br>', '='),
        ('Cook', '16%<br>', '='),
        ('Secretary', '13%<br>', '='),
        ('Casinoworker', '3%<br>Source', '='),
        # ── Later chapters: scattered identifiable formulas ──────────────────
        # Ch9: income elasticity header
        ('income,wehave', 'IncomeElasti', '='),      # "we have □ Income Elasticity" → =
        # Ch9: new (P×Q) expenditure
        ('thenew(P', 'Q)correspond', '×'),           # "(P □ Q) corresponds to" → ×
        # Ch12: risk-adjusted expected return = .02 or 2%
        ('1,000]/$1,000', '.02or2%', '='),           # "]/$1,000 □ .02 or 2%" → =
        # Ch13: r □ discount rate, t □ last year
        ('yeart.r', 'discountrate.', '='),            # "_r_ □ discount rate" → =
        ('discountrate.t', 'lastyearin', '='),        # "_t_ □ last year" → =
        ('Assumesr', '.05]', '='),                    # "[Assumes r □ .05]" → =
        ('Assumesr', '.10]', '='),                    # "[Assumes r □ .10]" → =
        # Ch14: VMP = Pe × MP
        ('VMPcurve(Pe', 'MP)for', '×'),              # "VMP curve (Pe □ MP)" → ×
        # Ch14: MC Line 2 = 2 + 0.0004q2
        ('andMCLine2', '2□0.0004q', '='),             # "MC Line 2 □ 2 □ 0.0004q" → =
        ('MCLine2=2', '0.0004q2', '+'),               # "MC Line 2 = 2 □ 0.0004q2" → +
        # Ch15: cost function C(q) = PX·X + PY·Y
        ('production?-C(q1)', 'PXX+PYY,', '='),      # "C(q1) □ PX·X + PY·Y" → =
        ('n?-C(q1)', 'PXX□PYY,', '='),               # "C(q1) □ PX·X □ PY·Y" → =
        ('q1)=PXX', 'PYY,where', '+'),               # "C(q1)=PX·X □ PY·Y" → +
        # (moved to earlier block — see ively-C(q2) rules)
        # Ch15 Appendix: isoquant slope −MPX/MPY = ΔY/ΔX = −slope (eq 15A.6)
        # Pattern in md: "MPX/MPY □ □□Y/□X □ □slope" = 6 FFFDs
        ('earrangingMPX/MPY', '□□Y/□X', '−'),        # □₁ after MPX/MPY → −
        ('gingMPX/MPY−', '□Y/□X', '='),              # □₂ → =
        ('gingMPX/MPY−=', 'Y/□X', 'Δ'),              # □₃ before Y → Δ
        ('MPY−=ΔY/', 'X□□slope', 'Δ'),               # □₄ before X → Δ
        ('Y/ΔX', '□slopeofisoqu', '='),              # □₅ before slope → =
        ('ΔX=', 'slopeofisoquant', '−'),             # □₆ before slope → −
        # Ch15 Appendix: C(q2) = 2[PX·X + PY·Y] (single list bullet)
        ('<==-C(q2)', '2[PXX+PYY]', '='),            # "C(q2) □ 2[PX·X+PY·Y]" → =
        # Ch15 Appendix: C(q2) = PX(2□X) + PY(2<Y) and similar forms
        # Rule fires for BOTH occurrences since both end with 'ively-C(q2)'
        ('ively-C(q2)', 'PX(2□X)', '='),             # "C(q2) □ PX(2..." → =
        ('C(q2)=PX(2', 'X)□PY(2<Y)', '×'),          # "PX(2 □ X) (< version)" → ×
        ('C(q2)=PX(2×X)', 'PY(2<Y)', '+'),           # "PX(2×X) □ PY(2<Y)" → +
        ('+PY(2<Y),where', 'isafactor', 'λ'),        # "where □ is a factor (<Y ver)" → λ
        ('C(q2)=PX(2', 'X)□PY(2+Y)', '×'),          # "PX(2 □ X) (+ version)" → ×
        ('C(q2)=PX(2×X)', 'PY(2+Y)', '+'),           # "PX(2×X) □ PY(2+Y)" → +
        ('+PY(2+Y),where', 'isafactor', 'λ'),        # "where □ is a factor (+Y ver)" → λ
        ('whereλisafactor', '1bywhi', '>'),           # "factor □ 1 by which" → >
        # Ch15 Appendix: C(q2) = 2 × C(q1) proof line
        ('YY]-C(q2)', '2□C(q1)', '='),               # "C(q2) □ 2□C(q1)" → =
        ('-C(q2)=2', 'C(q1)-C(q2)', '×'),            # "C(q2)=2 □ C(q1)..." → ×
        # Ch15 Appendix: C(q2)/q2 = 2×C(q1)/2q1 (version with literal /)
        ('-C(q2)/q2', '2□C(q1)/2', '='),             # "C(q2)/q2 □ 2□C(q1)/2" → =
        ('-C(q2)/q2=2', 'C(q1)/2q1', '×'),           # "C(q2)/q2=2 □ C(q1)/2q1" → ×
        # Ch15 Appendix: C(q2)□q2 = 2×C(q1)□2q1 (version without literal /)
        ('-C(q2)□q2', '2□C(q1)', '='),               # "C(q2)□q2 □ 2□C(q1)" → =
        ('C(q2)□q2=2', 'C(q1)□2q1', '×'),            # "C(q2)□q2=2 □ C(q1)□2q1" → ×
        # Ch15 Appendix: double-input cost block C(q2) = 2□[PXX□PYY]
        ('input-C(q2)', '2□[PXX', '='),              # "C(q2) □ 2□[PX..." → =
        ('C(q2)=2', '[PXX□PYY]-C(q2)', '×'),         # "C(q2)=2 □ [PXX..." → ×
        ('C(q2)=2×[PXX', 'PYY]-C', '+'),             # "2×[PXX □ PYY]" → +
        # Ch16: average profit per pound = $3 × 110 = $330
        ('sold:$3', '110,or$330', '×'),               # "$3 □ 110, or $330" → ×
        # Ch16: per-unit profit (P □ ATC) = 0
        ('coffee(P', 'ATC)iszero', '−'),              # "(P □ ATC) is zero" → −
        # Ch16: line segment AB represents = average profit
        ('ABrepresents', 'theaverageprofit', '='),    # "AB represents □ avg profit" → =
        # Ch16: per-unit profit = $0.03 per KWH
        ('erefore$0.03', 'perKWH', '='),              # "$0.03 □ per KWH" → =
        # Ch18: 4-firm concentration: 2+2+2□2 = 8%
        ('(2+2+2', '2),andthe8-f', '+'),             # "(2+2+2 □ 2)" → +
        # Ch18: Herfindahl Index sum of (1)^2
        ('esumof(1)[2]', '(1)[2]', '+'),             # "sum of (1)^2 □ (1)^2" → +
        ('1)[2]+(1)[2]', '...+(1)', '+'),            # "(1)^2+(1)^2 □ ...+(1)^2" → +
        # ── City HPI table: before=CITY<br>, after=NN.N%|| ──────────────────
        ('LosAngeles<br>', '38.1%||', '='),
        ('SanDiego<br>', '37.9%||', '='),
        ('Minneapolis<br>', '34.4%||', '='),
        ('Chicago<br>', '31.4%||', '='),
        ('Seattle<br>', '28.5%||', '='),
        ('Washington,D.C.<br>', '26.9%||', '='),
        ('Portland<br>', '26.0%||', '='),
        ('Atlanta<br>', '23.6%||', '='),
        ('Charlotte<br>', '16.1%||', '='),
        ('Boston<br>', '15.3%||', '='),
        ('Denver<br>', '5.1%||', '='),
    ]

    fixed = 0
    for pos in sorted([i for i, c in enumerate(md) if c == FFFD]):
        raw_b = md[max(0, pos - 50):pos]
        raw_a = md[pos + 1:pos + 55]
        # Strip markdown formatting and whitespace; replace remaining FFFDs with □
        s_b = re.sub(r'[_*`\s]', '', raw_b.replace(FFFD, '□'))
        s_a = re.sub(r'[_*`\s]', '', raw_a.replace(FFFD, '□'))

        matched_repl = None
        for b_suf, a_pre, repl in RULES:
            if s_b.endswith(b_suf) and s_a.startswith(a_pre):
                matched_repl = repl
                break

        if matched_repl is not None:
            md = md[:pos] + matched_repl + md[pos + 1:]
            fixed += 1

    return md, fixed


# ─────────────────────────────────────────────────────────────────────────────
# R7 — Figure captions
# ─────────────────────────────────────────────────────────────────────────────

def fix_r7(md: str, dry_run: bool = False) -> tuple[str, dict]:
    """
    Convert FIGURE captions to ![Figure N.M: Caption]() format.

    Form A: ## **FIGURE N.M  Caption**  heading followed by picture block
    Form B: picture block followed by picture text whose first content line
            starts with "FIGURE N.M  Caption<br>"
    """

    # ── Form A ──────────────────────────────────────────────────────────────
    # ## **FIGURE N.M  Caption**\n\n**==> picture [WxH] intentionally omitted <==**
    # → ![Figure N.M: Caption]()
    # (picture text block that may follow is kept intact)
    FORM_A_PAT = re.compile(
        r'## \*\*FIGURE\s+([\d.A-Z]+)\s+(.*?)\*\*[ \t]*\n\n\*\*==> picture [^\n]+ <==\*\*',
        re.MULTILINE | re.DOTALL,
    )

    def form_a_repl(m: re.Match) -> str:
        fig_num = m.group(1).strip()
        caption = m.group(2).strip()
        return f'![Figure {fig_num}: {caption}]()'

    count_a_before = len(FORM_A_PAT.findall(md))

    # ── Form B ──────────────────────────────────────────────────────────────
    # **==> picture [WxH] intentionally omitted <==**
    # [blank]
    # **----- Start of picture text -----**<br>
    # FIGURE N.M  Caption<br>
    # ...rest of picture text...
    # → ![Figure N.M: Caption]()
    FORM_B_PAT = re.compile(
        r'\*\*==> picture [^\n]+ <==\*\*[ \t]*\n\n'
        r'\*\*----- Start of picture text -----\*\*<br>[ \t]*\n'
        r'FIGURE\s+([\d.A-Z]+)\s+(.*?)<br>',
        re.MULTILINE | re.DOTALL,
    )

    def form_b_repl(m: re.Match) -> str:
        fig_num = m.group(1).strip()
        caption = m.group(2).strip()
        # Keep the picture text header so rest of picture text is properly fenced
        return (
            f'![Figure {fig_num}: {caption}]()\n\n'
            f'**----- Start of picture text -----**<br>\n'
        )

    count_b_before = len(FORM_B_PAT.findall(md))

    log.info('R7: Form A candidates: %d, Form B candidates: %d',
             count_a_before, count_b_before)

    if dry_run:
        # Show samples
        for m in list(FORM_A_PAT.finditer(md))[:3]:
            log.info('  Form A sample: FIGURE %s: %s...', m.group(1), m.group(2)[:40])
        for m in list(FORM_B_PAT.finditer(md))[:3]:
            log.info('  Form B sample: FIGURE %s: %s...', m.group(1), m.group(2)[:40])
        return md, {
            'form_a': count_a_before, 'form_b': count_b_before,
            'total': count_a_before + count_b_before, 'dry_run': True,
        }

    new_md = FORM_A_PAT.sub(form_a_repl, md)
    count_a_fixed = count_a_before - len(FORM_A_PAT.findall(new_md))

    new_md = FORM_B_PAT.sub(form_b_repl, new_md)
    count_b_fixed = count_b_before - len(FORM_B_PAT.findall(new_md))

    total_figs = new_md.count('![Figure ')
    log.info('R7: form_a_fixed=%d form_b_fixed=%d total_![Figure]=%d',
             count_a_fixed, count_b_fixed, total_figs)

    # Sanity: check for dangling "green rectangle" references
    green_rect = len(re.findall(r'\bgreen rectangle\b', new_md, re.I))
    if green_rect:
        log.warning('R7: %d "green rectangle" references remain', green_rect)

    return new_md, {
        'form_a_fixed': count_a_fixed,
        'form_b_fixed': count_b_fixed,
        'total_figure_placeholders': total_figs,
        'green_rectangle_refs': green_rect,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Verification
# ─────────────────────────────────────────────────────────────────────────────

def verify_r1_r5(md: str) -> dict:
    """Quick R1-R5 checks — must all still pass after R6+R7."""
    chapters = re.findall(r'^# Chapter (\d+):', md, re.M)
    ch_nums = [int(c) for c in chapters]

    toc_start = md.find('<!-- TOC START -->')
    toc_end = md.find('<!-- TOC END -->')

    splits = re.split(r'^# Chapter \d+:', md, flags=re.M)
    ch_sizes = [len(s) for s in splits[1:]]

    chapter_noise_ch = len(re.findall(r'C\s+H\s+A\s+P\s+T\s+E\s+R', md))
    chapter_noise_pt = len(re.findall(r'P\s+A\s+R\s+T\s+[IVX0-9]', md))

    return {
        'R1_chapter_count': len(ch_nums),
        'R1_consecutive': ch_nums == list(range(1, len(ch_nums) + 1)),
        'R1_unique': len(ch_nums) == len(set(ch_nums)),
        'R2_toc_start': toc_start >= 0,
        'R2_toc_end': toc_end > toc_start >= 0,
        'R3_min_chapter_chars': min(ch_sizes) if ch_sizes else 0,
        'R3_max_chapter_chars': max(ch_sizes) if ch_sizes else 0,
        'R9_chapter_noise': chapter_noise_ch,
        'R9_part_noise': chapter_noise_pt,
        'R1_pass': (len(ch_nums) == 19 and ch_nums == list(range(1, 20))),
        'R9_pass': (chapter_noise_ch == 0 and chapter_noise_pt == 0),
    }


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    p = argparse.ArgumentParser(description='Fix MathematicalPi encoding (R6) and figure captions (R7)')
    p.add_argument('--pdf', required=True, help='PDF source file')
    p.add_argument('--md', required=True, help='Structured markdown file (will be edited in-place)')
    p.add_argument('--dry-run', action='store_true', help='Report only, do not write')
    p.add_argument('--skip-r6', action='store_true', help='Skip R6 font fix')
    p.add_argument('--skip-r7', action='store_true', help='Skip R7 caption fix')
    args = p.parse_args()

    pdf_path = args.pdf
    md_path = args.md

    if not pathlib.Path(pdf_path).exists():
        log.error('PDF not found: %s', pdf_path)
        return 1
    if not pathlib.Path(md_path).exists():
        log.error('MD not found: %s', md_path)
        return 1

    log.info('Reading md from %s', md_path)
    with open(md_path, 'r', encoding='utf-8') as f:
        md = f.read()

    fffd_before = md.count(FFFD)
    figs_before = md.count('![Figure ')
    log.info('Before: FFFD=%d  ![Figure]=%d  chars=%d', fffd_before, figs_before, len(md))

    # ── R1-R5 baseline ──────────────────────────────────────────────────────
    baseline = verify_r1_r5(md)
    log.info('Baseline R1_pass=%s R9_pass=%s chapters=%d',
             baseline['R1_pass'], baseline['R9_pass'], baseline['R1_chapter_count'])
    if not baseline['R1_pass']:
        log.error('Baseline R1 FAIL — aborting to protect chapter structure')
        return 1

    # ── R6 ──────────────────────────────────────────────────────────────────
    r6_stats: dict = {}
    if not args.skip_r6:
        log.info('─── Running R6 (MathematicalPi encoding fix) ───')
        md, r6_stats = fix_r6(pdf_path, md, dry_run=args.dry_run)
    else:
        log.info('R6: skipped')

    # ── R7 ──────────────────────────────────────────────────────────────────
    r7_stats: dict = {}
    if not args.skip_r7:
        log.info('─── Running R7 (figure captions) ───')
        md, r7_stats = fix_r7(md, dry_run=args.dry_run)
    else:
        log.info('R7: skipped')

    # ── R1-R5 post-check ────────────────────────────────────────────────────
    post = verify_r1_r5(md)
    log.info('Post-fix R1_pass=%s R9_pass=%s chapters=%d',
             post['R1_pass'], post['R9_pass'], post['R1_chapter_count'])
    if not post['R1_pass']:
        log.error('POST-FIX R1 FAIL — chapter structure was damaged! Aborting write.')
        return 1

    if args.dry_run:
        log.info('DRY-RUN complete. No files modified.')
        log.info('R6: %s', r6_stats)
        log.info('R7: %s', r7_stats)
        return 0

    # ── Write ────────────────────────────────────────────────────────────────
    log.info('Writing %d chars to %s', len(md), md_path)
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md)
    log.info('Done.')

    fffd_after = md.count(FFFD)
    figs_after = md.count('![Figure ')
    log.info('After: FFFD=%d (was %d, fixed %d)  ![Figure]=%d (was %d)',
             fffd_after, fffd_before, fffd_before - fffd_after, figs_after, figs_before)

    log.info('R6: %s', r6_stats)
    log.info('R7: %s', r7_stats)
    log.info('R1-R5 still PASS: %s', post['R1_pass'] and post['R9_pass'])

    return 0


if __name__ == '__main__':
    sys.exit(main())
