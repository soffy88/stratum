"""A Repository P7 — projection builder.

Runs the fixed pipeline over the A仓 rows and emits the read artifact.

    P7.1 Load Frozen Units      canonical units and their aliases
            |
            v
    P7.2 Resolve Identity       alias -> canonical, never re-hashed
            |
            v
    P7.3 Attach Evidence        every unit back to its source span
            |
            v
    P7.4 Build Reading Map      chapters, status, last run
            |
            v
    P7.5 Build Coverage         how much has a fact chain
            |
            v
    P7.6 Emit Artifact          canonical JSON, byte-identical on replay

Run: PYTHONPATH=src python3 -m stratum.knowledge.a_repository.projection_builder

    G1 Authority      every table read is an A仓 table
    G2 Traceability   KU -> Evidence -> Source, 100%
    G3 Determinism    three consecutive builds, one hash
    G4 Replay         rebuild mutates nothing and reproduces the artifact
    G5 Isolation      BU2, B仓 and C仓 are untouched

Read-only by construction: this module contains no DML, imports no writer,
and holds no reference to any sink. It reads A仓 through P6's deterministic
rebuild, which is the same seam P5 and P6 use.

Two limitations of A仓 pass through here rather than being smoothed over,
because reporting them is P7's job and fixing them is not:

- `reading_status` is whatever `reading_run.status` says. The chain never
  advances it past READING, so a projection of the pilot reads READING
  forever. P7 reports the row; it does not interpret it.
- `last_run_id` is the last run **by id**, not by time. `reading_run` has
  `started_at` / `completed_at` columns and they are NULL, because P4.1's
  emitter does not write them. So the ordering is deterministic and stable
  but is not a chronology, and this module says so in the spec rather than
  pretending otherwise.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .identity import KUIdentityService
from .ku_evolution_runner import base_sha, migration_evidence
from .ku_identity_runner import build_identity
from .projection import (
    AUTHORITY,
    FORBIDDEN_KG_TABLES,
    PROJECTION_VERSION,
    BookReadingProjection,
    BookUnderstandingProjection,
    ChapterReading,
    EvidenceRef,
    EvidenceTraceProjection,
    KUTraversalView,
    ProjectionViolation,
    UnderstandingCoverageView,
    assert_no_new_ids,
    authority_scan,
    canonical_json,
    content_hash,
    forbid_write,
    identifier_keys,
)
from .verification import VerificationStatus
from .verdict import (
    VERDICT_BLOCKED,
    VERDICT_PASS,
    verdict,
    verdict_inputs,
)


#: §13 fixes the directory; §4 illustrates the file name. Both are honoured:
#: `artifacts/a_repository/p7_projection/book_<book_id>_projection.json`.
ARTIFACT_DIR = Path(__file__).parents[4] / "artifacts" / "a_repository" / \
    "p7_projection"

#: Reading order for traversal. Page, then section, then evidence id.
#:
#: The third key is a tiebreak, not a fact: two units anchored to spans on
#: the same page and in the same section have no reading-order fact
#: separating them, because A仓 records one evidence row per span and
#: nothing about their order on the page. Sorting by evidence id is stable
#: and content-derived, so replay agrees — but it carries no meaning, and a
#: reader must not read one into it.
READING_ORDER = ("page_number", "section", "evidence_id")


class ProjectionError(Exception):
    """The A仓 rows do not support the projection; nothing was emitted."""


# ── P7.1 Load Frozen Units ───────────────────────────────────────────────────

class ProjectionSource:
    """A read-only handle on the A仓 rows P7 is allowed to see."""

    def __init__(self):
        chain = build_identity()
        self.chain = chain
        self.identity: KUIdentityService = chain["identity"]
        # P5's lifecycle service: it owns the revision edges. P6's identity
        # service deliberately does not, because alias resolution and
        # revision history are different questions.
        self.evolution = chain["evolved"]["evolution"]
        self.store = chain["result"]["base"]["pipeline"].store
        self.verifications = chain["result"]["verification"].store.verifications
        self.freeze_store = chain["result"]["freeze"].store
        self.sink = chain["sink"]
        self.units = self.sink.units
        self.evidence = self.store.evidence
        self.candidates = self.store.ku_candidates

    # ── P7.2 Resolve Identity ───────────────────────────────────────────────

    def canonical(self, any_id: str) -> Optional[str]:
        """alias -> canonical. Never re-hashed, never re-minted."""
        return self.identity.resolve(any_id).canonical_ku_id

    def canonical_of(self, unit) -> str:
        return self.identity.canonical_of_unit(unit)

    def aliases_of(self, ku_id: str) -> List[str]:
        return [row.alias_id for row in self.identity.aliases_of(ku_id)]

    def frozen_unit_of(self, unit) -> object:
        """The P4 frozen unit behind a durable row, for its retired id."""
        return self.freeze_store.frozen_units[
            self.freeze_store._unit_by_candidate[unit.candidate_id]]

    def candidate_of(self, unit):
        return self.candidates.get(unit.candidate_id)

    def evidence_of(self, unit):
        candidate = self.candidate_of(unit)
        return self.evidence.get(candidate.evidence_id) if candidate else None

    def verification_of(self, unit):
        return self.verifications.get(unit.verification_id)

    # ── current vs superseded ───────────────────────────────────────────────

    def superseded_ids(self) -> List[str]:
        """Canonical ids a revision has retired.

        §9 forbids deleting, merging or replacing these. They are excluded
        from the navigation views and counted in the coverage view, which is
        the smallest disclosure that keeps them from vanishing.
        """
        return sorted({revision.prior_unit_id
                       for revision in self.sink.revisions.values()})

    def revision_chain(self, ku_id: str) -> List[str]:
        """Oldest-first chain ending at `ku_id`.

        Walks back through prior_of, so a unit that superseded another opens
        with the one it replaced.
        """
        chain = [ku_id]
        cursor = ku_id
        while True:
            prior = self.evolution.prior_of(cursor)
            if not prior:
                break
            chain.append(prior)
            cursor = prior
        return list(reversed(chain))

    def reading_run_for(self, source_version_id: str):
        runs = [run for run in self.store.reading_runs.values()
                if run.source_version_id == source_version_id]
        if not runs:
            return None
        # Last by id. A仓 persists no run timestamp — `started_at` and
        # `completed_at` are NULL — so this ordering is deterministic but
        # is not a chronology. See the module docstring.
        return sorted(runs, key=lambda r: r.id)[-1]

    def source_version_of(self, source_version_id: str):
        return self.store.source_versions.get(source_version_id)


# ── P7.3 Attach Evidence ─────────────────────────────────────────────────────

def evidence_trace(source: ProjectionSource, ku_id: str) -> EvidenceTraceProjection:
    """One unit, and the span it was anchored to."""
    unit = source.units.get(ku_id)
    if unit is None:
        raise ProjectionError(f"{ku_id} is not a durable unit.")
    candidate = source.candidate_of(unit)
    if candidate is None:
        raise ProjectionError(f"{ku_id} has no candidate.")
    evidence = source.evidence.get(candidate.evidence_id)
    if evidence is None:
        raise ProjectionError(f"{ku_id} has no evidence.")
    return EvidenceTraceProjection(
        ku_id=ku_id,
        evidence=(EvidenceRef(
            evidence_id=evidence.id,
            source_version=evidence.source_version_id,
            locator=dict(evidence.locator or {}),
            span=evidence.content_span or "",
            extractor_version=evidence.extractor_version or "",
        ),),
    )


def reading_order_key(source: ProjectionSource, unit) -> Tuple:
    """(page, section, evidence id) — see READING_ORDER."""
    evidence = source.evidence_of(unit)
    if evidence is None:
        raise ProjectionError(f"{unit.id} has no evidence; it cannot be ordered.")
    locator = evidence.locator or {}
    return (evidence.page_number if evidence.page_number is not None else 0,
            str(locator.get("section", "")),
            evidence.id)


def chapter_of(source: ProjectionSource, unit) -> str:
    """The chapter label the evidence locator carries.

    A仓 has no chapter table and no chapter id. It records one chapter
    *label* on every evidence row, and that string is the only chapter
    identity in existence. Minting an id here would be the new knowledge
    P7 must not produce.
    """
    evidence = source.evidence_of(unit)
    if evidence is None:
        raise ProjectionError(f"{unit.id} has no evidence; it has no chapter.")
    return str((evidence.locator or {}).get("chapter", ""))


# ── P7.4 Build Reading Map ───────────────────────────────────────────────────

def build_reading_map(source: ProjectionSource, ku_ids: List[str],
                      book_id: str, source_version_id: str
                      ) -> BookReadingProjection:
    """Chapters, reading status and the last run — all as recorded."""
    chapters: Dict[str, Dict[str, int]] = {}
    order: List[str] = []

    for evidence in source.evidence.values():
        if evidence.source_version_id != source_version_id:
            continue
        label = str((evidence.locator or {}).get("chapter", ""))
        if label not in chapters:
            chapters[label] = {"evidence_count": 0, "ku_count": 0,
                               "verified_count": 0}
            order.append(label)
        chapters[label]["evidence_count"] += 1

    for ku_id in ku_ids:
        label = chapter_of(source, source.units[ku_id])
        if label not in chapters:
            chapters[label] = {"evidence_count": 0, "ku_count": 0,
                               "verified_count": 0}
            order.append(label)
        chapters[label]["ku_count"] += 1
        verification = source.verification_of(source.units[ku_id])
        # Counted from the verification, not assumed equal to ku_count: a
        # frozen unit exists because its verification passed, so the two
        # being equal here is a fact to check rather than a fact to bake in.
        if verification is not None and \
                verification.verification_status == \
                VerificationStatus.VERIFIED.value:
            chapters[label]["verified_count"] += 1

    run = source.reading_run_for(source_version_id)
    return BookReadingProjection(
        book_id=book_id,
        source_version_id=source_version_id,
        chapters=tuple(ChapterReading(
            chapter_id=label,
            title=label,          # same A fact; see ChapterReading
            evidence_count=chapters[label]["evidence_count"],
            ku_count=chapters[label]["ku_count"],
            verified_count=chapters[label]["verified_count"],
        ) for label in sorted(order)),
        reading_status=run.status if run is not None else "",
        last_run_id=run.id if run is not None else "",
    )


# ── P7.5 Build Coverage ──────────────────────────────────────────────────────

def build_coverage(source: ProjectionSource, book_id: str,
                   ku_ids: List[str]) -> UnderstandingCoverageView:
    """How much of the book has a fact chain.

    Not how much of it is true. A unit anchored to a real span can still
    misread that span, and a low number here says nothing about quality.
    """
    run_ids = {run.id for run in source.store.reading_runs.values()}
    total = 0
    rejected = 0
    for verification in source.verifications.values():
        candidate = source.candidates.get(verification.candidate_id)
        if candidate is None or candidate.reading_run_id not in run_ids:
            continue
        total += 1
        if verification.verification_status != \
                VerificationStatus.VERIFIED.value:
            rejected += 1

    traced = sum(1 for ku_id in ku_ids
                 if trace_complete(source, ku_id))
    evidence_coverage = round(traced / len(ku_ids), 4) if ku_ids else 0.0
    verified = len(ku_ids)
    return UnderstandingCoverageView(
        book_id=book_id,
        total_candidates=total,
        verified_units=verified,
        rejected_candidates=rejected,
        coverage_ratio=round(verified / total, 4) if total else 0.0,
        evidence_coverage=evidence_coverage,
        superseded_units=len(source.superseded_ids()),
    )


def trace_complete(source: ProjectionSource, ku_id: str) -> bool:
    """KU -> verification -> candidate -> evidence -> source version."""
    unit = source.units.get(ku_id)
    if unit is None or not unit.canonical_text:
        return False
    verification = source.verification_of(unit)
    candidate = source.candidate_of(unit)
    if verification is None or candidate is None:
        return False
    if verification.verification_status != VerificationStatus.VERIFIED.value:
        return False
    if verification.candidate_id != candidate.id:
        return False
    evidence = source.evidence.get(candidate.evidence_id)
    if evidence is None:
        return False
    if evidence.source_version_id != unit.source_version_id:
        return False
    return evidence.source_version_id in source.store.source_versions


# ── the pipeline ─────────────────────────────────────────────────────────────

def build_projection() -> BookUnderstandingProjection:
    """P7.1 → P7.6. Deterministic, read-only, no arguments.

    There is deliberately no parameter. A projection built from anything but
    the whole frozen A仓 chain would be a projection of a subset, and this
    stage has no concept of a subset.
    """
    source = ProjectionSource()

    # P7.1 + P7.2 — canonical units only. A superseded unit is still
    # reachable through its successor's revision_chain, never dropped.
    superseded = set(source.superseded_ids())
    ku_ids = sorted(ku for ku in source.units if ku not in superseded)
    if not ku_ids:
        raise ProjectionError("A仓 has no current knowledge unit to project.")
    for ku_id in ku_ids:
        if source.canonical(ku_id) != ku_id:
            raise ProjectionError(
                f"{ku_id} is not canonical; the projection must key on "
                "knowledge_unit.id only.")

    book_source = source.store.book_sources[
        sorted(source.store.book_sources)[0]]
    source_version_id = book_source and sorted(
        source.store.source_versions,
        key=lambda sv: source.store.source_versions[sv].book_source_id
        == book_source.id)[0]
    version = source.source_version_of(source_version_id)
    if version is None:
        raise ProjectionError(f"source version {source_version_id} is missing.")

    # P7.3
    traces = [evidence_trace(source, ku_id) for ku_id in ku_ids]

    # P7.4
    reading_map = build_reading_map(source, ku_ids, book_source.id,
                                    source_version_id)

    # P7.5
    coverage = build_coverage(source, book_source.id, ku_ids)

    traversal = build_traversal(source, ku_ids)

    return BookUnderstandingProjection(
        authority=AUTHORITY,
        projection_version=PROJECTION_VERSION,
        book_id=book_source.id,
        book_title=book_source.title,
        source_version_id=source_version_id,
        reading_map=reading_map,
        evidence_traces=tuple(traces),
        traversal=traversal,
        coverage=coverage,
    )


def build_traversal(source: ProjectionSource, ku_ids: List[str]
                    ) -> List[KUTraversalView]:
    """P7.4b — reading order and revision chains. Nothing inferred."""
    ordered = sorted(ku_ids,
                     key=lambda ku: reading_order_key(source, source.units[ku]))
    by_chapter: Dict[str, List[str]] = {}
    for ku_id in ordered:
        by_chapter.setdefault(chapter_of(source, source.units[ku_id]),
                              []).append(ku_id)

    views: List[KUTraversalView] = []
    for index, ku_id in enumerate(ordered):
        unit = source.units[ku_id]
        views.append(KUTraversalView(
            ku_id=ku_id,
            previous=ordered[index - 1] if index else None,
            next=ordered[index + 1] if index + 1 < len(ordered) else None,
            same_chapter_units=tuple(by_chapter[
                chapter_of(source, unit)]),
            revision_chain=tuple(source.revision_chain(ku_id)),
        ))
    return tuple(views)


# ── P7.6 Emit Artifact ───────────────────────────────────────────────────────

def artifact_name(projection: BookUnderstandingProjection) -> str:
    """`book_<book_id>_projection.json` — keyed by an A仓 id, as §4 shows."""
    return f"book_{projection.book_id}_projection.json"


def write_artifact(projection: BookUnderstandingProjection,
                   directory: Optional[Path] = None) -> Path:
    """Write the canonical JSON. Never touches A仓; only writes the file."""
    target = (directory or ARTIFACT_DIR) / artifact_name(projection)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(canonical_json(projection.payload()), encoding="utf-8")
    return target


# ── G1 Authority ─────────────────────────────────────────────────────────────

#: Modules the projection layer is allowed to import. A仓 chain plus the
#: standard library — which is what makes "reaches nothing else" structural
#: rather than a promise, since P7 cannot read a repository it cannot
#: import.
ALLOWED_IMPORT_ROOTS = frozenset({
    "__future__", "json", "os", "re", "pathlib", "typing", "dataclasses",
    "hashlib",
    "pilot_corpus", "identity", "ku_identity_runner", "ku_evolution_runner",
    "projection", "verification", "verdict",
    ".", ".identity", ".ku_identity_runner", ".ku_evolution_runner",
    ".projection", ".verification", ".verdict",
    ". import pilot_corpus as C",
})


def _imports_of(module: str) -> List[str]:
    """The real imports of one module.

    Docstrings and comments are stripped first: prose that happens to begin
    with "from" is not an import, and a gate that reads it as one fails for
    the wrong reason.
    """
    source = (Path(__file__).parent / f"{module}.py").read_text(
        encoding="utf-8")
    code = re.sub(r'""".*?"""', "", source, flags=re.DOTALL)
    code = re.sub(r"^\s*#.*$", "", code, flags=re.MULTILINE)
    return sorted(set(re.findall(r"^\s*(?:from|import)\s+([\w.]+)",
                                 code, re.MULTILINE)))


def external_imports() -> List[str]:
    """Imports outside the A chain. Empty is the requirement."""
    found: List[str] = []
    for module in ("projection", "projection_builder"):
        for name in _imports_of(module):
            root = name.split(".")[0] if not name.startswith(".") else name
            if root not in ALLOWED_IMPORT_ROOTS and \
                    not name.startswith(".knowledge"):
                found.append(f"{module}:{name}")
    return sorted(set(found))


def artifact_drift(payload: Dict) -> Dict[str, List[str]]:
    """Forbidden authority anywhere in the emitted artifact.

    The artifact rather than the source: a source file legitimately contains
    the forbidden-name list that G1 checks against, so scanning the source
    would always find the list and always fail. What has to be clean is the
    output.
    """
    found = authority_scan(canonical_json(payload))
    text = canonical_json(payload).lower()
    for table in FORBIDDEN_KG_TABLES:
        if table in text:
            found.setdefault(table, ["artifact"])
    return found


def authority_gate(projection: BookUnderstandingProjection) -> str:
    """A_ONLY — the artifact carries no other repository, and the layer
    cannot reach one even if asked."""
    if artifact_drift(projection.payload()):
        return "FAIL"
    if external_imports():
        return "FAIL"
    return "PASS"


def authority_drift(projection: BookUnderstandingProjection) -> Dict:
    """The empty result G1 requires, spelled out for the report."""
    return {"artifact": artifact_drift(projection.payload()),
            "external_imports": external_imports()}


def no_new_id_gate(projection: BookUnderstandingProjection) -> str:
    """§5 — no projection mints a business identity."""
    return "FAIL" if assert_no_new_ids(projection.payload()) else "PASS"


# ── G2 Traceability ──────────────────────────────────────────────────────────

def traceability_gate(projection: BookUnderstandingProjection) -> str:
    """KU -> Evidence -> Source, 100%, for every id in the artifact."""
    source = ProjectionSource()
    seen = set()
    for trace in projection.evidence_traces:
        if not trace.evidence:
            return "FAIL"
        for ref in trace.evidence:
            if not ref.evidence_id or not ref.span:
                return "FAIL"
            if not ref.source_version:
                return "FAIL"
            if ref.source_version not in source.store.source_versions:
                return "FAIL"
        seen.add(trace.ku_id)
    if not seen:
        return "FAIL"
    for ku_id in seen:
        if not trace_complete(source, ku_id):
            return "FAIL"
    return "PASS"


# ── G3 Determinism ───────────────────────────────────────────────────────────

def determinism_gate() -> Dict[str, object]:
    """Three consecutive builds must produce one hash."""
    hashes = [content_hash(build_projection().payload()) for _ in range(3)]
    return {"hashes": hashes, "identical": int(len(set(hashes)) == 1)}


# ── G4 Replay ────────────────────────────────────────────────────────────────

def replay_gate(projection: BookUnderstandingProjection) -> Dict[str, object]:
    """Rebuild: same artifact, and no A仓 row moved.

    Both halves matter. A rebuild that reproduces the bytes while quietly
    changing a row would be a worse outcome than one that changed the bytes.
    """
    before = _a_state()
    rebuilt = build_projection()
    after = _a_state()
    return {
        "same_payload": int(canonical_json(rebuilt.payload())
                            == canonical_json(projection.payload())),
        "same_hash": int(content_hash(rebuilt.payload())
                         == content_hash(projection.payload())),
        "no_mutation": int(before == after),
        "unit_count": len(before.get("knowledge_unit", {})),
    }


def _a_state() -> Dict[str, Dict]:
    """Every A仓 row P7 can see, as a comparable dict.

    The mutation check compares this before and after a rebuild. It covers
    units, evidence, candidates, verifications, revisions and identities:
    the tables §1 puts inside the authority boundary.
    """
    source = ProjectionSource()
    return {
        "knowledge_unit": {k: dict(vars(v)) for k, v in
                           sorted(source.sink.units.items())},
        "reading_evidence": {k: dict(vars(v)) for k, v in
                             sorted(source.evidence.items())},
        "ku_candidate": {k: dict(vars(v)) for k, v in
                         sorted(source.candidates.items())},
        "ku_verification": {k: dict(vars(v)) for k, v in
                            sorted(source.verifications.items())},
        "ku_revision": {k: dict(vars(v)) for k, v in
                        sorted(source.sink.revisions.items())},
        "ku_identity": {k: dict(vars(v)) for k, v in
                        sorted(source.sink.identities.items())},
    }


def read_only_gate() -> str:
    """The projection layer cannot write A仓 even if asked.

    The views are frozen dataclasses, the guard raises, and the builder's
    source carries no DML at all.
    """
    builder = (Path(__file__).parent / "projection_builder.py").read_text(
        encoding="utf-8")
    code = re.sub(r'""".*?"""', "", builder, flags=re.DOTALL)
    code = re.sub(r"^\s*#.*$", "", code, flags=re.MULTILINE)
    if re.search(r"^[ \t]*(INSERT|UPDATE|DELETE|DROP)\b", code, re.MULTILINE):
        return "FAIL"
    try:
        forbid_write("knowledge_unit")
    except ProjectionViolation:
        pass
    else:
        return "FAIL"
    view = build_projection()
    try:
        view.book_id = "ku_forged"          # type: ignore[misc]
    except Exception:
        pass
    else:
        return "FAIL"
    try:
        view.reading_map.chapters + ("forged",)   # type: ignore[assignment]
    except Exception:
        pass
    try:
        view.reading_map.chapters[0].evidence_count = 99   # type: ignore[misc]
    except Exception:
        pass
    else:
        return "FAIL"
    return "PASS"


# ── G5 Isolation ─────────────────────────────────────────────────────────────

#: Tables belonging to repositories P7 must not touch. Named here so the
#: claim is checkable; checked against the emitted artifact and the import
#: graph, never against this file's own source text — a forbidden-name list
#: inside the scanned file would match itself.
ISOLATED_TABLES = {
    "bu2": ("chapter_bu", "bu_onto", "bu_learning_state"),
    "b": ("refined_ku", "refined_concept", "b_unit"),
    "c": ("learning_progress", "mastery", "learning_card"),
}


#: The tables P7 reads. Named here so the gate can check they are all present
#: rather than trusting that a database it has never connected to has them.
REQUIRED_TABLES = frozenset({
    "book_source", "source_version", "reading_run", "reading_evidence",
    "evidence_quality", "ku_candidate", "ku_verification", "knowledge_unit",
    "ku_freeze_event", "ku_revision", "ku_confidence_evolution",
    "ku_identity",
})


def catalog_tables(path: Optional[str] = None) -> Optional[Set[str]]:
    """The tables a DBA-side query found, from A_P7_DB_TABLES.

    Absent means unknown, and unknown is NOT_PASS rather than PASS. The previous
    form of this check counted tables whose *name* contained "projection" and
    required the answer to be zero. That is true on staging and false on a
    complete database, where migrations 047-049 create three tables belonging
    to other subsystems -- so it passed for the wrong reason, and a substring is
    not a statement about ownership in any case.
    """
    target = path or os.environ.get("A_P7_DB_TABLES")
    if not target:
        return None
    source = Path(target)
    if not source.exists():
        return None
    # An empty catalog is a fact, not an absence of one: a database with no A
    # tables is a database P7 cannot read, and that is FAIL. Only a missing or
    # unset file means the catalog is unknown.
    return {word.strip() for word in re.split(r"[\s,]+",
                                             source.read_text(encoding="utf-8"))
            if word.strip()}


def schema_closure_gate() -> str:
    """G5's schema half: P7 needs its tables, and owns none.

    Two questions, both answered from the catalog rather than from a name:

      are all the tables P7 reads present?   missing -> FAIL
      does P7 own a table?                   declared -> FAIL

    The second stays a migration-history question, because that is where the
    truth lives: a stage cannot own a table it never declared.
    """
    if schema_change_count()["schema_change"] != 0:
        return "FAIL"
    present = catalog_tables()
    if present is None:
        return "NOT_EXECUTED"
    if not REQUIRED_TABLES <= present:
        return "FAIL"
    # P7 owns nothing. Only P7's own naming counts here; `*projection*` belongs
    # to other repositories and says nothing about this stage.
    if any(name.lower().startswith("p7") or "_p7" in name.lower()
           for name in present):
        return "FAIL"
    return "PASS"


def isolation_gate(projection: BookUnderstandingProjection) -> str:
    """BU2, B仓 and C仓 are untouched by this stage.

    Two independent reasons, either sufficient: P7 adds no migration, so
    there is no schema surface on which it could touch another repository;
    and it reads only A仓, so it has no path to one.
    """
    if schema_change_count()["schema_change"] != 0:
        return "FAIL"
    if artifact_drift(projection.payload()):
        return "FAIL"
    if external_imports():
        return "FAIL"
    if schema_closure_gate() == "FAIL":
        return "FAIL"
    return "PASS"


def isolation_drift(projection: BookUnderstandingProjection) -> Dict:
    """Which other-repository tables this stage names anywhere it counts.
    Empty."""
    artifact = canonical_json(projection.payload())
    imports = " ".join(_imports_of("projection")
                      + _imports_of("projection_builder"))
    found: Dict[str, List[str]] = {}
    for repository, tables in ISOLATED_TABLES.items():
        for table in tables:
            where = []
            if table in artifact:
                where.append("artifact")
            if table in imports:
                where.append("import")
            if where:
                found[f"{repository}.{table}"] = where
    return found


def schema_change_count() -> Dict[str, int]:
    """DB_MUTATION and SCHEMA_CHANGE, both zero by construction.

    P7 declares no table. If a `*p7*` migration ever appears, this returns a
    non-zero count and G5 fails rather than letting the stage grow a schema
    surface nobody authorised.
    """
    migrations = Path(__file__).parents[2] / "db" / "pg_migrations"
    p7 = sorted(p.name for p in migrations.glob("*p7*"))
    return {"db_mutation": len(p7), "schema_change": len(p7)}


# ── report ───────────────────────────────────────────────────────────────────

# There was a `GATE_ORDER` here listing five names beside the gates this
# function returns. It was five while the function returned seven:
# `G1_no_new_id` and `G1_read_only` were reported to the reader and missing from
# the list. The list was short on the day it was written.
#
# It is deleted rather than corrected. Correcting five to seven would leave the
# mechanism that produced the drift in place for the eighth gate, and it is the
# mechanism -- a parallel list of names -- not the length that was wrong. Order
# now comes from the mapping `gate_results` returns, and the verdict is computed
# from that same mapping by the shared contract in verdict.py, the same way P5
# Evolution and P6 compute theirs.


def gate_results(projection: BookUnderstandingProjection) -> Dict[str, object]:
    """Every gate, which is all of them. A gate that cannot be evidenced is
    NOT_EXECUTED rather than omitted, so nothing can go missing by not being
    reported."""
    determinism = determinism_gate()
    replay = replay_gate(projection)
    return {
        "G1_authority": authority_gate(projection),
        "G1_no_new_id": no_new_id_gate(projection),
        "G1_read_only": read_only_gate(),
        "G2_traceability": traceability_gate(projection),
        "G3_determinism": "PASS" if determinism["identical"] == 1
        else "FAIL",
        "G4_replay": "PASS" if (replay["same_payload"] == 1
                                and replay["same_hash"] == 1
                                and replay["no_mutation"] == 1) else "FAIL",
        "G5_isolation": isolation_gate(projection),
        "G5_schema_closure": schema_closure_gate(),
    }


def report(projection: BookUnderstandingProjection) -> Dict:
    """The final acceptance report the task asks for."""
    payload = projection.payload()
    determinism = determinism_gate()
    replay = replay_gate(projection)
    mutation = schema_change_count()
    ids, forbidden = identifier_keys(payload)
    chain = ProjectionSource()
    gates = gate_results(projection)
    return {
        "task": "A_P7_BOOK_UNDERSTANDING_PROJECTION",
        "authority": AUTHORITY,
        "projection_version": PROJECTION_VERSION,
        "book_id": projection.book_id,
        "source_version_id": projection.source_version_id,
        "content_hash": content_hash(payload),
        "artifact": artifact_name(projection),
        "gates": gates,
        "verdict_inputs": verdict_inputs(gates),
        "A_P7_BOOK_UNDERSTANDING_PROJECTION": verdict(gates),
        "traceability": ("100%" if traceability_gate(projection) == "PASS"
                         else "FAIL"),
        "determinism": f"{determinism['hashes'][0]} x3="
                       f"{'identical' if determinism['identical'] else 'DIFFERENT'}",
        "replay": ("PASS" if replay["same_payload"] == 1
                   and replay["no_mutation"] == 1 else "FAIL"),
        "authority_drift": authority_drift(projection),
        "isolation_drift": isolation_drift(projection),
        "db_mutation": mutation["db_mutation"],
        "schema_change": mutation["schema_change"],
        "identity_drift": int(no_new_id_gate(projection) != "PASS"),
        "identifier_fields": ids,
        "forbidden_identifier_fields": forbidden,
        "unit_count": len(chain.units),
        "superseded_units": len(chain.superseded_ids()),
        "coverage": payload["coverage"],
        "reading_map": payload["reading_map"],
        "chapters": len(payload["reading_map"]["chapters"]),
        "traversal_units": len(payload["traversal"]),
        "aliases_resolvable": sum(
            1 for ku in chain.units if chain.aliases_of(ku)
            and chain.canonical(chain.aliases_of(ku)[0]) == ku),
    }


# ── freeze ────────────────────────────────────────────────────────────────────

#: Evidence a freeze cannot be written without. Absent evidence stays
#: UNVERIFIED and blocks, exactly as in P5 Evolution: the P5 freeze gate was
#: first written to check only this and let a blocked layer through.
FREEZE_EVIDENCE = ("dependency_closure", "db_acceptance")


def freeze_artifact(projection: BookUnderstandingProjection) -> Dict:
    """The evidence artifact that closes this stage.

    P7 declares no migration, so `declared_migrations` is 0 by design rather
    than by measurement. The A chain it reads is fingerprinted anyway: a
    read-only projection is still entitled to say which rows it read, and the
    chain moved from 7 to 13 underneath this stage's spec.
    """
    gates = gate_results(projection)
    doc = report(projection)
    fingerprints, destructive = migration_evidence()
    doc.update({
        "stage": "P7_PROJECTION",
        "base_sha": base_sha("A_P7_BASE_SHA"),
        "declared_migrations": 0,
        "chain_read": len(fingerprints),
        "chain_fingerprints": fingerprints,
        "destructive_in_chain_read": destructive,
        "dependency_closure": os.environ.get(
            "A_P7_DEPENDENCY_CLOSURE", "UNVERIFIED"),
        "db_acceptance": os.environ.get("A_P7_DB_ACCEPTANCE", "UNVERIFIED"),
        "db_acceptance_mode": "read-only cross-check against staging",
        "verdict_inputs": verdict_inputs(gates),
        "verdict": verdict(gates),
    })
    return doc


def freeze_blockers(doc: Dict) -> List[str]:
    """Why a freeze may not be written. Empty means it may be.

    Two kinds of "no", both required: evidence that was never recorded, and a
    layer verdict that never reached PASS.
    """
    blockers = [key for key in FREEZE_EVIDENCE if doc[key] != VERDICT_PASS]
    if doc["verdict"] != VERDICT_PASS:
        blockers.append(f"layer_verdict:{doc['verdict']}")
    return blockers


def main() -> None:
    target = os.environ.get("A_P7_FREEZE_ARTIFACT")
    if target:
        doc = freeze_artifact(build_projection())
        blockers = freeze_blockers(doc)
        if blockers:
            print(json.dumps({"A_P7_PROJECTION_FREEZE": VERDICT_BLOCKED,
                              "blockers": blockers,
                              "verdict": doc["verdict"]},
                             ensure_ascii=False, indent=2))
            raise SystemExit(1)
        Path(target).write_text(
            json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        print(json.dumps({"A_P7_PROJECTION_FREEZE": doc["verdict"],
                          "artifact": target,
                          "base_sha": doc["base_sha"],
                          "db_mutation": doc["db_mutation"],
                          "schema_change": doc["schema_change"]},
                         ensure_ascii=False, indent=2))
        return
    projection = build_projection()
    path = write_artifact(projection)
    doc = report(projection)
    doc["artifact_path"] = str(path.relative_to(Path(__file__).parents[4]))
    print(json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
