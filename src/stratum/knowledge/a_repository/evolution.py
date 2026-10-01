"""A Repository P5 — KU lifecycle evolution.

    Frozen KU (P4)  ->  Durable KU (P4.1)  ->  Evolving KU (P5)

P4 froze a knowledge unit and P4.1 made it durable. Neither gave it a
history: the row is immutable and the only thing that ever happened to it
is the freeze. A仓 still needs to say *this unit was reviewed, it was
found wanting, here is the review* — and it may not say that by editing the
row, because the row is exactly what everything downstream cites.

So the lifecycle lives beside the unit, never inside it:

    ku_revision              a successor exists; the prior row is untouched
    ku_review_event          a review happened, and cites the span it read
    ku_confidence_evolution  a measurement, appended, never overwritten
    ku_relation              a fact about two rows that already exist

The status of a unit is the **fold** of its review log, not a column:

    ACTIVE ──> QUARANTINED ──> ACTIVE
       │             │
       └─────────────┴──────> SUPERSEDED   (terminal)

Rules:
- append only. Every operation adds a row. None of them edits or deletes
  one, and `update_*` / `delete_*` raise rather than do it.
- a revision is a new unit, not an edit. `link_revision` takes two durable
  unit ids and joins them; it never touches the prior unit's row.
- one successor only. A unit is superseded at most once, so the history is
  a chain and `SUPERSEDED` is emittable once per unit — which is what
  074's UNIQUE(knowledge_unit_id, event_type) already required of it.
- evidence-bearing. Every review cites the evidence it was based on, and
  the service refuses an evidence row from a different source version. A
  review with nothing to point at is an opinion, and opinions are not
  recorded here.
- deterministic. Every id and every fingerprint is content-derived, so a
  replay appends nothing and a later process reads back the same ids.
- relations are factual. The vocabulary holds no value meaning "these say
  the same thing"; deciding that is a semantic judgement and belongs to
  B仓, which this repository has no authority over.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Sequence, Tuple

from .persistence import (
    EventType,
    FreezeEvent,
    FreezeTransaction,
    InMemorySink,
    PersistedUnit,
    PersistenceStatus,
    event_hash,
    event_id,
)
from .verification import VerificationStatus


EVOLUTION_VERSION = "a-p5-v0.1"


#: 074 restricts `ku_freeze_event.to_status` to FREEZE_PENDING / FROZEN /
#: FAILED. A supersession does not change the unit's freeze status — the
#: unit is still frozen and still citable — it only stops being current, so
#: both endpoints are FROZEN and the event type carries the meaning. This
#: is why 074 defined SUPERSEDED as an event type rather than a status.
SUPERSEDE_FROM_STATUS = PersistenceStatus.FROZEN.value
SUPERSEDE_TO_STATUS = PersistenceStatus.FROZEN.value


class KULifecycleStatus(str, Enum):
    """A unit's position in its own review history."""

    ACTIVE = "ACTIVE"
    QUARANTINED = "QUARANTINED"
    SUPERSEDED = "SUPERSEDED"


#: SUPERSEDED has no outgoing edge: UNIQUE(prior_unit_id) gives a unit one
#: successor only, and a unit that already has one is finished.
LEGAL_LIFECYCLE_TRANSITIONS: Dict[KULifecycleStatus, frozenset] = {
    KULifecycleStatus.ACTIVE: frozenset({
        KULifecycleStatus.QUARANTINED, KULifecycleStatus.SUPERSEDED}),
    KULifecycleStatus.QUARANTINED: frozenset({
        KULifecycleStatus.ACTIVE, KULifecycleStatus.SUPERSEDED}),
    KULifecycleStatus.SUPERSEDED: frozenset(),
}

#: A review that records a signal without moving the unit out of ACTIVE.
#: It is still an event, still cites evidence, and still appends — it just
#: does not move the status, which is why from_status may equal to_status.
NON_TRANSITIONING_REVIEWS = frozenset({"CONFIRMED", "CHALLENGED"})


class ReviewType(str, Enum):
    CONFIRMED = "CONFIRMED"
    CHALLENGED = "CHALLENGED"
    QUARANTINED = "QUARANTINED"
    RELEASED = "RELEASED"
    SUPERSEDED = "SUPERSEDED"


class ConfidenceBasis(str, Enum):
    VERIFICATION_SCORE = "VERIFICATION_SCORE"
    REVIEW_SIGNAL = "REVIEW_SIGNAL"
    EVIDENCE_QUALITY = "EVIDENCE_QUALITY"


class RelationType(str, Enum):
    """Factual relations only. See the module docstring.

    Every value is decidable by reading two rows. Nothing here asserts
    that two units mean the same thing, are in tension, or belong together
    as a concept — that is a semantic judgement, and A仓 has no authority
    to make it.
    """

    SHARES_EVIDENCE = "SHARES_EVIDENCE"
    SAME_SOURCE_SPAN = "SAME_SOURCE_SPAN"
    REVISES = "REVISES"


#: The exact vocabulary the migration's CHECK admits. A test asserts the two
#: agree, because a value the code emits and the schema rejects would only
#: surface as a failed transaction at write time.
DECLARED_RELATION_TYPES = frozenset(r.value for r in RelationType)


class EvolutionViolation(Exception):
    """Raised on a forbidden A仓 evolution operation."""


class EvolutionPrecondition(Exception):
    """A lifecycle change may not be recorded yet; nothing was written."""


# ── identity ─────────────────────────────────────────────────────────────────
#
# Every formula here is content-derived. Never uuid4, never a sequence,
# never a timestamp: a reload must produce the ids a fresh run would.

def revision_id(prior_unit_id: str, revised_unit_id: str) -> str:
    """`krv_<sha256(prior | revised)[:12]>`."""
    digest = hashlib.sha256(
        f"{prior_unit_id}|{revised_unit_id}".encode("utf-8")).hexdigest()
    return f"krv_{digest[:12]}"


