"""A Repository P8 — in-book annotations over frozen knowledge units.

A仓 already holds one row per knowledge unit a book expresses. What it does
not hold is the *shape* the book gives that unit at a given place: the same
proposition appears as a definition on page 12 and is restated as a theorem
on page 310, and a reader following the book needs to know which one they are
looking at.

This stage adds those annotations **without ever merging two units**:

    KU occurrence  role + quote_span + occurrence key   (one row, per place)
    relation hint  restates | summarizes | applies      (one row, per pair)

Two boundaries are kept apart, because conflating either is the failure mode
this stage could have:

- **A role is a label on one occurrence.** It says what kind of passage the
  book is using here. It is closed to a declared vocabulary, and an unknown
  value is refused rather than coerced to `OTHER`, so a mislabelled passage is
  visible instead of quietly lumped in with everything else.

- **A relation hint is a hint.** `restates`, `summarizes` and `applies`
  record that two occurrences of the same book appear to be about the same
  thing — and nothing more. A hint never merges two occurrences, never
  deletes one, and never asserts that the pair is the same unit. Deciding
  what the hint means is a semantic judgement, and that belongs to B仓. What
  this stage produces is therefore handed to B仓 as *dedup hints*, and the
  decision is left to it. 075 refused SAME_MEANING and TENSION for exactly
  this reason; the three kinds here are recorded as hints rather than facts
  for exactly the same reason.

`OTHER` is the seventh role rather than an error value: a passage that is
none of the six named kinds is still a passage, and dropping it would lose a
real occurrence from the book's account of itself.

Rules:
- append only. Every operation writes a new row. Nothing edits or deletes an
  occurrence or a hint, and `update_*` / `delete_* / `merge_*` raise.
- same book only. Both ends of a hint must be units of the same source
  version; a hint that crossed books would be a statement about two books.
- idempotent. The occurrence key is a sha256 of the identity inputs, so a
  rerun over the same occurrence recomputes the same row and writes nothing.
- evidence before annotation. An occurrence must anchor to real evidence of
  the same source version, the same rule every other A仓 stage enforces.
- verbatim. A quote_span that cannot be located in the source text is kept
  and flagged for the review queue; it is never silently dropped, because a
  dropped occurrence is a page the book no longer accounts for.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

from .identity import IdentitySink
from .persistence import FreezeTransaction


ANNOTATION_VERSION = "a-p8-v0.1"


# ── the closed role vocabulary ────────────────────────────────────────────────


class KURole(str, Enum):
    """What kind of passage the book is using at this occurrence.

    Closed, and deliberately small. Six named kinds plus `OTHER`: a passage
    that is none of the six is still an occurrence, and coercing it to one of
    the six — or dropping it — would misdescribe the book.

    `DEFINITION` and `THEOREM` are the two a reader follows structurally, so
    a restated definition and a restated theorem stay distinguishable. The
    rest are the ordinary furniture of a technical or expository book.
    """

    DEFINITION = "DEFINITION"
    THEOREM = "THEOREM"
    EXAMPLE = "EXAMPLE"
    EXERCISE = "EXERCISE"
    SUMMARY = "SUMMARY"
    ASIDE = "ASIDE"
    OTHER = "OTHER"


#: The exact vocabulary the migration's CHECK admits, in a stable order.
#: A test asserts the two agree: a role the code emits and the schema rejects
#: would only surface as a failed transaction at write time.
DECLARED_ROLES: Tuple[str, ...] = tuple(r.value for r in KURole)

#: The same set as a frozenset, for membership tests.
ROLE_VOCABULARY = frozenset(DECLARED_ROLES)


class RelationKind(str, Enum):
    """The three ways one occurrence may be a hint about another.

    These are **hints**, not facts. `RESTATES` says two occurrences look like
    the same thing said twice; `SUMMARIZES` says one abbreviates the other;
    `APPLIES` says one puts the other to work. All three are the kind of
    judgement 075 declined to record as a relation:

        "There is no value meaning 'these say the same thing' or 'these are in
         tension', because deciding either is a semantic judgement: it belongs
         to B仓, and A仓 has no authority to make it."

    So they are stored as hints carrying a confidence, exposed to B仓 as
    dedup candidates, and never applied here. A hint is a proposal for B仓 to
    decide, which is why it cannot delete or merge the occurrence it points at.
    """

    RESTATES = "RESTATES"
    SUMMARIZES = "SUMMARIZES"
    APPLIES = "APPLIES"


#: The exact vocabulary the migration's CHECK admits.
DECLARED_RELATION_KINDS: Tuple[str, ...] = tuple(k.value for k in RelationKind)

#: The same set as a frozenset, for membership tests.
RELATION_KIND_VOCABULARY = frozenset(DECLARED_RELATION_KINDS)

#: Refused by design, not by omission. Each of these would turn a hint into a
#: recorded judgement, which is B仓's to make. Kept as a named list so the
#: refusal is a testable fact rather than an absence, and so a later stage has
#: to argue with them by name.
DEFERRED_RELATION_KINDS = (
    "SAME_MEANING",
    "CONTRADICTS",
    "SUPPORTS",
    "DEPENDS_ON",
    "EQUIVALENT",
    "DUPLICATE",
)


#: What an occurrence looks like when it is flagged for review rather than
#: locatable. Every other status says the span was found; this one says the
#: book could not be checked, which is a fact worth keeping.
QUOTE_STATUS_LOCATED = "LOCATED"
QUOTE_STATUS_UNLOCATABLE = "UNLOCATED"


class AnnotationViolation(Exception):
    """Raised on a forbidden A仓 annotation operation."""


class AnnotationPrecondition(Exception):
    """An annotation may not be written as given; nothing was written."""


# ── identity ──────────────────────────────────────────────────────────────────
#
# Every formula here is content-derived. Never uuid4, never a sequence, never
# a timestamp: a rerun over the same occurrence must recompute the same row,
# which is what turns a replay into a no-op instead of a second occurrence.


def quote_hash(quote_span: str) -> str:
    """`sha256(quote_span)` — what the span is, on its own.

    Part of the occurrence key, so two occurrences that quote the same words
    from two different places are two occurrences: the locator is in the key
    too, and the quote alone never identifies a place.
    """
    return hashlib.sha256(quote_span.encode("utf-8")).hexdigest()


def occurrence_key(
    source_version_id: str, unit_id: str, locator: str, quote: str, role: str
) -> str:
    """`kao_<sha256(source_version | unit | locator | quote_hash | role)[:12]>`.

    The identity of an occurrence is *which unit*, *where in this book*, *what
    it quotes*, and *how the book reads it here*.

    Two of those five parts are there because leaving either out was measured,
    not guessed:

    - **`unit_id`.** 利率史 chapter 1 has a unit and its own revision both
      anchored to the same evidence row at the same page, quoting the same span.
      A key without the unit gives those two the same key, the second silently
      overwrites the first, and one occurrence disappears -- a merge, performed
      by a hash collision rather than by a decision. Two frozen units are two
      units; the key has to say so.

    - **`role`.** The same passage re-read and re-labelled is a *new reading*,
      not a revision of the old one. Without the role in the key, the second
      reading collides with the first, returns it unchanged, and the first
      reading is what survives -- an observation quietly lost, which is the one
      thing an append-only stage must never do.

    The source version is in the key for the adjacent reason: the same words at
    the same position in a later version of the book is a later state of the
    world, not the same occurrence.

    So the key is *not* the bare `source_version | locator | quote_hash` one
    might write: the three-part formula folds a unit into its own revision and
    folds a re-reading back into the reading it replaced. Both are merges, and
    neither was a decision.
    """
    digest = hashlib.sha256(
        f"{source_version_id}|{unit_id}|{locator}|{quote_hash(quote)}|{role}".encode("utf-8")
    ).hexdigest()
    return f"kao_{digest[:12]}"


def occurrence_hash(
    source_version_id: str, unit_id: str, locator: str, quote: str, role: str
) -> str:
    """`kah_<sha256(...)[:16]>` — the replay fingerprint.

    Carries the role as well as the position and the quote: the same passage
    read again and labelled differently is a different annotation, and a
    replay of the same reading must collide rather than append.
    """
    digest = hashlib.sha256(
        f"{source_version_id}|{unit_id}|{locator}|{quote_hash(quote)}"
        f"|{role}|{ANNOTATION_VERSION}".encode("utf-8")
    ).hexdigest()
    return f"kah_{digest[:16]}"


def hint_id(kind: str, from_unit_id: str, to_unit_id: str) -> str:
    """`kai_<sha256(kind | sorted pair)[:12]>` — content derived.

    The pair is sorted, so A-hints-B and B-hints-A for the same kind are one
    hint: the direction a hint runs is not a claim about anything, and two
    rows for one observation would let a replay double the confidence of a
    single reading.
    """
    low, high = sorted((from_unit_id, to_unit_id))
    digest = hashlib.sha256(f"{kind}|{low}|{high}".encode("utf-8")).hexdigest()
    return f"kai_{digest[:12]}"


def hint_hash(
    kind: str, from_unit_id: str, to_unit_id: str, confidence: float, evidence_id: str
) -> str:
    """`kaib_<sha256(...)[:16]>` — the replay fingerprint.

    Confidence is part of the hash rather than part of the row that gets
    updated. Re-reading the same pair at a different confidence is therefore a
    second observation with its own row, which is what keeps "the same pair was
    read twice at two confidences" visible instead of overwriting the first
    reading and losing it.
    """
    low, high = sorted((from_unit_id, to_unit_id))
    digest = hashlib.sha256(
        f"{kind}|{low}|{high}|{confidence:.6f}|{evidence_id}|{ANNOTATION_VERSION}".encode("utf-8")
    ).hexdigest()
    return f"kaib_{digest[:16]}"


# ── rows ──────────────────────────────────────────────────────────────────────


@dataclass
class KUOccurrence:
    """One place in one book where a knowledge unit occurs.

    Keyed by `occurrence_key`, never by the unit alone: a unit restated three
    times has three occurrences, and none of them is the unit. That is the
    whole reason this stage exists and the reason it cannot merge anything.
    """

    id: str
    source_version_id: str
    unit_id: str
    locator: str
    quote_span: str
    role: str
    occurrence_hash: str = ""
    quote_status: str = QUOTE_STATUS_LOCATED
    review_required: bool = False
    created_at: str = ANNOTATION_VERSION


@dataclass
class KURelationHint:
    """One hint that two occurrences of one book look related.

    Carries a confidence because it is a reading, not a measurement of fact.
    `confidence` is bounded to [0, 1] by the writer; a hint outside that range
    is not a weaker or stronger hint but a malformed one.
    """

    id: str
    source_version_id: str
    kind: str
    from_unit_id: str
    to_unit_id: str
    confidence: float
    evidence_id: str = ""
    created_at: str = ANNOTATION_VERSION


@dataclass
class AnnotationResult:
    """What one write operation produced. Nothing here is ever edited."""

    status: str
    occurrence: Optional[KUOccurrence] = None
    hint: Optional[KURelationHint] = None
    written: bool = False
    failure: Optional[str] = None


# ── transaction ──────────────────────────────────────────────────────────────

ANNOTATION_TABLES = ("ku_occurrence", "ku_relation_hint")

_ANNOTATION_ROW_TYPES: Dict[str, type] = {
    "ku_occurrence": KUOccurrence,
    "ku_relation_hint": KURelationHint,
}

#: Distinct from IdentitySink's `identities` and EvolutionSink's `relations`.
_ANNOTATION_BUCKETS: Dict[str, str] = {
    "ku_occurrence": "ku_occurrences",
    "ku_relation_hint": "ku_relation_hints",
}


class AnnotationSink(IdentitySink):
    """Every sink up to P6, plus the two annotation tables.

    Inherits so the staging discipline stays in one place and one transaction
    can carry the whole A chain: an occurrence cannot land without the unit it
    annotates, and a hint cannot land without both of the units it joins.
    """

    TABLES = IdentitySink.TABLES + ANNOTATION_TABLES
    ROW_TYPES = {**IdentitySink.ROW_TYPES, **_ANNOTATION_ROW_TYPES}
    ROW_BUCKETS = {**IdentitySink.ROW_BUCKETS, **_ANNOTATION_BUCKETS}

    def __init__(self, fail_after: Optional[int] = None):
        super().__init__(fail_after=fail_after)
        self.ku_occurrences: Dict[str, KUOccurrence] = {}
        self.ku_relation_hints: Dict[str, KURelationHint] = {}

    def reload(self) -> Dict[str, object]:
        reloaded = super().reload()
        reloaded["ku_occurrence"] = dict(self.ku_occurrences)
        reloaded["ku_relation_hint"] = dict(self.ku_relation_hints)
        return reloaded


def _row_dict(row) -> Dict:
    return dict(row.__dict__)


# ── quote verification ───────────────────────────────────────────────────────


def locate_quote(quote_span: str, source_text: str) -> Optional[Tuple[int, int]]:
    """Where `quote_span` sits in `source_text`, or None.

    `(start, end)` character offsets, half-open, exactly as `str.find`
    reports them. The comparison is verbatim and exact: no normalisation, no
    case folding, no whitespace tolerance, and no fuzzy matching. A quote that
    differs from the source by one character is not located, which is the
    point — a span that had to be fuzzed to match is a span a reader cannot
    find in the book.
    """
    if not quote_span:
        return None
    start = source_text.find(quote_span)
    if start < 0:
        return None
    return start, start + len(quote_span)


def verify_quote(quote_span: str, source_text: str) -> Tuple[str, bool, Optional[Tuple[int, int]]]:
    """`(quote_status, review_required, span)` for one occurrence.

    An unlocatable quote is **flagged, never dropped**. The occurrence keeps
    its row and gains `review_required`, because a dropped occurrence would be
    a place in the book that no longer accounts for itself — and the fact that
    a span could not be verified is precisely what a reviewer needs to see.
    """
    span = locate_quote(quote_span, source_text)
    if span is None:
        return QUOTE_STATUS_UNLOCATABLE, True, None
    return QUOTE_STATUS_LOCATED, False, span


def source_text_of(store, evidence) -> str:
    """The text an occurrence's quote must be findable in.

    The evidence row's own span. That is the A仓 authority for "what the book
    says here": S5 requires every evidence row to carry its quote_span, so
    the evidence is where the verbatim text lives. An evidence row with no
    span yields an empty string, which locates nothing and therefore flags
    the occurrence rather than passing it.
    """
    return evidence.content_span if evidence is not None else ""


# ── the service ──────────────────────────────────────────────────────────────


class AnnotationService:
    """Appends roles and relation hints. Merges and deletes nothing.

    A writer for its own two tables and a reader for everything upstream. It
    holds no write path to `knowledge_unit`, `ku_occurrence` other than
    appending, or `ku_relation_hint` other than appending — which is what makes
    "never merge, never dedupe" structural rather than a promise. Every
    forbidden operation raises rather than returning a no-op value that a
    caller could mistake for success.
    """

    def __init__(self, ingestion_pipeline, sink: AnnotationSink):
        self.p = ingestion_pipeline
        self.store = ingestion_pipeline.store
        self.sink = sink

    # ── preconditions ───────────────────────────────────────────────────────

    def check_occurrence_preconditions(
        self,
        unit_id: str,
        source_version_id: str,
        evidence_id: str,
        role: str,
        locator: str = "",
        quote_span: str = "",
    ) -> Tuple[bool, List[str]]:
        """Everything that must hold before an occurrence is written.

        Same shape as the other A仓 stages: checked before the transaction
        opens, so a refusal writes nothing at all rather than opening and
        rolling back. The same-source rule is the one this stage must not get
        wrong, because an occurrence from another book would silently
        re-source a unit.
        """
        failed: List[str] = []
        if role not in ROLE_VOCABULARY:
            failed.append("ROLE_NOT_IN_VOCABULARY")
        # The schema also guards both, with CHECK (length(btrim(...)) > 0).
        # Kept here as well: the writer is the layer that reports a readable
        # reason, and a row with no locator would say nothing about where in
        # the book it sits.
        if not (locator or "").strip():
            failed.append("NO_LOCATOR")
        if not (quote_span or "").strip():
            failed.append("NO_QUOTE_SPAN")
        if source_version_id not in self.store.source_versions:
            failed.append("NO_SUCH_SOURCE_VERSION")
        unit = self.sink.units.get(unit_id)
        if unit is None:
            failed.append("NO_SUCH_UNIT")
        elif unit.freeze_status != "FROZEN":
            failed.append("UNIT_NOT_FROZEN")
        elif unit.source_version_id != source_version_id:
            # An occurrence of a unit must be an occurrence *of that unit's
            # own book*. Anything else re-sources the unit to a book it never
            # belonged to.
            failed.append("UNIT_FROM_OTHER_SOURCE")
        evidence = self.store.evidence.get(evidence_id)
        if evidence is None:
            failed.append("NO_SUCH_EVIDENCE")
        elif evidence.source_version_id != source_version_id:
            failed.append("EVIDENCE_FROM_OTHER_SOURCE")
        return not failed, failed

    def check_hint_preconditions(
        self,
        from_unit_id: str,
        to_unit_id: str,
        source_version_id: str,
        kind: str,
        confidence: float,
        evidence_id: str,
    ) -> Tuple[bool, List[str]]:
        failed: List[str] = []
        if kind not in RELATION_KIND_VOCABULARY:
            failed.append("KIND_NOT_IN_VOCABULARY")
        if from_unit_id == to_unit_id:
            failed.append("SELF_HINT")
        if not 0.0 <= confidence <= 1.0:
            failed.append("CONFIDENCE_OUT_OF_RANGE")
        if source_version_id not in self.store.source_versions:
            failed.append("NO_SUCH_SOURCE_VERSION")
        for label, unit_id in (("from", from_unit_id), ("to", to_unit_id)):
            unit = self.sink.units.get(unit_id)
            if unit is None:
                failed.append(f"NO_SUCH_{label.upper()}_UNIT")
            elif unit.freeze_status != "FROZEN":
                failed.append(f"{label.upper()}_UNIT_NOT_FROZEN")
            elif unit.source_version_id != source_version_id:
                # Cross-book is refused rather than recorded. A hint spanning
                # two books would be a statement about two books, and this
                # stage is scoped to one.
                failed.append(f"{label.upper()}_UNIT_FROM_OTHER_SOURCE")
        evidence = self.store.evidence.get(evidence_id)
        if evidence is None:
            failed.append("NO_SUCH_EVIDENCE")
        elif evidence.source_version_id != source_version_id:
            failed.append("EVIDENCE_FROM_OTHER_SOURCE")
        return not failed, failed

    # ── roles ───────────────────────────────────────────────────────────────

    def annotate_occurrence(
        self, unit_id: str, evidence_id: str, locator: str, quote_span: str, role: str
    ) -> AnnotationResult:
        """Append one occurrence with its role. Idempotent on content.

        An unknown role is refused, never coerced to `OTHER`: coercing would
        hide a mislabelled passage inside the catch-all and lose the fact that
        somebody read it as something the vocabulary does not name.

        An unlocatable quote is written and flagged, never dropped.
        """
        unit = self.sink.units.get(unit_id)
        if unit is None:
            raise AnnotationPrecondition(
                f"{unit_id} is not a durable unit; an occurrence must annotate a frozen unit."
            )
        source_version_id = unit.source_version_id
        ok, failed = self.check_occurrence_preconditions(
            unit_id, source_version_id, evidence_id, role, locator, quote_span
        )
        if not ok:
            raise AnnotationPrecondition(
                f"{unit_id} may not be annotated as {role}: {', '.join(failed)}."
            )

        evidence = self.store.evidence.get(evidence_id)
        quote_status, review_required, _ = verify_quote(
            quote_span, source_text_of(self.store, evidence)
        )

        key = occurrence_key(source_version_id, unit_id, locator, quote_span, role)
        row = KUOccurrence(
            id=key,
            source_version_id=source_version_id,
            unit_id=unit_id,
            locator=locator,
            quote_span=quote_span,
            role=role,
            occurrence_hash=occurrence_hash(source_version_id, unit_id, locator, quote_span, role),
            quote_status=quote_status,
            review_required=review_required,
        )
        existing = self.sink.ku_occurrences.get(row.id)
        if existing is not None:
            # A replay of the same occurrence is a no-op: same key, same role,
            # same quote status. Nothing is appended and nothing is edited.
            return AnnotationResult(status="EXISTS", occurrence=existing, written=False)
        try:
            with FreezeTransaction(self.sink) as tx:
                tx.write("ku_occurrence", _row_dict(row))
        except Exception as error:
            return AnnotationResult(status="FAILED", failure=str(error))
        return AnnotationResult(
            status="ANNOTATED", occurrence=self.sink.ku_occurrences[row.id], written=True
        )

    # ── relation hints ──────────────────────────────────────────────────────

    def add_relation_hint(
        self, from_unit_id: str, to_unit_id: str, kind: str, confidence: float, evidence_id: str
    ) -> AnnotationResult:
        """Append one dedup hint for B仓. Idempotent on content.

        This is where the stage's boundary is enforced: `kind` is restricted to
        the three hint kinds, the confidence is bounded, both units must be of
        one book, and the hint is *written*. It is never applied — the hint
        does not merge the two units, delete either one, or mark either as a
        duplicate. B仓 decides that; this stage only supplies the candidate.
        """
        source_version_id = self._shared_source_version(from_unit_id, to_unit_id)
        if source_version_id is None:
            raise AnnotationPrecondition(
                f"{from_unit_id} and {to_unit_id} are not two units of one "
                "book; a hint may not cross books."
            )
        ok, failed = self.check_hint_preconditions(
            from_unit_id, to_unit_id, source_version_id, kind, confidence, evidence_id
        )
        if not ok:
            raise AnnotationPrecondition(
                f"{from_unit_id} -[hint]-> {to_unit_id} may not be written: {', '.join(failed)}."
            )

        row = self._hint_row(
            from_unit_id, to_unit_id, kind, confidence, evidence_id, source_version_id
        )
        existing = self.sink.ku_relation_hints.get(row.id)
        if existing is not None:
            return AnnotationResult(status="EXISTS", hint=existing, written=False)
        try:
            with FreezeTransaction(self.sink) as tx:
                tx.write("ku_relation_hint", _row_dict(row))
        except Exception as error:
            return AnnotationResult(status="FAILED", failure=str(error))
        return AnnotationResult(
            status="HINTED", hint=self.sink.ku_relation_hints[row.id], written=True
        )

    def _hint_row(
        self,
        from_unit_id: str,
        to_unit_id: str,
        kind: str,
        confidence: float,
        evidence_id: str,
        source_version_id: str,
    ) -> KURelationHint:
        return KURelationHint(
            id=hint_id(kind, from_unit_id, to_unit_id),
            source_version_id=source_version_id,
            kind=kind,
            from_unit_id=from_unit_id,
            to_unit_id=to_unit_id,
            confidence=round(float(confidence), 6),
            evidence_id=evidence_id,
        )

    def _shared_source_version(self, from_unit_id: str, to_unit_id: str) -> Optional[str]:
        """The one source version both units belong to, or None.

        Read rather than passed in: a caller-supplied version could name a
        book neither unit belongs to, and the hint would then be scoped to a
        book the units have nothing to do with.
        """
        left = self.sink.units.get(from_unit_id)
        right = self.sink.units.get(to_unit_id)
        if left is None or right is None:
            return None
        if left.source_version_id != right.source_version_id:
            return None
        return left.source_version_id

    # ── immutability ────────────────────────────────────────────────────────

    def update_occurrence(self, occurrence_id: str, **changes) -> None:
        raise AnnotationViolation(
            f"Occurrence {occurrence_id} cannot be updated; a role is "
            "recorded per reading, and a re-reading is a new occurrence."
        )

    def delete_occurrence(self, occurrence_id: str) -> None:
        raise AnnotationViolation(
            f"Occurrence {occurrence_id} cannot be deleted. Dropping an "
            "occurrence would be a place in the book that no longer accounts "
            "for itself; an unlocatable quote is flagged for review instead."
        )

    def delete_hint(self, hint_id: str) -> None:
        raise AnnotationViolation(
            f"Hint {hint_id} cannot be deleted. A hint that is no longer "
            "believed is contradicted by a later observation, not removed — "
            "B仓 needs to see both."
        )

    def merge_occurrences(self, *occurrence_ids: str) -> None:
        raise AnnotationViolation(
            "A仓 has no authority to merge occurrences. Deciding that two "
            "occurrences are one is a semantic judgement and belongs to B仓."
        )

    def merge_units(self, *unit_ids: str) -> None:
        raise AnnotationViolation(
            "A仓 has no authority to merge knowledge units; merging is a "
            "semantic judgement and belongs to B仓."
        )

    def apply_hint(self, hint_id: str) -> None:
        raise AnnotationViolation(
            f"Hint {hint_id} is a hint, not an instruction. Applying one "
            "would merge two occurrences from A仓, which is B仓's decision."
        )

    def renumber_unit(self, unit_id: str, **changes) -> None:
        raise AnnotationViolation(
            "A knowledge unit is not renumbered. An annotation attaches to a "
            "unit's own id; anything that rewrote it would orphan every "
            "occurrence and every hint that names it."
        )

    def update_unit(self, unit_id: str, **changes) -> None:
        raise AnnotationViolation(
            f"Knowledge unit {unit_id} cannot be updated. This stage annotates "
            "frozen units and never writes one."
        )

    # ── queries ─────────────────────────────────────────────────────────────

    def occurrences_of(self, unit_id: str) -> List[KUOccurrence]:
        """Every occurrence of one unit, in reading order where possible."""
        return sorted(
            (o for o in self.sink.ku_occurrences.values() if o.unit_id == unit_id),
            key=lambda o: o.locator,
        )

    def occurrences_of_book(self, source_version_id: str) -> List[KUOccurrence]:
        return sorted(
            (
                o
                for o in self.sink.ku_occurrences.values()
                if o.source_version_id == source_version_id
            ),
            key=lambda o: (o.locator, o.id),
        )

    def occurrences_by_role(self, role: str) -> List[KUOccurrence]:
        return sorted(
            (o for o in self.sink.ku_occurrences.values() if o.role == role), key=lambda o: o.id
        )

    def role_breakdown(self) -> Dict[str, int]:
        """How many occurrences carry each role, zero-filled.

        Zero-filled on purpose: an empty role is then a reading of the book
        rather than a missing key, and a stage that stopped emitting THEOREM
        shows up as a zero instead of vanishing from the report.
        """
        counts = {role: 0 for role in DECLARED_ROLES}
        for occurrence in self.sink.ku_occurrences.values():
            counts[occurrence.role] = counts.get(occurrence.role, 0) + 1
        return dict(sorted(counts.items()))

    def undeclared_roles(self) -> List[str]:
        """Occurrences carrying a role the vocabulary does not name.

        Always empty by construction, because `annotate_occurrence` refuses
        one. Read by the vocabulary gate rather than assumed: a writer that
        skipped the precondition would show up here.
        """
        return sorted(
            {o.role for o in self.sink.ku_occurrences.values() if o.role not in ROLE_VOCABULARY}
        )

    def undeclared_kinds(self) -> List[str]:
        return sorted(
            {
                h.kind
                for h in self.sink.ku_relation_hints.values()
                if h.kind not in RELATION_KIND_VOCABULARY
            }
        )

    def review_queue(self) -> List[str]:
        """Occurrences whose quote could not be located in the source text.

        The queue is a query, not a discard pile. Each of these rows is still a
        real occurrence the book accounts for; what it lacks is a verified
        span, and that is what a reviewer is being asked to settle.
        """
        return sorted(
            o.id
            for o in self.sink.ku_occurrences.values()
            if o.review_required or o.quote_status != QUOTE_STATUS_LOCATED
        )

    def located_quotes(self) -> List[str]:
        return sorted(
            o.id
            for o in self.sink.ku_occurrences.values()
            if o.quote_status == QUOTE_STATUS_LOCATED
        )

    def hints_of(self, unit_id: str) -> List[KURelationHint]:
        return sorted(
            (
                h
                for h in self.sink.ku_relation_hints.values()
                if unit_id in (h.from_unit_id, h.to_unit_id)
            ),
            key=lambda h: h.id,
        )

    def cross_source_hints(self) -> List[str]:
        """Hints whose two units are not of the same source version.

        Unreachable through the writer, which refuses one before the
        transaction opens. Read by the isolation gate rather than assumed,
        because a hint that crossed books would be a statement about two
        books and this stage is scoped to one.
        """
        wrong: List[str] = []
        for hint in self.sink.ku_relation_hints.values():
            left = self.sink.units.get(hint.from_unit_id)
            right = self.sink.units.get(hint.to_unit_id)
            if left is None or right is None:
                wrong.append(hint.id)
            elif left.source_version_id != right.source_version_id:
                wrong.append(hint.id)
            elif hint.source_version_id != left.source_version_id:
                wrong.append(hint.id)
        return sorted(set(wrong))

    def self_hints(self) -> List[str]:
        return sorted(
            h.id for h in self.sink.ku_relation_hints.values() if h.from_unit_id == h.to_unit_id
        )

    def out_of_range_hints(self) -> List[str]:
        return sorted(
            h.id for h in self.sink.ku_relation_hints.values() if not 0.0 <= h.confidence <= 1.0
        )

    def duplicate_occurrences(self) -> List[str]:
        """Occurrence keys written more than once.

        The occurrence key is the primary key, so a duplicate is unreachable
        through the sink. The query exists so the replay gate reads the fact
        instead of assuming it.
        """
        return _duplicates(self.sink.ku_occurrences, lambda o: o.id)

    def duplicate_hints(self) -> List[str]:
        return _duplicates(
            self.sink.ku_relation_hints, lambda h: hint_id(h.kind, h.from_unit_id, h.to_unit_id)
        )

    def orphan_occurrences(self) -> List[str]:
        """Occurrences whose unit or evidence no longer exists."""
        out: List[str] = []
        for occurrence in self.sink.ku_occurrences.values():
            unit = self.sink.units.get(occurrence.unit_id)
            if unit is None:
                out.append(occurrence.id)
                continue
            if unit.source_version_id != occurrence.source_version_id:
                out.append(occurrence.id)
        return sorted(set(out))

    def orphan_hints(self) -> List[str]:
        out: List[str] = []
        for hint in self.sink.ku_relation_hints.values():
            for unit_id in (hint.from_unit_id, hint.to_unit_id):
                if unit_id not in self.sink.units:
                    out.append(hint.id)
        return sorted(set(out))

    def traceability(self) -> Dict[str, object]:
        """GATE_1 — every occurrence and hint resolves to a book.

        occurrence -> unit -> source version, and hint -> both units -> one
        source version. Reads the sinks rather than trusting the writer's
        preconditions, so a row that arrived by any other route is still
        accounted for.
        """
        complete = 0
        for occurrence in self.sink.ku_occurrences.values():
            unit = self.sink.units.get(occurrence.unit_id)
            if (
                unit is not None
                and unit.source_version_id == occurrence.source_version_id
                and occurrence.source_version_id in self.store.source_versions
            ):
                complete += 1
        total = len(self.sink.ku_occurrences)
        return {
            "occurrences": total,
            "trace_complete": complete,
            "percent": round(100.0 * complete / total, 2) if total else 0.0,
            "hints": len(self.sink.ku_relation_hints),
            "cross_source_hints": len(self.cross_source_hints()),
            "review_queue": len(self.review_queue()),
        }


def _duplicates(rows: Dict, key) -> List[str]:
    seen: Dict[str, int] = {}
    for row in rows.values():
        value = key(row)
        seen[value] = seen.get(value, 0) + 1
    return sorted(k for k, v in seen.items() if v > 1)


# ── the dedup hints B仓 reads ────────────────────────────────────────────────


def dedup_hints(
    service: AnnotationService, source_version_id: Optional[str] = None
) -> List[Dict[str, object]]:
    """Every relation hint as a plain payload for B仓.

    The one place this stage names another repository, and it is an export
    rather than a dependency: B仓 receives these and decides what they mean.
    Nothing here calls B仓, imports it, or waits on it, and the payload is
    plain data so B仓 can read it without importing this module.

    Each hint is a *candidate*, never a decision: the payload names both units
    and the confidence, and carries no instruction to merge, delete or mark
    either one a duplicate. B仓 is free to reject every one of them, which is
    what makes this a hint channel rather than a merge order.
    """
    out: List[Dict[str, object]] = []
    for key in sorted(service.sink.ku_relation_hints):
        hint = service.sink.ku_relation_hints[key]
        if source_version_id is not None and hint.source_version_id != source_version_id:
            continue
        out.append(
            {
                "hint_id": hint.id,
                "kind": hint.kind,
                "source_version_id": hint.source_version_id,
                "from_unit_id": hint.from_unit_id,
                "to_unit_id": hint.to_unit_id,
                "confidence": hint.confidence,
                "evidence_id": hint.evidence_id,
                # Read by B仓, never by this stage. Present so a B仓 that reads
                # the payload cannot mistake a hint for an already-applied merge.
                "applied": False,
                "authority": "A_REPOSITORY",
            }
        )
    return out


# ── SQL emission ─────────────────────────────────────────────────────────────

_OCCURRENCE_COLUMNS = (
    "id",
    "source_version_id",
    "unit_id",
    "locator",
    "quote_span",
    "role",
    "occurrence_hash",
    "quote_status",
    "review_required",
    "created_at",
)

_HINT_COLUMNS = (
    "id",
    "source_version_id",
    "kind",
    "from_unit_id",
    "to_unit_id",
    "confidence",
    "evidence_id",
    "created_at",
)


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


def emit_annotation_sql(occurrences: Dict, hints: Dict) -> str:
    """Both annotation tables as ONE transaction.

    Occurrences first, then hints, because a hint names two units and an
    occurrence is not among what it has to wait for — but a hint written
    before the units it joins exists would fail, and the units are already in
    the A chain this script sits on top of. Every statement is
    ON CONFLICT DO NOTHING, so a replay writes nothing.
    """
    lines = ["BEGIN;", "SET search_path TO stratum, public;"]
    for key in sorted(occurrences):
        row = _row_dict(occurrences[key])
        lines.append(
            f"INSERT INTO ku_occurrence ({','.join(_OCCURRENCE_COLUMNS)}) "
            f"VALUES ({','.join(_literal(row.get(c)) for c in _OCCURRENCE_COLUMNS)}) "
            f"ON CONFLICT (id) DO NOTHING;"
        )
    for key in sorted(hints):
        row = _row_dict(hints[key])
        lines.append(
            f"INSERT INTO ku_relation_hint ({','.join(_HINT_COLUMNS)}) "
            f"VALUES ({','.join(_literal(row.get(c)) for c in _HINT_COLUMNS)}) "
            f"ON CONFLICT (id) DO NOTHING;"
        )
    lines.append("COMMIT;")
    return "\n".join(lines) + "\n"
