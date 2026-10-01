"""A Repository P3 — Knowledge Unit Verification.

Chain:

    ReadingEvidence -> EvidenceQuality -> KU Candidate -> KU Verified

A candidate becomes a verified knowledge unit only when its own evidence
chain and the four recorded checks say so.

    Evidence > Candidate > Verification

A verdict never outranks its evidence, a human never overrides evidence,
and nothing automatically combines candidates. The decision is the
product of the candidate, its evidence chain and the checks below.

State machine:

    PENDING ──> VERIFYING ──> VERIFIED   (terminal)
                   └───────> REJECTED   (terminal)

Refused: VERIFIED -> REJECTED, VERIFIED -> PENDING, REJECTED -> VERIFIED.

Rules:
- resumable: a decided candidate is never re-decided.
- idempotent: re-running produces no new rows.
- deterministic: same inputs, same id, same score, same verdict.
- append only: a settled verdict is never rewritten.
- anchored: the quote must occur inside the evidence content. A
  generated or paraphrased quote is never stored as verified.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from .types import KIClassification, PipelineStage


VERIFIER_VERSION = "a-p3-v0.1"
VERIFICATION_METHOD = "evidence_chain_checks"

#: GATE_3 — a verdict of VERIFIED requires the weakest of the four checks
#: to reach this threshold.
VERIFICATION_THRESHOLD = 0.8


class VerificationStatus(str, Enum):
    """Four states, one path out of PENDING."""

    PENDING = "PENDING"
    VERIFYING = "VERIFYING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


#: The only legal transitions. VERIFIED -> REJECTED, VERIFIED -> PENDING
#: and REJECTED -> VERIFIED are absent by construction.
LEGAL_TRANSITIONS: Dict[VerificationStatus, frozenset] = {
    VerificationStatus.PENDING: frozenset({VerificationStatus.VERIFYING}),
    VerificationStatus.VERIFYING: frozenset(
        {VerificationStatus.VERIFIED, VerificationStatus.REJECTED}),
    VerificationStatus.VERIFIED: frozenset(),
    VerificationStatus.REJECTED: frozenset(),
}

TERMINAL_STATUSES = frozenset(
    {VerificationStatus.VERIFIED, VerificationStatus.REJECTED}
)


# ── semantic integrity vocabulary ─────────────────────────────────────────────
# A predicate marker is a relation word: what makes a span a proposition
# rather than a noun phrase. Longest match wins at the leftmost position.
PREDICATE_MARKERS: Tuple[str, ...] = (
    "确定为", "早于", "晚于", "仿效", "模仿", "取消", "废除", "禁止", "允许",
    "要求", "防止", "免除", "终止", "开启", "起源", "制订", "造成", "导致",
    "出现", "得到", "成为", "受到", "规定", "保护", "计算", "达到", "应用",
    "开始", "包括", "限制", "处以", "爆发", "是", "为", "有", "超过",
)

#: A definition marker introduces a span that says what a thing IS. Without
#: one a span asserts something but defines nothing.
DEFINITION_MARKERS: Tuple[str, ...] = (
    "是指", "所谓", "定义为", "意思是", "含义是", "称为", "叫做",
)

TIME_MARKERS: Tuple[str, ...] = (
    "公元前", "世纪", "年代", "时期", "时代", "当时", "年",
)

ACTOR_MARKERS: Tuple[str, ...] = (
    "国王", "法典", "罗马", "巴比伦", "雅典", "索伦", "政府", "官员",
    "债权人", "债主",
)


def deterministic_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:12]}"


def candidate_fingerprint(candidate, evidence) -> str:
    """GATE_5 identity: source version + reading run + the candidate's own
    text. A change to any of them is a different unit, not a duplicate."""
    locator = (evidence.locator or {}) if evidence is not None else {}
    return hashlib.sha256("|".join([
        evidence.source_version_id if evidence is not None else "",
        candidate.reading_run_id,
        candidate.evidence_id,
        candidate.source_span or "",
        candidate.content or "",
        candidate.classification or "",
        locator.get("content_hash", ""),
    ]).encode("utf-8")).hexdigest()


def _first_marker(text: str, markers: Tuple[str, ...]) -> Optional[Tuple[int, str]]:
    hits = [(text.find(m), m) for m in markers if text.find(m) >= 0]
    if not hits:
        return None
    leftmost = min(i for i, _ in hits)
    longest = max((m for i, m in hits if i == leftmost), key=len)
    return leftmost, longest


def split_proposition(text: str) -> Tuple[str, str, str]:
    """Split a candidate into (subject, predicate, object).

    The marker is the relation; what sits either side is subject and
    object. A span with no marker yields two empty sides, which is exactly
    how a noun phrase fails the check.
    """
    found = _first_marker(text, PREDICATE_MARKERS)
    if found is None:
        return "", "", ""
    index, marker = found
    return text[:index].strip(), marker, text[index + len(marker):].strip()


def find_definition_span(text: str) -> str:
    """The span a candidate uses to define its referent, or ""."""
    for marker in sorted(DEFINITION_MARKERS, key=len, reverse=True):
        index = text.find(marker)
        if index >= 0:
            return text[index:].strip()
    return ""


# ── model ────────────────────────────────────────────────────────────────────

@dataclass
class SemanticIntegrity:
    """GATE_4 — whether the candidate is anchored in its own evidence."""

    anchored: bool = False
    subject: str = ""
    predicate: str = ""
    object: str = ""
    definition_span: str = ""
    actor: str = ""
    time: str = ""
    action: str = ""

    def slots(self) -> Dict[str, bool]:
        return {
            "ANCHORED": self.anchored,
            "SUBJECT": bool(self.subject),
            "PREDICATE": bool(self.predicate),
            "OBJECT": bool(self.object),
            "DEFINITION_SPAN": bool(self.definition_span),
            "ACTOR": bool(self.actor),
            "TIME": bool(self.time),
            "ACTION": bool(self.action),
        }


@dataclass
class KnowledgeUnitVerification:
    """Mirrors stratum.ku_verification, one row per decision."""

    id: str
    candidate_id: str
    verification_status: str
    verification_score: float
    definition_check: bool
    trace_check: bool
    source_check: bool
    quality_check: bool
    verified_quote: Optional[str]
    verifier_version: str = VERIFIER_VERSION
    verification_method: str = VERIFICATION_METHOD
    trace: Dict = field(default_factory=dict)


@dataclass
class VerificationEvent:
    stage: PipelineStage
    run_id: str
    payload: Dict = field(default_factory=dict)


class VerificationViolation(Exception):
    """Raised on a forbidden A仓 verification operation."""


# ── pipeline ─────────────────────────────────────────────────────────────────

class AVerificationPipeline:
    """P3 verification stage. Append-only and decision-final."""

    def __init__(self, ingestion_pipeline, quality_pipeline=None,
                 event_sink=None):
        self.p = ingestion_pipeline
        self.store = ingestion_pipeline.store
        self.qp = quality_pipeline
        self.store.verifications: Dict[str, KnowledgeUnitVerification] = {}
        self.store._verification_by_candidate: Dict[str, str] = {}
        self._events: List[VerificationEvent] = []
        self._event_sink = event_sink or (lambda e: None)

    # ── GATE_4: anchor verification ───────────────────────────────────────

    @staticmethod
    def is_anchored(candidate, evidence) -> bool:
        """The quote must occur inside the evidence content.

        This is the whole anchoring guarantee. A generated quote, a
        summary standing in for the original text, or a paraphrase that is
        not a substring all fail here.
        """
        quote = candidate.source_span or ""
        content = (evidence.content_span or "") if evidence else ""
        return bool(quote) and quote in content

    # ── the four checks ───────────────────────────────────────────────────

    @staticmethod
    def required_slots(kind: str) -> Tuple[str, ...]:
        return {
            KIClassification.FACT.value: ("ANCHORED", "SUBJECT", "PREDICATE", "OBJECT"),
            KIClassification.RELATION.value: ("ANCHORED", "SUBJECT", "PREDICATE", "OBJECT"),
            KIClassification.CONCEPT.value: ("ANCHORED", "DEFINITION_SPAN"),
            KIClassification.EVENT.value: ("ANCHORED", "ACTOR", "TIME", "ACTION"),
            KIClassification.ARGUMENT.value: ("ANCHORED", "DEFINITION_SPAN"),
        }.get(kind, ("ANCHORED",))

    @classmethod
    def check_semantic_integrity(cls, candidate, evidence) -> SemanticIntegrity:
        kind = candidate.classification or KIClassification.CONCEPT.value
        quote = candidate.source_span or ""
        anchored = cls.is_anchored(candidate, evidence)
        text = candidate.content or quote

        def resolve(source: str) -> SemanticIntegrity:
            subject, predicate, obj = split_proposition(source)
            return SemanticIntegrity(
                anchored=anchored, subject=subject, predicate=predicate,
                object=obj, definition_span=find_definition_span(source),
                actor=next((m for m in ACTOR_MARKERS if m in source), ""),
                time=next((m for m in TIME_MARKERS if m in source), ""),
                action=predicate or obj)

        primary = resolve(text)
        if primary.predicate or primary.definition_span:
            return primary
        fallback = resolve(quote)
        return fallback if (fallback.predicate
                           or fallback.definition_span) else primary

    @classmethod
    def definition_score(cls, candidate, evidence) -> Tuple[float, SemanticIntegrity]:
        """Satisfied required slots / required slots."""
        kind = candidate.classification or KIClassification.CONCEPT.value
        integrity = cls.check_semantic_integrity(candidate, evidence)
        required = cls.required_slots(kind)
        present = integrity.slots()
        satisfied = sum(1 for slot in required if present.get(slot))
        return satisfied / len(required), integrity

    def trace_score(self, candidate, evidence) -> float:
        """candidate -> evidence -> reading run."""
        checks = [
            bool(candidate.evidence_id),
            evidence is not None,
            bool(evidence is not None and evidence.reading_run_id),
            bool(evidence is not None
                 and evidence.reading_run_id in self.store.reading_runs),
        ]
        return sum(checks) / len(checks)

    def source_score(self, evidence) -> float:
        """evidence -> source version -> addressable position."""
        locator = (evidence.locator or {}) if evidence else {}
        checks = [
            bool(evidence is not None and evidence.source_version_id),
            bool(evidence is not None
                 and evidence.source_version_id in self.store.source_versions),
            bool(locator.get("content_hash")),
            bool(locator.get("logical_locator") or locator.get("physical_locator")),
        ]
        return sum(checks) / len(checks)

    @staticmethod
    def quality_score(quality: Optional[Dict]) -> float:
        """The weakest of the P2 scores decides."""
        if not quality:
            return 0.0
        scores = [quality.get(k) for k in (
            "source_trace_score", "locator_score",
            "completeness_score", "confidence_score")]
        present = [s for s in scores if s is not None]
        return min(present) if present else 0.0

    @staticmethod
    def verification_score(definition: float, trace: float, source: float,
                           quality: float) -> float:
        """GATE_3 — the minimum of the four checks."""
        return min(definition, trace, source, quality)

    # ── GATE_2: candidate integrity ───────────────────────────────────────

    def load_candidate(self, candidate_id: str) -> Tuple[object, object, Dict]:
        """Resolve a candidate to itself, its evidence and its quality row.

        Everything a decision may rely on is returned here, so no stage can
        reach for an input outside the evidence chain.
        """
        candidate = self.store.ku_candidates.get(candidate_id)
        if candidate is None:
            raise VerificationViolation(
                f"Candidate {candidate_id} does not exist.")
        evidence = self.store.evidence.get(candidate.evidence_id)
        if evidence is None:
            raise VerificationViolation(
                f"Candidate {candidate_id} has no evidence; a decision "
                "requires evidence.")
        quality = self.store.quality.get(
            self.store._quality_by_evidence.get(candidate.evidence_id, ""))
        return candidate, evidence, (dict(quality.__dict__) if quality else {})

    @staticmethod
    def candidate_is_complete(candidate, evidence) -> Tuple[bool, List[str]]:
        """evidence_id, source_span and a resolvable content hash."""
        missing = []
        if not candidate.evidence_id:
            missing.append("NO_EVIDENCE_ID")
        if not candidate.source_span:
            missing.append("NO_SOURCE_SPAN")
        if not ((evidence.locator or {}).get("content_hash") if evidence else None):
            missing.append("NO_CONTENT_HASH")
        return not missing, missing

    # ── transitions ───────────────────────────────────────────────────────

    def _open(self, candidate_id: str, verification_id: Optional[str] = None
              ) -> KnowledgeUnitVerification:
        """Record a PENDING task, then move it to VERIFYING."""
        verification = KnowledgeUnitVerification(
            id=verification_id or deterministic_id(
                "kv", candidate_id, VERIFIER_VERSION),
            candidate_id=candidate_id,
            verification_status=VerificationStatus.PENDING.value,
            verification_score=0.0,
            definition_check=False, trace_check=False,
            source_check=False, quality_check=False,
            verified_quote=None,
        )
        self.store.verifications[verification.id] = verification
        self.store._verification_by_candidate[candidate_id] = verification.id
        self.transition(verification.id, VerificationStatus.VERIFYING)
        return verification

    def transition(self, verification_id: str, target: VerificationStatus
                   ) -> None:
        """The only way a verification changes state."""
        verification = self.store.verifications.get(verification_id)
        if verification is None:
            raise VerificationViolation(
                f"Verification {verification_id} does not exist.")
        current = VerificationStatus(verification.verification_status)
        if target not in LEGAL_TRANSITIONS[current]:
            raise VerificationViolation(
                f"{current.value} -> {target.value} is not a legal "
                "transition; a settled verdict is final.")
        verification.verification_status = target.value

    def reject_verified(self, verification_id: str) -> None:
        raise VerificationViolation(
            "A verified unit cannot be rejected; the verdict is final.")

    def reopen(self, verification_id: str) -> None:
        raise VerificationViolation(
            "A verification cannot return to PENDING; the verdict is final.")

    def overturn(self, verification_id: str) -> None:
        raise VerificationViolation(
            "A rejected candidate cannot become verified; the verdict "
            "is final.")

    # ── the decision ──────────────────────────────────────────────────────

    def has_verification(self, candidate_id: str) -> bool:
        return candidate_id in self.store._verification_by_candidate

    def verify(self, candidate_id: str,
               verification_id: Optional[str] = None
               ) -> KnowledgeUnitVerification:
        """GATE_2 -> GATE_3 -> GATE_4 for one candidate. Idempotent: a
        decided candidate is returned unchanged."""
        settled = self.store._verification_by_candidate.get(candidate_id)
        if settled is not None:
            return self.store.verifications[settled]

        candidate, evidence, quality = self.load_candidate(candidate_id)
        run_id = candidate.reading_run_id
        verification = self._open(candidate_id, verification_id)

        complete, missing = self.candidate_is_complete(candidate, evidence)
        self._emit("candidate", run_id,
                   {"candidate_id": candidate_id,
                    "status": VerificationStatus.VERIFYING.value})

        definition, integrity = self.definition_score(candidate, evidence)
        trace = self.trace_score(candidate, evidence)
        source = self.source_score(evidence)
        quality_value = self.quality_score(quality)
        score = self.verification_score(definition, trace, source, quality_value)

        checks = {
            "definition_check": definition >= VERIFICATION_THRESHOLD,
            "trace_check": trace >= VERIFICATION_THRESHOLD,
            "source_check": source >= VERIFICATION_THRESHOLD,
            "quality_check": quality_value >= VERIFICATION_THRESHOLD,
        }
        verification.definition_check = checks["definition_check"]
        verification.trace_check = checks["trace_check"]
        verification.source_check = checks["source_check"]
        verification.quality_check = checks["quality_check"]
        verification.verification_score = score
        # The quote is stored only when it was found in the evidence.
        verification.verified_quote = (
            candidate.source_span if integrity.anchored else None)

        failed = sorted(k for k, ok in checks.items() if not ok)
        if not complete:
            failed.extend(missing)

        target = (VerificationStatus.VERIFIED
                  if not failed and score >= VERIFICATION_THRESHOLD
                  else VerificationStatus.REJECTED)
        self.transition(verification.id, target)

        kind = candidate.classification
        verification.trace = {
            "candidate_id": candidate_id,
            "fingerprint": candidate_fingerprint(candidate, evidence),
            "evidence_ids": [candidate.evidence_id],
            "classification": kind,
            "required_slots": list(self.required_slots(kind)),
            "slots_present": sorted(k for k, v in integrity.slots().items() if v),
            "scores": {"definition": definition, "trace": trace,
                       "source": source, "quality": quality_value},
            "failed_checks": failed,
            "verifier_version": VERIFIER_VERSION,
        }

        self._emit("verify", run_id,
                   {"candidate_id": candidate_id,
                    "verification_id": verification.id,
                    "status": target.value,
                    "verification_score": score,
                    "failed_checks": failed})
        return verification

    def verify_all(self, candidate_ids: List[str]) -> List[KnowledgeUnitVerification]:
        """Decide every candidate in a stable order (GATE_5 determinism)."""
        return [self.verify(cid) for cid in sorted(candidate_ids)]

    # ── queries ───────────────────────────────────────────────────────────

    def _candidates(self, reading_run_id: str):
        return [k for k in self.store.ku_candidates.values()
                if k.reading_run_id == reading_run_id]

    def verification_count(self, reading_run_id: str) -> int:
        return sum(1 for v in self.store.verifications.values()
                   if v.candidate_id in self.store.ku_candidates
                   and self.store.ku_candidates[v.candidate_id].reading_run_id
                   == reading_run_id)

    def _count(self, reading_run_id: str, status: VerificationStatus) -> int:
        return sum(
            1 for v in self.store.verifications.values()
            if v.candidate_id in self.store.ku_candidates
            and self.store.ku_candidates[v.candidate_id].reading_run_id
            == reading_run_id
            and v.verification_status == status.value)

    def verified_count(self, reading_run_id: str) -> int:
        return self._count(reading_run_id, VerificationStatus.VERIFIED)

    def rejected_count(self, reading_run_id: str) -> int:
        return self._count(reading_run_id, VerificationStatus.REJECTED)

    def status_breakdown(self, reading_run_id: str) -> Dict[str, int]:
        counts = {s.value: 0 for s in VerificationStatus}
        for verification in self.store.verifications.values():
            candidate = self.store.ku_candidates.get(verification.candidate_id)
            if candidate is None or candidate.reading_run_id != reading_run_id:
                continue
            counts[verification.verification_status] += 1
        return dict(sorted(counts.items()))

    def false_positives(self, reading_run_id: str) -> List[str]:
        """GATE_3/GATE_4 — a verified unit that is not anchored, or that
        carries any failed check, is a false positive."""
        offenders = []
        for verification in self.store.verifications.values():
            if verification.verification_status != VerificationStatus.VERIFIED.value:
                continue
            candidate = self.store.ku_candidates.get(verification.candidate_id)
            if candidate is None or candidate.reading_run_id != reading_run_id:
                continue
            if not verification.verified_quote:
                offenders.append(verification.candidate_id)
            elif verification.verification_score < VERIFICATION_THRESHOLD:
                offenders.append(verification.candidate_id)
            elif not all((verification.definition_check,
                          verification.trace_check,
                          verification.source_check,
                          verification.quality_check)):
                offenders.append(verification.candidate_id)
        return offenders

    def rejection_reasons(self, reading_run_id: str) -> Dict[str, List[str]]:
        reasons = {}
        for verification in self.store.verifications.values():
            candidate = self.store.ku_candidates.get(verification.candidate_id)
            if candidate is None or candidate.reading_run_id != reading_run_id:
                continue
            if verification.verification_status != VerificationStatus.REJECTED.value:
                continue
            reasons[verification.candidate_id] = list(
                verification.trace.get("failed_checks", []))
        return dict(sorted(reasons.items()))

    def traceability(self, reading_run_id: str) -> Dict[str, object]:
        """GATE_2 — candidate -> evidence -> source, counted."""
        candidates = self._candidates(reading_run_id)
        complete = 0
        fingerprints = set()
        for candidate in candidates:
            evidence = self.store.evidence.get(candidate.evidence_id)
            ok, _ = self.candidate_is_complete(candidate, evidence)
            if ok and evidence is not None:
                complete += 1
                fingerprints.add(candidate_fingerprint(candidate, evidence))
        return {
            "candidates": len(candidates),
            "traceable": complete,
            "percent": round(100.0 * complete / len(candidates), 2)
            if candidates else 0.0,
            "unique_fingerprints": len(fingerprints),
            "duplicates": len(candidates) - len(fingerprints),
        }

    def orphan_verifications(self) -> List[str]:
        return [v.id for v in self.store.verifications.values()
                if v.candidate_id not in self.store.ku_candidates]

    # ── events ────────────────────────────────────────────────────────────

    @property
    def events(self) -> List[VerificationEvent]:
        return list(self._events)

    def _emit(self, stage: str, run_id: str, payload: Dict) -> None:
        event = VerificationEvent(stage=stage, run_id=run_id, payload=payload)
        self._events.append(event)
        self._event_sink(event)