def revision_hash(prior_unit_id: str, revised_unit_id: str,
                  revision_basis: str, index: int) -> str:
    """`kvh_<sha256(...)[:16]>` — the replay fingerprint."""
    digest = hashlib.sha256(
        f"{prior_unit_id}|{revised_unit_id}|{revision_basis}|{index}"
        f"|{EVOLUTION_VERSION}".encode("utf-8")).hexdigest()
    return f"kvh_{digest[:16]}"


def review_id(unit_id_: str, sequence: int, review_type: str) -> str:
    digest = hashlib.sha256(
        f"{unit_id_}|{sequence}|{review_type}|{EVOLUTION_VERSION}"
        .encode("utf-8")).hexdigest()
    return f"kre_{digest[:12]}"


def review_hash(unit_id_: str, sequence: int, review_type: str,
                rationale: str, evidence_id: str,
                from_status: str, to_status: str) -> str:
    digest = hashlib.sha256(
        f"{unit_id_}|{sequence}|{review_type}|{rationale}|{evidence_id}"
        f"|{from_status}|{to_status}|{EVOLUTION_VERSION}".encode("utf-8")
    ).hexdigest()
    return f"krh_{digest[:16]}"


def relation_id(first_unit_id: str, second_unit_id: str,
                relation_type: str) -> str:
    """Content-derived from the *canonical* pair, so the mirror of a
    relation hashes to the same id and cannot be appended."""
    low, high = sorted((first_unit_id, second_unit_id))
    digest = hashlib.sha256(
        f"{low}|{high}|{relation_type}".encode("utf-8")).hexdigest()
    return f"krl_{digest[:12]}"


def relation_hash(first_unit_id: str, second_unit_id: str,
                  relation_type: str) -> str:
    low, high = sorted((first_unit_id, second_unit_id))
    digest = hashlib.sha256(
        f"{low}|{high}|{relation_type}|{EVOLUTION_VERSION}".encode("utf-8")
    ).hexdigest()
    return f"krhh_{digest[:16]}"


def observation_id(unit_id_: str, sequence: int, basis: str,
                   measured_confidence: float) -> str:
    digest = hashlib.sha256(
        f"{unit_id_}|{sequence}|{basis}|{measured_confidence:.6f}"
        f"|{EVOLUTION_VERSION}".encode("utf-8")).hexdigest()
    return f"kcx_{digest[:12]}"


def observation_hash(unit_id_: str, sequence: int, basis: str,
                     measured_confidence: float) -> str:
    digest = hashlib.sha256(
        f"{unit_id_}|{sequence}|{basis}|{measured_confidence:.6f}"
        f"|{EVOLUTION_VERSION}".encode("utf-8")).hexdigest()
    return f"kxh_{digest[:16]}"


# ── rows ─────────────────────────────────────────────────────────────────────

@dataclass
class Revision:
    id: str
    prior_unit_id: str
    revised_unit_id: str
    revision_index: int
    revision_basis: str
    revision_hash: str
    lifecycle_version: str = EVOLUTION_VERSION
    created_at: str = EVOLUTION_VERSION


@dataclass
class ReviewEvent:
    id: str
    knowledge_unit_id: str
    review_type: str
    from_status: str
    to_status: str
    rationale: str
    evidence_id: str
    review_hash: str
    sequence: int
    lifecycle_version: str = EVOLUTION_VERSION
    created_at: str = EVOLUTION_VERSION


@dataclass
class ConfidenceObservation:
    id: str
    knowledge_unit_id: str
    sequence: int
    measured_confidence: float
    basis: str
    observation_hash: str
    lifecycle_version: str = EVOLUTION_VERSION
    created_at: str = EVOLUTION_VERSION


@dataclass
class Relation:
    id: str
    from_unit_id: str
    to_unit_id: str
    relation_type: str
    relation_hash: str
    lifecycle_version: str = EVOLUTION_VERSION
    created_at: str = EVOLUTION_VERSION


@dataclass
class EvolutionResult:
    """What one lifecycle operation wrote. Nothing here is ever edited."""

    status: str
    unit_id: str = ""
    revision: Optional[Revision] = None
    review: Optional[ReviewEvent] = None
    observation: Optional[ConfidenceObservation] = None
    relations: List[Relation] = field(default_factory=list)
    supersede_event: Optional[object] = None
    written: bool = False
    failure: Optional[str] = None


# ── transaction ──────────────────────────────────────────────────────────────

#: Tables this stage may write. Anything else in a transaction is a bug,
#: and the sink refuses it rather than staging it. `knowledge_unit` and
#: `ku_freeze_event` are here because P5 writes both of them too: a revised
#: unit is a new unit row, and its supersession is a 074 event.
EVOLUTION_TABLES = ("knowledge_unit", "ku_freeze_event", "ku_revision",
                    "ku_review_event", "ku_confidence_evolution",
                    "ku_relation")

#: The row type each staged table holds. `knowledge_unit` and
#: `ku_freeze_event` are P4.1's, unchanged.
ROW_TYPES: Dict[str, type] = {
    "knowledge_unit": PersistedUnit,
    "ku_freeze_event": FreezeEvent,
    "ku_revision": Revision,
    "ku_review_event": ReviewEvent,
    "ku_confidence_evolution": ConfidenceObservation,
    "ku_relation": Relation,
}

#: The sink attribute each staged table is merged into.
ROW_BUCKETS: Dict[str, str] = {
    "knowledge_unit": "units",
    "ku_freeze_event": "events",
    "ku_revision": "revisions",
    "ku_review_event": "reviews",
    "ku_confidence_evolution": "observations",
    "ku_relation": "relations",
}


