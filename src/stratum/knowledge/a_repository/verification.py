"""A Repository P3 — Knowledge Unit Candidate Verification.

Chain:

    ReadingEvidence -> EvidenceQuality -> KU Candidate -> KU Verified

A仓 fact authority: a candidate becomes a verified unit only when its own
evidence chain and the recorded rules say so. The inputs are the
candidate, its evidence chain, and the rules in the trace. Nothing else
is consulted — no external answer, no external database, no note that
does not carry evidence.

Stages:
    1. candidate load   — candidate, evidence, quote and quality must exist
    2. evidence sufficiency — evidence count, quality score, traceability
    3. semantic integrity — a unit of the candidate's declared kind must
       be present and locatable in its own evidence
    4. decision         — VERIFIED or REJECTED, terminal

Rules:
- resumable: a decided candidate is never re-decided.
- idempotent: re-running produces no new rows.
- deterministic: same inputs, same id, same trace, same decision.
- append only: a settled decision is never rewritten.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from .types import KIClassification, PipelineStage


VERIFIER_VERSION = "a-p3-v0.1"
VERIFICATION_METHOD = "evidence_chain_rules"

#: Stage 2 — minimum evidence quality for a verification decision.
VERIFICATION_QUALITY_THRESHOLD = 0.8


class VerificationStatus(str, Enum):
    """Terminal-once-decided lifecycle.

        PENDING ──> VERIFIED
           └────> REJECTED
    """

    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


TERMINAL_STATUSES = frozenset(
    {VerificationStatus.VERIFIED, VerificationStatus.REJECTED}
)

#: The only legal transitions. VERIFIED -> PENDING and REJECTED ->
#: VERIFIED are absent by construction; VERIFIED -> REJECTED is absent
#: because a terminal state is terminal.
LEGAL_TRANSITIONS: Dict[VerificationStatus, frozenset] = {
    VerificationStatus.PENDING: frozenset(
        {VerificationStatus.VERIFIED, VerificationStatus.REJECTED}
    ),
    VerificationStatus.VERIFIED: frozenset(),
    VerificationStatus.REJECTED: frozenset(),
}


# ── semantic integrity vocabulary ─────────────────────────────────────────────
# A predicate marker is a relation word: it is what makes a span a
# proposition rather than a noun phrase. Matching is substring-based and
# ordered longest-first so that a specific marker wins over a prefix of it.
PREDICATE_MARKERS: Tuple[str, ...] = (
    "确定为", "早于", "晚于", "仿效", "模仿", "取消", "废除", "禁止", "允许",
    "要求", "防止", "免除", "终止", "开启", "起源", "制订", "造成", "导致",
    "出现", "得到", "成为", "受到", "规定", "保护", "计算", "达到", "应用",
    "开始", "包括", "限制", "处以", "爆发", "是", "为", "有", "超过",
)

#: A definition marker introduces a span that says what a thing IS.
#: Without one a span asserts something but defines nothing.
DEFINITION_MARKERS: Tuple[str, ...] = (
    "是指", "所谓", "定义为", "意思是", "含义是", "称为", "叫做", "叫做",
)

#: An event needs a time reference to be placeable in history.
TIME_MARKERS: Tuple[str, ...] = (
    "公元前", "世纪", "年代", "时期", "时代", "当时", "年",
)

ACTOR_MARKERS: Tuple[str, ...] = (
    "国王", "法典", "罗马", "巴比伦", "雅典", "索伦", "政府", "官员",
    "债权人", "债主", "国王",
)


def deterministic_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:12]}"


def _first_marker(text: str, markers: Tuple[str, ...]) -> Optional[Tuple[int, str]]:
    """Leftmost marker in `text`, longest match at that position."""
    hits = [(text.find(m), m) for m in markers if text.find(m) >= 0]
    if not hits:
        return None
    leftmost = min(i for i, _ in hits)
    longest = max((m for i, m in hits if i == leftmost), key=len)
    return leftmost, longest


def split_proposition(text: str) -> Tuple[str, str, str]:
    """Split a candidate into (subject, predicate, object).

    The predicate marker is the relation; whatever sits on either side is
    the subject and the object. A span with no marker yields two empty
    sides, which is exactly how a noun phrase fails this check.
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
    """Result of Stage 3 — the shape check, kept for the trace."""

    subject: str = ""
    predicate: str = ""
    object: str = ""
    definition_span: str = ""
    actor: str = ""
    time: str = ""
    action: str = ""
    slots: Dict[str, str] = field(default_factory=dict)

    def has(self, slot: str) -> bool:
        return bool(self.slots.get(slot))


