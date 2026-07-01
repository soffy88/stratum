#!/usr/bin/env python3
"""
fix_werner_fffd.py — §20 stratum/scripts

修复 Werner & Sotskov (01KW24VDA4HWGF942CMFFS43A7) Markdown 中的 190 个 FFFD。

原因: pdfplumber 无法解码 MathTime Pro (MTEX/MTMI) 字体中无 ToUnicode 条目的字形。
关键字体编码 (来自 PDF xref 5269/5270/5266):
  MTMI code 8  (Delta1)         → Δ  (U+0394)  — calculus increments
  MTEX code 5  (summationtext)  → ∑  (U+2211)
  MTEX code 7  (producttext)    → ∏  (U+220F)
  MTEX code 9  (integraltext)   → ∫  (U+222B)
  MTEX code 44 (integraldisplay)→ ∫
  MTEX code 22-25 (radical*)    → √  (U+221A)
  MTEX code 3-4 (parenleft/right*) → (  )
  MTSYN code 28 (mapsto)        → leading component of ↦ (U+21A6)

Usage:
    docker exec stratum-sl python3 /app/scripts/fix_werner_fffd.py [--dry-run] [--update-db]

Reads the Werner markdown from the stratum API, applies context-based replacements,
and optionally writes the result back to the derivative table via DuckDB.
"""
from __future__ import annotations

import argparse
import collections
import re
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

FFFD = "�"
WERNER_ID = "01KW24VDA4HWGF942CMFFS43A7"
API_BASE = "http://127.0.0.1:9304"
JWT = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJzdWIiOiIwMUtWOEVSS0NCSk42SEE3TUJINUtKWEZCUSIsImlhdCI6MTc4MjQ4MzYwOCwiZXhwIjoxNzgyNTcwMDA4fQ"
    ".jjHvnZXiNZTjI53ZRFgx4oKGqNANqCCIQqJ23IeBgpE"
)


# ─── 从 API 读取 markdown ─────────────────────────────────────────────────────

def fetch_markdown() -> str:
    import urllib.request, json
    url = f"{API_BASE}/api/v1/documents/{WERNER_ID}/derivatives"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {JWT}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    md = next((d["content"] for d in data if d["kind"] == "markdown"), None)
    if md is None:
        raise RuntimeError("Werner markdown derivative not found")
    return md


# ─── 上下文感知单次扫描替换 ───────────────────────────────────────────────────

def _ctx(md: str, pos: int, window: int = 12) -> tuple[str, str]:
    """返回位置 pos 处的 (left, right) 上下文字符串。"""
    return md[max(0, pos - window): pos], md[pos + 1: pos + window + 1]