class EvolutionSink(InMemorySink):
    """P4.1's transactional sink plus the four lifecycle tables.

    Subclasses rather than reimplements: the units and events a revision
    writes must land in the same objects the durable writer reads, or a
    revised unit would exist in one store and be invisible to the other.
    `fail_after` therefore keeps P4.1's meaning — it names the write index
    at which the transaction dies — which is how a crash between two of the
    lifecycle writes is exercised.

    The staging discipline is P4.1's, unchanged and for the same reason:
    applying writes as they arrived left a unit row behind when the event
    write failed, which is exactly the half-written state a transaction
    exists to prevent.

    `TABLES` is the seam: a later stage that appends a table of its own
    widens this tuple and supplies its row type, rather than copying the
    staging body again.
    """

    TABLES: tuple = EVOLUTION_TABLES
    ROW_TYPES: Dict[str, type] = ROW_TYPES
    ROW_BUCKETS: Dict[str, str] = ROW_BUCKETS

    def __init__(self, fail_after: Optional[int] = None):
        super().__init__(fail_after=fail_after)
        self.revisions: Dict[str, Revision] = {}
        self.reviews: Dict[str, ReviewEvent] = {}
        self.observations: Dict[str, ConfidenceObservation] = {}
        self.relations: Dict[str, Relation] = {}

    def commit(self, pending: Sequence[Tuple[str, Dict]]) -> None:
        staged: Dict[str, Dict[str, Dict]] = {
            table: {} for table in self.TABLES}
        for index, (table, row) in enumerate(pending):
            if self.fail_after is not None and index >= self.fail_after:
                self.rollbacks += 1
                raise RuntimeError(f"injected failure at write {index} ({table})")
            if table not in staged:
                raise EvolutionViolation(f"unknown table {table}")
            staged[table][row["id"]] = row

        for table, rows in staged.items():
            row_type = self.ROW_TYPES[table]
            getattr(self, self.ROW_BUCKETS[table]).update(
                {key: row_type(**value) for key, value in rows.items()})
        self.commits += 1

    def reload(self) -> Dict[str, object]:
        """What a later process reads back. Ids are unchanged."""
        return {
            "knowledge_unit": dict(self.units),
            "ku_revision": dict(self.revisions),
            "ku_review_event": dict(self.reviews),
            "ku_confidence_evolution": dict(self.observations),
            "ku_relation": dict(self.relations),
        }


# ── the service ──────────────────────────────────────────────────────────────

