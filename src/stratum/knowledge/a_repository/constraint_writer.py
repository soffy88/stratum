"""A Repository P5.4 — constraint annotation.

    reading_evidence (raw span) ──> constraint_candidate ──> knowledge_unit

A constraint annotation here is a **candidate**: a limiting rule the source
states about itself, quoted from the span that states it.

The rule the whole stage turns on, frozen as `DECISION=SPAN_ONLY`:

    Every one of subject, predicate, object and boundary must be a literal
    substring of the reading_evidence span. Anything else is refused.

Not a matter of tidiness. Measured on the frozen corpus, the knowledge_unit
statement and the raw span use different words:

    KU   : 巴比伦法定利率上限：银子贷款20%/年（按重量计）
    SPAN : 银子贷款按重量计算每年20%

The silver-loan span states a rate and contains **no** 上限, no 不得超过, no
禁止. The cap framing exists only in the KU statement, which P3/P4 wrote. If
fields could be quoted from the KU statement, an extractor could change the
semantics first and have the constraint appear evidenced:

    raw span   "谷物贷款每年33.333%"
    extractor  "谷物贷款每年33.333%，存在20%上限"
    => predicate 不得超过, object 20%, typed HARD

That turns a source declaration into an extractor assertion. So the Babylon
rate cap is rejected — a rate fact is not a constraint — and that rejection is
recorded as LIMITATION-6 rather than treated as a gap to be filled.

Two boundaries are kept apart:

- **A constraint is a stated limit.** HARD means the source prohibits
  outright, because the span says 不得超过 — not because a cap is strict.
- **A constraint is not advice.** `CONSTRAINT_BANNED_FIELDS` refuses the words
  that would turn a recorded limit into a recommendation.

Identity is derived in two steps:

    1. constraint_id   = f(source_version_id, knowledge_unit_id,
                            constraint_type, extractor_version)
    2. constraint_hash = f(1's inputs, subject, predicate, object, boundary,
                           sorted(evidence_ids))

`evidence_ids` is sorted before hashing: the order spans were read in is a
traversal artefact, not a claim. Same rule as 080's `evidence_hash`.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Sequence, Tuple

from .identity import IdentitySink
from .persistence import FreezeTransaction


CONSTRAINT_VERSION = "a-p5-4-v0.1"

#: A real extraction. Never used by the pilot.
EXTRACTOR_VERSION = "constraint_extractor_v1"

#: A candidate declared to exercise the persistence contract. Not an extraction
#: result, and not evidence that the extractor works. It is inside
#: constraint_hash, so an extractor run over the same span produces a different
#: candidate rather than being swallowed as a replay.
PILOT_DECLARED_VERSION = "pilot-declared"

#: How strongly the source binds itself. Nothing here says whether a limit is
#: reasonable, high, low or ought to be followed.
CONSTRAINT_TYPES = ("HARD", "SOFT", "SELF_DEFINED")

#: Field names a constraint may not grow. These are the words that turn a
#: recorded limit into a recommendation — "合理利率应该低于20%" is advice, and a
#: column that could hold advice would let A仓 give it.
CONSTRAINT_BANNED_FIELDS = ("recommendation", "recommended", "advice",
                            "should", "reasonable", "optimal", "normative",
                            "compliance_score", "enforceability",
                            "fairness", "optimal_rate", "rule")

#: Words that would make a constraint into advice. Checked against the quoted
#: span, so a rule the source states in advisory language is not typed as a
#: constraint at all.
ADVISORY_MARKERS: Tuple[str, ...] = ("应该", "应当", "宜", "建议", "推荐",
                                     "最好", "必须遵守")

#: Soft-constraint markers. Measured **zero** occurrences on this corpus, and
#: kept because that is a fact about the corpus, not about the vocabulary.
SOFT_MARKERS: Tuple[str, ...] = ("通常", "一般情况", "一般而言", "大多数",
                                  "多半", "往往", "一般情况下")


def evidence_span(evidence) -> Optional[str]:
    """The raw span text of a reading_evidence row, or None.

    The same value has two names across the 070 boundary: `content_span` on the
    in-memory row, `content` in the database. Both are accepted, because a
    rename in either layer must not silently turn every constraint into an
    unquotable one — the symptom would be a quote gate that refuses everything
    for a reason nobody can see.

    This is deliberately NOT the knowledge_unit statement. DECISION=SPAN_ONLY
    means the quotation is checked against the book's own span.
    """
    if evidence is None:
        return None
    span = getattr(evidence, "content_span", None)
    if span is None:
        span = getattr(evidence, "content", None)
    return span


class ConstraintType(str, Enum):
    HARD = "HARD"
    SOFT = "SOFT"
    SELF_DEFINED = "SELF_DEFINED"


class ConstraintStatus(str, Enum):
    """No VERIFIED, no CONFIRMED, no APPROVED.

    `VERIFIED` is the success value of `ku_verification.verification_status`;
    `CONFIRMED` and `APPROVED` are two more words for that same judgement. A
    constraint the source states is not a verified proposition.
    """

    GENERATED = "GENERATED"
    SUPPORTED = "SUPPORTED"
    REJECTED = "REJECTED"


#: Both SUPPORTED and REJECTED are final. A仓 corrects by appending a new
#: candidate under a new hash, never by downgrading one in place — the rule
#: 077, 078, 079 and 080 all freeze against.
LEGAL_STATUS_TRANSITIONS: Dict[ConstraintStatus, frozenset] = {
    ConstraintStatus.GENERATED: frozenset({ConstraintStatus.SUPPORTED,
                                           ConstraintStatus.REJECTED}),
    ConstraintStatus.SUPPORTED: frozenset(),
    ConstraintStatus.REJECTED: frozenset(),
}


class ConstraintViolation(Exception):
    """Raised on a forbidden constraint operation."""


class ConstraintPrecondition(Exception):
    """A candidate may not be written as given; nothing was written."""


# ── identity ─────────────────────────────────────────────────────────────────

def constraint_id(source_version_id: str, knowledge_unit_id: str,
                  constraint_type: str, extractor_version: str) -> str:
    """`cnc_<sha256(...)[:12]>` — step 1.

    No quoted fields: this is the identity of the *annotation of this unit*, so
    a second rule read from the same unit is a distinct candidate rather than a
    rewrite of the first.
    """
    digest = hashlib.sha256(
        f"{source_version_id}|{knowledge_unit_id}|{constraint_type}"
        f"|{extractor_version}".encode("utf-8")).hexdigest()
    return f"cnc_{digest[:12]}"


def constraint_hash(source_version_id: str, knowledge_unit_id: str,
                    constraint_type: str, subject: str, predicate: str,
                    obj: str, boundary: Optional[str],
                    evidence_ids: Sequence[str], extractor_version: str) -> str:
    """`cnh_<sha256(...)[:16]>` — step 2, the replay identity.

    Covers all four quoted fields and the evidence set. Sorting `evidence_ids`
    here is what makes "read the same span in a different order" a replay rather
    than a new annotation: the order spans were traversed in is not a claim
    about the rule.
    """
    ordered = "|".join(sorted(evidence_ids))
    digest = hashlib.sha256(
        f"{source_version_id}|{knowledge_unit_id}|{constraint_type}|{subject}"
        f"|{predicate}|{obj}|{boundary}|{ordered}|{extractor_version}"
        .encode("utf-8")).hexdigest()
    return f"cnh_{digest[:16]}"


# ── rows ─────────────────────────────────────────────────────────────────────

@dataclass
class ConstraintCandidate:
    id: str
    source_version_id: str
    knowledge_unit_id: str
    constraint_type: str
    subject: str
    predicate: str
    object: str
    evidence_ids: List[str] = field(default_factory=list)
    boundary: Optional[str] = None
    constraint_hash: str = ""
    extractor_version: str = EXTRACTOR_VERSION
    status: str = ConstraintStatus.GENERATED.value
    created_at: str = CONSTRAINT_VERSION


CONSTRAINT_COLUMNS = ("id", "source_version_id", "knowledge_unit_id",
                      "constraint_type", "subject", "predicate", "object",
                      "boundary", "evidence_ids", "constraint_hash",
                      "extractor_version", "status", "created_at")

#: created_at carries DEFAULT now() in 081, so the insert omits it: the database
#: stamps it, and a replay cannot supply a timestamp that disagrees with the row.
CONSTRAINT_INSERT_COLUMNS = tuple(c for c in CONSTRAINT_COLUMNS
                                  if c != "created_at")


# ── the constraint ───────────────────────────────────────────────────────────

def field_is_quoted(candidate: ConstraintCandidate, span_text: str) -> bool:
    """Is every quoted field a literal substring of the span?

    The gate `DECISION=SPAN_ONLY` rests on. It is not expressible as a CHECK: it
    reads reading_evidence, and PostgreSQL refuses a CHECK that reads another
    table. So it is the writer's, and this function is the single place the rule
    is written down.
    """
    for name, value in (("subject", candidate.subject),
                        ("predicate", candidate.predicate),
                        ("object", candidate.object),
                        ("boundary", candidate.boundary)):
        if value is None:
            continue
        if value not in span_text:
            return False
    return True


def unquoted_fields(candidate: ConstraintCandidate, span_text: str) -> List[str]:
    """Which quoted fields are absent from the span, by name.

    Read by the quote-authority gate so a regression names the field rather than
    just reporting a refusal.
    """
    missing: List[str] = []
    for name, value in (("subject", candidate.subject),
                        ("predicate", candidate.predicate),
                        ("object", candidate.object),
                        ("boundary", candidate.boundary)):
        if value is None:
            continue
        if value not in span_text:
            missing.append(name)
    return missing


class ConstraintBuilder:
    """Composes a constraint out of a frozen unit and its raw span.

    Reads the span out of the store rather than accepting quoted text from a
    caller. That is what makes the quote rule enforceable: the span is the
    reference the fields are checked against, so a caller cannot supply a
    "quotation" of something the book never said.
    """

    def __init__(self, ingestion_pipeline, units: Optional[Dict] = None):
        """`units` is the durable unit table, keyed by `knowledge_unit.id`.

        Needed because a constraint is given a canonical unit id while the
        candidate table is keyed by candidate id: unit -> candidate -> evidence.
        """
        self.store = ingestion_pipeline.store
        self.units = units if units is not None else {}

    def span_of(self, unit_id: str) -> Optional[str]:
        """The raw span text a frozen unit is anchored to, or None.

        `content` on the in-memory row; the same value as `content` in the
        database. This is the text `field_is_quoted` checks against — never the
        KU statement.
        """
        candidate = self.candidate_of(unit_id)
        if candidate is None:
            return None
        return evidence_span(self.store.evidence.get(candidate.evidence_id))

    def evidence_of(self, unit_id: str) -> List[str]:
        candidate = self.candidate_of(unit_id)
        if candidate is None:
            return []
        return [candidate.evidence_id]

    def candidate_of(self, unit_id: str):
        unit = self.units.get(unit_id)
        if unit is None:
            return None
        return self.store.ku_candidates.get(unit.candidate_id)

    def build(self, source_version_id: str, unit_id: str,
              constraint_type: str, subject: str, predicate: str, obj: str,
              boundary: Optional[str], extractor_version: str
              ) -> ConstraintCandidate:
        """Build one constraint, quoted from the unit's own span.

        Every argument is text the caller believes the span states. None of it is
        trusted: `preconditions()` checks each field against the span, and a
        field that is not there is refused rather than stored.
        """
        if constraint_type not in CONSTRAINT_TYPES:
            raise ConstraintPrecondition(
                f"{constraint_type} is not a constraint type in 081; only "
                f"{', '.join(CONSTRAINT_TYPES)} are declared.")
        evidence_ids = self.evidence_of(unit_id)
        return ConstraintCandidate(
            id=constraint_id(source_version_id, unit_id, constraint_type,
                             extractor_version),
            source_version_id=source_version_id,
            knowledge_unit_id=unit_id,
            constraint_type=constraint_type,
            subject=subject,
            predicate=predicate,
            object=obj,
            boundary=boundary,
            evidence_ids=evidence_ids,
            constraint_hash=constraint_hash(
                source_version_id, unit_id, constraint_type, subject, predicate,
                obj, boundary, evidence_ids, extractor_version),
            extractor_version=extractor_version,
        )


def transition(candidate: ConstraintCandidate,
               target: ConstraintStatus) -> None:
    """The only way a candidate's status changes.

    Both SUPPORTED and REJECTED are final, so a correction is a new candidate
    under a new hash.
    """
    current = ConstraintStatus(candidate.status)
    if target not in LEGAL_STATUS_TRANSITIONS[current]:
        raise ConstraintViolation(
            f"{current.value} -> {target.value} is not a legal status "
            "transition; a supported constraint is final and A仓 corrects by "
            "appending a new candidate.")
    candidate.status = target.value


# ── durability ───────────────────────────────────────────────────────────────

CONSTRAINT_TABLES = ("constraint_candidate",)

#: The bucket is not called `constraints`: nothing else in IdentitySink maps to
#: that name today, but the frozen layers have twice been shadowed by a shared
#: bucket name (075's `relations` in 079), so the collision is avoided by
#: construction rather than by luck.
_CONSTRAINT_BUCKETS: Dict[str, str] = {
    "constraint_candidate": "constraint_candidates",
}

_CONSTRAINT_ROW_TYPES: Dict[str, type] = {
    "constraint_candidate": ConstraintCandidate,
}


class ConstraintSink(IdentitySink):
    """Every sink up to P6, plus the constraint table."""

    TABLES = IdentitySink.TABLES + CONSTRAINT_TABLES
    ROW_TYPES = {**IdentitySink.ROW_TYPES, **_CONSTRAINT_ROW_TYPES}
    ROW_BUCKETS = {**IdentitySink.ROW_BUCKETS, **_CONSTRAINT_BUCKETS}

    def __init__(self, fail_after: Optional[int] = None):
        super().__init__(fail_after=fail_after)
        self.constraint_candidates: Dict[str, ConstraintCandidate] = {}

    def commit(self, pending: Sequence[Tuple[str, Dict]]) -> None:
        staged: Dict[str, Dict[str, Dict]] = {
            table: {} for table in self.TABLES}
        for index, (table, row) in enumerate(pending):
            if self.fail_after is not None and index >= self.fail_after:
                self.rollbacks += 1
                raise RuntimeError(f"injected failure at write {index} ({table})")
            if table not in staged:
                raise ConstraintViolation(f"unknown table {table}")
            staged[table][row["id"]] = row
        for table, rows in staged.items():
            row_type = self.ROW_TYPES[table]
            getattr(self, self.ROW_BUCKETS[table]).update(
                {key: row_type(**value) for key, value in rows.items()})
        self.commits += 1

    def reload(self) -> Dict[str, object]:
        reloaded = super().reload()
        for table in CONSTRAINT_TABLES:
            reloaded[table] = dict(getattr(self, self.ROW_BUCKETS[table]))
        return reloaded


class ConstraintWriter:
    """Appends constraints. Holds no path to anything upstream."""

    def __init__(self, ingestion_pipeline, sink: ConstraintSink):
        self.store = ingestion_pipeline.store
        self.builder = ConstraintBuilder(ingestion_pipeline, sink.units)
        self.sink = sink

    # ── gates ──────────────────────────────────────────────────────────────

    def preconditions(self, candidate: ConstraintCandidate
                      ) -> Tuple[bool, List[str]]:
        """Everything that must hold, checked before the transaction opens."""
        failed: List[str] = []
        if candidate.constraint_type not in CONSTRAINT_TYPES:
            failed.append("CONSTRAINT_TYPE_NOT_AUTHORISED")
        if not candidate.evidence_ids:
            failed.append("NO_EVIDENCE")
        if candidate.source_version_id not in self.store.source_versions:
            failed.append("NO_SUCH_SOURCE_VERSION")
        unit = self.sink.units.get(candidate.knowledge_unit_id)
        if unit is None:
            failed.append("NO_SUCH_UNIT")
        elif unit.source_version_id != candidate.source_version_id:
            # 081's composite key enforces this too; kept because it reports a
            # readable reason instead of a constraint name.
            failed.append("CROSS_SOURCE_UNIT")
        if not self._fields_quoted(candidate):
            failed.append("FIELD_NOT_IN_SPAN")
        if not self._evidence_same_book(candidate):
            failed.append("CROSS_BOOK_EVIDENCE")
        if self._advisory(candidate):
            failed.append("ADVISORY_NOT_A_CONSTRAINT")
        return not failed, failed

    def _fields_quoted(self, candidate: ConstraintCandidate) -> bool:
        """Every quoted field is a literal substring of the span.

        DECISION=SPAN_ONLY. The KU statement is explicitly not consulted: it is
        human context, and quoting from it would let an extractor restate a
        rate as a cap and have the restatement look evidenced.
        """
        for evidence_id in candidate.evidence_ids:
            span = evidence_span(self.store.evidence.get(evidence_id))
            if span is None:
                return False
            if not field_is_quoted(candidate, span):
                return False
        return True

    def _evidence_same_book(self, candidate: ConstraintCandidate) -> bool:
        """Every evidence id is real and of the same book.

        TEXT[] carries no foreign key, so 081's CHECK proves the array is
        non-empty and nothing more. This is the layer that proves the members
        exist and belong here.
        """
        for evidence_id in candidate.evidence_ids:
            evidence = self.store.evidence.get(evidence_id)
            if evidence is None:
                return False
            if evidence.source_version_id != candidate.source_version_id:
                return False
        return True

    def _advisory(self, candidate: ConstraintCandidate) -> bool:
        """Does the quoted span read as advice rather than as a rule?

        "合理利率应该低于20%" is a recommendation. A仓 stores that the source
        *declares* a limit; it does not store what anyone ought to do. The
        markers are checked against the span, so this is a property of the
        source's wording, not of the annotator's mood.
        """
        span = ""
        for evidence_id in candidate.evidence_ids:
            span = evidence_span(self.store.evidence.get(evidence_id))
            if span:
                break
        return any(marker in (span or "") for marker in ADVISORY_MARKERS)

    # ── persistence ────────────────────────────────────────────────────────

    def write(self, candidate: ConstraintCandidate) -> ConstraintCandidate:
        """One constraint, in one transaction.

        Returns the **stored** object, not the one passed in — the copy-on-write
        shape P4.1, P5.0, 078, 079 and 080 all use.
        """
        ok, failed = self.preconditions(candidate)
        if not ok:
            raise ConstraintPrecondition(
                f"{candidate.id} may not be written: {', '.join(failed)}.")
        if candidate.id in self.sink.constraint_candidates:
            return self.sink.constraint_candidates[candidate.id]
        try:
            with FreezeTransaction(self.sink) as tx:
                tx.write("constraint_candidate", dict(candidate.__dict__))
        except Exception as error:
            raise ConstraintViolation(
                f"{candidate.id} was not written: {error}") from error
        return self.sink.constraint_candidates[candidate.id]

    # ── lifecycle ──────────────────────────────────────────────────────────

    def support(self, constraint_id_: str) -> ConstraintCandidate:
        """GENERATED -> SUPPORTED, only on a fully quoted candidate."""
        candidate = self.sink.constraint_candidates[constraint_id_]
        ok, failed = self.preconditions(candidate)
        if not ok:
            raise ConstraintPrecondition(
                f"{constraint_id_} may not be supported: {', '.join(failed)}.")
        transition(candidate, ConstraintStatus.SUPPORTED)
        return candidate

    def reject(self, constraint_id_: str) -> ConstraintCandidate:
        """GENERATED -> REJECTED. Not available from SUPPORTED."""
        candidate = self.sink.constraint_candidates[constraint_id_]
        transition(candidate, ConstraintStatus.REJECTED)
        return candidate

    # ── immutability ───────────────────────────────────────────────────────

    def update_candidate(self, constraint_id_: str, **changes) -> None:
        raise ConstraintViolation(
            f"{constraint_id_} cannot be updated; a correction is a new "
            "candidate under a new hash, never an edit of this one.")

    def delete_candidate(self, constraint_id_: str) -> None:
        raise ConstraintViolation(
            "A constraint cannot be deleted. One that is no longer supported is "
            "REJECTED, which keeps the record and the reason.")

    def derive_constraint(self, *constraint_ids: str) -> None:
        raise ConstraintViolation(
            "A仓 does not derive constraints. A limit the source did not state "
            "is an inference, and LIMITATION-6 is the record of one being "
            "refused.")

    def recommend(self, constraint_id_: str, **advice) -> None:
        raise ConstraintViolation(
            "A constraint records what a source states, not what anyone ought "
            "to do. '合理利率应该低于20%' is advice and belongs to B仓.")

    def merge_constraints(self, *constraint_ids: str) -> None:
        raise ConstraintViolation(
            "A仓 has no authority to merge constraints; deciding two stated "
            "limits are one is a semantic judgement.")

    def enforce(self, constraint_id_: str) -> None:
        raise ConstraintViolation(
            "A constraint has no enforcement state; A仓 records a stated limit, "
            "it does not police one.")

    def update_verification(self, *args, **kwargs) -> None:
        raise ConstraintViolation("This layer never touches a verification.")

    # ── queries ────────────────────────────────────────────────────────────

    def unquoted_candidates(self) -> List[str]:
        """Candidates carrying a field that is not in their own span.

        Should always be empty. Read by the quote-authority gate rather than
        assumed.
        """
        wrong: List[str] = []
        for candidate in self.sink.constraint_candidates.values():
            for evidence_id in candidate.evidence_ids:
                span = evidence_span(self.store.evidence.get(evidence_id))
                if span is None or not field_is_quoted(candidate, span):
                    wrong.append(candidate.id)
                    break
        return sorted(set(wrong))

    def cross_source_candidates(self) -> List[str]:
        wrong: List[str] = []
        for candidate in self.sink.constraint_candidates.values():
            unit = self.sink.units.get(candidate.knowledge_unit_id)
            if unit is None or \
                    unit.source_version_id != candidate.source_version_id:
                wrong.append(candidate.id)
        return sorted(set(wrong))

    def unauthorised_type_rows(self) -> List[str]:
        return sorted(c.id for c in self.sink.constraint_candidates.values()
                      if c.constraint_type not in CONSTRAINT_TYPES)

    def duplicate_hashes(self) -> List[str]:
        seen: Dict[str, int] = {}
        for candidate in self.sink.constraint_candidates.values():
            seen[candidate.constraint_hash] = seen.get(
                candidate.constraint_hash, 0) + 1
        return sorted(h for h, count in seen.items() if count > 1)

    def type_coverage(self) -> Dict[str, bool]:
        """Which constraint types this corpus has actually exercised.

        SOFT and SELF_DEFINED are expected False, and that is the frozen
        decision rather than a gap: the vocabulary that would define a SOFT
        constraint occurs zero times on this corpus, and no span makes an
        author's self-defined range judgeable. Reported per run so an
        unexercised type stays visible instead of quietly disappearing.
        """
        stored = {c.constraint_type
                  for c in self.sink.constraint_candidates.values()}
        return {t: t in stored for t in CONSTRAINT_TYPES}

    def pilot_rows(self) -> List[str]:
        return sorted(c.id for c in self.sink.constraint_candidates.values()
                      if c.extractor_version == PILOT_DECLARED_VERSION)

    def extracted_rows(self) -> List[str]:
        return sorted(c.id for c in self.sink.constraint_candidates.values()
                      if c.extractor_version != PILOT_DECLARED_VERSION)

    def traceability_percent(self) -> float:
        """constraint -> unit -> span, as a percentage.

        Counted as a verified substring test per field, not as an evidence id
        existing: "an id exists" is not "the words are the book's".
        """
        total = 0
        traced = 0
        for candidate in self.sink.constraint_candidates.values():
            unit = self.sink.units.get(candidate.knowledge_unit_id)
            if unit is None or unit.source_version_id != \
                    candidate.source_version_id:
                continue
            for evidence_id in candidate.evidence_ids:
                total += 1
                evidence = self.store.evidence.get(evidence_id)
                span = evidence_span(evidence)
                if span is None:
                    continue
                if evidence.source_version_id != candidate.source_version_id:
                    continue
                if field_is_quoted(candidate, span):
                    traced += 1
        return round(100.0 * traced / total, 2) if total else 0.0


# ── SQL emission ─────────────────────────────────────────────────────────────

def _literal(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, Enum):
        value = value.value
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (list, tuple)):
        return "ARRAY[" + ",".join(_literal(v) for v in value) + "]"
    return "'" + str(value).replace("'", "''") + "'"


def _values(row: Dict, columns: Sequence[str]) -> str:
    """One VALUES tuple.

    created_at is absent from `columns`: 081 declares DEFAULT now(), so the
    database stamps it and a replay cannot supply a timestamp that disagrees
    with the stored row.
    """
    return ",".join(_literal(row.get(c)) for c in columns)


def emit_constraint_sql(candidates) -> str:
    """The constraint table as one transaction.

    Every statement is ON CONFLICT DO NOTHING, so a replay writes nothing.
    """
    lines = ["BEGIN;", "SET search_path TO stratum, public;"]
    for key in sorted(candidates):
        row = dict(candidates[key].__dict__)
        lines.append(
            f"INSERT INTO constraint_candidate "
            f"({','.join(CONSTRAINT_INSERT_COLUMNS)}) "
            f"VALUES ({_values(row, CONSTRAINT_INSERT_COLUMNS)}) "
            f"ON CONFLICT (constraint_hash) DO NOTHING;")
    lines.append("COMMIT;")
    return "\n".join(lines) + "\n"


def banned_field_report() -> Dict[str, List[str]]:
    """Which banned field names appear anywhere in this stage.

    Structural: the row dataclass, not a word scan of the source. A constraint
    that grew a `recommendation` column would be A仓 giving advice, and this is
    where that is noticed.
    """
    rows: Dict[str, List[str]] = {}
    for name in CONSTRAINT_BANNED_FIELDS:
        rows[name] = ([f"ConstraintCandidate.{name}"]
                      if hasattr(ConstraintCandidate, name) else [])
    return rows


#: Frozen notes for the artifact. Kept as data so the runner cannot report a
#: limitation the module has stopped honouring.
CONSTRAINT_NOTES = {
    "CONSTRAINT_TYPES": list(CONSTRAINT_TYPES),
    "QUOTE_AUTHORITY": "READING_EVIDENCE_ONLY",
    "KU_STATEMENT_AS_EVIDENCE": "FORBIDDEN",
    "STATE_MACHINE": "GENERATED -> SUPPORTED | REJECTED; both terminal",
    "PILOT_YIELD": 1,
    "DB_GUARANTEES": [
        "foreign key integrity (source_version, knowledge_unit)",
        "the unit is of the annotation's own source version, via composite keys",
        "constraint_type vocabulary closed to three values",
        "status vocabulary closed, with no VERIFIED / CONFIRMED / APPROVED",
        "subject, predicate, object non-empty",
        "evidence_ids non-empty",
        "replay hash uniqueness",
    ],
    "DB_DOES_NOT_GUARANTEE": [
        "that the four quoted fields appear in the evidence span: a CHECK cannot "
        "read another table, so DECISION=SPAN_ONLY is the writer's to enforce",
        "that evidence_ids members are real rows of the same book",
        "the state machine: a CHECK cannot read a column's previous value",
        "constraint_type: a CHECK cannot tell whether a span binds hard",
    ],
    "KNOWN_LIMITATIONS": [
        "LIMITATION-1 constraint extraction quality is not proven",
        "LIMITATION-2 soft constraint boundary depends on source wording",
        "LIMITATION-3 evidence array FK is service verified only",
        "LIMITATION-4 database guarantees source/KU identity, not semantic "
        "validity",
        "LIMITATION-5 no constraint may be promoted to B仓 automatically",
        "LIMITATION-6 some historically known constraints cannot enter A仓 when "
        "the span records a fact but not the limiting rule; this is intentional",
    ],
    "REJECTED_BY_DECISION": [
        "Babylon silver-loan rate cap: the span states 银子贷款按重量计算每年20% "
        "with no 上限, no 不得超过 and no 禁止. The cap framing exists only in "
        "the KU statement, which P3/P4 wrote. A rate fact is not a constraint.",
        "p4 grain cap 法定利率上限确定为谷物贷款每年33.333%: no frozen KU, and "
        "081 requires knowledge_unit_id",
        "p5 所有贷款都必须附有书面合约: no frozen KU",
        "p7 但是禁止个人劳役偿债: no frozen KU",
        "p5 如果作弊收取的利息高于法定上限，那么债务的本金就会被免除: a "
        "conditional consequence, not a limit on the rate",
        "p6 因而必须进行重大改革: 必须 refers to reform, not to a credit "
        "constraint",
        "p9 高于法定上限的利息将被处以4倍损害赔偿: a sanction attached to a "
        "limit, not the limit itself",
    ],
    "PILOT_SCOPE": (
        "persistence, traceability, replay and authority boundary; constraint "
        "completeness, legal correctness and economic interpretation are not "
        "measured and no extractor ships in this stage"),
}