def apply_fixes(md: str) -> tuple[str, dict[str, int]]:
    stats: dict[str, int] = collections.defaultdict(int)

    # ── 1: Δ (MTMI Delta1)  _FFFD[letter] → _Δ[letter] ──────────────────────
    # Covers: Δx, Δy, Δz, Δt, Δξ, Δi, Δn, Δp, Δu, Δv, Δf, Δ**x** (vector), etc.
    before = md.count(FFFD)
    md = re.sub(r"_�([A-Za-z])", r"_Δ\1", md)
    # _FFFD_ form: standalone italic Δ (e.g. _Δ_ **x**)
    md = md.replace("_�_", "_Δ_")
    stats["Δ (delta)"] = before - md.count(FFFD)

    # ── 2: √ (MTEX radical)  ~~FFFD~~ → ~~√~~  ──────────────────────────────
    before = md.count(FFFD)
    # Exclude only ~~FFFD~~<br>_A_= (logic table ∧); all other ~~FFFD~~<br> = √
    md = re.sub(r"~~�~~(?!<br>_A_=)", "~~√~~", md)
    stats["√ (radical)"] = before - md.count(FFFD)

    # ── 3: ↦ (mapsto)  FFFD→ → ↦  ───────────────────────────────────────────
    before = md.count(FFFD)
    md = md.replace(f"{FFFD}→", "↦")  # → = →
    stats["↦ (mapsto)"] = before - md.count(FFFD)

    # ── 4: Notation table symbols ─────────────────────────────────────────────
    before = md.count(FFFD)
    md = re.sub(r"�(\|summation)", r"∑\1", md)    # ∑ in table symbol column
    md = re.sub(r"�(<br>_ai_)", r"∑\1", md)       # ∑ ai formula
    md = re.sub(r"�(\|product)", r"∏\1", md)      # ∏ in table
    md = re.sub(r"�(\|integral)", r"∫\1", md)     # ∫ in table
    stats["∑∏ (table)"] = before - md.count(FFFD)

    # ── 5: ∫ (integral) — integration chapter, single-pass scan ──────────────
    # RIGHT-context patterns that uniquely identify ∫
    INTEGRAL_RIGHT = [
        " _f (x) dx",   " _f(x) dx",    " _f (x)_",
        " _x_[2] _d",   " _x[x]_[2",    " _x_[3]",
        " _x[x]_[3",    " _x_[4]",
        " _f (x_",       " _f(x_",
        " where _C_",   " _a[x] a[x",   " ln _a_[+]",
        " cos _x dx",   " _dx_ = ta",   " cos[2] _x",
        " 2[+] _[ k",   " _dx_ = − ", " sin[2] _x",
        " ~~√~~ 1", " 1 + _x_[2",  " 1 + _x_[3",
        "\n\nThis in",   "\n\nAlthoug",  "\n\nIn this",
        "\n\nFirst, ",   "\n\nNote t",   "\n\nSince ",
        " _a b_ →", " _a b b_",    "−∞ _a_",
        " _a_ ∞",   "−∞ _b_", " _a a_ →",
        "−1 _x_[2", "�1 x [2", "1 x [2] +",
        "0<br>∞ 4", "�0 √ x", "0 √ x",
        "0 (x  + 1",    " _f (x)_ dx",  " f (x) dx",
        " _a[f][ (]",   " sin _x dx",   " _x_ dx_",
        "� _R_ \n", " _R_ \n\n_F",
        "� y [dx",  " y [dx dy]",
        " _dx_ − ", " dx_·",
        " _a_  dx",     " _dx_ ",
    ]

    # LEFT-context patterns that alone identify ∫ (used if right-context scan misses)
    INTEGRAL_LEFT_EXACT = [
        "integral_ ",   "denoted by ",  "line. (c) ",
        " R: \n\n(a) ", "[ 0;] (b) ",   " ̸ 1 _)_ ",
        "k]_[∈][Z] ", "os[2] _x_ ", "k][π]_[,] ",
        "_ ∈ Z _)_ ", "_x_ + _C_ ", "x]_ + _C_ ",
        "| + _C_ . ",   " _x dx_ = ",  "e can add ",
        "eidentity ",   " _x dx_ . ",  "4] _dx_ . ",
        "f (x) dx_ ",   " _a b_ →∞ ", "(x) dx_~~ ",
        "∞ _a_ →−∞ ",
        "f (x) dx_ ",   "−∞ _b_ →∞ ",
        "\n> 1 _dx_ ",  "] dx ;<br>",  " 2 x  + 1 ",
        ") (f )<br>",   " _) dR_ , ",  "<br>\nx<br>",
    ]

    # Single-pass scan: for each FFFD, check context
    new_chars = list(md)
    for i, c in enumerate(new_chars):
        if c != FFFD:
            continue
        left, right = _ctx("".join(new_chars), i, 14)
        # right-context check
        matched = False
        for pat in INTEGRAL_RIGHT:
            if right.startswith(pat):
                new_chars[i] = "∫"
                stats["∫ (right-ctx)"] = stats.get("∫ (right-ctx)", 0) + 1
                matched = True
                break
        if matched:
            continue
        # left-context check
        for pat in INTEGRAL_LEFT_EXACT:
            if left.endswith(pat):
                new_chars[i] = "∫"
                stats["∫ (left-ctx)"] = stats.get("∫ (left-ctx)", 0) + 1
                break
    md = "".join(new_chars)

    # ── 6: ∫ in improper integral limit notation (consecutive patterns) ───────
    # ∫_{-∞} and ∫_{∞} in table format: FFFD directly before -∞ / ∞ subscripts
    before = md.count(FFFD)
    md = re.sub(r"�(−∞)", r"∫\1", md)    # FFFD-∞ → ∫-∞
    md = re.sub(r"�(∞)", r"∫\1", md)          # FFFD∞ → ∫∞  (guard: after above)
    stats["∫ (limit-∞)"] = before - md.count(FFFD)

    # ── 7: Large parens for binomial coefficients ─────────────────────────────
    # Pattern: FFFD _k_ FFFD (open/close paren around variable)
    # Also FFFD _n n_ ! and binomial definition
    before = md.count(FFFD)
    # In binomial coefficient notation tables and definitions
    md = re.sub(r"�( _[kn]_ )�", r"(\1)", md)
    md = re.sub(r"�( _k_ )�", r"(\1)", md)  # duplicate guard
    # "at most (3) = 10 basic" → FFFD3FFFD
    md = re.sub(r"�(\d)�", r"(\1)", md)
    # "coefficient: FFFD _k_ FFFD _n" form
    md = re.sub(r"(coefficient[: ]+)�( _[kn]_)", r"\1(\2", md)
    stats["() binomial"] = before - md.count(FFFD)

    # ── 8: Misc single-context rules ─────────────────────────────────────────

    # Logical ~~FFFD~~<br>_A_= context: MTEX logicalanddisplay → ∧
    before = md.count(FFFD)
    md = md.replace(f"~~{FFFD}~~<br>_A_=", "~~∧~~<br>_A_=")
    stats["∧ (logic)"] = before - md.count(FFFD)

    # FFFD<br>=⇒_( context: second logic table FFFD → likely ∨ or similar
    before = md.count(FFFD)
    md = md.replace(f"{FFFD}<br>=⇒_(", "∨<br>=⇒_(")
    stats["∨ (logic)"] = before - md.count(FFFD)

    # Conjunction / disjunction definitions: MTEX display logical operators
    before = md.count(FFFD)
    md = re.sub(r"(conjunction \n\n)�( _A)", r"\1∧\2", md)
    md = re.sub(r"(disjunction \n\n)�( _A)", r"\1∨\2", md)
    stats["∧∨ conj/disj"] = before - md.count(FFFD)

    # ∀ / ∃ quantifiers: FFFD before _A(x)_ in predicate context
    before = md.count(FFFD)
    md = re.sub(r"�( _A\(x\)_ un)", r"∀\1", md)
    md = re.sub(r"�( _A\(x\)_ ex)", r"∃\1", md)
    stats["∀∃ (quant)"] = before - md.count(FFFD)

    # Log base formula: log_a FFFD _a[x]_[FFFD] → log_a(_a^x_)
    before = md.count(FFFD)
    md = re.sub(r"(log _a_ )�( _a\[x\]_)\[?�?\]?", r"\1(\2)", md)
    md = re.sub(r"(log _a_ )�( _b\[y\]_)\[?�?\]?", r"\1(\2)", md)
    md = re.sub(r"(� _a\[x\]_)\[�\]", r"(\1)", md)
    md = re.sub(r"(� _b\[y\]_)\[�\]", r"(\1)", md)
    stats["log ()"] = before - md.count(FFFD)

    # Matrix determinant: exact patterns from xref
    # Text: "determinants FF _a_11 ... _a_1_k_ FF FF FF FF _a_21 ... _a_2_k_ FF FF _Dk_=~~F F~~"
    before = md.count(FFFD)
    md = re.sub(f"(determinants ){FFFD}{FFFD}( _a_ 1)", r"\1|\2", md)        # opening ||
    md = re.sub(f"(_a_ 1 _k_ ){FFFD}{FFFD} {FFFD}{FFFD}( _a_ 2)", r"\1|| ||\2", md)  # row sep
    md = re.sub(f"(_a_ 2 _k_ ){FFFD}{FFFD}( _Dk_)", r"\1||\2", md)           # closing ||
    md = re.sub(f"(_Dk_ = ~~){FFFD} {FFFD}(~~ ,)", r"\1| |\2", md)           # |D_k|
    # k-th row: "... ... ... FFFD×4 _ak_" and "_akk_ FFFD×4 i.e."
    F4 = FFFD * 4
    md = re.sub(f"(\\.\\.\\. ){re.escape(F4)}( _ak_)", r"\1|| ||\2", md)
    md = re.sub(f"(_akk_ ){re.escape(F4)}( i\\.e\\.)", r"\1|| ||\2", md)
    stats["|| determinant"] = before - md.count(FFFD)

    # | _Aij_ | FFFD → remove stray FFFD after matrix element
    before = md.count(FFFD)
    md = re.sub(r"(\| _Aij_ \|)�( is the tr)", r"\1 \2", md)
    stats["Aij trace"] = before - md.count(FFFD)

    # "he matrix FFFD _(- 1 _)" → matrix determinant leading bar
    before = md.count(FFFD)
    md = re.sub(r"(he matrix )�( _\(_ −1)", r"\1|\2", md)
    stats["matrix |"] = before - md.count(FFFD)

    # | _b_ |; FFF FFF (5) — complex number absolute value inequality
    # Exact text: "| _b_ |; ??? ??? (5)" = 3+3 vertical bars (MTEX vextendsingle)
    before = md.count(FFFD)
    md = md.replace(
        f"| _b_ |; {FFFD}{FFFD}{FFFD} {FFFD}{FFFD}{FFFD} (5)",
        "| _b_ |; ||| ||| (5)"
    )
    # Fallback: replace any remaining FFFDs in this window
    md = re.sub(
        f"(\\| _b_ \\|; (?:\\|+)?){FFFD}+( ?(?:\\|+)?){FFFD}*( ?\\(5\\))",
        lambda m: m.group(1) + "|" + m.group(2) + m.group(3),
        md
    )
    stats["|| b || bars"] = before - md.count(FFFD)

    # LP "at most FFFD var FFFD" — binomial coefficients C(n, var)
    # Exact text: "at most ? _pn_ ? basic", "at most ? _m_ ? extreme", etc.
    before = md.count(FFFD)
    md = re.sub(f"(at most ){FFFD}( _pn_ ){FFFD}( ba)", r"\1C(\2)\3", md)
    md = re.sub(f"(at most ){FFFD}( _n_ [+] _mm_ ){FFFD}", r"\1C(\2)", md)
    md = re.sub(f"(at most ){FFFD}( _[mn]_ ){FFFD}", r"\1C(\2)", md)
    stats["C() LP bounds"] = before - md.count(FFFD)

    # Δy/Δx difference quotient: slash or open-paren before FFFD
    before = md.count(FFFD)
    md = re.sub(r"/�([A-Za-z])", r"/Δ\1", md)      # _Δy/_Δx case
    md = re.sub(r"\(�([A-Za-z])", r"(Δ\1", md)    # _(Δx_1, Δx_2) vector case
    stats["Δ slash/paren"] = before - md.count(FFFD)

    # Negation symbol in predicate table: negation[FFFD] → negation[¬]
    before = md.count(FFFD)
    md = re.sub(r"(negation\[)�(\])", r"\1¬\2", md)
    stats["¬ (negation)"] = before - md.count(FFFD)

    # Cost function trailing FFFD: "... + 1 _)_ FFFD is the cost" → add comma
    before = md.count(FFFD)
    md = re.sub(r"(\+ 1 _\)_ )�( is the cost)", r"\1,\2", md)
    stats[", cost comma"] = before - md.count(FFFD)

    # ∫∫ double integral: FFFD FFFD in double integral context
    before = md.count(FFFD)
    md = re.sub(r"(dR_ , )�( � _R_)", r"\1∫\2", md)
    md = re.sub(r"(dR_ , ∫ )�( _R_)", r"\1∫\2", md)
    md = re.sub(r"(\nx<br>)�( � y \[dx)", r"\1∫\2", md)
    md = re.sub(r"(\nx<br>∫ )�( y \[dx)", r"\1∫\2", md)
    stats["∫∫ double"] = before - md.count(FFFD)

    return md, dict(stats)


