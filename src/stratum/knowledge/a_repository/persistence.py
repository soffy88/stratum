"""A Repository P4.1 — KU durable persistence.

Turns a frozen knowledge unit held in memory into a durable A仓 asset:
written in one transaction, recoverable by a later process, and
unaltered by a replay.

    KUVerification(VERIFIED)
        |
        v
    Freeze Service
        |
        v
    knowledge_unit  +  ku_freeze_event

Persistence lifecycle:

    FREEZE_PENDING ──> FROZEN
           └───────> FAILED

`FAILED` is the terminal outcome of an *attempt*. A failed freeze leaves
no unit row at all, so there is no unit left sitting in a failed state.

Rules:
- atomic: the unit row and its event are written in one transaction.
  There is no reachable state with a unit and no event, or an event and
  no unit.
- idempotent: the same (candidate_id, verification_id, content_hash)
  persists once. A replay writes nothing.
- deterministic: ids and event fingerprints are content-derived, so a
  reload sees the same ids a fresh run would produce.
- immutable: FROZEN is never modified and never deleted.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Sequence, Tuple

from .freeze import FREEZE_SCORE_THRESHOLD, FREEZE_VERSION
from .verification import VerificationStatus


PERSISTENCE_VERSION = "a-p4-1-v0.1"


class PersistenceStatus(str, Enum):
    """Lifecycle of one persistence attempt."""

    FREEZE_PENDING = "FREEZE_PENDING"
    FROZEN = "FROZEN"
    FAILED = "FAILED"


class EventType(str, Enum):
    """The event vocabulary the schema admits.

    CREATED and SUPERSEDED are reserved. Nothing emits them yet: the unit
    row is its own record of existence, so a creation event would restate
    it, and a revision is a new unit under a new freeze_version, a stage
    that does not exist. Only FROZEN carries a state change today.
    """

    CREATED = "CREATED"
    FROZEN = "FROZEN"
    SUPERSEDED = "SUPERSEDED"


#: The only event type this stage emits.
IMPLEMENTED_EVENT_TYPES = (EventType.FROZEN,)


class PersistenceViolation(Exception):
    """Raised on a forbidden A仓 persistence operation."""


class PersistencePrecondition(Exception):
    """A unit may not be persisted yet; nothing was written."""


# ── identity ─────────────────────────────────────────────────────────────────

def persisted_unit_id(candidate_id: str, verification_id: str,
                      content_hash: str) -> str:
    """The durable unit id.

        ku_<sha256(candidate_id | verification_id | content_hash)[:12]>

    Content-derived. Never uuid4, never a sequence, never a timestamp: a
    reload must produce the same id a fresh run would.
    """
    digest = hashlib.sha256(
        f"{candidate_id}|{verification_id}|{content_hash}".encode("utf-8")
    ).hexdigest()
    return f"ku_{digest[:12]}"


def event_id(unit_id_: str, event_type: str) -> str:
    digest = hashlib.sha256(
        f"{unit_id_}|{event_type}|{PERSISTENCE_VERSION}".encode("utf-8")
    ).hexdigest()
    return f"kfe_{digest[:12]}"


def event_hash(unit_id_: str, event_type: str, from_status: Optional[str],
               to_status: str) -> str:
    """Deterministic event fingerprint.

    Content-derived rather than time-derived: a replay of the same freeze
    must produce the same fingerprint, which is what lets the unique
    constraint turn the replay into a no-op instead of a second event.
    """
    digest = hashlib.sha256(
        f"{unit_id_}|{event_type}|{from_status or ''}|{to_status}"
        f"|{PERSISTENCE_VERSION}".encode("utf-8")
    ).hexdigest()
    return f"keh_{digest[:16]}"


# ── rows ─────────────────────────────────────────────────────────────────────

@dataclass
class FreezeEvent:
    id: str
    knowledge_unit_id: str
    event_type: str
    from_status: Optional[str]
    to_status: str
    event_hash: str
    created_at: str = ""


@dataclass
class PersistedUnit:
    id: str
    candidate_id: str
    verification_id: str
    source_version_id: str
    content_hash: str
    statement: str
    canonical_text: str
    verification_score: float
    freeze_status: str
    freeze_version: str = FREEZE_VERSION
    title: str = ""
    evidence_count: int = 1
    created_at: str = ""
    frozen_at: Optional[str] = None
    events: List[FreezeEvent] = field(default_factory=list)


@dataclass
class PersistenceResult:
    status: str
    unit: Optional[PersistedUnit] = None
    events: List[FreezeEvent] = field(default_factory=list)
    written_unit: bool = False
    written_events: int = 0
    failure: Optional[str] = None


# ── transaction ──────────────────────────────────────────────────────────────

class FreezeTransaction:
    """A real transaction over a pluggable sink.

    The sink exposes only commit/rollback and an ordered write log, which
    is enough to prove the atomicity the contract requires: on any failure
    both writes are discarded together, so a unit without its event and an
    event without its unit are both unreachable.
    """

    def __init__(self, sink):
        self.sink = sink
        self._pending: List[Tuple[str, Dict]] = []

    def __enter__(self) -> "FreezeTransaction":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc_type is not None:
            self.sink.rollback(self._pending)
            self._pending = []
            return False
        self.sink.commit(self._pending)
        self._pending = []
        return False

    def write(self, table: str, row: Dict) -> None:
        self._pending.append((table, row))

    @property
    def pending(self) -> List[Tuple[str, Dict]]:
        return list(self._pending)


class InMemorySink:
    """Transactional sink with fault injection.

    `fail_after` names a write index at which the transaction dies, which
    is how the crash-recovery case is exercised: the unit is written, the
    event is not, and neither survives.
    """

    def __init__(self, fail_after: Optional[int] = None):
        self.fail_after = fail_after
        self.units: Dict[str, PersistedUnit] = {}
        self.events: Dict[str, FreezeEvent] = {}
        self.commits = 0
        self.rollbacks = 0

    def commit(self, pending: Sequence[Tuple[str, Dict]]) -> None:
        """Apply every write or none.

        The writes are staged into fresh dicts and merged only once the
        last one has succeeded. Applying them as they arrive would leave
        the unit row behind when the event write failed, which is exactly
        the half-written state the transaction exists to prevent.
        """
        staged: Dict[str, Dict[str, object]] = {"knowledge_unit": {},
                                                "ku_freeze_event": {}}
        for index, (table, row) in enumerate(pending):
            if self.fail_after is not None and index >= self.fail_after:
                self.rollbacks += 1
                raise RuntimeError(
                    f"injected failure at write {index} ({table})")
            if table not in staged:
                raise PersistenceViolation(f"unknown table {table}")
            staged[table][row["id"]] = row

        self.units.update({k: PersistedUnit(**v)
                           for k, v in staged["knowledge_unit"].items()})
        self.events.update({k: FreezeEvent(**v)
                            for k, v in staged["ku_freeze_event"].items()})
        self.commits += 1

    def rollback(self, pending: Sequence[Tuple[str, Dict]]) -> None:
        self.rollbacks += 1


# ── writer ───────────────────────────────────────────────────────────────────

class KUDurableWriter:
    """Persists frozen knowledge units and records their transitions."""

    def __init__(self, ingestion_pipeline, verification_pipeline,
                 freeze_pipeline, sink):
        self.p = ingestion_pipeline
        self.store = ingestion_pipeline.store
        self.vp = verification_pipeline
        self.fp = freeze_pipeline
        self.sink = sink

    # ── preconditions ─────────────────────────────────────────────────────

    def check_preconditions(self, verification_id: str) -> Tuple[bool, List[str]]:
        """Everything that must hold before a row is written.

        Checked before the transaction opens, so a refusal writes nothing
        at all rather than opening and rolling back.
        """
        failed: List[str] = []
        verification = self.vp.store.verifications.get(verification_id)
        if verification is None:
            return False, ["NO_SUCH_VERIFICATION"]
        if verification.verification_status != VerificationStatus.VERIFIED.value:
            failed.append("VERIFICATION_NOT_VERIFIED")
        if verification.verification_score < FREEZE_SCORE_THRESHOLD:
            failed.append("SCORE_BELOW_THRESHOLD")

        unit_id_ = self.fp.store._unit_by_verification.get(verification_id)
        if unit_id_ is None:
            failed.append("NO_FROZEN_UNIT")
            return not failed, failed
        unit = self.fp.store.frozen_units[unit_id_]

        candidate = self.store.ku_candidates.get(unit.candidate_id)
        if candidate is None:
            failed.append("NO_CANDIDATE")
        evidence = (self.store.evidence.get(candidate.evidence_id)
                    if candidate else None)
        if evidence is None:
            failed.append("NO_EVIDENCE")
        elif evidence.source_version_id not in self.store.source_versions:
            failed.append("NO_SOURCE_VERSION")
        if not unit.canonical_text:
            failed.append("UNANCHORED_UNIT")
        return not failed, failed

    # ── the write ─────────────────────────────────────────────────────────

    def rows_for(self, unit) -> Tuple[Dict, List[Dict]]:
        """The unit row and its event row.

        One event per unit. The unit row is its own record of existence;
        the event records the one state change that matters, the
        transition into immutability. Two events per unit would contradict
        the acceptance counts, which state one freeze event per frozen
        unit alongside one unit per verified candidate.
        """
        durable_id = persisted_unit_id(
            unit.candidate_id, unit.verification_id, unit.content_hash)
        unit_row = {
            "id": durable_id,
            "candidate_id": unit.candidate_id,
            "verification_id": unit.verification_id,
            "source_version_id": unit.source_version_id,
            "content_hash": unit.content_hash,
            "statement": unit.statement,
            "canonical_text": unit.canonical_text,
            "verification_score": unit.verification_score,
            "freeze_status": PersistenceStatus.FROZEN.value,
            "freeze_version": unit.freeze_version,
            "title": unit.title,
            "evidence_count": unit.evidence_count,
        }
        event_row = {
            "id": event_id(durable_id, EventType.FROZEN.value),
            "knowledge_unit_id": durable_id,
            "event_type": EventType.FROZEN.value,
            "from_status": PersistenceStatus.FREEZE_PENDING.value,
            "to_status": PersistenceStatus.FROZEN.value,
            "event_hash": event_hash(
                durable_id, EventType.FROZEN.value,
                PersistenceStatus.FREEZE_PENDING.value,
                PersistenceStatus.FROZEN.value),
            "created_at": PERSISTENCE_VERSION,
        }
        return unit_row, [event_row]

    def persist(self, verification_id: str) -> PersistenceResult:
        """Persist one unit atomically. Idempotent."""
        ok, failed = self.check_preconditions(verification_id)
        if not ok:
            raise PersistencePrecondition(
                f"{verification_id} may not be persisted: "
                f"{', '.join(failed)}.")

        unit_id_ = self.fp.store._unit_by_verification[verification_id]
        unit = self.fp.store.frozen_units[unit_id_]
        unit_row, event_rows = self.rows_for(unit)

        existing = self.sink.units.get(unit_row["id"])
        if existing is not None:
            # Already durable. The replay writes nothing: not the unit, not
            # the events, not a second event with a new fingerprint.
            return PersistenceResult(
                status=PersistenceStatus.FROZEN.value,
                unit=existing,
                events=[e for e in self.sink.events.values()
                        if e.knowledge_unit_id == existing.id],
                written_unit=False, written_events=0)

        try:
            with FreezeTransaction(self.sink) as tx:
                tx.write("knowledge_unit", unit_row)
                for row in event_rows:
                    tx.write("ku_freeze_event", row)
        except Exception as error:  # the transaction rolled back
            return PersistenceResult(
                status=PersistenceStatus.FAILED.value,
                failure=str(error))

        stored = self.sink.units[unit_row["id"]]
        written = [e for e in self.sink.events.values()
                   if e.knowledge_unit_id == stored.id]
        return PersistenceResult(
            status=PersistenceStatus.FROZEN.value, unit=stored,
            events=sorted(written, key=lambda e: e.id),
            written_unit=True, written_events=len(written))

    def persist_verified(self, reading_run_id: str) -> List[PersistenceResult]:
        """Persist every already-frozen unit for a reading run, in a stable
        order."""
        verification_ids = sorted(
            self.fp.store._unit_by_verification)
        return [self.persist(vid) for vid in verification_ids]

    # ── immutability ──────────────────────────────────────────────────────

    def update_unit(self, unit_id_: str, **changes) -> None:
        unit = self.sink.units.get(unit_id_)
        state = unit.freeze_status if unit else "MISSING"
        raise PersistenceViolation(
            f"A persisted knowledge unit cannot be updated (state {state}); "
            "a correction is a new unit under a new freeze_version.")

    def delete_unit(self, unit_id_: str) -> None:
        raise PersistenceViolation(
            "A persisted knowledge unit cannot be deleted.")

    def delete_event(self, event_id_: str) -> None:
        raise PersistenceViolation(
            "A freeze event is immutable and cannot be deleted.")

    # ── queries ───────────────────────────────────────────────────────────

    def unit_count(self) -> int:
        return len(self.sink.units)

    def event_count(self) -> int:
        return len(self.sink.events)

    def duplicate_units(self) -> List[str]:
        seen: Dict[str, int] = {}
        for unit in self.sink.units.values():
            key = f"{unit.candidate_id}|{unit.verification_id}|" \
                  f"{unit.content_hash}"
            seen[key] = seen.get(key, 0) + 1
        return sorted(k for k, v in seen.items() if v > 1)

    def duplicate_events(self) -> List[str]:
        seen: Dict[str, int] = {}
        for event in self.sink.events.values():
            key = f"{event.knowledge_unit_id}|{event.event_type}"
            seen[key] = seen.get(key, 0) + 1
        return sorted(k for k, v in seen.items() if v > 1)

    def orphan_events(self) -> List[str]:
        return sorted(e.id for e in self.sink.events.values()
                      if e.knowledge_unit_id not in self.sink.units)

    def reload(self) -> Dict[str, PersistedUnit]:
        """A later process reads what was written. Ids are unchanged."""
        return dict(self.sink.units)

    def traceability(self) -> Dict[str, object]:
        """unit -> verification -> candidate -> evidence -> source."""
        complete = 0
        for unit in self.sink.units.values():
            verification = self.vp.store.verifications.get(
                unit.verification_id)
            candidate = self.store.ku_candidates.get(unit.candidate_id)
            evidence = (self.store.evidence.get(candidate.evidence_id)
                        if candidate else None)
            if (verification is not None and candidate is not None
                    and evidence is not None
                    and verification.candidate_id == candidate.id
                    and evidence.source_version_id == unit.source_version_id
                    and evidence.source_version_id in self.store.source_versions):
                complete += 1
        total = len(self.sink.units)
        return {
            "units": total,
            "trace_complete": complete,
            "percent": round(100.0 * complete / total, 2) if total else 0.0,
            "unique_ids": len({u.id for u in self.sink.units.values()}),
        }


# ── SQL emission ─────────────────────────────────────────────────────────────

def _literal(value) -> str:
    if value is None:
        return "NULL"
    # A model field may hold an Enum; the column wants its value.
    if isinstance(value, Enum):
        value = value.value
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def emit_sql(units: Sequence[PersistedUnit],
             events: Sequence[FreezeEvent]) -> str:
    """The whole freeze as one SQL transaction.

    Every unit and every event go inside a single BEGIN/COMMIT, so a
    failure anywhere leaves the database exactly as it was: no unit
    without its event, and no event without its unit.

    `ON CONFLICT DO NOTHING` is what makes a replay a no-op at the
    database level rather than only in the writer.
    """
    lines = ["BEGIN;", "SET search_path TO stratum, public;"]
    for unit in units:
        columns = ("id", "candidate_id", "verification_id",
                   "source_version_id", "content_hash", "statement",
                   "canonical_text", "verification_score", "freeze_status",
                   "freeze_version", "title", "evidence_count", "frozen_at")
        # 073 requires frozen_at whenever the unit is FROZEN, so the row
        # carries the write time rather than NULL. The timestamp is the one
        # value here that is not content-derived; identity and the event
        # fingerprint do not depend on it, which is what keeps a replay a
        # no-op.
        frozen_at = ("NOW()" if unit.freeze_status
                     == PersistenceStatus.FROZEN.value else "NULL")
        values = ",".join(
            frozen_at if c == "frozen_at" else _literal(getattr(unit, c))
            for c in columns)
        lines.append(
            f"INSERT INTO knowledge_unit ({','.join(columns)}) "
            f"VALUES ({values}) ON CONFLICT (id) DO NOTHING;")
    for event in events:
        columns = ("id", "knowledge_unit_id", "event_type", "from_status",
                   "to_status", "event_hash")
        values = ",".join(_literal(getattr(event, c)) for c in columns)
        lines.append(
            f"INSERT INTO ku_freeze_event ({','.join(columns)}) "
            f"VALUES ({values}) "
            f"ON CONFLICT (knowledge_unit_id, event_type) DO NOTHING;")
    lines.append("COMMIT;")
    return "\n".join(lines) + "\n"


def sql_for_result(result: Dict) -> str:
    """The SQL a successful run would execute, in a stable order."""
    sink = result["sink"]
    units = [sink.units[k] for k in sorted(sink.units)]
    events = [sink.events[k] for k in sorted(sink.events)]
    return emit_sql(units, events)


def _insert(table: str, columns: Sequence[str], values: Sequence[str],
            conflict: str) -> str:
    return (f"INSERT INTO {table} ({','.join(columns)}) "
            f"VALUES ({','.join(values)}) ON CONFLICT ({conflict}) DO NOTHING;")


def emit_chain_sql(store, verification_pipeline, freeze_pipeline,
                   sink) -> str:
    """The whole A chain as one transaction.

    A knowledge unit cannot be written on its own: its foreign keys reach
    back through the verification, the candidate, the evidence, the
    reading run and the source version to the book. Every stage before
    P4.1 ran in memory, so the database has the schema and none of the
    rows. Writing only the unit would fail on its first foreign key.

    So the durable writer emits the ancestry it depends on, parents before
    children, inside the same BEGIN/COMMIT. ON CONFLICT DO NOTHING makes
    the whole script safe to re-run: the second execution writes nothing.
    """
    lines = ["BEGIN;", "SET search_path TO stratum, public;"]

    for key in sorted(store.book_sources):
        source = store.book_sources[key]
        lines.append(_insert(
            "book_source",
            ("id", "title", "author", "publisher", "isbn", "language",
             "metadata"),
            (_literal(source.id), _literal(source.title),
             _literal(source.author), _literal(source.publisher),
             _literal(source.isbn), _literal(source.language),
             _literal(store_metadata(store, source))),
            "id"))

    for key in sorted(store.source_versions):
        version = store.source_versions[key]
        lines.append(_insert(
            "source_version", ("id", "book_source_id", "version",
                               "file_hash", "storage_uri"),
            (_literal(version.id), _literal(version.book_source_id),
             _literal(version.version), _literal(version.file_hash),
             _literal(version.storage_uri)),
            "id"))

    for key in sorted(store.reading_runs):
        run = store.reading_runs[key]
        lines.append(_insert(
            "reading_run", ("id", "source_version_id", "status"),
            (_literal(run.id), _literal(run.source_version_id),
             _literal(run.status)),
            "id"))

    for key in sorted(store.evidence):
        evidence = store.evidence[key]
        lines.append(_insert(
            "reading_evidence", ("id", "reading_run_id", "page_number",
                                 "location", "content"),
            (_literal(evidence.id), _literal(evidence.reading_run_id),
             _literal(evidence.page_number),
             _literal(_json(evidence.locator)),
             _literal(evidence.content_span)),
            "id"))

    for key in sorted(store.quality):
        quality = store.quality[key]
        lines.append(_insert(
            "evidence_quality",
            ("id", "evidence_id", "source_trace_score", "locator_score",
             "completeness_score", "confidence_score", "quality_version"),
            (_literal(quality.id), _literal(quality.evidence_id),
             _literal(quality.source_trace_score), _literal(quality.locator_score),
             _literal(quality.completeness_score),
             _literal(quality.confidence_score),
             _literal(quality.quality_version)),
            "id"))

    for key in sorted(store.ku_candidates):
        candidate = store.ku_candidates[key]
        lines.append(_insert(
            "ku_candidate", ("id", "reading_run_id", "evidence_id", "content",
                             "candidate_type", "confidence", "classification"),
            (_literal(candidate.id), _literal(candidate.reading_run_id),
             _literal(candidate.evidence_id), _literal(candidate.content),
             _literal(candidate.candidate_type), _literal(candidate.confidence),
             _literal(candidate.classification)),
            "id"))

    for key in sorted(verification_pipeline.store.verifications):
        verification = verification_pipeline.store.verifications[key]
        lines.append(_insert(
            "ku_verification",
            ("id", "candidate_id", "verification_status", "verification_score",
             "definition_check", "trace_check", "source_check",
             "quality_check", "verified_quote", "verifier_version"),
            (_literal(verification.id), _literal(verification.candidate_id),
             _literal(verification.verification_status),
             _literal(verification.verification_score),
             _literal(verification.definition_check),
             _literal(verification.trace_check),
             _literal(verification.source_check),
             _literal(verification.quality_check),
             _literal(verification.verified_quote),
             _literal(verification.verifier_version)),
            "id"))

    units = [sink.units[k] for k in sorted(sink.units)]
    events = [sink.events[k] for k in sorted(sink.events)]
    # Reuse the unit/event statements without their own BEGIN and COMMIT:
    # this script is already inside one transaction.
    inner = emit_sql(units, events).splitlines()
    lines.extend(line for line in inner
                 if line.startswith("INSERT INTO"))
    lines.append("COMMIT;")
    return "\n".join(lines) + "\n"


def store_metadata(store, source) -> str:
    import json
    return json.dumps(getattr(source, "metadata", {}) or {},
                      ensure_ascii=False, sort_keys=True)


def _json(value) -> str:
    import json
    return json.dumps(value or {}, ensure_ascii=False, sort_keys=True)