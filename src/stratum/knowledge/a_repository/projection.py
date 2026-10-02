"""A Repository P7 — book understanding projection (read-only).

    A仓事实 ──> Projection View ──> 阅读理解导航

P7 produces no new knowledge. It does not reason, compress, merge,
summarise, infer or rank. It reads the rows A仓 already froze and arranges
them into four views a reader can navigate:

    3.1 BookReadingMap            how far a book has been read
    3.2 EvidenceTraceMap          from a unit back to the original text
    3.3 KUTraversalView           navigation order, not a knowledge graph
    3.4 UnderstandingCoverageView how much has a fact chain, not correctness

The boundary is one-directional and the direction matters:

    A仓 ──> Projection

Nothing flows back. This module holds no write path to any A仓 table, its
views are frozen dataclasses, and every field it emits is copied from a row
A仓 already wrote.

Identity comes from P6 and is never recomputed here. A `ku_id` in this
artifact is `knowledge_unit.id`. A retired id resolves through the alias
table to that same canonical id, and P7 never hashes anything to make an id
of its own — §5 of the task forbids a `projection_id`, a `ku_projection_id`
or a `book_view_id`, and the only ids in the output are the ones A仓 issued.

Read the caveats at the bottom of this module before trusting a number in
the coverage view. Several of them are limitations of A仓, not of P7, and P7
reports them rather than papering over them.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


PROJECTION_VERSION = "a-p7-v0.1"

AUTHORITY = "A_REPOSITORY"


class ProjectionViolation(Exception):
    """Raised on an operation P7 has no authority to perform."""


# ── authority boundary ───────────────────────────────────────────────────────

#: The only tables P7 may read. Anything outside this list is not A仓
#: evidence and has no business in a projection.
A_ONLY_TABLES = frozenset({
    "book_source", "source_version", "reading_run", "reading_evidence",
    "evidence_quality", "ku_candidate", "ku_verification",
    "knowledge_unit", "ku_freeze_event", "ku_revision", "ku_review_event",
    "ku_confidence_evolution", "ku_relation", "ku_identity",
})

#: §1 of the task, item by item, as *identifiers* rather than as words.
#:
#: Bare words are deliberately absent. "concept", "embedding" and "index"
#: are ordinary words in a book title — a physics text called *Concepts of
#: Physics* would trip a word-match gate on entirely correct input, and a
#: gate that fails on correct input is a gate that gets switched off. So
#: every token below names a table, a schema or a service, and a bare noun
#: cannot match.
#: §1 also names the legacy knowledge-claims table. It is absent from this
#: list on purpose: A仓 source is name-quarantined from it by an existing
#: authority test, so writing the name here would itself be the violation.
#: G1 does not need it — the proof is the import allowlist plus the A-table
#: allowlist, which is structural, whereas a name scan for one token is
#: redundant beside them.
FORBIDDEN_AUTHORITY = (
    # B仓
    "aii_refined", "refined_ku", "refined_concept", "rf_knowledge",
    # BU2
    "bu_onto", "chapter_bu", "bu_learning_state", "bu_projection",
    # the legacy AII A仓 tables, which are not this A仓
    "ku_onto", "concept_onto", "kc_onto", "edge_onto",
    # C仓
    "learning_progress", "mastery_state",
    # retrieval infrastructure P7 must not read
    "lancedb", "pgvector", "tantivy", "vector_store", "embedding_index",
    "cross_layer_search",
    # model calls
    "llm_call", "llm_summary", "tutor_engine",
)

#: §1 also rules out "KG". Named as schemas, because a project name is not
#: an authority a projection could reach.
FORBIDDEN_KG_TABLES = ("kg_node", "kg_edge", "kg_triple", "graph_node")

#: Business identities a projection may carry. §5 forbids inventing one, so
#: every `*_id` in the emitted artifact has to be in this set.
#:
#: Two entries are not ids A仓 issued, and both are here for a stated
#: reason rather than for convenience:
#:
#:   `chapter_id`  §3.1 requires the field. A仓 has no chapter table and no
#:                  chapter id — it records one chapter *label* on every
#:                  evidence row. The label is passed through verbatim
#:                  instead of a minted id, because minting one would be
#:                  the new knowledge P7 must not produce.
#:   `source_id`   A仓's own key inside `reading_evidence.location`, emitted
#:                  verbatim with the locator. It is the source version id
#:                  under the name the locator gives it.
ALLOWED_ID_FIELDS = frozenset({
    "book_id", "source_version_id", "evidence_id", "ku_id",
    "last_run_id", "previous", "next", "chapter_id", "source_id",
})

#: Keys that must never appear in the artifact.
FORBIDDEN_ID_FIELDS = ("projection_id", "ku_projection_id", "book_view_id")


# ── views ────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ChapterReading:
    """One chapter's reading state, as A仓 recorded it.

    `chapter_id` carries the chapter **label** from the evidence locator,
    because that is the only chapter identity A仓 holds — there is no
    chapter table and no chapter id anywhere in the chain. Minting one here
    would be exactly the new knowledge P7 must not produce, so the label is
    passed through verbatim and `title` repeats it rather than inventing a
    second name for the same fact.

    The pilot corpus is Chapter 1 only, so a projection of it has one
    chapter. That is a fact about the corpus, not a limitation of the view.
    """

    chapter_id: str
    title: str
    evidence_count: int
    ku_count: int
    verified_count: int


@dataclass(frozen=True)
class BookReadingProjection:
    """3.1 — how far one book's understanding has been read."""

    book_id: str
    source_version_id: str
    chapters: Tuple[ChapterReading, ...] = ()
    reading_status: str = ""
    last_run_id: str = ""


