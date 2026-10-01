"""A Repository P5.2 — relation candidate.

    Frozen KU (P4/P4.1) ──> relation_candidate ──> evidence (left and right)

A relation here is a **candidate**: two frozen knowledge units of one book, in
an order the caller declares, each carrying its own evidence. It records a
comparison the book makes between two of its own rows.

Two boundaries are kept apart, because conflating them is the failure mode this
stage could have:

- **A relation is a comparison.** PRECEDES is one: left sits earlier in the
  book than right, and that ordering is checkable against the locator the book
  supplies.
- **A relation is not a judgement.** SUPPORTS, CONTRASTS and DEPENDS_ON are
  deferred out of 079 entirely, not merely unused — see `DEFERRED_TYPES` and
  the migration header. 075's own comment already refused this class of value
  when it declined to add SAME_MEANING or TENSION: deciding whether two units
  agree or clash is a semantic judgement, and A仓 has no authority to make it.

The frozen `ku_relation` from 075 is left alone. This is a second, narrower
layer: 075 stores undirected machine-comparable facts about two rows with no
evidence columns of its own; this stores directed PRECEDES with evidence on both
sides and a source version. The vocabularies are disjoint, so neither table is
ever a row of the other.

Identity is derived in two steps, in this order:

    1. relation_id  = f(relation_type, source_version_id, left, right,
                        extractor_version)
    2. relation_hash = f(relation_type, source_version_id, left, right,
                         sorted(left evidence), sorted(right evidence),
                         extractor_version)

`relation_id` excludes evidence and the hash includes it, matching the P5.0
pattern and the review spec: the id names the relation, the hash names the
relation *as evidenced*. The same pair with different evidence is therefore a
different relation, which is the behaviour §REPLAY asks for.

Both evidence arrays are sorted before hashing, so re-reading the same book in a
different traversal order produces the same hash. Order within a set of evidence
ids for one side is not a claim about anything.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Sequence, Tuple

from .identity import IdentitySink
from .persistence import FreezeTransaction


RELATION_VERSION = "a-p5-2-v0.2"

#: A real extraction. Never used by the pilot.
EXTRACTOR_VERSION = "relation_extractor_v1"

#: A relation declared to exercise the persistence contract. Not an extraction
#: result, and not evidence that the extractor works. A gate asserts the two are
#: distinguishable, so a pilot row can never be read as a finding — and the
#: value is inside relation_hash, so an extractor run over the same two units
#: and evidence cannot be swallowed as a replay of the pilot.
PILOT_DECLARED_VERSION = "pilot-declared"

#: The one relation type A仓 is authorised to record.
#:
#: PRECEDES is a comparison between two locators the book itself supplies, the
#: same grade as 075's SAME_SOURCE_SPAN.
RELATION_TYPES = ("PRECEDES",)

#: Refused by design, not by omission. 075 declined to add SAME_MEANING or
#: TENSION with this reasoning, and CONTRASTS is that judgement renamed:
#:
#:   "deciding either is a semantic judgement: it belongs to B仓, and A仓 has no
#:    authority to make it."
#:
#: Kept as a named list so the refusal is a testable fact rather than an
#: absence, and so a future stage has to argue with these three by name.
DEFERRED_TYPES = ("SUPPORTS", "CONTRASTS", "DEPENDS_ON")

#: Field names a relation may not grow. The first four are the review spec's
#: artifact ban; the rest are the words that would turn a recorded comparison
#: into a recorded judgement.
RELATION_BANNED_FIELDS = ("meaning", "interpretation", "explanation",
                          "truth_score", "cause", "significance", "contrast",
                          "implies", "proves", "validates")


class RelationType(str, Enum):
    PRECEDES = "PRECEDES"


class RelationStatus(str, Enum):
    """No VERIFIED, no CONFIRMED.

    `VERIFIED` is the success value of `ku_verification.verification_status`,
    and a relation between two rows is not a verified proposition. `CONFIRMED`
    would be a second word for that same fact.
    """

    GENERATED = "GENERATED"
    SUPPORTED = "SUPPORTED"
    REJECTED = "REJECTED"


#: Both SUPPORTED and REJECTED are final. v0.2's arrow diagram permitted
#: SUPPORTED -> REJECTED; that is refused here, matching v1.0 §9 and the rule
#: 077 and 078 freeze against. A仓 corrects by appending a new relation under a
#: new hash, never by downgrading one in place.
LEGAL_STATUS_TRANSITIONS: Dict[RelationStatus, frozenset] = {
    RelationStatus.GENERATED: frozenset({RelationStatus.SUPPORTED,
                                         RelationStatus.REJECTED}),
    RelationStatus.SUPPORTED: frozenset(),
    RelationStatus.REJECTED: frozenset(),
}


class RelationViolation(Exception):
    """Raised on a forbidden relation operation."""


class RelationPrecondition(Exception):
    """A relation may not be written as given; nothing was written."""


# ── identity ─────────────────────────────────────────────────────────────────

def relation_id(relation_type: str, source_version_id: str, left_unit_id: str,
                right_unit_id: str, extractor_version: str) -> str:
    """`rlc_<sha256(...)[:12]>` — step 1.

    No evidence: this is the identity of the *relation*, matching the P5.0
    pattern where `id` excludes evidence and the hash includes it.
    """
    digest = hashlib.sha256(
        f"{relation_type}|{source_version_id}|{left_unit_id}|{right_unit_id}"
        f"|{extractor_version}".encode("utf-8")).hexdigest()
    return f"rlc_{digest[:12]}"


def relation_hash(relation_type: str, source_version_id: str,
                  left_unit_id: str, right_unit_id: str,
                  left_evidence_ids: Sequence[str],
                  right_evidence_ids: Sequence[str],
                  extractor_version: str) -> str:
    """`rlh_<sha256(...)[:16]>` — step 2, the replay identity.

    The v0.2 formula, with `extractor_version` appended. Each side's evidence is
    sorted independently, so the two sides are distinguishable but traversal
    order within a side is not a claim.

    Order is not normalised away: left and right keep their positions. PRECEDES
    is directed, so A-precedes-B and B-precedes-A are different relations, and
    swapping the sides must produce a different hash.
    """
    left = "|".join(sorted(left_evidence_ids))
    right = "|".join(sorted(right_evidence_ids))
    digest = hashlib.sha256(
        f"{relation_type}|{source_version_id}|{left_unit_id}|{right_unit_id}"
        f"|{left}|{right}|{extractor_version}".encode("utf-8")).hexdigest()
    return f"rlh_{digest[:16]}"


# ── rows ─────────────────────────────────────────────────────────────────────

@dataclass
class RelationCandidate:
    id: str
    relation_type: str
    source_version_id: str
    left_unit_id: str
    right_unit_id: str
    left_evidence_ids: List[str] = field(default_factory=list)
    right_evidence_ids: List[str] = field(default_factory=list)
    relation_hash: str = ""
    status: str = RelationStatus.GENERATED.value
    extractor_version: str = EXTRACTOR_VERSION
    created_at: str = RELATION_VERSION


RELATION_COLUMNS = ("id", "relation_type", "source_version_id", "left_unit_id",
                    "right_unit_id", "left_evidence_ids", "right_evidence_ids",
                    "status", "relation_hash", "extractor_version",
                    "created_at")

#: 079 gives created_at DEFAULT now(), unlike 078 which had to write NOW() into
#: every statement. The insert therefore omits the column: the database stamps
#: it, so a replay cannot carry a timestamp that disagrees with the stored row,
#: and a hand-written INSERT cannot fail on a forgotten column.
RELATION_INSERT_COLUMNS = tuple(c for c in RELATION_COLUMNS
                                if c != "created_at")


# ── the relation ─────────────────────────────────────────────────────────────

class RelationBuilder:
    """Composes a relation out of two frozen units of one book.

    Takes an explicit `(left_unit_id, right_unit_id)` pair. There is no sorting
    and no inference: the caller states which unit comes first, and this refuses
    anything that is not a well-formed PRECEDES over two units it can trace to
    evidence of the same book.
    """

    def __init__(self, ingestion_pipeline, units: Optional[Dict] = None):
        """`units` is the durable unit table, keyed by `knowledge_unit.id`.

        Needed because a relation is given canonical unit ids while the
        candidate table is keyed by candidate id: unit -> candidate -> evidence.
        Without the mapping the lookup returns nothing and both sides look
        un-evidenced.
        """
        self.store = ingestion_pipeline.store
        self.units = units if units is not None else {}

    def build(self, source_version_id: str, left_unit_id: str,
              right_unit_id: str, relation_type: str,
              extractor_version: str) -> RelationCandidate:
        if relation_type not in RELATION_TYPES:
            raise RelationPrecondition(
                f"{relation_type} is not a relation type A仓 may record; "
                f"only {', '.join(RELATION_TYPES)} is in 079, and "
                f"{', '.join(DEFERRED_TYPES)} are deferred because deciding "
                "them is a B仓 judgement.")
        if left_unit_id == right_unit_id:
            raise RelationPrecondition(
                "a unit cannot precede itself; PRECEDES needs two units.")
        left = self.evidence_of(left_unit_id)
        right = self.evidence_of(right_unit_id)
        for side, unit_id, evidence in (("left", left_unit_id, left),
                                        ("right", right_unit_id, right)):
            if not evidence:
                raise RelationPrecondition(
                    f"{side} unit {unit_id} has no evidence; both sides of a "
                    "relation must be evidence-linked.")
        return RelationCandidate(
            id=relation_id(relation_type, source_version_id, left_unit_id,
                           right_unit_id, extractor_version),
            relation_type=relation_type,
            source_version_id=source_version_id,
            left_unit_id=left_unit_id,
            right_unit_id=right_unit_id,
            left_evidence_ids=left,
            right_evidence_ids=right,
            relation_hash=relation_hash(
                relation_type, source_version_id, left_unit_id, right_unit_id,
                left, right, extractor_version),
            extractor_version=extractor_version,
        )

    def candidate_of(self, unit_id: str):
        """The candidate behind a durable unit id, or None."""
        unit = self.units.get(unit_id)
        if unit is None:
            return None
        return self.store.ku_candidates.get(unit.candidate_id)

    def evidence_of(self, unit_id: str) -> List[str]:
        """Evidence a frozen unit is anchored to, via its own chain.

        unit -> candidate -> evidence, the same path A仓's other stages walk.
        An id that is not a durable unit resolves to nothing, which is how a
        relation naming an absent unit is refused.
        """
        candidate = self.candidate_of(unit_id)
        if candidate is None:
            return []
        return [candidate.evidence_id]

    def locator_of(self, unit_id: str) -> Optional[Tuple[int, str]]:
        """`(page, locator)` for a unit, or None if it cannot be placed.

        This is what PRECEDES is measured against. The key is total: the locator
        dict is serialised with sorted keys so two evidence rows on the same
        page are still ordered deterministically rather than comparing equal by
        accident.

        The field is `locator` on the in-memory row and `location` in the
        database — the same value under two names across the 070 boundary — so
        both are accepted and a rename in either layer cannot silently turn
        every relation into an unorderable one.
        """
        evidence_ids = self.evidence_of(unit_id)
        if not evidence_ids:
            return None
        evidence = self.store.evidence.get(evidence_ids[0])
        if evidence is None:
            return None
        locator = getattr(evidence, "locator", None)
        if locator is None:
            locator = getattr(evidence, "location", None)
        return (evidence.page_number,
                json.dumps(locator or {}, sort_keys=True, ensure_ascii=False))


def precedes_in_book(builder: RelationBuilder, left_unit_id: str,
                     right_unit_id: str) -> bool:
    """Does left actually sit earlier in the book than right?

    Not expressible as a CHECK: ordering needs reading_evidence, and PostgreSQL
    refuses a CHECK that reads another table ("cannot use subquery in check
    constraint"). This is the service gate, recorded as a known limitation.
    """
    left = builder.locator_of(left_unit_id)
    right = builder.locator_of(right_unit_id)
    if left is None or right is None:
        return False
    return left < right


def transition(candidate: RelationCandidate, target: RelationStatus) -> None:
    """The only way a relation's status changes.

    Both SUPPORTED and REJECTED are final, so a supported relation is final and
    a correction is a new relation under a new hash.
    """
    current = RelationStatus(candidate.status)
    if target not in LEGAL_STATUS_TRANSITIONS[current]:
        raise RelationViolation(
            f"{current.value} -> {target.value} is not a legal relation "
            "transition; a supported relation is final and A仓 corrects by "
            "appending a new relation.")
    candidate.status = target.value


# ── durability ───────────────────────────────────────────────────────────────

RELATION_TABLES = ("relation_candidate",)

_RELATION_ROW_TYPES: Dict[str, type] = {
    "relation_candidate": RelationCandidate,
}

#: The bucket is NOT called `relations`. IdentitySink already maps 075's
#: `ku_relation` to a bucket by that name, and two tables sharing one bucket
#: would put 075's frozen Relation rows and this stage's RelationCandidate rows
#: in the same dict — a collision that reads as an AttributeError much later,
#: on a report, with no hint that a name was shared.
_RELATION_BUCKETS: Dict[str, str] = {
    "relation_candidate": "relation_candidates",
}


class RelationSink(IdentitySink):
    """Every sink up to P6, plus the relation table.

    Inherits so the staging discipline stays in one place. One sink means one
    transaction can carry the whole relation, which is what the review spec's
    transaction contract needs.
    """

    TABLES = IdentitySink.TABLES + RELATION_TABLES
    ROW_TYPES = {**IdentitySink.ROW_TYPES, **_RELATION_ROW_TYPES}
    ROW_BUCKETS = {**IdentitySink.ROW_BUCKETS, **_RELATION_BUCKETS}

    def __init__(self, fail_after: Optional[int] = None):
        super().__init__(fail_after=fail_after)
        self.relation_candidates: Dict[str, RelationCandidate] = {}

    def commit(self, pending: Sequence[Tuple[str, Dict]]) -> None:
        staged: Dict[str, Dict[str, Dict]] = {
            table: {} for table in self.TABLES}
        for index, (table, row) in enumerate(pending):
            if self.fail_after is not None and index >= self.fail_after:
                self.rollbacks += 1
                raise RuntimeError(f"injected failure at write {index} ({table})")
            if table not in staged:
                raise RelationViolation(f"unknown table {table}")
            staged[table][row["id"]] = row
        for table, rows in staged.items():
            row_type = self.ROW_TYPES[table]
            getattr(self, self.ROW_BUCKETS[table]).update(
                {key: row_type(**value) for key, value in rows.items()})
        self.commits += 1

    def reload(self) -> Dict[str, object]:
        reloaded = super().reload()
        reloaded["relation_candidate"] = dict(self.relation_candidates)
        return reloaded


class RelationWriter:
    """Appends relations. Holds no path to anything upstream."""

    def __init__(self, ingestion_pipeline, sink: RelationSink):
        self.store = ingestion_pipeline.store
        self.builder = RelationBuilder(ingestion_pipeline, sink.units)
        self.sink = sink

    # ── gates ──────────────────────────────────────────────────────────────

    def preconditions(self, candidate: RelationCandidate
                      ) -> Tuple[bool, List[str]]:
        """Everything that must hold, checked before the transaction opens."""
        failed: List[str] = []
        if candidate.relation_type not in RELATION_TYPES:
            failed.append("RELATION_TYPE_NOT_AUTHORISED")
        if candidate.source_version_id not in self.store.source_versions:
            failed.append("NO_SUCH_SOURCE_VERSION")
        if not candidate.left_evidence_ids:
            failed.append("NO_LEFT_EVIDENCE")
        if not candidate.right_evidence_ids:
            failed.append("NO_RIGHT_EVIDENCE")
        if candidate.left_unit_id == candidate.right_unit_id:
            failed.append("SELF_RELATION")
        if not self._same_source(candidate):
            failed.append("CROSS_SOURCE_VERSION")
        if not self._evidence_same_book(candidate):
            failed.append("CROSS_BOOK_EVIDENCE")
        if not precedes_in_book(self.builder, candidate.left_unit_id,
                                candidate.right_unit_id):
            failed.append("ORDER_NOT_PRECEDING")
        return not failed, failed

    def _same_source(self, candidate: RelationCandidate) -> bool:
        """Both units are of the relation's own source version.

        079 also enforces this declaratively, with two composite foreign keys.
        The check is kept because the composite key needs an index on a frozen
        table and this one does not: belt and braces, and the writer is the
        layer that reports a readable reason.
        """
        for unit_id in (candidate.left_unit_id, candidate.right_unit_id):
            unit = self.sink.units.get(unit_id)
            if unit is None:
                return False
            if unit.source_version_id != candidate.source_version_id:
                return False
        return True

    def _evidence_same_book(self, candidate: RelationCandidate) -> bool:
        """Every evidence id on both sides is real and of the same book.

        `TEXT[]` carries no foreign key, so the CHECK in 079 proves the arrays
        are non-empty and nothing more. This is the layer that proves the
        members exist and belong here.
        """
        for evidence_id in (list(candidate.left_evidence_ids)
                            + list(candidate.right_evidence_ids)):
            evidence = self.store.evidence.get(evidence_id)
            if evidence is None:
                return False
            if evidence.source_version_id != candidate.source_version_id:
                return False
        return True

    # ── persistence ────────────────────────────────────────────────────────

    def write(self, candidate: RelationCandidate) -> RelationCandidate:
        """One relation, in one transaction.

        Returns the **stored** object, not the one passed in. The sink holds a
        copy, so the caller's candidate is consumed and later lifecycle changes
        must go through what this returns — the same copy-on-write shape as
        P4.1's writer, P5.0's and P5.1's. Mutating the original would change an
        object the relation does not see, which is a quiet way to believe a
        transition happened when it did not.
        """
        ok, failed = self.preconditions(candidate)
        if not ok:
            raise RelationPrecondition(
                f"{candidate.id} may not be written: {', '.join(failed)}.")
        if candidate.id in self.sink.relation_candidates:
            # Replay. The same relation is a no-op, not a second copy.
            return self.sink.relation_candidates[candidate.id]
        try:
            with FreezeTransaction(self.sink) as tx:
                tx.write("relation_candidate", dict(candidate.__dict__))
        except Exception as error:
            raise RelationViolation(
                f"{candidate.id} was not written: {error}") from error
        return self.sink.relation_candidates[candidate.id]

    # ── lifecycle ──────────────────────────────────────────────────────────

    def support(self, relation_id_: str) -> RelationCandidate:
        """GENERATED -> SUPPORTED."""
        candidate = self.sink.relation_candidates[relation_id_]
        ok, failed = self.preconditions(candidate)
        if not ok:
            raise RelationPrecondition(
                f"{relation_id_} may not be supported: {', '.join(failed)}.")
        transition(candidate, RelationStatus.SUPPORTED)
        return candidate

    def reject(self, relation_id_: str) -> RelationCandidate:
        """GENERATED -> REJECTED. Not available from SUPPORTED."""
        candidate = self.sink.relation_candidates[relation_id_]
        transition(candidate, RelationStatus.REJECTED)
        return candidate

    # ── immutability ───────────────────────────────────────────────────────

    def update_relation(self, relation_id_: str, **changes) -> None:
        raise RelationViolation(
            f"{relation_id_} cannot be updated; a correction is a new relation "
            "under a new hash, never an edit of this one.")

    def delete_relation(self, relation_id_: str) -> None:
        raise RelationViolation(
            "A relation cannot be deleted. A relation that is no longer "
            "supported is REJECTED, which keeps the record and the reason.")

    def merge_relations(self, *relation_ids: str) -> None:
        raise RelationViolation(
            "A仓 has no authority to merge relations; deciding two comparisons "
            "are one is a semantic judgement.")

    def verify_relation(self, relation_id_: str) -> None:
        raise RelationViolation(
            "A relation has no VERIFIED state; A仓 does not declare a recorded "
            "comparison to be true.")

    def add_semantics(self, *relation_ids: str) -> None:
        raise RelationViolation(
            "A relation records a comparison, not what it means. SUPPORTS, "
            "CONTRASTS and DEPENDS_ON belong to B仓.")

    def update_verification(self, *args, **kwargs) -> None:
        raise RelationViolation("This layer never touches a verification.")

    # ── queries ────────────────────────────────────────────────────────────

    def cross_source_relations(self) -> List[str]:
        wrong: List[str] = []
        for candidate in self.sink.relation_candidates.values():
            if not self._same_source(candidate):
                wrong.append(candidate.id)
        return sorted(set(wrong))

    def single_side_relations(self) -> List[str]:
        """Relations missing evidence on either side.

        The two CHECKs in 079 make this unreachable through SQL; the query
        exists so the gate can read it rather than assume it.
        """
        return sorted(candidate.id for candidate in self.sink.relation_candidates.values()
                      if not candidate.left_evidence_ids
                      or not candidate.right_evidence_ids)

    def self_relations(self) -> List[str]:
        return sorted(candidate.id for candidate in self.sink.relation_candidates.values()
                      if candidate.left_unit_id == candidate.right_unit_id)

    def out_of_order_relations(self) -> List[str]:
        """Relations whose left unit does not sit earlier in the book."""
        return sorted(
            candidate.id for candidate in self.sink.relation_candidates.values()
            if not precedes_in_book(self.builder, candidate.left_unit_id,
                                    candidate.right_unit_id))

    def duplicate_hashes(self) -> List[str]:
        seen: Dict[str, int] = {}
        for candidate in self.sink.relation_candidates.values():
            seen[candidate.relation_hash] = seen.get(
                candidate.relation_hash, 0) + 1
        return sorted(h for h, count in seen.items() if count > 1)

    def deferred_type_rows(self) -> List[str]:
        """Rows carrying a relation type 079 does not authorise.

        Always empty by construction; read by the vocabulary gate.
        """
        return sorted(candidate.id for candidate in self.sink.relation_candidates.values()
                      if candidate.relation_type not in RELATION_TYPES)

    def pilot_rows(self) -> List[str]:
        return sorted(r.id for r in self.sink.relation_candidates.values()
                      if r.extractor_version == PILOT_DECLARED_VERSION)

    def extracted_rows(self) -> List[str]:
        return sorted(r.id for r in self.sink.relation_candidates.values()
                      if r.extractor_version != PILOT_DECLARED_VERSION)

    def traceability_percent(self) -> float:
        """relation -> unit -> evidence -> same book, as a percentage."""
        total = 0
        traced = 0
        for candidate in self.sink.relation_candidates.values():
            for unit_id, evidence_ids in (
                    (candidate.left_unit_id, candidate.left_evidence_ids),
                    (candidate.right_unit_id, candidate.right_evidence_ids)):
                total += 1
                unit = self.sink.units.get(unit_id)
                if unit is None or not evidence_ids:
                    continue
                if unit.source_version_id != candidate.source_version_id:
                    continue
                if all(self.store.evidence.get(e) is not None
                       and self.store.evidence[e].source_version_id
                       == candidate.source_version_id
                       for e in evidence_ids):
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

    created_at is deliberately absent from `columns`: 079 declares
    DEFAULT now(), so the database stamps it and a replay cannot supply a
    timestamp that disagrees with the stored row.
    """
    return ",".join(_literal(row.get(c)) for c in columns)


def emit_relation_sql(relations) -> str:
    """The relation table as one transaction.

    Every statement is ON CONFLICT DO NOTHING, so a replay writes nothing.
    """
    lines = ["BEGIN;", "SET search_path TO stratum, public;"]
    for key in sorted(relations):
        row = dict(relations[key].__dict__)
        lines.append(
            f"INSERT INTO relation_candidate "
            f"({','.join(RELATION_INSERT_COLUMNS)}) "
            f"VALUES ({_values(row, RELATION_INSERT_COLUMNS)}) "
            f"ON CONFLICT (relation_hash) DO NOTHING;")
    lines.append("COMMIT;")
    return "\n".join(lines) + "\n"


def banned_field_report() -> Dict[str, List[str]]:
    """Which banned field names appear anywhere in this stage.

    Structural: the row dataclass, not a word scan of the source. A relation
    that grew a `meaning` column would be a relation making a judgement, and
    this is where that is noticed.
    """
    rows = {}
    for name in RELATION_BANNED_FIELDS:
        rows[name] = [f"RelationCandidate.{name}"] if hasattr(
            RelationCandidate, name) else []
    return rows


#: Frozen notes for the artifact. Kept as data so the runner cannot report a
#: limitation the module has stopped honouring.
RELATION_NOTES = {
    "RELATION_TYPE": "PRECEDES_ONLY",
    "DEFERRED_TYPES": list(DEFERRED_TYPES),
    "STATE_MACHINE": "GENERATED -> SUPPORTED | REJECTED; both terminal",
    "DB_GUARANTEES": [
        "foreign key integrity (source_version)",
        "same source for both units, via composite foreign keys",
        "relation_type closed to PRECEDES",
        "both evidence arrays non-empty",
        "status vocabulary closed",
        "replay hash uniqueness",
        "self-relation exclusion",
    ],
    "DB_DOES_NOT_GUARANTEE": [
        "the state machine: a CHECK cannot read a column's previous value, so "
        "a raw UPDATE can still move SUPPORTED back to GENERATED",
        "locator order: ordering needs reading_evidence and a CHECK cannot "
        "read another table, so PRECEDES direction is a writer gate",
        "evidence existence: TEXT[] carries no foreign key, so the CHECK "
        "proves non-empty and not real",
    ],
    "FROZEN_RELATION_LAYER": (
        "stratum.ku_relation (075) is untouched; vocabularies are disjoint"),
    "PILOT_SCOPE": (
        "persistence, replay and traceability only; semantic correctness is "
        "not measured and no extractor ships in this stage"),
}