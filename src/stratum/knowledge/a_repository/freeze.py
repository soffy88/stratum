"""A Repository P4 — Frozen Knowledge Unit.

    ReadingEvidence -> KU Candidate -> KU Verification -> Frozen KU

A frozen knowledge unit is a stable projection of a verified candidate:
something that can be cited by id. It is not a judgement that the world is
true, and it is not a concept. Grouping units into concepts belongs to a
later repository.

Authority priority:

    Evidence > Verification > Frozen KU

A frozen unit never outranks the evidence it came from, and never
outranks the verification that admitted it.

Freeze lifecycle:

    VERIFIED ──> FREEZE_PENDING ──> FROZEN   (terminal)
                      └──────────> REJECTED  (terminal)

Refused: FROZEN -> VERIFIED, FROZEN -> MODIFY, FROZEN -> DELETE.

Rules:
- content-derived identity: the same statement over the same evidence
  always yields the same unit id. Never a random UUID, never a sequence,
  never a timestamp.
- a unit is freezable only from a verification that passed.
- immutable: a frozen unit's statement, canonical text, evidence and
  verification are never rewritten. A correction is a new unit under a
  new freeze_version, not an update.
- idempotent: re-running freezes nothing twice.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from .verification import (
    VERIFICATION_THRESHOLD,
    VERIFIER_VERSION,
    VerificationStatus,
)


FREEZE_VERSION = "a-p4-v0.1"

#: A verification must reach this score before its unit may be frozen. The
#: same threshold P3 verified against — the freeze stage does not get to
#: be more forgiving than the verification it depends on.
FREEZE_SCORE_THRESHOLD = VERIFICATION_THRESHOLD


class FreezeStatus(str, Enum):
    """Terminal once frozen."""

    VERIFIED = "VERIFIED"
    FREEZE_PENDING = "FREEZE_PENDING"
    FROZEN = "FROZEN"
    REJECTED = "REJECTED"


#: The only legal transitions. FROZEN -> VERIFIED is absent by
#: construction, and FROZEN -> MODIFY does not exist as a state at all.
LEGAL_TRANSITIONS: Dict[FreezeStatus, frozenset] = {
    FreezeStatus.VERIFIED: frozenset({FreezeStatus.FREEZE_PENDING}),
    FreezeStatus.FREEZE_PENDING: frozenset(
        {FreezeStatus.FROZEN, FreezeStatus.REJECTED}),
    FreezeStatus.FROZEN: frozenset(),
    FreezeStatus.REJECTED: frozenset(),
}

TERMINAL_FREEZE_STATUSES = frozenset(
    {FreezeStatus.FROZEN, FreezeStatus.REJECTED}
)


class FreezeViolation(Exception):
    """Raised on a forbidden A仓 freeze operation."""


# ── identity ─────────────────────────────────────────────────────────────────

def content_hash(statement: str, evidence_fingerprint: str) -> str:
    """The unit's identity: sha256(statement + evidence fingerprint).

    The evidence fingerprint is part of the hash on purpose. The same
    proposition drawn from two different spans is two units, because a
    reader must be able to tell which span was actually read.
    """
    return hashlib.sha256(
        f"{statement}|{evidence_fingerprint}".encode("utf-8")).hexdigest()


def unit_id(statement: str, evidence_fingerprint: str) -> str:
    """`ku_<sha256 prefix>` — content-derived, never random."""
    return f"ku_{content_hash(statement, evidence_fingerprint)[:12]}"


def deterministic_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:12]}"


# ── model ────────────────────────────────────────────────────────────────────

@dataclass
class FrozenKnowledgeUnit:
    """Mirrors stratum.knowledge_unit, one row per frozen unit."""

    id: str
    verification_id: str
    candidate_id: str
    source_version_id: str
    title: str
    statement: str
    canonical_text: str
    evidence_count: int
    verification_score: float
    content_hash: str
    freeze_status: str
    freeze_version: str = FREEZE_VERSION
    evidence_ids: List[str] = field(default_factory=list)
    created_at: str = ""
    frozen_at: Optional[str] = None
    trace: Dict = field(default_factory=dict)


@dataclass
class FreezeEvent:
    stage: str
    run_id: str
    payload: Dict = field(default_factory=dict)


# ── pipeline ─────────────────────────────────────────────────────────────────

class AKnowledgeUnitFreezePipeline:
    """P4 freeze stage. Append-only and freeze-final."""

    def __init__(self, ingestion_pipeline, verification_pipeline,
                 event_sink=None):
        self.p = ingestion_pipeline
        self.store = ingestion_pipeline.store
        self.vp = verification_pipeline
        self.store.frozen_units: Dict[str, FrozenKnowledgeUnit] = {}
        self.store._unit_by_candidate: Dict[str, str] = {}
        self.store._unit_by_verification: Dict[str, str] = {}
        self._events: List[FreezeEvent] = []
        self._event_sink = event_sink or (lambda e: None)

    # ── GATE_2: verification gate ─────────────────────────────────────────

    def freezeable(self, verification_id: str
                   ) -> tuple:
        """A unit may only be frozen from a passed verification.

        Returns (ok, verification, reasons).
        """
        reasons: List[str] = []
        verification = self.vp.store.verifications.get(verification_id)
        if verification is None:
            return False, None, ["NO_SUCH_VERIFICATION"]
        if verification.verification_status != VerificationStatus.VERIFIED.value:
            reasons.append("VERIFICATION_NOT_VERIFIED")
        if verification.verification_score < FREEZE_SCORE_THRESHOLD:
            reasons.append("SCORE_BELOW_THRESHOLD")
        return not reasons, verification, reasons

    # ── content rules ─────────────────────────────────────────────────────

    def compose(self, verification) -> FrozenKnowledgeUnit:
        """Build the unit from the verification and its own chain.

        statement      the candidate's extracted proposition
        canonical_text the span the verification anchored to

        Both are copied, never generated. The freeze stage adds no wording
        of its own, so a frozen unit cannot say anything its evidence does
        not already say.
        """
        candidate = self.store.ku_candidates[verification.candidate_id]
        evidence = self.store.evidence[candidate.evidence_id]
        fingerprint = verification.trace.get("fingerprint", "")
        statement = candidate.content or ""
        digest = content_hash(statement, fingerprint)

        unit = FrozenKnowledgeUnit(
            id=f"ku_{digest[:12]}",
            verification_id=verification.id,
            candidate_id=candidate.id,
            source_version_id=evidence.source_version_id,
            title=self._title(statement, verification),
            statement=statement,
            canonical_text=verification.verified_quote or "",
            evidence_count=1,
            verification_score=verification.verification_score,
            content_hash=digest,
            freeze_status=FreezeStatus.VERIFIED.value,
            freeze_version=FREEZE_VERSION,
            evidence_ids=list(verification.trace.get("evidence_ids", [])),
            created_at=FREEZE_VERSION,
        )
        unit.trace = {
            "verification_id": verification.id,
            "candidate_id": candidate.id,
            "evidence_ids": unit.evidence_ids,
            "source_version_id": unit.source_version_id,
            "fingerprint": fingerprint,
            "required_slots": list(verification.trace.get("required_slots", [])),
            "freeze_version": FREEZE_VERSION,
        }
        return unit

    @staticmethod
    def _title(statement: str, verification) -> str:
        """A short label taken from the statement's own opening.

        Derived, never written: the first clause of the statement, cut at
        the first punctuation that ends a clause. A title that said
        something the evidence did not would be a second, unsourced claim.
        """
        head = statement.strip()
        for mark in ("：", ":", "，", ",", "。", "；", ";", "（", "("):
            index = head.find(mark)
            if index > 0:
                head = head[:index]
                break
        head = head.strip()
        return head[:40] if head else (verification.candidate_id[:12])

    # ── transitions ───────────────────────────────────────────────────────

    def transition(self, unit_id_: str, target: FreezeStatus) -> None:
        unit = self.store.frozen_units.get(unit_id_)
        if unit is None:
            raise FreezeViolation(f"Knowledge unit {unit_id_} does not exist.")
        current = FreezeStatus(unit.freeze_status)
        if target not in LEGAL_TRANSITIONS[current]:
            raise FreezeViolation(
                f"{current.value} -> {target.value} is not a legal "
                "transition; a frozen unit is final.")
        unit.freeze_status = target.value

    # ── FROZEN mutation policy ────────────────────────────────────────────

    def update_unit(self, unit_id_: str, **changes) -> None:
        """Refused always. A frozen unit is immutable."""
        unit = self.store.frozen_units.get(unit_id_)
        state = unit.freeze_status if unit else "MISSING"
        raise FreezeViolation(
            f"A knowledge unit cannot be updated (state {state}); a "
            "correction is a new unit under a new freeze_version, not an "
            "edit of this one.")

    def replace_evidence(self, unit_id_: str, *evidence_ids: str) -> None:
        raise FreezeViolation(
            "A frozen unit's evidence reference cannot be replaced.")

    def replace_verification(self, unit_id_: str, verification_id: str) -> None:
        raise FreezeViolation(
            "A frozen unit's verification cannot be replaced.")

    def delete_unit(self, unit_id_: str) -> None:
        raise FreezeViolation(
            "A frozen unit cannot be deleted; it is the stable projection "
            "other stages cite.")

    def unfreeze(self, unit_id_: str) -> None:
        raise FreezeViolation(
            "FROZEN -> VERIFIED is not a legal transition.")

    # ── the freeze ────────────────────────────────────────────────────────

    def has_unit(self, candidate_id: str) -> bool:
        return candidate_id in self.store._unit_by_candidate

    def freeze(self, verification_id: str) -> FrozenKnowledgeUnit:
        """Freeze one verified unit. Idempotent: a settled unit is
        returned unchanged."""
        settled = self.store._unit_by_verification.get(verification_id)
        if settled is not None:
            return self.store.frozen_units[settled]

        ok, verification, reasons = self.freezeable(verification_id)
        if not ok:
            raise FreezeViolation(
                f"Verification {verification_id} cannot be frozen: "
                f"{', '.join(reasons)}.")

        unit = self.compose(verification)
        run_id = self.store.ku_candidates[
            verification.candidate_id].reading_run_id
        self.store.frozen_units[unit.id] = unit
        self.store._unit_by_candidate[unit.candidate_id] = unit.id
        self.store._unit_by_verification[unit.verification_id] = unit.id

        self.transition(unit.id, FreezeStatus.FREEZE_PENDING)
        self._emit("freeze_pending", run_id,
                   {"unit_id": unit.id, "candidate_id": unit.candidate_id,
                    "status": unit.freeze_status})
        self.transition(unit.id, FreezeStatus.FROZEN)
        unit.frozen_at = FREEZE_VERSION
        self._emit("freeze", run_id,
                   {"unit_id": unit.id, "verification_id": verification_id,
                    "status": unit.freeze_status,
                    "verification_score": unit.verification_score})
        return unit

    def freeze_all(self, verification_ids: List[str]
                   ) -> List[FrozenKnowledgeUnit]:
        """Freeze every unit in a stable order (GATE_5 determinism)."""
        return [self.freeze(vid) for vid in sorted(verification_ids)]

    def freeze_verified(self, reading_run_id: str) -> List[FrozenKnowledgeUnit]:
        """Freeze exactly the units whose verification passed.

        A rejected verification is not an error here — it simply produces
        no unit, which is why the frozen count is bounded by the verified
        count rather than the candidate count.
        """
        verified = [
            v.id for v in self.vp.store.verifications.values()
            if v.verification_status == VerificationStatus.VERIFIED.value
            and v.candidate_id in self.store.ku_candidates
            and self.store.ku_candidates[v.candidate_id].reading_run_id
            == reading_run_id
        ]
        return self.freeze_all(verified)

    # ── queries ───────────────────────────────────────────────────────────

    def _units(self, reading_run_id: str):
        return [u for u in self.store.frozen_units.values()
                if u.candidate_id in self.store.ku_candidates
                and self.store.ku_candidates[u.candidate_id].reading_run_id
                == reading_run_id]

    def unit_count(self, reading_run_id: str) -> int:
        return len(self._units(reading_run_id))

    def frozen_count(self, reading_run_id: str) -> int:
        return sum(1 for u in self._units(reading_run_id)
                   if u.freeze_status == FreezeStatus.FROZEN.value)

    def status_breakdown(self, reading_run_id: str) -> Dict[str, int]:
        counts = {s.value: 0 for s in FreezeStatus}
        for unit in self._units(reading_run_id):
            counts[unit.freeze_status] += 1
        return dict(sorted(counts.items()))

    def verified_input(self, reading_run_id: str) -> int:
        """How many verifications were presented to the freeze stage."""
        return sum(
            1 for v in self.vp.store.verifications.values()
            if v.candidate_id in self.store.ku_candidates
            and self.store.ku_candidates[v.candidate_id].reading_run_id
            == reading_run_id)

    def rejected_input(self, reading_run_id: str) -> int:
        return sum(
            1 for v in self.vp.store.verifications.values()
            if v.verification_status == VerificationStatus.REJECTED.value
            and v.candidate_id in self.store.ku_candidates
            and self.store.ku_candidates[v.candidate_id].reading_run_id
            == reading_run_id)

    def traceability(self, reading_run_id: str) -> Dict[str, object]:
        """GATE_4 — unit -> verification -> candidate -> evidence -> source."""
        units = self._units(reading_run_id)
        complete = 0
        for unit in units:
            verification = self.vp.store.verifications.get(unit.verification_id)
            candidate = self.store.ku_candidates.get(unit.candidate_id)
            evidence = (self.store.evidence.get(candidate.evidence_id)
                        if candidate else None)
            if (verification is not None and candidate is not None
                    and evidence is not None
                    and verification.candidate_id == candidate.id
                    and candidate.evidence_id == evidence.id
                    and evidence.source_version_id == unit.source_version_id
                    and evidence.source_version_id in self.store.source_versions):
                complete += 1
        return {
            "units": len(units),
            "trace_complete": complete,
            "percent": round(100.0 * complete / len(units), 2) if units else 0.0,
            "unique_ids": len({u.id for u in units}),
            "unique_content_hashes": len({u.content_hash for u in units}),
        }

    def orphan_units(self) -> List[str]:
        return [u.id for u in self.store.frozen_units.values()
                if u.candidate_id not in self.store.ku_candidates
                or u.verification_id not in self.vp.store.verifications]

    def unanchored_units(self) -> List[str]:
        """A frozen unit must carry the span that anchored it."""
        return [u.id for u in self.store.frozen_units.values()
                if not u.canonical_text]

    # ── events ────────────────────────────────────────────────────────────

    @property
    def events(self) -> List[FreezeEvent]:
        return list(self._events)

    def _emit(self, stage: str, run_id: str, payload: Dict) -> None:
        event = FreezeEvent(stage=stage, run_id=run_id, payload=payload)
        self._events.append(event)
        self._event_sink(event)