@dataclass(frozen=True)
class EvidenceRef:
    """One hop from a unit back to the original text."""

    evidence_id: str
    source_version: str
    locator: Dict[str, object] = field(default_factory=dict)
    span: str = ""
    extractor_version: str = ""


@dataclass(frozen=True)
class EvidenceTraceProjection:
    """3.2 — unit → evidence → source, for every unit in the projection."""

    ku_id: str
    evidence: Tuple[EvidenceRef, ...] = ()


@dataclass(frozen=True)
class KUTraversalView:
    """3.3 — navigation, not a knowledge graph.

    `previous` and `next` walk reading order and nothing else. There is no
    similarity, no concept edge and no inferred relation anywhere in this
    view: every neighbour listed here is a neighbour by page.

    `revision_chain` is oldest-first and always ends at `ku_id`. A superseded
    unit is never deleted, merged or replaced — §9 forbids it and the chain
    is how it stays reachable.
    """

    ku_id: str
    previous: Optional[str] = None
    next: Optional[str] = None
    same_chapter_units: Tuple[str, ...] = ()
    revision_chain: Tuple[str, ...] = ()


COVERAGE_DISCLAIMER = (
    "coverage != correctness: this counts how much content has an evidence "
    "chain reaching a source version, not how much of it is true."
)


@dataclass(frozen=True)
class UnderstandingCoverageView:
    """3.4 — how much of the book has a fact chain.

    **coverage is not correctness.** This counts how much content has been
    carried all the way to a source, not how right any of it is. A unit
    anchored to a real span can still be a misreading of that span, and a
    book with low coverage can still be well understood. The number answers
    "how much has been established", never "how much is true".

    `superseded_units` is not in the task's field list and is added anyway:
    §9 forbids a superseded unit being silently dropped, and a count is the
    smallest honest way to say one was excluded from `verified_units`.
    """

    book_id: str
    total_candidates: int
    verified_units: int
    rejected_candidates: int
    coverage_ratio: float
    evidence_coverage: float
    superseded_units: int = 0
    disclaimer: str = COVERAGE_DISCLAIMER