# ─── 写回数据库 ───────────────────────────────────────────────────────────────

def update_derivative_via_api(new_content: str) -> None:
    """通过 stratum admin API 更新 Werner 的 markdown derivative。
    (DuckDB 被服务器持有写锁，需通过 API 中转写入。)
    """
    import urllib.request, json
    url = f"{API_BASE}/api/v1/admin/derivative-content"
    body = json.dumps({
        "substrate_id": WERNER_ID,
        "kind": "markdown",
        "content": new_content,
    }).encode()
    req = urllib.request.Request(
        url,
        data=body,
        method="PATCH",
        headers={"Authorization": f"Bearer {JWT}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())
    log.info("API update: %s", result)


# ─── 主程序 ───────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Fix Werner FFFD chars")
    parser.add_argument("--dry-run", action="store_true", help="只报告,不写库")
    parser.add_argument("--update-db", action="store_true", help="写回 DuckDB derivative 表")
    args = parser.parse_args()

    log.info("Fetching Werner markdown from API…")
    md = fetch_markdown()
    initial_count = md.count(FFFD)
    log.info("Initial FFFD count: %d", initial_count)

    md_fixed, stats = apply_fixes(md)

    remaining = md_fixed.count(FFFD)
    fixed_total = initial_count - remaining

    print("\n=== Werner FFFD Fix Report ===")
    print(f"Before: {initial_count}  After: {remaining}  Fixed: {fixed_total}")
    print()
    print("By category:")
    for cat, cnt in sorted(stats.items(), key=lambda x: -x[1]):
        if cnt:
            print(f"  {cat:25s} {cnt:4d}")

    if remaining > 0:
        print(f"\nRemaining {remaining} FFFDs (sample contexts):")
        positions = [i for i, c in enumerate(md_fixed) if c == FFFD]
        seen = set()
        for pos in positions[:30]:
            left = md_fixed[max(0, pos - 15): pos]
            right = md_fixed[pos + 1: pos + 16]
            ctx = repr(left[-12:]) + "|X|" + repr(right[:12])
            if ctx not in seen:
                seen.add(ctx)
                print(f"  {ctx}")

    if args.dry_run:
        log.info("Dry-run: no changes written.")
        return

    if args.update_db:
        log.info("Writing fixed markdown via API…")
        update_derivative_via_api(md_fixed)
        log.info("Done. %d FFFDs fixed, %d remaining.", fixed_total, remaining)
    else:
        log.info("Use --update-db to write back to DuckDB, or --dry-run to preview only.")
        # Write to /tmp for inspection
        out = "/tmp/werner_fixed.md"
        with open(out, "w") as f:
            f.write(md_fixed)
        log.info("Fixed markdown written to %s for inspection.", out)


if __name__ == "__main__":
    main()