class KUEvolutionService:
    """Appends a lifecycle to units that P4.1 already made durable.

    It is a writer for its own four tables and a reader for everything
    upstream: it never modifies a unit row, a verification, a candidate or
    an evidence row, and it holds no write path that could.
    """

    def __init__(self, ingestion_pipeline, quality_pipeline,
                 verification_pipeline, freeze_pipeline, durable_writer,
                 sink: EvolutionSink):
        self.p = ingestion_pipeline
        self.store = ingestion_pipeline.store
        self.qp = quality_pipeline
        self.vp = verification_pipeline
        self.fp = freeze_pipeline
        self.writer = durable_writer
        self.sink = sink

    # ── derived status ──────────────────────────────────────────────────────

    def history(self, unit_id_: str) -> List[ReviewEvent]:
        """A unit's review log in `sequence` order.

        Ordering by sequence rather than by insertion is what makes the
        fold independent of which process wrote which row.
        """
        return sorted((r for r in self.sink.reviews.values()
                       if r.knowledge_unit_id == unit_id_),
                      key=lambda r: r.sequence)

    def status_of(self, unit_id_: str) -> str:
        """Fold the log. A unit is ACTIVE until a review says otherwise."""
        status = KULifecycleStatus.ACTIVE.value
        for review in self.history(unit_id_):
            if review.to_status != status and not self._is_signal(review):
                status = review.to_status
        return status

    @staticmethod
    def _is_signal(review: ReviewEvent) -> bool:
        return review.review_type in NON_TRANSITIONING_REVIEWS

    def status_breakdown(self) -> Dict[str, int]:
        counts = {status.value: 0 for status in KULifecycleStatus}
        for unit_id_ in self.sink.units:
            counts[self.status_of(unit_id_)] += 1
        return dict(sorted(counts.items()))

    # ── preconditions ───────────────────────────────────────────────────────

    def _unit(self, unit_id_: str):
        return self.sink.units.get(unit_id_)

    def _require_frozen(self, unit_id_: str, label: str):
        unit = self._unit(unit_id_)
        if unit is None:
            raise EvolutionPrecondition(f"{label} {unit_id_} is not durable.")
        if unit.freeze_status != PersistenceStatus.FROZEN.value:
            raise EvolutionPrecondition(
                f"{label} {unit_id_} is {unit.freeze_status}, not FROZEN.")
        return unit

    def _require_traceable(self, unit) -> Tuple[bool, List[str]]:
        """GATE_1 / GATE_5 — the unit resolves to its own evidence.

        Same chain P4.1 checks, re-checked here because a lifecycle row
        pointing at an untraceable unit would make the whole history
        unsourceable.
        """
        failed: List[str] = []
        verification = self.vp.store.verifications.get(unit.verification_id)
        candidate = self.store.ku_candidates.get(unit.candidate_id)
        evidence = (self.store.evidence.get(candidate.evidence_id)
                    if candidate else None)
        if verification is None:
            failed.append("NO_VERIFICATION")
        elif verification.verification_status != VerificationStatus.VERIFIED.value:
            failed.append("VERIFICATION_NOT_VERIFIED")
        if candidate is None:
            failed.append("NO_CANDIDATE")
        if evidence is None:
            failed.append("NO_EVIDENCE")
        elif evidence.source_version_id != unit.source_version_id:
            failed.append("EVIDENCE_SOURCE_MISMATCH")
        elif evidence.source_version_id not in self.store.source_versions:
            failed.append("NO_SOURCE_VERSION")
        if not unit.canonical_text:
            failed.append("UNANCHORED_UNIT")
        return not failed, failed

    def check_review_preconditions(self, unit_id_: str,
                                   evidence_id: str) -> Tuple[bool, List[str]]:
        """A review needs a frozen unit and real evidence from its book.

        Checked before the transaction opens, so a refusal writes nothing.
        """
        failed: List[str] = []
        unit = self._unit(unit_id_)
        if unit is None:
            return False, ["NO_SUCH_UNIT"]
        if unit.freeze_status != PersistenceStatus.FROZEN.value:
            failed.append("UNIT_NOT_FROZEN")
        traceable, trace_failed = self._require_traceable(unit)
        if not traceable:
            failed.extend(trace_failed)
        evidence = self.store.evidence.get(evidence_id)
        if evidence is None:
            failed.append("NO_SUCH_EVIDENCE")
        elif evidence.source_version_id != unit.source_version_id:
            # A review of a unit from book X must cite book X. Anything else
            # is a review of a different book that happens to name this unit.
            failed.append("EVIDENCE_FROM_OTHER_SOURCE")
        if self.status_of(unit_id_) == KULifecycleStatus.SUPERSEDED.value:
            failed.append("UNIT_ALREADY_SUPERSEDED")
        return not failed, failed

    def check_revision_preconditions(self, prior_unit_id: str,
                                     revised_unit_id: str,
                                     revision_basis: str
                                     ) -> Tuple[bool, List[str]]:
        failed: List[str] = []
        if prior_unit_id == revised_unit_id:
            failed.append("SELF_REVISION")
        if not (revision_basis or "").strip():
            failed.append("NO_REVISION_BASIS")
        prior = self._unit(prior_unit_id)
        revised = self._unit(revised_unit_id)
        for label, unit in (("prior", prior), ("revised", revised)):
            if unit is None:
                failed.append(f"NO_SUCH_{label.upper()}_UNIT")
            elif unit.freeze_status != PersistenceStatus.FROZEN.value:
                failed.append(f"{label.upper()}_UNIT_NOT_FROZEN")
        if failed:
            return False, failed
        for label, unit in (("prior", prior), ("revised", revised)):
            traceable, trace_failed = self._require_traceable(unit)
            if not traceable:
                failed.extend(f"{label.upper()}_{reason}"
                              for reason in trace_failed)
        if revised.source_version_id != prior.source_version_id:
            # A revision corrects a unit against its own book. A successor
            # from a different source version is a different proposition,
            # and calling that a revision would be a silent re-sourcing.
            failed.append("REVISION_CROSSES_SOURCE_VERSION")
        if self._revision_of(prior_unit_id) is not None:
            failed.append("PRIOR_ALREADY_SUPERSEDED")
        if self._revision_by(revised_unit_id) is not None:
            failed.append("REVISED_ALREADY_SUPERSEDES")
        if self.status_of(prior_unit_id) == KULifecycleStatus.SUPERSEDED.value:
            failed.append("PRIOR_ALREADY_SUPERSEDED")
        return not failed, failed

    def _revision_of(self, unit_id_: str) -> Optional[Revision]:
        found = [r for r in self.sink.revisions.values()
                 if r.prior_unit_id == unit_id_]
        return found[0] if found else None

    def _revision_by(self, unit_id_: str) -> Optional[Revision]:
        found = [r for r in self.sink.revisions.values()
                 if r.revised_unit_id == unit_id_]
        return found[0] if found else None

    def successor_of(self, unit_id_: str) -> Optional[str]:
        revision = self._revision_of(unit_id_)
        return revision.revised_unit_id if revision else None

    def prior_of(self, unit_id_: str) -> Optional[str]:
        revision = self._revision_by(unit_id_)
        return revision.prior_unit_id if revision else None

    def revision_index_of(self, unit_id_: str) -> int:
        """Depth in the chain. A unit nothing revised sits at 0."""
        revision = self._revision_by(unit_id_)
        return revision.revision_index if revision else 0

    # ── reviews ─────────────────────────────────────────────────────────────

    def next_sequence(self, unit_id_: str) -> int:
        existing = [r.sequence for r in self.sink.reviews.values()
                    if r.knowledge_unit_id == unit_id_]
        return max(existing) + 1 if existing else 1

    def find_review(self, unit_id_: str, review_type: str, rationale: str,
                    evidence_id: str) -> Optional[ReviewEvent]:
        """The review an input already produced, if it produced one.

        Content-addressed, not sequence-addressed. Allocating the next
        sequence before checking would make a replay append a *second*
        CHALLENGED event instead of recognising the first, because the
        replay would see sequence 1 taken and mint sequence 2. The identity
        of a review is what it says and what it read.
        """
        for review in self.sink.reviews.values():
            if (review.knowledge_unit_id == unit_id_
                    and review.review_type == review_type
                    and review.rationale == rationale
                    and review.evidence_id == evidence_id):
                return review
        return None

    def review(self, unit_id_: str, review_type: str, rationale: str,
               evidence_id: str) -> EvolutionResult:
        """Append one review. Never moves a unit row, only the fold."""
        if not (rationale or "").strip():
            raise EvolutionPrecondition(
                "A review without a rationale is an opinion, not a review.")
        existing = self.find_review(unit_id_, review_type, rationale,
                                    evidence_id)
        if existing is not None:
            return EvolutionResult(status=self.status_of(unit_id_),
                                   unit_id=unit_id_, review=existing,
                                   written=False)

        ok, failed = self.check_review_preconditions(unit_id_, evidence_id)
        if not ok:
            raise EvolutionPrecondition(
                f"{unit_id_} may not be reviewed: {', '.join(failed)}.")

        sequence = self.next_sequence(unit_id_)
        current = self.status_of(unit_id_)
        kind = ReviewType(review_type)
        target = self._target_status(kind, current)
        row = ReviewEvent(
            id=review_id(unit_id_, sequence, kind.value),
            knowledge_unit_id=unit_id_,
            review_type=kind.value,
            from_status=current,
            to_status=target,
            rationale=rationale,
            evidence_id=evidence_id,
            review_hash=review_hash(unit_id_, sequence, kind.value, rationale,
                                   evidence_id, current, target),
            sequence=sequence,
        )
        if row.id in self.sink.reviews:  # pragma: no cover - defensive
            return EvolutionResult(status=self.status_of(unit_id_),
                                   unit_id=unit_id_,
                                   review=self.sink.reviews[row.id],
                                   written=False)

        try:
            with FreezeTransaction(self.sink) as tx:
                tx.write("ku_review_event", _row_dict(row))
        except Exception as error:
            return EvolutionResult(status="FAILED", unit_id=unit_id_,
                                   failure=str(error))
        return EvolutionResult(status=self.status_of(unit_id_),
                               unit_id=unit_id_,
                               review=self.sink.reviews[row.id], written=True)

    @staticmethod
    def _target_status(kind: ReviewType, current: str) -> str:
        """Where a review of this type leaves the unit.

        A signal (CONFIRMED / CHALLENGED) leaves the status alone. The
        others name their own target, and the transition table is what
        refuses `QUARANTINED -> RELEASED` and every move out of
        SUPERSEDED.
        """
        if kind.value in NON_TRANSITIONING_REVIEWS:
            return current
        target = KULifecycleStatus(kind.value if kind is not ReviewType.RELEASED
                                   else KULifecycleStatus.ACTIVE.value)
        if target not in LEGAL_LIFECYCLE_TRANSITIONS[
                KULifecycleStatus(current)]:
            raise EvolutionPrecondition(
                f"{current} -> {target.value} is not a legal lifecycle "
                "transition; a superseded unit is final.")
        return target.value

    # ── confidence ──────────────────────────────────────────────────────────

    def find_observation(self, unit_id_: str, basis: str,
                         measured_confidence: float
                         ) -> Optional[ConfidenceObservation]:
        """The measurement this input already produced, if any.

        Content-addressed for the same reason as `find_review`. A second
        observation of the same basis at the same value records nothing new:
        it is the same measurement, and letting it append would let a replay
        inflate a unit's history.
        """
        for observation in self.sink.observations.values():
            if (observation.knowledge_unit_id == unit_id_
                    and observation.basis == basis
                    and abs(observation.measured_confidence
                            - measured_confidence) < 1e-9):
                return observation
        return None

    def observe_confidence(self, unit_id_: str, basis: str,
                           measured_confidence: float) -> EvolutionResult:
        """Append one measurement. Confidence only ever grows a row."""
        if not 0.0 <= measured_confidence <= 1.0:
            raise EvolutionPrecondition(
                "Confidence is a measurement in [0, 1], not a claim.")
        kind = ConfidenceBasis(basis)
        if self._unit(unit_id_) is None:
            raise EvolutionPrecondition(f"{unit_id_} is not durable.")
        existing = self.find_observation(unit_id_, kind.value,
                                         measured_confidence)
        if existing is not None:
            return EvolutionResult(status=self.status_of(unit_id_),
                                   unit_id=unit_id_, observation=existing,
                                   written=False)
        sequence = self.next_confidence_sequence(unit_id_)
        row = ConfidenceObservation(
            id=observation_id(unit_id_, sequence, kind.value,
                              measured_confidence),
            knowledge_unit_id=unit_id_,
            sequence=sequence,
            measured_confidence=measured_confidence,
            basis=kind.value,
            observation_hash=observation_hash(unit_id_, sequence, kind.value,
                                              measured_confidence),
        )
        try:
            with FreezeTransaction(self.sink) as tx:
                tx.write("ku_confidence_evolution", _row_dict(row))
        except Exception as error:
            return EvolutionResult(status="FAILED", unit_id=unit_id_,
                                   failure=str(error))
        return EvolutionResult(status=self.status_of(unit_id_),
                               unit_id=unit_id_,
                               observation=self.sink.observations[row.id],
                               written=True)

    def next_confidence_sequence(self, unit_id_: str) -> int:
        existing = [o.sequence for o in self.sink.observations.values()
                    if o.knowledge_unit_id == unit_id_]
        return max(existing) + 1 if existing else 1

    def confidence_series(self, unit_id_: str) -> List[ConfidenceObservation]:
        return sorted((o for o in self.sink.observations.values()
                       if o.knowledge_unit_id == unit_id_),
                      key=lambda o: o.sequence)

    # ── relations ───────────────────────────────────────────────────────────

    def relate(self, first_unit_id: str, second_unit_id: str,
               relation_type: str) -> EvolutionResult:
        """Record one factual relation between two durable units.

        The type must be in the declared vocabulary, which is checked
        against the migration's own list in the tests. There is no
        parameter for a judgement, and none may be added here.
        """
        if first_unit_id == second_unit_id:
            raise EvolutionPrecondition(
                "A relation joins two units; a unit is not related to itself.")
        kind = RelationType(relation_type)
        low, high = sorted((first_unit_id, second_unit_id))
        for unit_id_ in (low, high):
            if self._unit(unit_id_) is None:
                raise EvolutionPrecondition(
                    f"{unit_id_} is not durable; relations join durable units.")
        row = Relation(
            id=relation_id(first_unit_id, second_unit_id, kind.value),
            from_unit_id=low,
            to_unit_id=high,
            relation_type=kind.value,
            relation_hash=relation_hash(first_unit_id, second_unit_id,
                                        kind.value),
        )
        existing = self.sink.relations.get(row.id)
        if existing is not None:
            return EvolutionResult(status=self.status_of(low), unit_id=low,
                                   relations=[existing], written=False)
        try:
            with FreezeTransaction(self.sink) as tx:
                tx.write("ku_relation", _row_dict(row))
        except Exception as error:
            return EvolutionResult(status="FAILED", unit_id=low,
                                   failure=str(error))
        return EvolutionResult(status=self.status_of(low), unit_id=low,
                               relations=[self.sink.relations[row.id]],
                               written=True)

    def relations_of(self, unit_id_: str) -> List[Relation]:
        return sorted((r for r in self.sink.relations.values()
                       if unit_id_ in (r.from_unit_id, r.to_unit_id)),
                      key=lambda r: r.id)

    # ── revision ────────────────────────────────────────────────────────────

    def revision_rows(self, prior_unit_id: str, revised_unit_id: str,
                      basis: str) -> Tuple[Revision, ReviewEvent, Dict,
                                            List[Relation]]:
        """The four lifecycle rows one revision appends, plus its event.

        Built before the transaction opens so a refusal costs nothing, and
        so the whole revision is visible as one unit of work.
        """
        index = self.revision_index_of(prior_unit_id) + 1
        revision = Revision(
            id=revision_id(prior_unit_id, revised_unit_id),
            prior_unit_id=prior_unit_id,
            revised_unit_id=revised_unit_id,
            revision_index=index,
            revision_basis=basis,
            revision_hash=revision_hash(prior_unit_id, revised_unit_id,
                                        basis, index),
        )
        # The superseding review cites the prior unit's own evidence: it is
        # the span the reviewer was looking at when they decided the unit
        # needed replacing.
        prior_unit = self._unit(prior_unit_id)
        evidence_id = self._evidence_of(prior_unit)
        sequence = self.next_sequence(prior_unit_id)
        review = ReviewEvent(
            id=review_id(prior_unit_id, sequence, ReviewType.SUPERSEDED.value),
            knowledge_unit_id=prior_unit_id,
            review_type=ReviewType.SUPERSEDED.value,
            from_status=KULifecycleStatus.ACTIVE.value,
            to_status=KULifecycleStatus.SUPERSEDED.value,
            rationale=basis,
            evidence_id=evidence_id,
            review_hash=review_hash(prior_unit_id, sequence,
                                    ReviewType.SUPERSEDED.value, basis,
                                    evidence_id,
                                    KULifecycleStatus.ACTIVE.value,
                                    KULifecycleStatus.SUPERSEDED.value),
            sequence=sequence,
        )
        # The successor's own series, seeded here rather than by the
        # baseline sweep. A baseline pass that ran before the successor
        # existed never saw it, so seeding it here is what keeps the pass
        # idempotent afterwards — and it is the right order anyway: the
        # score that admitted the unit comes first, then the fact that it
        # exists because a review produced it.
        revised_unit = self._unit(revised_unit_id)
        sequence = self.next_confidence_sequence(revised_unit_id)
        observations: List[ConfidenceObservation] = []
        if self.find_observation(revised_unit_id,
                                 ConfidenceBasis.VERIFICATION_SCORE.value,
                                 revised_unit.verification_score) is None:
            observations.append(_observation(
                revised_unit_id, sequence,
                ConfidenceBasis.VERIFICATION_SCORE.value,
                revised_unit.verification_score))
            sequence += 1
        observations.append(_observation(
            revised_unit_id, sequence, ConfidenceBasis.REVIEW_SIGNAL.value,
            revised_unit.verification_score))
        relations = self._derived_relations(prior_unit_id, revised_unit_id)
        event = {
            "id": event_id(prior_unit_id, EventType.SUPERSEDED.value),
            "knowledge_unit_id": prior_unit_id,
            "event_type": EventType.SUPERSEDED.value,
            "from_status": SUPERSEDE_FROM_STATUS,
            "to_status": SUPERSEDE_TO_STATUS,
            "event_hash": event_hash(prior_unit_id,
                                     EventType.SUPERSEDED.value,
                                     SUPERSEDE_FROM_STATUS,
                                     SUPERSEDE_TO_STATUS),
            "created_at": EVOLUTION_VERSION,
        }
        return revision, review, event, [*observations, *relations]

    def _derived_relations(self, prior_unit_id: str,
                           revised_unit_id: str) -> List[Relation]:
        """Relations that two rows already prove.

        REVISES is asserted by the revision itself. SHARES_EVIDENCE and
        SAME_SOURCE_SPAN are *derived*, not declared: a relation this
        service inferred from comparing two units is still a fact about
        rows, and inferring it is not a judgement about meaning.
        """
        rows: List[Relation] = []
        prior, revised = self._unit(prior_unit_id), self._unit(revised_unit_id)

        def add(first: str, second: str, kind: RelationType) -> None:
            low, high = sorted((first, second))
            rows.append(Relation(
                id=relation_id(first, second, kind.value),
                from_unit_id=low, to_unit_id=high, relation_type=kind.value,
                relation_hash=relation_hash(first, second, kind.value)))

        add(prior_unit_id, revised_unit_id, RelationType.REVISES)
        prior_evidence = self._evidence_of(prior)
        revised_evidence = self._evidence_of(revised)
        if prior_evidence and prior_evidence == revised_evidence:
            add(prior_unit_id, revised_unit_id, RelationType.SHARES_EVIDENCE)
        if (prior.source_version_id == revised.source_version_id
                and prior.canonical_text
                and prior.canonical_text == revised.canonical_text):
            add(prior_unit_id, revised_unit_id, RelationType.SAME_SOURCE_SPAN)
        return sorted(rows, key=lambda r: r.id)

    def _evidence_of(self, unit) -> str:
        candidate = self.store.ku_candidates.get(unit.candidate_id)
        return candidate.evidence_id if candidate else ""

    def find_revision(self, prior_unit_id: str,
                      revised_unit_id: str) -> Optional[Revision]:
        """The revision this pair already produced, if it produced one."""
        return self._revision_of(prior_unit_id)

    def link_revision(self, prior_unit_id: str, revised_unit_id: str,
                     basis: str) -> EvolutionResult:
        """Record a revision: append the successor, retire the prior.

        The prior unit's row is not touched, not here and anywhere else.
        What changes is that the fold now reports it SUPERSEDED and a
        reader can ask for its successor.
        """
        # The existing-revision lookup comes first, before the
        # preconditions. A replay legitimately fails "PRIOR_ALREADY_
        # SUPERSEDED" — that is the very fact the replay is confirming — so
        # checking first is what turns the replay into a no-op instead of a
        # refusal.
        settled = self.find_revision(prior_unit_id, revised_unit_id)
        if settled is not None and settled.revised_unit_id == revised_unit_id:
            return EvolutionResult(
                status=self.status_of(prior_unit_id), unit_id=prior_unit_id,
                revision=settled,
                review=next((r for r in self.sink.reviews.values()
                             if r.knowledge_unit_id == prior_unit_id
                             and r.review_type == ReviewType.SUPERSEDED.value
                             and r.rationale == settled.revision_basis), None),
                written=False)

        ok, failed = self.check_revision_preconditions(prior_unit_id,
                                                       revised_unit_id, basis)
        if not ok:
            raise EvolutionPrecondition(
                f"{prior_unit_id} cannot be revised by {revised_unit_id}: "
                f"{', '.join(failed)}.")
        revision, review, event, extras = self.revision_rows(
            prior_unit_id, revised_unit_id, basis)

        try:
            with FreezeTransaction(self.sink) as tx:
                tx.write("ku_revision", _row_dict(revision))
                tx.write("ku_review_event", _row_dict(review))
                tx.write("ku_freeze_event", event)
                for row in extras:
                    table = ("ku_confidence_evolution"
                             if isinstance(row, ConfidenceObservation)
                             else "ku_relation")
                    tx.write(table, _row_dict(row))
        except Exception as error:
            return EvolutionResult(status="FAILED", unit_id=prior_unit_id,
                                   failure=str(error))

        return EvolutionResult(
            status=self.status_of(prior_unit_id), unit_id=prior_unit_id,
            revision=self.sink.revisions[revision.id],
            review=self.sink.reviews[review.id],
            observation=next((o for o in extras
                              if isinstance(o, ConfidenceObservation)), None),
            relations=[r for r in extras if isinstance(r, Relation)],
            supersede_event=FreezeEvent(**event), written=True)

    # ── derived relations across a whole run ────────────────────────────────

    def derive_run_relations(self) -> List[Relation]:
        """Every relation two durable rows prove, in a stable order.

        Derived, never declared: a caller cannot choose to assert that two
        units are related, only to ask what the rows already show.
        """
        units = [self.sink.units[k] for k in sorted(self.sink.units)]
        found: Dict[str, Relation] = {}
        for left, right in _pairs(units):
            prior_evidence = self._evidence_of(left)
            revised_evidence = self._evidence_of(right)
            if prior_evidence and prior_evidence == revised_evidence:
                key = relation_id(left.id, right.id,
                                  RelationType.SHARES_EVIDENCE.value)
                found[key] = Relation(
                    id=key, from_unit_id=min(left.id, right.id),
                    to_unit_id=max(left.id, right.id),
                    relation_type=RelationType.SHARES_EVIDENCE.value,
                    relation_hash=relation_hash(left.id, right.id,
                                                RelationType.SHARES_EVIDENCE
                                                .value))
            if (left.source_version_id == right.source_version_id
                    and left.canonical_text
                    and left.canonical_text == right.canonical_text):
                key = relation_id(left.id, right.id,
                                  RelationType.SAME_SOURCE_SPAN.value)
                found[key] = Relation(
                    id=key, from_unit_id=min(left.id, right.id),
                    to_unit_id=max(left.id, right.id),
                    relation_type=RelationType.SAME_SOURCE_SPAN.value,
                    relation_hash=relation_hash(left.id, right.id,
                                                RelationType.SAME_SOURCE_SPAN
                                                .value))
        return [found[k] for k in sorted(found)]

    def record_derived_relations(self) -> List[Relation]:
        """Append every derivable relation not already present."""
        appended: List[Relation] = []
        for relation in self.derive_run_relations():
            if relation.id in self.sink.relations:
                continue
            result = self.relate(relation.from_unit_id, relation.to_unit_id,
                                 relation.relation_type)
            appended.extend(result.relations)
        return sorted(appended, key=lambda r: r.id)

    def record_baseline_confidence(self) -> List[ConfidenceObservation]:
        """Seed each unit's series with the score that admitted it.

        A unit's first confidence reading is the verification score it was
        frozen on — not a fresh judgement, just the measurement that
        already exists, recorded where the history can find it.
        """
        appended: List[ConfidenceObservation] = []
        for key in sorted(self.sink.units):
            unit = self.sink.units[key]
            result = self.observe_confidence(
                key, ConfidenceBasis.VERIFICATION_SCORE.value,
                unit.verification_score)
            if result.observation is not None:
                appended.append(result.observation)
        return appended

    # ── immutability ────────────────────────────────────────────────────────

    def update_unit(self, unit_id_: str, **changes) -> None:
        raise EvolutionViolation(
            f"Knowledge unit {unit_id_} cannot be updated; its lifecycle "
            "lives in appended events, and a correction is a new unit.")

    def set_status(self, unit_id_: str, status: str) -> None:
        raise EvolutionViolation(
            "A unit's status is the fold of its review log; it is never "
            "assigned.")

    def delete_unit(self, unit_id_: str) -> None:
        raise EvolutionViolation("A knowledge unit cannot be deleted.")

    def delete_revision(self, revision_id_: str) -> None:
        raise EvolutionViolation("A revision is immutable and cannot be deleted.")

    def delete_review(self, review_id_: str) -> None:
        raise EvolutionViolation("A review event is immutable.")

    def delete_observation(self, observation_id_: str) -> None:
        raise EvolutionViolation("A confidence measurement is immutable.")

    def delete_relation(self, relation_id_: str) -> None:
        raise EvolutionViolation("A relation is immutable.")

    def supersede(self, unit_id_: str) -> None:
        raise EvolutionViolation(
            "A unit is superseded by appending a revision, never by "
            "declaration.")

    def merge_units(self, *unit_ids: str) -> None:
        raise EvolutionViolation(
            "A仓 has no authority to merge knowledge units; merging is a "
            "semantic judgement and belongs to B仓.")

    def dedupe_units(self, *unit_ids: str) -> None:
        raise EvolutionViolation(
            "A仓 has no authority to deduplicate knowledge units; deciding "
            "two units say the same thing is a semantic judgement.")

    # ── queries ─────────────────────────────────────────────────────────────

    def revision_count(self) -> int:
        return len(self.sink.revisions)

    def review_count(self) -> int:
        return len(self.sink.reviews)

    def observation_count(self) -> int:
        return len(self.sink.observations)

    def relation_count(self) -> int:
        return len(self.sink.relations)

    def orphan_revisions(self) -> List[str]:
        return sorted(r.id for r in self.sink.revisions.values()
                      if (r.prior_unit_id not in self.sink.units
                          or r.revised_unit_id not in self.sink.units))

    def orphan_reviews(self) -> List[str]:
        return sorted(r.id for r in self.sink.reviews.values()
                      if (r.knowledge_unit_id not in self.sink.units
                          or r.evidence_id not in self.store.evidence))

    def orphan_observations(self) -> List[str]:
        return sorted(o.id for o in self.sink.observations.values()
                      if o.knowledge_unit_id not in self.sink.units)

    def orphan_relations(self) -> List[str]:
        return sorted(r.id for r in self.sink.relations.values()
                      if (r.from_unit_id not in self.sink.units
                          or r.to_unit_id not in self.sink.units))

    def duplicate_revisions(self) -> List[str]:
        return _duplicates(self.sink.revisions,
                           lambda r: f"{r.prior_unit_id}|{r.revised_unit_id}")

    def duplicate_reviews(self) -> List[str]:
        return _duplicates(self.sink.reviews,
                           lambda r: f"{r.knowledge_unit_id}|{r.sequence}")

    def duplicate_relations(self) -> List[str]:
        return _duplicates(
            self.sink.relations,
            lambda r: f"{r.from_unit_id}|{r.to_unit_id}|{r.relation_type}")

    def traceability(self) -> Dict[str, object]:
        """GATE_1 — every lifecycle row resolves to a source version.

        Walks each row back to the book: unit -> verification -> candidate
        -> evidence -> source_version, and separately checks that a review
        cites evidence from the unit's own source version.
        """
        complete = 0
        reviewed = 0
        for unit in self.sink.units.values():
            traceable, _ = self._require_traceable(unit)
            if traceable:
                complete += 1
        for review in self.sink.reviews.values():
            unit = self.sink.units.get(review.knowledge_unit_id)
            evidence = self.store.evidence.get(review.evidence_id)
            if (unit is not None and evidence is not None
                    and evidence.source_version_id == unit.source_version_id):
                reviewed += 1
        total = len(self.sink.units)
        return {
            "units": total,
            "trace_complete": complete,
            "percent": round(100.0 * complete / total, 2) if total else 0.0,
            "reviews": len(self.sink.reviews),
            "reviews_sourced": reviewed,
            "review_percent": (round(100.0 * reviewed / len(self.sink.reviews), 2)
                               if self.sink.reviews else 0.0),
        }