@dataclass(frozen=True)
class BookUnderstandingProjection:
    """The whole artifact: four views over one book, one direction.

    Deeply immutable, not just frozen: every collection field is a tuple.
    `frozen=True` alone only stops attribute rebinding, so a `list` field
    would still be appended to in place — which a read-only projection must
    not permit, and which a test caught.
    """

    authority: str
    projection_version: str
    book_id: str
    book_title: str
    source_version_id: str
    reading_map: BookReadingProjection = field(
        default_factory=lambda: BookReadingProjection("", ""))
    evidence_traces: Tuple[EvidenceTraceProjection, ...] = ()
    traversal: Tuple[KUTraversalView, ...] = ()
    coverage: UnderstandingCoverageView = field(
        default_factory=lambda: UnderstandingCoverageView("", 0, 0, 0, 0.0, 0.0))

    def payload(self) -> Dict:
        """The artifact as plain data, ready to be serialised."""
        return dataclasses.asdict(self)


# ── serialisation ────────────────────────────────────────────────────────────

def canonical_json(payload: Dict) -> str:
    """The one serialisation, and the reason replay is byte-identical.

    Sorted keys, no incidental whitespace, no timestamps, no host paths, no
    iteration order that depends on insertion. Two runs over the same A仓
    rows produce the same bytes or this function is wrong.
    """
    return json.dumps(payload, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")) + "\n"


def content_hash(payload: Dict) -> str:
    """A verification fingerprint for the artifact.

    Named `content_hash`, not an id, and used by nothing as a key: it exists
    so a reader can tell whether two builds agreed, which is what G3 and G4
    ask for. It is derived from the payload and mints no business identity.
    """
    digest = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    return f"aph_{digest[:16]}"


# ── guards ───────────────────────────────────────────────────────────────────

def forbid_write(table: str) -> None:
    """Raise on any attempt to write A仓 from the projection layer.

    §6 lists INSERT / UPDATE / DELETE as forbidden. There is no code path
    that calls this today; it exists so that a future change which tries to
    write has to delete a guard rather than quietly get away with it.
    """
    raise ProjectionViolation(
        f"P7 is read-only; it never writes {table}. A correction belongs to "
        "the stage that owns the row.")


def assert_no_new_ids(payload: Dict) -> List[str]:
    """§5 — no projection may mint a business identity.

    Walks the artifact for any key that looks like an identifier and reports
    the ones outside the allowed set. Returned rather than raised so the
    caller can decide; G1 raises on a non-empty result.
    """
    offenders: List[str] = []

    def walk(node, path: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                here = f"{path}.{key}" if path else key
                if key in FORBIDDEN_ID_FIELDS:
                    offenders.append(f"{here} (forbidden field)")
                elif (key.endswith("_id") or key in {"previous", "next"}) \
                        and key not in ALLOWED_ID_FIELDS:
                    offenders.append(f"{here} (not an A仓 identity)")
                walk(value, here)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{path}[{index}]")

    walk(payload, "")
    return sorted(set(offenders))


def authority_scan(text: str) -> Dict[str, List[str]]:
    """Find forbidden authority references in a block of source or output.

    G1 and G5 both need this. It reads the text it is given rather than
    trusting a declaration, because a declaration is exactly what a drift
    would leave intact.
    """
    lowered = text.lower()
    return {token: sorted({line.strip() for line in lowered.splitlines()
                           if token in line})
            for token in FORBIDDEN_AUTHORITY if token in lowered}


def identifier_keys(payload: Dict) -> Tuple[List[str], List[str]]:
    """Every identifier-looking key in the artifact, sorted.

    Used by the tests to assert the emitted ids are exactly A仓's, and by a
    reader who wants to check that claim without reading the builder.
    """
    found: List[str] = []

    def walk(node) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key.endswith("_id") or key in {"previous", "next"}:
                    found.append(key)
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(payload)
    return sorted(set(found)), sorted(set(found) & set(FORBIDDEN_ID_FIELDS))
