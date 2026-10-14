"""A-P9: freeze a real book into the A warehouse and annotate its KUs.

The A-P8 runner (``ku_annotation_runner``) only exercises the annotation gates
on an in-memory pilot. Production ``aii_kg`` had no frozen book at all, so
nothing downstream (B dedup hints, review queue) could read real rows. This
module closes that gap for one substrate at a time:

    substrate markdown (the same text BU2 reads)
      -> book_source / source_version / reading_run
      -> reading_evidence (one verbatim block per marker)
      -> ku_candidate -> ku_verification -> knowledge_unit (FROZEN)
      -> ku_occurrence (closed role vocabulary, verbatim quote_span)
      -> ku_relation_hint (in-book RESTATES / SUMMARIZES / APPLIES only)

Extraction is deterministic and rule based: textbook markers at line start
(``定理 1``, ``定义 2``, ``例 3``, ``习题 1-1``, ``THEOREM 4—Name``,
``DEFINITION``, ``EXAMPLE 5``, ``Exercises 2.1``, ``Summary``, ``注``). No LLM
is involved, so a rerun over the same text yields byte-identical ids and every
INSERT is ``ON CONFLICT DO NOTHING``. Relation hints never cross books and
never merge or delete occurrences; they are dedup hints for the B warehouse.

CLI::

    python -m stratum.knowledge.a_repository.book_freeze <substrate_id> [--persist] [--json]
    python -m stratum.knowledge.a_repository.book_freeze --all-pending [--persist] [--limit N]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import unicodedata
from bisect import bisect_right
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable

FREEZE_VERSION = "a-p9-book-freeze-v1"
EXTRACTOR_VERSION = "a-p9-rule-markers-v1"

DEFINITION = "DEFINITION"
THEOREM = "THEOREM"
EXAMPLE = "EXAMPLE"
EXERCISE = "EXERCISE"
SUMMARY = "SUMMARY"
ASIDE = "ASIDE"
OTHER = "OTHER"
ROLES = (DEFINITION, THEOREM, EXAMPLE, EXERCISE, SUMMARY, ASIDE, OTHER)

RESTATES = "RESTATES"
SUMMARIZES = "SUMMARIZES"
APPLIES = "APPLIES"

QUOTE_CHARS = 240
MAX_BLOCK_CHARS = 1500
MAX_APPLY_DISTANCE = 60_000

_LEAD = r"^[ \t>*_#]*"
_NAME = r"(?:\s*[（(]([^）)\n]{1,40})[）)])?"
_DASH_NAME = r"(?:\s*[—–-]+\s*([^\n*]{1,80}))?"

# (role, label, pattern). Order matters only for ties at the same offset.
_MARKERS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (THEOREM, "定理", re.compile(_LEAD + r"(定理|推论|引理)\s*(\d+)" + _NAME, re.M)),
    (DEFINITION, "定义", re.compile(_LEAD + r"(定义)\s*(\d+)" + _NAME, re.M)),
    (EXAMPLE, "例", re.compile(_LEAD + r"(例)\s*(\d+)(?=[\s.．、:：])", re.M)),
    (
        EXERCISE,
        "习题",
        re.compile(
            _LEAD + r"(总习题|习题)\s*([0-9一二三四五六七八九十]+(?:\s*[-—–]\s*\d+)?)", re.M
        ),
    ),
    (SUMMARY, "小结", re.compile(_LEAD + r"(本章小结|小结)\s*$", re.M)),
    (ASIDE, "注", re.compile(_LEAD + r"(注)\s*(\d*)(?=[\s:：])", re.M)),
    (
        THEOREM,
        "THEOREM",
        re.compile(_LEAD + r"(THEOREM|COROLLARY|LEMMA)\b\s*(\d+)?" + _DASH_NAME, re.M),
    ),
    (DEFINITION, "DEFINITION", re.compile(_LEAD + r"(DEFINITION)\b()" + _DASH_NAME, re.M)),
    (EXAMPLE, "EXAMPLE", re.compile(_LEAD + r"(EXAMPLE)\s+(\d+)\b", re.M)),
    (EXERCISE, "Exercises", re.compile(_LEAD + r"(Exercises)\s+(\d+\.\d+)\b", re.M)),
    (EXERCISE, "EXERCISES", re.compile(_LEAD + r"(EXERCISES)\b[ \t]*(\d+\.\d+)?[ \t]*$", re.M)),
    (SUMMARY, "Summary", re.compile(_LEAD + r"(Chapter Summary|Summary)\s*\**\s*$", re.M)),
)

_PROOF_START = re.compile(r"\n\s*(?:证\s|证明|Proof\b|PROOF\b)")
_REF_ZH = re.compile(r"定理\s*(\d+)")
_REF_EN = re.compile(r"\bTheorem\s+(\d+)\b")


def _h(*parts: object, n: int = 16) -> str:
    raw = "\x1f".join(str(p) for p in parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:n]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text or "")).strip()


@dataclass
class ChapterSpan:
    label: str
    start: int


@dataclass
class ExtractedKU:
    role: str
    label: str
    number: str
    name: str
    start: int
    end: int
    text: str
    chapter: str
    marker: str

    @property
    def title(self) -> str:
        base = f"{self.marker} {self.number}".strip()
        return f"{base}（{self.name}）" if self.name else base

    @property
    def quote(self) -> str:
        return self.text[:QUOTE_CHARS].strip()

    @property
    def statement(self) -> str:
        cut = _PROOF_START.search(self.text)
        body = self.text[: cut.start()] if cut and cut.start() > 20 else self.text
        return body.strip()


@dataclass
class Hint:
    kind: str
    from_index: int
    to_index: int
    confidence: float


@dataclass
class Extraction:
    kus: list[ExtractedKU] = field(default_factory=list)
    hints: list[Hint] = field(default_factory=list)

    def role_counts(self) -> dict[str, int]:
        c = Counter(k.role for k in self.kus)
        return {r: c.get(r, 0) for r in ROLES}

    def hint_counts(self) -> dict[str, int]:
        c = Counter(h.kind for h in self.hints)
        return {k: c.get(k, 0) for k in (RESTATES, SUMMARIZES, APPLIES)}


_ZH_NUM = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}
_TOC_LINE = re.compile(
    r"^[ \t#*]*第\s*([一二三四五六七八九十]+|\d+)\s*章[ \t]*([^\n…]{1,40}?)[ \t]*(?:…+|\.{3,})?[ \t]*\d+[ \t]*$",
    re.M,
)
_CHAPTER_END = re.compile(
    r"^[ \t#*]*第\s*([一二三四五六七八九十]+|\d+)\s*章\s*(?:释疑解难|例题精讲|总习题)", re.M
)
_TOC_EXERCISE = re.compile(r"(?:[(（]\d+[)）]|\s\d{2,4})\s*$")


def _zh_int(raw: str) -> int:
    if raw.isdigit():
        return int(raw)
    if raw == "十":
        return 10
    if raw.startswith("十"):
        return 10 + _ZH_NUM.get(raw[1:], 0)
    if raw.endswith("十"):
        return _ZH_NUM.get(raw[0], 0) * 10
    if "十" in raw:
        a, b = raw.split("十", 1)
        return _ZH_NUM.get(a, 0) * 10 + _ZH_NUM.get(b, 0)
    return _ZH_NUM.get(raw, 0)


def body_start(text: str) -> int:
    """End of a Chinese table of contents (``第X章 …… 12`` lines), else 0."""
    last = 0
    for m in _TOC_LINE.finditer(text):
        if m.start() < len(text) // 5:
            last = m.end()
    return last


def chapter_spans(text: str, chapters: Iterable[Any] = ()) -> list[ChapterSpan]:
    """Chapter boundaries.

    The loader's chapter list wins. Without it (同济 has no body headings), the
    table of contents gives the titles and each ``第X章释疑解难`` / ``例题精讲``
    block marks where chapter X ends, so chapter X starts where X-1 ended.
    """
    spans = [
        ChapterSpan(
            label=f"{getattr(c, 'number', '')} {getattr(c, 'title', '')}".strip(),
            start=int(getattr(c, "start", 0)),
        )
        for c in chapters
    ]
    if not spans:
        titles = {_zh_int(m.group(1)): m.group(2).strip() for m in _TOC_LINE.finditer(text)}
        ends: dict[int, int] = {}
        for m in _CHAPTER_END.finditer(text):
            ends.setdefault(_zh_int(m.group(1)), m.start())
        start = body_start(text)
        for num in sorted(ends):
            label = f"第{num}章 {titles.get(num, '')}".strip()
            spans.append(ChapterSpan(label=label, start=start))
            start = ends[num]
    spans.sort(key=lambda s: s.start)
    return spans


def _chapter_at(spans: list[ChapterSpan], starts: list[int], offset: int) -> str:
    i = bisect_right(starts, offset) - 1
    return spans[i].label if i >= 0 else "front matter"


_NAME_STOP = re.compile(
    r"\s+(?:If|Let|Suppose|Assume|The following|For|When|Given|A|An)\s|<|\$|\\\("
)


def _clean_name(raw: str) -> str:
    name = raw.strip(" *_")
    m = _NAME_STOP.search(name)
    if m:
        name = name[: m.start()]
    return name.strip(" *_.,:;")[:60]


def extract(text: str, chapters: Iterable[Any] = ()) -> Extraction:
    """Find every marker block in ``text`` and derive in-book relation hints."""
    hits: list[tuple[int, int, str, str, str, str, str]] = []
    seen: set[int] = set()
    for role, label, pat in _MARKERS:
        for m in pat.finditer(text):
            begin = m.start(1)
            if begin in seen:
                continue
            seen.add(begin)
            number = (m.group(2) or "").strip() if m.lastindex and m.lastindex >= 2 else ""
            name = ""
            if m.lastindex and m.lastindex >= 3 and m.group(3):
                name = _clean_name(m.group(3))
            hits.append((begin, m.end(), role, label, m.group(1), number, name))
    hits.sort(key=lambda h: h[0])
    skip_before = body_start(text)
    hits = [
        h
        for h in hits
        if h[0] >= skip_before
        and not (
            h[2] == EXERCISE
            and _TOC_EXERCISE.search(
                text[h[0] : text.find("\n", h[0]) if "\n" in text[h[0] :] else len(text)]
            )
        )
    ]

    spans = chapter_spans(text, chapters)
    span_starts = [s.start for s in spans]
    out = Extraction()
    for i, (begin, _mend, role, label, marker, number, name) in enumerate(hits):
        nxt = hits[i + 1][0] if i + 1 < len(hits) else len(text)
        end = min(nxt, begin + MAX_BLOCK_CHARS)
        block = text[begin:end].rstrip()
        if len(_norm(block)) < 8:
            continue
        out.kus.append(
            ExtractedKU(
                role=role,
                label=label,
                number=number,
                name=name,
                start=begin,
                end=begin + len(block),
                text=block,
                chapter=_chapter_at(spans, span_starts, begin),
                marker=marker,
            )
        )
    out.hints = derive_hints(out.kus)
    return out


def derive_hints(kus: list[ExtractedKU]) -> list[Hint]:
    """In-book hints only: APPLIES (example cites a theorem), RESTATES (same
    named statement repeated), SUMMARIZES (summary names a statement)."""
    hints: dict[tuple[str, int, int], Hint] = {}

    def add(kind: str, a: int, b: int, conf: float) -> None:
        if a != b:
            hints.setdefault((kind, a, b), Hint(kind, a, b, conf))

    theorems = [(i, k) for i, k in enumerate(kus) if k.role == THEOREM and k.number]
    for i, k in enumerate(kus):
        if k.role not in (EXAMPLE, EXERCISE):
            continue
        ref_re = _REF_ZH if k.label in ("例", "习题") else _REF_EN
        for num in sorted(set(ref_re.findall(k.text))):
            target = None
            for j, t in reversed(theorems):
                if t.start < k.start and t.number == num and t.chapter == k.chapter:
                    target = j
                    break
            if target is not None and k.start - kus[target].start <= MAX_APPLY_DISTANCE:
                add(APPLIES, i, target, 0.75)

    # Same role, same name AND same number: a bilingual edition or a recap
    # repeating one statement. Same name with a different number is usually a
    # different result (Limit Comparison Test for integrals vs. for series).
    first_by_name: dict[tuple[str, str, str], int] = {}
    for i, k in enumerate(kus):
        if k.role not in (THEOREM, DEFINITION) or len(_norm(k.name)) < 2:
            continue
        key = (k.role, _norm(k.name).lower(), k.number)
        if key in first_by_name:
            add(RESTATES, i, first_by_name[key], 0.8)
        else:
            first_by_name[key] = i

    named = [
        (i, _norm(k.name).lower())
        for i, k in enumerate(kus)
        if k.role in (THEOREM, DEFINITION) and len(_norm(k.name)) >= 4
    ]
    for i, k in enumerate(kus):
        if k.role != SUMMARY:
            continue
        low = _norm(k.text).lower()
        for j, nm in named:
            if kus[j].start < k.start and kus[j].chapter == k.chapter and nm in low:
                add(SUMMARIZES, i, j, 0.6)
    return sorted(hints.values(), key=lambda h: (h.from_index, h.kind, h.to_index))


# ---------------------------------------------------------------- persistence


@dataclass
class Rows:
    source_version_id: str
    book_source: dict[str, Any]
    source_version: dict[str, Any]
    reading_run: dict[str, Any]
    evidence: list[dict[str, Any]] = field(default_factory=list)
    candidates: list[dict[str, Any]] = field(default_factory=list)
    verifications: list[dict[str, Any]] = field(default_factory=list)
    units: list[dict[str, Any]] = field(default_factory=list)
    occurrences: list[dict[str, Any]] = field(default_factory=list)
    hints: list[dict[str, Any]] = field(default_factory=list)


_CLASSIFICATION = {
    DEFINITION: "CONCEPT",
    THEOREM: "FACT",
    EXAMPLE: "ARGUMENT",
    EXERCISE: "ARGUMENT",
    SUMMARY: "CONCEPT",
    ASIDE: "FACT",
    OTHER: "FACT",
}


def locate(text: str, start: int, quote: str) -> bool:
    """quote_span must sit verbatim at its locator."""
    return bool(quote) and text.find(quote, start, start + QUOTE_CHARS + 64) != -1


def build_rows(
    substrate_id: str, title: str, text: str, ex: Extraction, metadata: dict[str, Any] | None = None
) -> Rows:
    file_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    sv = f"sv_{file_hash[:16]}"
    run = f"rr_{_h(sv, FREEZE_VERSION)}"
    rows = Rows(
        source_version_id=sv,
        book_source={
            "id": substrate_id,
            "title": title or substrate_id,
            "metadata": json.dumps(metadata or {}, ensure_ascii=False),
        },
        source_version={
            "id": sv,
            "book_source_id": substrate_id,
            "version": FREEZE_VERSION,
            "file_hash": file_hash,
            "storage_uri": f"substrate:{substrate_id}",
        },
        reading_run={
            "id": run,
            "source_version_id": sv,
            "status": "COMPLETED",
            "metadata": json.dumps({"extractor": EXTRACTOR_VERSION}),
        },
    )
    evidence_ids: list[str] = []
    unit_ids: list[str] = []
    for k in ex.kus:
        key = _h(sv, k.role, k.start)
        ev, cand, ver, ku = f"ev_{key}", f"kc_{key}", f"kv_{key}", f"ku_{key}"
        locator = f"char:{k.start}-{k.end} ({k.chapter})"
        quote = k.quote
        located = locate(text, k.start, quote)
        evidence_ids.append(ev)
        unit_ids.append(ku)
        rows.evidence.append(
            {
                "id": ev,
                "reading_run_id": run,
                "page_number": None,
                "location": json.dumps(
                    {"start": k.start, "end": k.end, "chapter": k.chapter}, ensure_ascii=False
                ),
                "content": k.text,
                "evidence_type": k.role,
            }
        )
        rows.candidates.append(
            {
                "id": cand,
                "reading_run_id": run,
                "evidence_id": ev,
                "content": k.statement,
                "candidate_type": k.role,
                "confidence": 0.9 if k.number else 0.7,
                "classification": _CLASSIFICATION[k.role],
            }
        )
        score = 0.9 if k.number else 0.7
        rows.verifications.append(
            {
                "id": ver,
                "candidate_id": cand,
                "verification_status": "VERIFIED",
                "verification_score": score,
                "definition_check": True,
                "trace_check": located,
                "source_check": True,
                "quality_check": len(_norm(k.statement)) >= 20,
                "verified_quote": quote,
                "verifier_version": EXTRACTOR_VERSION,
            }
        )
        rows.units.append(
            {
                "id": ku,
                "verification_id": ver,
                "candidate_id": cand,
                "source_version_id": sv,
                "title": k.title,
                "statement": k.statement,
                "canonical_text": _norm(k.statement),
                "evidence_count": 1,
                "verification_score": score,
                "content_hash": _h(sv, k.start, _norm(k.statement), n=32),
                "freeze_status": "FROZEN",
                "freeze_version": FREEZE_VERSION,
            }
        )
        quote_hash = _h(_norm(quote))
        status = "LOCATED" if located else "UNLOCATED"
        rows.occurrences.append(
            {
                "id": f"kao_{_h(sv, locator, quote_hash, n=12)}",
                "source_version_id": sv,
                "unit_id": ku,
                "locator": locator,
                "quote_span": quote,
                "role": k.role,
                "quote_status": status,
                "review_required": not located,
                "occurrence_hash": _h(sv, locator, quote_hash, n=32),
            }
        )
    for h in ex.hints:
        frm, to = unit_ids[h.from_index], unit_ids[h.to_index]
        rows.hints.append(
            {
                "id": f"kah_{_h(h.kind, frm, to, n=12)}",
                "source_version_id": sv,
                "kind": h.kind,
                "from_unit_id": frm,
                "to_unit_id": to,
                "confidence": h.confidence,
                "evidence_id": evidence_ids[h.from_index],
                "hint_hash": _h(h.kind, frm, to, n=32),
            }
        )
    return rows


_TABLE_ORDER = (
    ("book_source", "book_source"),
    ("source_version", "source_version"),
    ("reading_run", "reading_run"),
    ("reading_evidence", "evidence"),
    ("ku_candidate", "candidates"),
    ("ku_verification", "verifications"),
    ("knowledge_unit", "units"),
    ("ku_occurrence", "occurrences"),
    ("ku_relation_hint", "hints"),
)


def _batches(rows: Rows) -> Iterable[tuple[str, list[dict[str, Any]]]]:
    for table, attr in _TABLE_ORDER:
        val = getattr(rows, attr)
        yield table, (val if isinstance(val, list) else [val])


def persist(rows: Rows, conn: Any) -> dict[str, int]:
    """Insert everything in one transaction; returns rows actually inserted."""
    inserted: dict[str, int] = {}
    with conn:
        with conn.cursor() as cur:
            for table, batch in _batches(rows):
                n = 0
                for row in batch:
                    cols = list(row)
                    extra = ", frozen_at" if table == "knowledge_unit" else ""
                    vals = ", ".join(f"%({c})s" for c in cols) + (", now()" if extra else "")
                    if table == "ku_occurrence":
                        # One occurrence per unit and role: a later extractor
                        # that only moves a block's end must not add a twin.
                        cur.execute(
                            f"INSERT INTO stratum.ku_occurrence ({', '.join(cols)}) "
                            f"SELECT {vals} WHERE NOT EXISTS (SELECT 1 FROM stratum.ku_occurrence "
                            "WHERE unit_id=%(unit_id)s AND role=%(role)s) ON CONFLICT DO NOTHING",
                            row,
                        )
                        n += cur.rowcount
                        continue
                    cur.execute(
                        f"INSERT INTO stratum.{table} ({', '.join(cols)}{extra}) VALUES ({vals}) ON CONFLICT DO NOTHING",
                        row,
                    )
                    n += cur.rowcount
                inserted[table] = n
    return inserted


def count_rows(conn: Any, sv: str) -> dict[str, int]:
    q = {
        "reading_evidence": "SELECT count(*) FROM stratum.reading_evidence e JOIN stratum.reading_run r ON r.id=e.reading_run_id WHERE r.source_version_id=%s",
        "knowledge_unit": "SELECT count(*) FROM stratum.knowledge_unit WHERE source_version_id=%s",
        "ku_occurrence": "SELECT count(*) FROM stratum.ku_occurrence WHERE source_version_id=%s",
        "ku_occurrence_review": "SELECT count(*) FROM stratum.ku_occurrence WHERE source_version_id=%s AND review_required",
        "ku_relation_hint": "SELECT count(*) FROM stratum.ku_relation_hint WHERE source_version_id=%s",
    }
    out = {}
    with conn.cursor() as cur:
        for k, sql in q.items():
            cur.execute(sql, (sv,))
            out[k] = cur.fetchone()[0]
    return out


def _connect() -> Any:
    import psycopg2

    from stratum.db import _dsn_kwargs

    return psycopg2.connect(**_dsn_kwargs())


# Books BU2 understood come first; then books the AII flywheels have ingested
# (aii.ingested_substrate with KUs, or any substrate with rows in aii.ku_onto),
# newest ingest first. Only substrates with a markdown derivative are eligible,
# because BookLoader freezes from stratum.derivative. Idempotency is the
# source_version check: a frozen book is never selected again.
PENDING_SQL = """
WITH cand AS (
    SELECT u.substrate_id, 0 AS prio, NULL::timestamptz AS ts
    FROM stratum.book_understandings_v2 u
    UNION ALL
    SELECT i.substrate_id, 1 AS prio, i.ingested_at AS ts
    FROM aii.ingested_substrate i
    WHERE COALESCE(i.ku_count, 0) > 0
    UNION ALL
    SELECT k.substrate_id, 2 AS prio, NULL::timestamptz AS ts
    FROM (SELECT DISTINCT substrate_id FROM aii.ku_onto) k
)
SELECT c.substrate_id
FROM cand c
WHERE EXISTS (
    SELECT 1 FROM stratum.derivative d
    WHERE d.substrate_id = c.substrate_id AND d.kind = 'markdown'
      AND d.content IS NOT NULL AND d.content <> ''
)
AND NOT EXISTS (
    SELECT 1 FROM stratum.source_version sv
    WHERE sv.book_source_id = c.substrate_id AND sv.version = %s
)
GROUP BY c.substrate_id
ORDER BY MIN(c.prio), MAX(c.ts) DESC NULLS LAST, c.substrate_id
LIMIT %s
"""

# Fallback when the aii schema is absent (fresh / non-AII deployments).
PENDING_SQL_BU2_ONLY = """
SELECT DISTINCT u.substrate_id
FROM stratum.book_understandings_v2 u
WHERE NOT EXISTS (
    SELECT 1 FROM stratum.source_version sv
    WHERE sv.book_source_id = u.substrate_id AND sv.version = %s
)
ORDER BY u.substrate_id
LIMIT %s
"""


def pending_substrates(conn: Any, limit: int) -> list[str]:
    """Books understood (BU2) or ingested by the AII flywheels, not yet frozen into A."""
    try:
        with conn.cursor() as cur:
            cur.execute(PENDING_SQL, (FREEZE_VERSION, limit))
            return [r[0] for r in cur.fetchall()]
    except Exception as exc:  # aii schema missing -> BU2-only selection
        if "aii." not in str(exc) and "does not exist" not in str(exc):
            raise
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute(PENDING_SQL_BU2_ONLY, (FREEZE_VERSION, limit))
            return [r[0] for r in cur.fetchall()]


def run_pending(limit: int, persist_rows: bool) -> int:
    """Flywheel entry: freeze up to ``limit`` pending books (BU2 or flywheel-ingested)."""
    conn = _connect()
    try:
        ids = pending_substrates(conn, limit)
    finally:
        conn.close()
    failures = 0
    for sid in ids:
        argv = [sid, "--json"] + (["--persist"] if persist_rows else [])
        try:
            if main(argv) != 0:
                failures += 1
        except Exception as exc:  # one bad book must not stop the batch
            failures += 1
            print(json.dumps({"substrate_id": sid, "error": str(exc)[:300]}), file=sys.stderr)
    print(json.dumps({"pending": len(ids), "failures": failures}))
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--all-pending" in args:
        bp = argparse.ArgumentParser(prog="book_freeze --all-pending")
        bp.add_argument("--all-pending", action="store_true")
        bp.add_argument("--persist", action="store_true")
        bp.add_argument("--limit", type=int, default=20)
        b = bp.parse_args(args)
        return run_pending(b.limit, b.persist)
    p = argparse.ArgumentParser(prog="book_freeze", description=__doc__.split("\n\n")[0])
    p.add_argument("substrate_id")
    p.add_argument("--persist", action="store_true", help="write to the A warehouse")
    p.add_argument("--json", action="store_true")
    p.add_argument("--samples", type=int, default=0, help="print N sample KUs per role")
    a = p.parse_args(args)

    from stratum.services.bu_v2_entrypoint import BookLoader

    t0 = time.monotonic()
    title, text, chapters = BookLoader().load(a.substrate_id)
    if not text:
        print(f"book_freeze: substrate {a.substrate_id} has no markdown", file=sys.stderr)
        return 2
    ex = extract(text, chapters)
    rows = build_rows(a.substrate_id, title, text, ex, {"chapters": len(chapters)})
    report: dict[str, Any] = {
        "substrate_id": a.substrate_id,
        "title": title,
        "source_version_id": rows.source_version_id,
        "chars": len(text),
        "kus": len(ex.kus),
        "roles": ex.role_counts(),
        "hints": ex.hint_counts(),
        "unlocated": sum(1 for o in rows.occurrences if o["review_required"]),
    }
    if a.samples:
        samples = []
        for role in ROLES:
            for k in [k for k in ex.kus if k.role == role][: a.samples]:
                samples.append(
                    {"role": role, "title": k.title, "chapter": k.chapter, "quote": k.quote[:160]}
                )
        report["samples"] = samples
        report["hint_samples"] = [
            {
                "kind": h.kind,
                "from": ex.kus[h.from_index].title,
                "from_quote": ex.kus[h.from_index].quote[:100],
                "to": ex.kus[h.to_index].title,
                "to_chapter": ex.kus[h.to_index].chapter,
                "confidence": h.confidence,
            }
            for kind in (APPLIES, RESTATES, SUMMARIZES)
            for h in [x for x in ex.hints if x.kind == kind][: a.samples]
        ]
    if a.persist:
        conn = _connect()
        try:
            report["inserted"] = persist(rows, conn)
            report["db_counts"] = count_rows(conn, rows.source_version_id)
        finally:
            conn.close()
    report["seconds"] = round(time.monotonic() - t0, 2)
    print(json.dumps(report, ensure_ascii=False, indent=None if a.json else 2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