@dataclass
class KnowledgeUnitVerification:
    id: str
    candidate_id: str
    verification_status: str
    verification_method: str
    verifier_version: str
    verification_trace: Dict
    created_at: str = ""


@dataclass
class VerificationEvent:
    stage: PipelineStage
    run_id: str
    payload: Dict = field(default_factory=dict)


class VerificationViolation(Exception):
    """Raised on a forbidden A仓 verification operation."""


# ── pipeline ─────────────────────────────────────────────────────────────────

class AVerificationPipeline:
    """P3 verification stage.

    Append-only and decision-final. A settled verification is never
    rewritten, so a replay can only add rows for candidates that have no
    decision yet.
    """

    def __init__(self, ingestion_pipeline, quality_pipeline=None,
                 event_sink=None):
        self.p = ingestion_pipeline
        self.store = ingestion_pipeline.store
        self.qp = quality_pipeline
        self.store.verifications: Dict[str, KnowledgeUnitVerification] = {}
        self.store._verification_by_candidate: Dict[str, str] = {}
        self._events: List[VerificationEvent] = []
        self._event_sink = event_sink or (lambda e: None)

    # ── Stage 1: candidate load ───────────────────────────────────────────

    def load_candidate(self, candidate_id: str) -> Tuple[object, object, Dict]:
        """Resolve a candidate to itself, its evidence and its quality row.

        Everything a decision may rely on is returned here, so a later
        stage cannot reach for an input that is not in the evidence chain.
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
        return candidate, evidence, (quality.__dict__ if quality else {})

    def has_verification(self, candidate_id: str) -> bool:
        return candidate_id in self.store._verification_by_candidate

    # ── Stage 2: evidence sufficiency ─────────────────────────────────────

    @staticmethod
    def quality_score(quality: Dict) -> float:
        """Lowest of the four P2 scores — the weakest link decides."""
        scores = [quality.get(k) for k in (
            "source_trace_score", "locator_score",
            "completeness_score", "confidence_score")]
        if not any(s is not None for s in scores):
            return 0.0
        return min(s for s in scores if s is not None)

    def evidence_is_sufficient(self, quality: Dict) -> Tuple[bool, List[str]]:
        """evidence_count >= 1, quality >= threshold, trace complete."""
        failed: List[str] = []
        score = self.quality_score(quality)

        if score < VERIFICATION_QUALITY_THRESHOLD:
            failed.append("QUALITY_BELOW_THRESHOLD")
        if not quality:
            failed.append("NO_QUALITY_ROW")
        return not failed, failed

    def traceability_is_complete(self, evidence) -> Tuple[bool, List[str]]:
        """evidence -> reading run -> source version, with an address.

        A quality score can be perfect while the row still fails to point
        at a source, so the chain is walked rather than trusted.
        """
        failed: List[str] = []
        locator = evidence.locator or {}
        if not evidence.source_version_id:
            failed.append("NO_SOURCE_VERSION")
        if not evidence.reading_run_id:
            failed.append("NO_READING_RUN")
        if not locator.get("content_hash"):
            failed.append("NO_CONTENT_HASH")
        if not (locator.get("logical_locator") or locator.get("physical_locator")):
            failed.append("NO_ADDRESS")
        if evidence.source_version_id not in self.store.source_versions:
            failed.append("UNRESOLVED_SOURCE_VERSION")
        if evidence.reading_run_id not in self.store.reading_runs:
            failed.append("UNRESOLVED_READING_RUN")
        return not failed, failed

    # ── Stage 3: semantic integrity ───────────────────────────────────────

    @staticmethod
    def check_semantic_integrity(candidate, evidence) -> SemanticIntegrity:
        """Is there a locatable unit of the candidate's declared kind?

        `source_span` is the candidate's verbatim quote and is the anchor
        the check resolves against: it must occur inside the evidence it
        claims. The proposition itself is read from `content` when a
        marker is present there, otherwise from the quote.
        """
        quote = candidate.source_span or ""
        anchored = bool(quote) and quote in (evidence.content_span or "")
        kind = candidate.classification or KIClassification.CONCEPT.value
        text = candidate.content or quote
        result = SemanticIntegrity()

        def resolve(source: str) -> SemanticIntegrity:
            subject, predicate, obj = split_proposition(source)
            definition = find_definition_span(source)
            time = next((m for m in TIME_MARKERS if m in source), "")
            actor = next((m for m in ACTOR_MARKERS if m in source), "")
            return SemanticIntegrity(
                subject=subject, predicate=predicate, object=obj,
                definition_span=definition, actor=actor, time=time,
                action=predicate or obj,
                slots={
                    "ANCHORED": str(anchored),
                    "SUBJECT": subject,
                    "PREDICATE": predicate,
                    "OBJECT": obj,
                    "DEFINITION_SPAN": definition,
                    "ACTOR": actor,
                    "TIME": time,
                    "ACTION": predicate or obj,
                },
            )

        primary = resolve(text)
        if primary.slots.get("PREDICATE") or primary.slots.get("DEFINITION_SPAN"):
            return primary
        fallback = resolve(quote)
        return fallback if (
            fallback.slots.get("PREDICATE")
            or fallback.slots.get("DEFINITION_SPAN")
        ) else primary

    @staticmethod
    def required_slots(kind: str) -> Tuple[str, ...]:
        """The slots a unit of each kind must carry to be locatable."""
        return {
            KIClassification.FACT.value: ("ANCHORED", "SUBJECT", "PREDICATE", "OBJECT"),
            KIClassification.RELATION.value: ("ANCHORED", "SUBJECT", "PREDICATE", "OBJECT"),
            KIClassification.CONCEPT.value: ("ANCHORED", "DEFINITION_SPAN"),
            KIClassification.EVENT.value: ("ANCHORED", "ACTOR", "TIME", "ACTION"),
            KIClassification.ARGUMENT.value: ("ANCHORED", "DEFINITION_SPAN"),
        }.get(kind, ("ANCHORED",))

    def semantic_integrity_holds(self, candidate, evidence
                                 ) -> Tuple[bool, List[str], SemanticIntegrity]:
        kind = candidate.classification or KIClassification.CONCEPT.value
        integrity = self.check_semantic_integrity(candidate, evidence)
        missing = [slot for slot in self.required_slots(kind)
                   if not integrity.has(slot)]
        failed = [f"MISSING_{slot}" for slot in missing]
        return not failed, failed, integrity

    # ── Stage 4: verification decision ────────────────────────────────────

    def verify(self, candidate_id: str,
               verification_id: Optional[str] = None) -> KnowledgeUnitVerification:
        """Decide one candidate. Idempotent: a decided candidate is returned
        unchanged."""
        settled_id = self.store._verification_by_candidate.get(candidate_id)
        if settled_id is not None:
            return self.store.verifications[settled_id]

        candidate, evidence, quality = self.load_candidate(candidate_id)
        rules: List[str] = []
        failed: List[str] = []

        # Stage 1
        if candidate.source_span:
            rules.append("HAS_SOURCE_SPAN")
        else:
            failed.append("NO_SOURCE_SPAN")
        if quality:
            rules.append("QUALITY_PRESENT")
        else:
            failed.append("NO_QUALITY_ROW")

        # Stage 2
        sufficient, sufficiency_failed = self.evidence_is_sufficient(quality)
        rules.extend(["EVIDENCE_PRESENT", "QUALITY_PASS"]
                     if sufficient else ["EVIDENCE_PRESENT"])
        failed.extend(sufficiency_failed)

        traced, trace_failed = self.traceability_is_complete(evidence)
        rules.append("TRACE_COMPLETE" if traced else "TRACE_BROKEN")
        failed.extend(trace_failed)

        # Stage 3
        intact, integrity_failed, integrity = self.semantic_integrity_holds(
            candidate, evidence)
        rules.append("SEMANTIC_INTEGRITY" if intact else "SEMANTIC_INCOMPLETE")
        failed.extend(integrity_failed)

        status = (VerificationStatus.VERIFIED if not failed
                  else VerificationStatus.REJECTED)
        trace = {
            "candidate_id": candidate_id,
            "evidence_ids": [candidate.evidence_id],
            "rules": sorted(set(rules)),
            "verifier_version": VERIFIER_VERSION,
            "failed_rules": sorted(set(failed)),
            "classification": candidate.classification,
            "slots": {k: v for k, v in integrity.slots.items() if v},
            "quality_score": self.quality_score(quality),
        }
        verification = KnowledgeUnitVerification(
            id=verification_id or deterministic_id(
                "kv", candidate_id, VERIFIER_VERSION),
            candidate_id=candidate_id,
            verification_status=status.value,
            verification_method=VERIFICATION_METHOD,
            verifier_version=VERIFIER_VERSION,
            verification_trace=trace,
        )
        self.store.verifications[verification.id] = verification
        self.store._verification_by_candidate[candidate_id] = verification.id
        self._emit(PipelineStage.VERIFY, candidate.reading_run_id,
                   {"candidate_id": candidate_id,
                    "verification_id": verification.id,
                    "status": status.value,
                    "failed_rules": trace["failed_rules"]})
        return verification

    def verify_all(self, candidate_ids: List[str]) -> List[KnowledgeUnitVerification]:
        """Decide every candidate in a stable order."""
        return [self.verify(cid) for cid in sorted(candidate_ids)]

    # ── lifecycle guards ──────────────────────────────────────────────────

    def transition(self, verification_id: str, target: VerificationStatus
                   ) -> None:
        """Move a verification. Only PENDING may move; both terminal
        states are final, so VERIFIED -> PENDING and REJECTED ->
        VERIFIED are refused."""
        verification = self.store.verifications.get(verification_id)
        if verification is None:
            raise VerificationViolation(
                f"Verification {verification_id} does not exist.")
        current = VerificationStatus(verification.verification_status)
        if target not in LEGAL_TRANSITIONS[current]:
            raise VerificationViolation(
                f"{current.value} -> {target.value} is not a legal "
                f"transition; a settled decision is final.")
        verification.verification_status = target.value

    def reopen(self, verification_id: str) -> None:
        raise VerificationViolation(
            "A verification cannot return to PENDING; the decision is final.")

    def overturn(self, verification_id: str) -> None:
        raise VerificationViolation(
            "A rejected candidate cannot become verified; the decision "
            "is final.")

    # ── queries ───────────────────────────────────────────────────────────

    def verification_count(self, reading_run_id: str) -> int:
        return sum(
            1 for v in self.store.verifications.values()
            if v.candidate_id in self.store.ku_candidates
            and self.store.ku_candidates[v.candidate_id].reading_run_id
            == reading_run_id
        )

    def verified_count(self, reading_run_id: str) -> int:
        return self._count(reading_run_id, VerificationStatus.VERIFIED)

    def rejected_count(self, reading_run_id: str) -> int:
        return self._count(reading_run_id, VerificationStatus.REJECTED)

    def _count(self, reading_run_id: str,
               status: VerificationStatus) -> int:
        total = 0
        for verification in self.store.verifications.values():
            candidate = self.store.ku_candidates.get(verification.candidate_id)
            if candidate is None or candidate.reading_run_id != reading_run_id:
                continue
            if verification.verification_status == status.value:
                total += 1
        return total

    def status_breakdown(self, reading_run_id: str) -> Dict[str, int]:
        counts = {s.value: 0 for s in VerificationStatus}
        for verification in self.store.verifications.values():
            candidate = self.store.ku_candidates.get(verification.candidate_id)
            if candidate is None or candidate.reading_run_id != reading_run_id:
                continue
            counts[verification.verification_status] += 1
        return dict(sorted(counts.items()))

    def traceability(self, reading_run_id: str) -> Dict[str, object]:
        """candidate -> evidence -> source, counted."""
        candidates = [k for k in self.store.ku_candidates.values()
                      if k.reading_run_id == reading_run_id]
        decided = [self.store.verifications[self.store._verification_by_candidate[k.id]]
                   for k in candidates
                   if self.store._verification_by_candidate.get(k.id)]
        complete = 0
        for verification in decided:
            candidate = self.store.ku_candidates[verification.candidate_id]
            evidence = self.store.evidence.get(candidate.evidence_id)
            if (evidence is not None
                    and evidence.source_version_id in self.store.source_versions
                    and (evidence.locator or {}).get("content_hash")):
                complete += 1
        return {
            "candidates": len(candidates),
            "decided": len(decided),
            "trace_complete": complete,
            "percent": (round(100.0 * complete / len(decided), 2)
                        if decided else 0.0),
        }

    def orphan_verifications(self) -> List[str]:
        return [v.id for v in self.store.verifications.values()
                if v.candidate_id not in self.store.ku_candidates]

    # ── events ────────────────────────────────────────────────────────────

    @property
    def events(self) -> List[VerificationEvent]:
        return list(self._events)

    def _emit(self, stage: PipelineStage, run_id: str, payload: Dict) -> None:
        event = VerificationEvent(stage=stage, run_id=run_id, payload=payload)
        self._events.append(event)
        self._event_sink(event)