# ── helpers ──────────────────────────────────────────────────────────────────

def _pairs(units: Sequence):
    for index, left in enumerate(units):
        for right in units[index + 1:]:
            yield left, right


def _duplicates(rows: Dict, key) -> List[str]:
    seen: Dict[str, int] = {}
    for row in rows.values():
        value = key(row)
        seen[value] = seen.get(value, 0) + 1
    return sorted(k for k, v in seen.items() if v > 1)


def _row_dict(row) -> Dict:
    """A dataclass as the plain dict the sink and the SQL writer want."""
    return dict(row.__dict__)


def _observation(unit_id_: str, sequence: int, basis: str,
                 measured_confidence: float) -> ConfidenceObservation:
    """One confidence row, with both ids derived from its own content."""
    return ConfidenceObservation(
        id=observation_id(unit_id_, sequence, basis, measured_confidence),
        knowledge_unit_id=unit_id_,
        sequence=sequence,
        measured_confidence=measured_confidence,
        basis=basis,
        observation_hash=observation_hash(unit_id_, sequence, basis,
                                          measured_confidence),
    )


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
    return "'" + str(value).replace("'", "''") + "'"


def _insert(table: str, row: Dict, conflict: str,
            columns: Sequence[str]) -> str:
    return (f"INSERT INTO {table} ({','.join(columns)}) "
            f"VALUES ({','.join(_literal(row.get(c)) for c in columns)}) "
            f"ON CONFLICT ({conflict}) DO NOTHING;")


