"""A Repository P5.0 — condition / boundary candidate layer.

    Source -> Evidence -> KU Candidate -> Verification -> Frozen KU
                                                       |
                                       Condition/Boundary Extractor
                                                       |
                                       Condition/Boundary Candidate

A condition is not an input to a verification decision. It is interpretation
enrichment applied *after* a unit is frozen, which is why this module reads
frozen units and never writes to anything upstream.

What this module must not do, and how that is enforced rather than promised:

- it must not change a verification verdict. `required_slots()`,
  `SemanticIntegrity`, `verification_score` and the P3 logic are imported for
  their marker lists and for nothing else; this file contains no assignment
  to any of them and no call to `transition`.
- it must not modify a frozen unit. `extract()` takes a unit and returns new
  objects; the unit is read once for its span.
- it must not paraphrase. Every `statement` is a verbatim substring of the
  unit's anchored `canonical_text`, and `misanchored_statements()` is a gate.

Three vocabularies, kept apart on purpose:

    qualifier   a checkable qualifier of the claim: an agent or a time
    tendency    "usually", "generally", "possibly" — not a condition
    causal      "because", "therefore", "leading to" — a mechanism, not a
                condition, and the mechanism layer does not exist yet

The second and third are refused here rather than down-weighted. A hedged
qualifier is not a weaker condition, it is a different kind of object, and
storing it in this table would blur the one distinction that keeps the table
honest. The guard below is directional: it rejects tendencies in a
condition, and a constraint candidate — which is a different table in a
different stage — is where tendencies belong.

Marker vocabularies are measured, not guessed. See `MARKER_NOTES` at the
bottom of this file for what was counted on the frozen pilot and why the
lists are shaped the way they are.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Sequence, Tuple

from .identity import IDENTITY_TABLES, IdentitySink
from .persistence import FreezeTransaction


CONDITION_BOUNDARY_VERSION = "a-p5-0-v0.1"

#: Delimiters a clause is cut at. Deterministic, and the same set the rest
#: of the A chain uses to take a statement's opening.
CLAUSE_DELIMITERS = ("，", "。", "；", "：", "！", "？", "、", ",", ".", ";",
                     ":", "!", "?", "（", "(", "）", ")")

#: A tendency is not a condition. Refused, never down-weighted.
TENDENCY_WORDS = ("通常", "一般", "可能", "大多数", "多数时候", "往往",
                  "一般情况", "一般情况下", "大多数时候")

#: Causality belongs to the mechanism layer, which is not built.
CAUSAL_WORDS = ("因为", "所以", "导致", "因此", "由于", "使得")

# ── measured marker vocabularies ─────────────────────────────────────────────

#: Agents, reusing P3's list. Every marker here was counted on the frozen
#: pilot and is an agent in the spans it appears in.
ACTOR_MARKERS: Tuple[str, ...] = (
    "国王", "债权人", "债主", "官员", "政府", "罗马", "巴比伦", "雅典", "索伦")

#: P3's list contains 法典, which is what a ruler *modifies*, not the ruler.
#: For a boolean slot that looseness is harmless. For a statement extracted
#: as an agent it is not, so it is withdrawn here rather than reused.
ACTOR_DISQUALIFIERS: Tuple[str, ...] = ("法典",)

#: Times, narrowed from P3's list. P3 asks "is there a time expression?" and
#: the bare 年 makes that true for every rate; this layer asks "is this a
#: temporal qualifier of the claim?" and 年 fails that. Dropped: 年.
TIME_MARKERS: Tuple[str, ...] = (
    "公元前", "世纪", "年代", "时期", "时代", "当时", "古代", "中世纪")

#: 每年 is a rate basis — "no more than 8.333% per year" states no temporal
#: condition at all. It was 2 of the 4 TIME hits on the frozen pilot while
#: P3's bare 年 was still in play.
#:
#: Currently **inert**: no marker in TIME_MARKERS is a substring of 每年, so
#: nothing is rejected by this list today. It is kept because withdrawing 年
#: is the only thing stopping 每年 from leaking back, and the day someone
#: re-widens TIME_MARKERS this is what catches it. A guard with no current
#: instance is documented as such rather than quietly left to look load-
#: bearing.
TIME_DISQUALIFIERS: Tuple[str, ...] = ("每年",)

#: Limits. Both sets score 0/10 on the frozen pilot, which is why the
#: boundary table is empty and why two of the four declared boundary types
#: are withheld from the schema.
TIME_LIMIT_MARKERS: Tuple[str, ...] = (
    "截至", "止于", "不迟于", "以前", "之后", "之前", "仅在", "限于")
ACTOR_LIMIT_MARKERS: Tuple[str, ...] = (
    "仅限", "只限", "不包括", "不适用于", "除外", "仅对", "仅在")

#: Condition factors the wider proposal named that have no extractor. Kept as
#: named constants so widening the schema later is a deliberate edit rather
#: than an accident.
NOT_YET_EXTRACTABLE_CONDITION_TYPES = ("STATE", "LOCATION", "PREREQUISITE")

#: Boundary types declared by the proposal but withheld for the same reason.
NOT_YET_EXTRACTABLE_BOUNDARY_TYPES = ("SCOPE_LIMIT", "EXCEPTION")


class ConditionType(str, Enum):
    ACTOR = "ACTOR"
    TIME = "TIME"


class BoundaryType(str, Enum):
    TIME_LIMIT = "TIME_LIMIT"
    ACTOR_LIMIT = "ACTOR_LIMIT"


class CandidateStatus(str, Enum):
    """No VERIFIED. A reading of a span is not a verdict about the world."""

    GENERATED = "GENERATED"
    SUPPORTED = "SUPPORTED"
    REJECTED = "REJECTED"


class ConditionBoundaryViolation(Exception):
    """Raised on a forbidden condition/boundary operation."""


class ConditionBoundaryPrecondition(Exception):
    """A candidate may not be written as given; nothing was written."""


# ── identity ─────────────────────────────────────────────────────────────────

def condition_id(knowledge_unit_id: str, condition_type: str,
                 statement: str) -> str:
    """`kcc_<sha256(...)[:12]>` — content-derived, never random."""
    digest = hashlib.sha256(
        f"{knowledge_unit_id}|{condition_type}|{statement}"
        f"|{CONDITION_BOUNDARY_VERSION}".encode("utf-8")).hexdigest()
    return f"kcc_{digest[:12]}"


def condition_hash(knowledge_unit_id: str, condition_type: str,
                   statement: str, evidence_ids: Sequence[str]) -> str:
    evidence = "|".join(sorted(evidence_ids))
    digest = hashlib.sha256(
        f"{knowledge_unit_id}|{condition_type}|{statement}|{evidence}"
        f"|{CONDITION_BOUNDARY_VERSION}".encode("utf-8")).hexdigest()
    return f"kch_{digest[:16]}"


def boundary_id(knowledge_unit_id: str, boundary_type: str,
                statement: str) -> str:
    digest = hashlib.sha256(
        f"{knowledge_unit_id}|{boundary_type}|{statement}"
        f"|{CONDITION_BOUNDARY_VERSION}".encode("utf-8")).hexdigest()
    return f"kbc_{digest[:12]}"


def boundary_hash(knowledge_unit_id: str, boundary_type: str,
                  statement: str, evidence_ids: Sequence[str]) -> str:
    evidence = "|".join(sorted(evidence_ids))
    digest = hashlib.sha256(
        f"{knowledge_unit_id}|{boundary_type}|{statement}|{evidence}"
        f"|{CONDITION_BOUNDARY_VERSION}".encode("utf-8")).hexdigest()
    return f"kbh_{digest[:16]}"


# ── rows ─────────────────────────────────────────────────────────────────────

@dataclass
class ConditionCandidate:
    id: str
    knowledge_unit_id: str
    condition_type: str
    statement: str
    evidence_ids: List[str] = field(default_factory=list)
    extractor_version: str = CONDITION_BOUNDARY_VERSION
    confidence: float = 0.0
    condition_hash: str = ""
    status: str = CandidateStatus.GENERATED.value
    created_at: str = CONDITION_BOUNDARY_VERSION


@dataclass
class BoundaryCandidate:
    id: str
    knowledge_unit_id: str
    boundary_type: str
    statement: str
    evidence_ids: List[str] = field(default_factory=list)
    extractor_version: str = CONDITION_BOUNDARY_VERSION
    confidence: float = 0.0
    boundary_hash: str = ""
    status: str = CandidateStatus.GENERATED.value
    created_at: str = CONDITION_BOUNDARY_VERSION


#: `created_at` is named so the emitter can substitute NOW() for it. The
#: column is NOT NULL with no default, so omitting it from the list made
#: every insert fail against a real database — the substitution above it was
#: dead code until the column was named.
CONDITION_COLUMNS = ("id", "knowledge_unit_id", "condition_type", "statement",
                     "evidence_ids", "extractor_version", "confidence",
                     "condition_hash", "status", "created_at")

BOUNDARY_COLUMNS = ("id", "knowledge_unit_id", "boundary_type", "statement",
                    "evidence_ids", "extractor_version", "confidence",
                    "boundary_hash", "status", "created_at")


# ── the guard ────────────────────────────────────────────────────────────────

def condition_constraint_boundary_guard(statement: str, kind: str) -> None:
    """Refuse a statement that is not a checkable qualifier.

    `kind` is `"condition"` or `"boundary"`. Both take the same rules, and
    the asymmetry that matters is with **constraint**, not between these
    two: a constraint candidate is where "usually" belongs, and this guard
    is never applied to one.

        Condition : 事实成立条件   — a fact's precondition
        Constraint: 规则限制       — a stated rule or limit

    An example from the frozen proposal, kept as the worked case:

        Condition : 贷款双方必须存在债务关系
        Constraint: 利率不得超过33.333%

    The first states when a fact holds; the second states a rule. A
    hedged qualifier belongs to neither as a condition, and a causal
    connective belongs to the mechanism layer, which does not exist.
    """
    if kind not in {"condition", "boundary"}:
        raise ConditionBoundaryPrecondition(f"unknown guard kind {kind}")
    text = statement or ""
    if not text.strip():
        raise ConditionBoundaryPrecondition(
            f"a {kind} statement may not be empty.")
    for word in TENDENCY_WORDS:
        if word in text:
            raise ConditionBoundaryPrecondition(
                f"a {kind} may not contain 「{word}」: that is a tendency, "
                "which belongs to a constraint candidate.")
    for word in CAUSAL_WORDS:
        if word in text:
            raise ConditionBoundaryPrecondition(
                f"a {kind} may not contain 「{word}」: that is a causal claim, "
                "which belongs to the mechanism layer.")


# ── extraction ───────────────────────────────────────────────────────────────

def clause_around(span: str, marker: str) -> str:
    """The clause of `span` containing `marker`, cut at clause delimiters.

    Deterministic and local: the nearest delimiter on each side. Verbatim by
    construction, which is what lets a gate assert every extracted statement
    is a substring of the span it claims to come from.
    """
    index = span.find(marker)
    if index < 0:
        return ""
    start = index
    while start > 0 and span[start - 1] not in CLAUSE_DELIMITERS:
        start -= 1
    end = index + len(marker)
    while end < len(span) and span[end] not in CLAUSE_DELIMITERS:
        end += 1
    return span[start:end].strip()


def anchor_confidence(span: str, marker: str) -> float:
    """How unambiguous the anchor is, from 1.0 down to 0.5.

    One occurrence in the span -> 1.0. More than one -> the clause cannot be
    attributed to a single place, and confidence falls by 0.1 per extra
    occurrence. It is a measurement of *anchor ambiguity* and nothing else;
    it is not a probability that the reading is right.
    """
    occurrences = span.count(marker)
    if occurrences <= 1:
        return 1.0
    return max(0.5, round(1.0 - 0.1 * (occurrences - 1), 4))


class ConditionBoundaryExtractor:
    """Reads frozen units and yields candidates. Writes nothing but its own
    two tables.

    Holds no reference to a verification pipeline's transition, to a
    candidate store's mutator, or to a unit's fields other than its span and
    its id.
    """

    EXTRACTOR_VERSION = CONDITION_BOUNDARY_VERSION

    def __init__(self, ingestion_pipeline):
        self.store = ingestion_pipeline.store

    # ── input ───────────────────────────────────────────────────────────────

    def evidence_of(self, unit) -> List[str]:
        """Evidence ids the unit is anchored to, via its own chain."""
        candidate = self.store.ku_candidates.get(unit.candidate_id)
        if candidate is None:
            return []
        return [candidate.evidence_id]

    def span_of(self, unit) -> str:
        """The anchored span. The only text this module ever reads."""
        frozen = getattr(unit, "canonical_text", "") or ""
        return frozen.strip()

    # ── conditions ──────────────────────────────────────────────────────────

    def extract(self, unit) -> Tuple[List[ConditionCandidate],
                                     List[BoundaryCandidate]]:
        """`FrozenKnowledgeUnit` -> (conditions, boundaries).

        Read-only with respect to the unit: it is opened, its span read once,
        and never written.
        """
        span = self.span_of(unit)
        if not span:
            return [], []
        evidence = self.evidence_of(unit)
        return (self.conditions_for(unit.id, span, evidence),
                self.boundaries_for(unit.id, span, evidence))

    def conditions_for(self, knowledge_unit_id: str, span: str,
                       evidence_ids: Sequence[str]) -> List[ConditionCandidate]:
        """Conditions for one span, deduplicated by statement.

        A clause is recorded once, not once per factor that matches it. In
        "古代巴比伦王朝的第一个国王汉谟拉比" both an ACTOR marker and a TIME
        marker land in the same clause; recording that text twice under two
        type values would inflate the count and read as two findings. The
        factor kept is the one that attributes the clause most specifically,
        which falls out of the loop order: ACTOR is visited before TIME.
        """
        found: Dict[str, ConditionCandidate] = {}
        for kind, markers, disqualifiers in (
                (ConditionType.ACTOR, ACTOR_MARKERS, ACTOR_DISQUALIFIERS),
                (ConditionType.TIME, TIME_MARKERS, TIME_DISQUALIFIERS)):
            for marker in markers:
                if any(bad in marker for bad in disqualifiers):
                    continue
                if marker not in span:
                    continue
                statement = clause_around(span, marker)
                if not statement:
                    continue
                try:
                    condition_constraint_boundary_guard(statement, "condition")
                except ConditionBoundaryPrecondition:
                    continue
                candidate = ConditionCandidate(
                    id=condition_id(knowledge_unit_id, kind.value, statement),
                    knowledge_unit_id=knowledge_unit_id,
                    condition_type=kind.value,
                    statement=statement,
                    evidence_ids=list(evidence_ids),
                    confidence=anchor_confidence(span, marker),
                )
                candidate.condition_hash = condition_hash(
                    knowledge_unit_id, kind.value, statement, evidence_ids)
                found.setdefault(statement, candidate)
        return [found[key] for key in sorted(found)]

    # ── boundaries ──────────────────────────────────────────────────────────

    def boundaries_for(self, knowledge_unit_id: str, span: str,
                       evidence_ids: Sequence[str]
                       ) -> List[BoundaryCandidate]:
        """Boundaries for one span, deduplicated by statement.

        Same rule as conditions: TIME_LIMIT is visited before ACTOR_LIMIT,
        so a clause matching both is recorded once.
        """
        found: Dict[str, BoundaryCandidate] = {}
        for kind, markers in ((BoundaryType.TIME_LIMIT, TIME_LIMIT_MARKERS),
                              (BoundaryType.ACTOR_LIMIT,
                               ACTOR_LIMIT_MARKERS)):
            for marker in markers:
                if marker not in span:
                    continue
                statement = clause_around(span, marker)
                if not statement:
                    continue
                try:
                    condition_constraint_boundary_guard(statement, "boundary")
                except ConditionBoundaryPrecondition:
                    continue
                candidate = BoundaryCandidate(
                    id=boundary_id(knowledge_unit_id, kind.value, statement),
                    knowledge_unit_id=knowledge_unit_id,
                    boundary_type=kind.value,
                    statement=statement,
                    evidence_ids=list(evidence_ids),
                    confidence=anchor_confidence(span, marker),
                )
                candidate.boundary_hash = boundary_hash(
                    knowledge_unit_id, kind.value, statement, evidence_ids)
                found.setdefault(statement, candidate)
        return [found[key] for key in sorted(found)]

    # ── whole run ───────────────────────────────────────────────────────────

    def extract_run(self, units: Sequence) -> Dict[str, object]:
        """Every candidate for a set of units, in a stable order.

        Deterministic: units are visited in sorted order and each unit's
        candidates come back sorted by (type, statement), so two runs over the
        same rows produce the same sequence.
        """
        conditions: List[ConditionCandidate] = []
        boundaries: List[BoundaryCandidate] = []
        for unit in sorted(units, key=lambda u: u.id):
            unit_conditions, unit_boundaries = self.extract(unit)
            conditions.extend(unit_conditions)
            boundaries.extend(unit_boundaries)
        return {"conditions": conditions, "boundaries": boundaries}


# ── durability ───────────────────────────────────────────────────────────────

CONDITION_BOUNDARY_TABLES = ("ku_condition_candidate",
                             "ku_boundary_candidate")

_ROW_TYPES: Dict[str, type] = {
    "ku_condition_candidate": ConditionCandidate,
    "ku_boundary_candidate": BoundaryCandidate,
}

_ROW_BUCKETS: Dict[str, str] = {
    "ku_condition_candidate": "conditions",
    "ku_boundary_candidate": "boundaries",
}


class ConditionBoundarySink(IdentitySink):
    """Every sink up to P6, plus the two candidate tables.

    Inherits rather than reimplements so the staging discipline stays in one
    place, and so a candidate cannot land without its unit and its identity
    row in the same store. One sink also means one transaction can carry the
    whole chain, which is what a DBA needs to run against staging.
    """

    TABLES = IDENTITY_TABLES + CONDITION_BOUNDARY_TABLES
    ROW_TYPES = {**IdentitySink.ROW_TYPES, **_ROW_TYPES}
    ROW_BUCKETS = {**IdentitySink.ROW_BUCKETS, **_ROW_BUCKETS}

    def __init__(self, fail_after: Optional[int] = None):
        super().__init__(fail_after=fail_after)
        self.conditions: Dict[str, ConditionCandidate] = {}
        self.boundaries: Dict[str, BoundaryCandidate] = {}

    def commit(self, pending: Sequence[Tuple[str, Dict]]) -> None:
        staged: Dict[str, Dict[str, Dict]] = {
            table: {} for table in self.TABLES}
        for index, (table, row) in enumerate(pending):
            if self.fail_after is not None and index >= self.fail_after:
                self.rollbacks += 1
                raise RuntimeError(f"injected failure at write {index} ({table})")
            if table not in staged:
                raise ConditionBoundaryViolation(f"unknown table {table}")
            staged[table][row["id"]] = row
        for table, rows in staged.items():
            row_type = self.ROW_TYPES[table]
            getattr(self, self.ROW_BUCKETS[table]).update(
                {key: row_type(**value) for key, value in rows.items()})
        self.commits += 1

    def reload(self) -> Dict[str, object]:
        reloaded = super().reload()
        reloaded["ku_condition_candidate"] = dict(self.conditions)
        reloaded["ku_boundary_candidate"] = dict(self.boundaries)
        return reloaded


class ConditionBoundaryWriter:
    """Appends candidates. Holds no path to anything upstream."""

    def __init__(self, ingestion_pipeline, sink: ConditionBoundarySink):
        self.store = ingestion_pipeline.store
        self.extractor = ConditionBoundaryExtractor(ingestion_pipeline)
        self.sink = sink

    def preconditions(self, candidate) -> Tuple[bool, List[str]]:
        """Everything that must hold, checked before the transaction opens."""
        failed: List[str] = []
        if candidate.knowledge_unit_id not in self.sink.units:
            failed.append("NO_SUCH_KNOWLEDGE_UNIT")
        if not candidate.statement.strip():
            failed.append("EMPTY_STATEMENT")
        if not candidate.evidence_ids:
            failed.append("NO_EVIDENCE")
        else:
            for evidence_id in candidate.evidence_ids:
                if evidence_id not in self.store.evidence:
                    failed.append("ORPHAN_EVIDENCE")
        try:
            condition_constraint_boundary_guard(
                candidate.statement,
                "condition" if isinstance(candidate, ConditionCandidate)
                else "boundary")
        except ConditionBoundaryPrecondition as error:
            failed.append(f"GUARD:{error}")
        return not failed, failed

    def write(self, candidate) -> ConditionBoundaryViolation:
        """One candidate, atomically. Idempotent on content."""
        ok, failed = self.preconditions(candidate)
        if not ok:
            raise ConditionBoundaryPrecondition(
                f"{candidate.id} may not be written: {', '.join(failed)}.")
        existing = self.sink.conditions.get(candidate.id) \
            if isinstance(candidate, ConditionCandidate) \
            else self.sink.boundaries.get(candidate.id)
        if existing is not None:
            return None
        table = ("ku_condition_candidate"
                 if isinstance(candidate, ConditionCandidate)
                 else "ku_boundary_candidate")
        try:
            with FreezeTransaction(self.sink) as tx:
                tx.write(table, dict(candidate.__dict__))
        except Exception as error:
            raise ConditionBoundaryViolation(
                f"{candidate.id} was not written: {error}") from error
        return None

    def write_all(self, extracted: Dict[str, object]) -> Dict[str, int]:
        written = {"conditions": 0, "boundaries": 0}
        for candidate in extracted["conditions"]:
            self.write(candidate)
            if candidate.id in self.sink.conditions:
                written["conditions"] += 1
        for candidate in extracted["boundaries"]:
            self.write(candidate)
            if candidate.id in self.sink.boundaries:
                written["boundaries"] += 1
        return written

    # ── immutability ────────────────────────────────────────────────────────

    def update_candidate(self, candidate_id: str, **changes) -> None:
        raise ConditionBoundaryViolation(
            f"{candidate_id} cannot be updated; a condition is an appended "
            "reading of a span, and a different reading is a new row.")

    def delete_candidate(self, candidate_id: str) -> None:
        raise ConditionBoundaryViolation(
            f"{candidate_id} cannot be deleted; a candidate is the record "
            "that this span was read this way.")

    def merge_candidates(self, *candidate_ids: str) -> None:
        raise ConditionBoundaryViolation(
            "A仓 has no authority to merge candidates; deciding two readings "
            "are the same reading is a semantic judgement.")

    def promote(self, candidate_id: str) -> None:
        raise ConditionBoundaryViolation(
            "A condition has no VERIFIED state; A仓 does not declare an "
            "interpretation true.")

    def update_verification(self, *args, **kwargs) -> None:
        raise ConditionBoundaryViolation(
            "This layer never touches a verification. A condition is applied "
            "after a unit is frozen.")

    # ── queries ─────────────────────────────────────────────────────────────

    def orphan_conditions(self) -> List[str]:
        return sorted(row.id for row in self.sink.conditions.values()
                      if row.knowledge_unit_id not in self.sink.units
                      or any(evidence_id not in self.store.evidence
                             for evidence_id in row.evidence_ids))

    def orphan_boundaries(self) -> List[str]:
        return sorted(row.id for row in self.sink.boundaries.values()
                      if row.knowledge_unit_id not in self.sink.units
                      or any(evidence_id not in self.store.evidence
                             for evidence_id in row.evidence_ids))

    def misanchored_statements(self) -> List[str]:
        """Candidates whose statement is not a verbatim substring of the span.

        The one check that makes "source-grounded" mean something: if this is
        non-empty, the layer has started writing prose instead of quoting.
        """
        wrong: List[str] = []
        for row in list(self.sink.conditions.values()) + \
                list(self.sink.boundaries.values()):
            unit = self.sink.units.get(row.knowledge_unit_id)
            span = (getattr(unit, "canonical_text", "") or "") if unit else ""
            if row.statement not in span:
                wrong.append(row.id)
        return sorted(wrong)

    def duplicate_candidates(self) -> List[str]:
        seen: Dict[str, int] = {}
        for row in list(self.sink.conditions.values()) + \
                list(self.sink.boundaries.values()):
            key = f"{row.knowledge_unit_id}|{row.statement}"
            seen[key] = seen.get(key, 0) + 1
        return sorted(k for k, v in seen.items() if v > 1)


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


def emit_condition_boundary_sql(units, conditions, boundaries) -> str:
    """Both candidate tables as one transaction.

    `knowledge_unit` rows are expected to exist already — this layer never
    writes them. Every statement is ON CONFLICT DO NOTHING, so the file is
    safe to run twice and a replay writes nothing.
    """
    lines = ["BEGIN;", "SET search_path TO stratum, public;"]
    for key in sorted(conditions):
        row = dict(conditions[key].__dict__)
        columns = ",".join(CONDITION_COLUMNS)
        lines.append(
            f"INSERT INTO ku_condition_candidate ({columns}) VALUES "
            f"({','.join('NOW()' if c == 'created_at' else _literal(row.get(c)) for c in CONDITION_COLUMNS)}) "
            f"ON CONFLICT (condition_hash) DO NOTHING;")
    for key in sorted(boundaries):
        row = dict(boundaries[key].__dict__)
        columns = ",".join(BOUNDARY_COLUMNS)
        lines.append(
            f"INSERT INTO ku_boundary_candidate ({columns}) VALUES "
            f"({','.join('NOW()' if c == 'created_at' else _literal(row.get(c)) for c in BOUNDARY_COLUMNS)}) "
            f"ON CONFLICT (boundary_hash) DO NOTHING;")
    lines.append("COMMIT;")
    return "\n".join(lines) + "\n"


# ── measured notes ───────────────────────────────────────────────────────────

#: What was counted on the frozen pilot (Chapter 1, 10 current units), and why
#: each list is shaped the way it is. Kept in the module rather than only in
#: the report, because these lists are corpus-derived and the next book will
#: change them.
#:
#:   P3 ACTOR_MARKERS 10 markers; 5/10 spans hit.
#:     法典 withdrawn: it is the object of 修改 / 取消 ("更多的都是模仿《汉谟拉比
#:     法典》"), not the agent. Harmless as a boolean slot, wrong as a
#:     statement.
#:   P3 TIME_MARKERS 7 markers; 4/10 spans hit — 2 of them on the bare 年.
#:     年 withdrawn: "贷款的利息被限制为不得超过每年8.333%" states a rate basis,
#:     not a temporal condition. 每年 added to the disqualifiers for the same
#:     reason.
#:   After narrowing: ACTOR 4 units, TIME 2 units, no known false positive.
#:   Boundary markers 0/10 spans — hence an empty boundary table, reported
#:     rather than engineered around.
#:
#: These are expected to need revision on the next book. A marker list fitted
#: to ten spans is a starting point, and a layer whose vocabulary is a claim
#: about all books would be exactly the kind of unfalsifiable assumption
#: this repository exists to avoid.
MARKER_NOTES = {
    "actor_markers": len(ACTOR_MARKERS),
    "actor_disqualified": len(ACTOR_DISQUALIFIERS),
    "time_markers": len(TIME_MARKERS),
    "time_disqualified": len(TIME_DISQUALIFIERS),
    "condition_types_declared": len(ConditionType),
    "boundary_types_declared": len(BoundaryType),
    "condition_types_withheld": len(NOT_YET_EXTRACTABLE_CONDITION_TYPES),
    "boundary_types_withheld": len(NOT_YET_EXTRACTABLE_BOUNDARY_TYPES),
}