_REVISION_COLUMNS = ("id", "prior_unit_id", "revised_unit_id",
                     "revision_index", "revision_basis", "revision_hash",
                     "lifecycle_version")

_REVIEW_COLUMNS = ("id", "knowledge_unit_id", "review_type", "from_status",
                   "to_status", "rationale", "evidence_id", "review_hash",
                   "lifecycle_version", "sequence")

_CONFIDENCE_COLUMNS = ("id", "knowledge_unit_id", "sequence",
                       "measured_confidence", "basis", "observation_hash",
                       "lifecycle_version")

_RELATION_COLUMNS = ("id", "from_unit_id", "to_unit_id", "relation_type",
                     "relation_hash", "lifecycle_version")


def emit_evolution_sql(store, verification_pipeline, freeze_pipeline,
                       sink) -> str:
    """The whole A chain plus the lifecycle as ONE transaction.

    The lifecycle tables carry foreign keys onto `knowledge_unit` and
    `reading_evidence`, and a revised unit is itself a new row in
    `knowledge_unit` with a new candidate and a new verification behind it.
    So this reuses P4.1's ancestry emission unchanged and appends the four
    lifecycle tables after it, parents before children.

    Every statement is ON CONFLICT DO NOTHING, which is what makes the
    whole file safe to run twice: the second execution writes nothing.
    """
    from .persistence import emit_chain_sql

    inner = emit_chain_sql(store, verification_pipeline, freeze_pipeline,
                           sink).splitlines()
    statements = [line for line in inner
                  if line.startswith("INSERT INTO")
                  and not line.startswith("INSERT INTO ku_revision")]

    for key in sorted(sink.revisions):
        statements.append(_insert("ku_revision",
                                  _row_dict(sink.revisions[key]),
                                  "revision_hash", _REVISION_COLUMNS))
    for key in sorted(sink.reviews):
        statements.append(_insert("ku_review_event",
                                  _row_dict(sink.reviews[key]),
                                  "review_hash", _REVIEW_COLUMNS))
    for key in sorted(sink.observations):
        statements.append(_insert("ku_confidence_evolution",
                                  _row_dict(sink.observations[key]),
                                  "observation_hash", _CONFIDENCE_COLUMNS))
    for key in sorted(sink.relations):
        statements.append(_insert("ku_relation", _row_dict(sink.relations[key]),
                                  "relation_hash", _RELATION_COLUMNS))

    # `emit_chain_sql` already writes every event the sink holds, including
    # the SUPERSEDED ones this stage adds, under P4.1's own conflict target
    # of (knowledge_unit_id, event_type). Re-emitting them here would put
    # the same row in the script twice.

    return "\n".join(["BEGIN;", "SET search_path TO stratum, public;"]
                     + statements + ["COMMIT;"]) + "\n"
