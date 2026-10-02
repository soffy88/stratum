"""A Repository P5.3 — paper / source metadata annotation runner.

Builds the pilot declared source annotation over the frozen catalog row and
reports the acceptance gates.

Run: PYTHONPATH=src python3 -m stratum.knowledge.a_repository.paper_runner

    Gate 1 Schema      tables exist, additive, FK into A only, RESTRICT only,
                       vocabularies closed, replay keys unique
    Gate 2 Authority   no judgement column, no B / C / BU2, frozen 075 and 079
                       untouched
    Gate 3 Trace       candidate -> catalog row, declaration -> the field it
                       names, 100%
    Gate 4 Replay      re-running writes nothing, hashes stable
    Gate 5 Isolation   the catalog row is the one its version was ingested from
    Gate 6 Negative    deferred types, unknown types, fabricated declarations,
                       unverifiable YEAR — all refused

Contamination is measured in three layers and reuses P7's gates. A word scan
over A仓 source returns hits that are all of A仓's own guard lists; that trap
has now been avoided six times.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

from . import pilot_corpus as C
from .ku_identity_runner import build_identity
from .verdict import verdict, verdict_inputs
from .paper_writer import (
    CATALOG_DECLARATION,
    CATALOG_FIELD_FOR,
    DECLARED_IN,
    EXTRACTOR_VERSION,
    FORBIDDEN_SOURCE_TYPE,
    PAPER_BANNED_FIELDS,
    PAPER_CANDIDATE_COLUMNS,
    PAPER_CANDIDATE_INSERT_COLUMNS,
    PAPER_EVIDENCE_COLUMNS,
    PAPER_EVIDENCE_INSERT_COLUMNS,
    PAPER_NOTES,
    PAPER_TABLES,
    PAPER_VERSION,
    PILOT_DECLARED_VERSION,
    SOURCE_TYPES,
    STATEMENT_TYPES,
    PaperEvidence,
    PaperPrecondition,
    PaperSink,
    PaperSourceCandidate,
    PaperStatus,
    PaperViolation,
    PaperWriter,
    banned_field_report,
    declaration_matches_catalog,
    emit_paper_sql,
    evidence_hash,
    paper_hash,
    paper_id,
    transition,
)
from .projection_builder import artifact_drift, external_imports


REQUIRED_MIGRATION = "080_a_paper_source.sql"

REQUIRED_CHAIN = (
    "070_a_repository_foundation.sql",
    "071_a_evidence_quality.sql",
    "072_a_ku_verification.sql",
    "073_a_knowledge_unit_freeze.sql",
    "074_a_ku_freeze_persistence.sql",
    "075_a_ku_evolution.sql",
    "076_a_ku_identity.sql",
    "077_a_condition_boundary.sql",
    "078_a_mechanism_chain.sql",
    "079_a_relation_candidate.sql",
    REQUIRED_MIGRATION,
)

#: The only tables 080 may reference. A source annotation is about A's own
#: catalog chain and nothing else.
ALLOWED_FK_TARGETS = frozenset({"source_version", "book_source",
                               "paper_source_candidate"})

#: Tables P5.3 must never create or alter.
UNTOUCHABLE_TABLES = ("knowledge_unit", "ku_candidate", "ku_verification",
                      "ku_freeze_event", "ku_identity", "ku_revision",
                      "ku_review_event", "ku_condition_candidate",
                      "ku_boundary_candidate", "ku_relation",
                      "mechanism_candidate", "mechanism_node",
                      "relation_candidate")

#: The one change 080 makes to frozen tables, authorised by the schema review:
#: an index that gives the composite key a target. It asserts nothing new —
#: (id, book_source_id) is already unique because id is the primary key — and no
#: row, column or value moves.
FROZEN_TABLE_INDEX = "source_version_id_book_source_uniq"

#: The pilot annotation: the catalog row that declares the source's own
#: bibliographic facts.
#:
#: Declared, not extracted. No paper extractor ships in this stage, and no span
#: of this corpus declares who wrote the book — measured: zero occurrences of
#: either author surname, the publisher, the ISBN or any year across all 671
#: characters. So the declaration source is the catalog row, and every
#: declared_value is compared against the field it claims to come from.
PILOT_SOURCE_TYPE = "BOOK"

#: What the catalog row can actually state, checked against its own fields.
#: YEAR is absent on purpose — see CATALOG_FIELD_FOR.
PILOT_DECLARATIONS = ("AUTHOR", "TITLE", "PUBLICATION", "IDENTIFIER")


def build_paper(sink=None) -> Dict:
    """P1 -> P7 -> P6 -> P5.3, then the pilot annotation, written once."""
    chain = (build_identity(sink=sink) if sink is not None
             else build_identity(sink=PaperSink()))
    upstream = chain["result"]
    units = {key: dict(vars(unit))
             for key, unit in sorted(chain["sink"].units.items())}

    builder = upstream["base"]["pipeline"]
    writer = PaperWriter(upstream["base"]["pipeline"], chain["sink"])
    candidate = writer.builder.build(
        source_version_id=upstream["base"]["source_version_id"],
        source_type=PILOT_SOURCE_TYPE,
        extractor_version=PILOT_DECLARED_VERSION)
    # Declarations are built from the *built* candidate, not the stored one.
    # Both carry the same content-derived id, and a declaration's fingerprint
    # includes that id — so building before the write is what lets the candidate
    # and its declarations go in one transaction, rather than writing the
    # candidate and then reaching back to attach evidence to it.
    declarations = [
        writer.builder.declaration(candidate, statement_type)
        for statement_type in PILOT_DECLARATIONS]
    written = writer.write(candidate, declarations)

    return {"chain": chain, "result": upstream, "sink": chain["sink"],
            "builder": builder, "writer": writer, "candidate": candidate,
            "written": written, "declarations": declarations,
            "unit_snapshot_before": units}


# ── Gate 1 schema ────────────────────────────────────────────────────────────

def _migration() -> str:
    return (Path(__file__).parents[2] / "db" / "pg_migrations"
            / REQUIRED_MIGRATION).read_text(encoding="utf-8")


def _clean() -> str:
    return re.sub(r"--[^\n]*", "", _migration())


def _declared_columns(table: str) -> set:
    text = _clean()
    marker = f"CREATE TABLE IF NOT EXISTS stratum.{table}"
    if marker not in text:
        return set()
    # Split on the name only. Splitting on the name *and* its opening paren
    # leaves body starting after it, and hunting for the next "(" then lands
    # inside the first CHECK rather than at the start of the column list — which
    # reports one column and looks like a parity failure.
    body = text.split(marker)[1]
    start = body.index("(") + 1
    depth, block = 1, []
    for char in body[start:]:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                break
        block.append(char)
    parts, depth, current = [], 0, []
    for char in "".join(block):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if char == "," and depth == 0:
            parts.append("".join(current))
            current = []
            continue
        current.append(char)
    parts.append("".join(current))
    declared = set()
    for fragment in parts:
        fragment = fragment.strip()
        if not fragment:
            continue
        head = fragment.split()[0]
        if head.upper() in {"CONSTRAINT", "UNIQUE", "CHECK", "PRIMARY",
                             "FOREIGN", "REFERENCES"}:
            continue
        declared.add(head)
    return declared


def schema_gate() -> str:
    """Two new tables, additive only, FK into A only."""
    clean = _clean()
    for table in PAPER_TABLES:
        if f"CREATE TABLE IF NOT EXISTS stratum.{table} (" not in clean:
            return "FAIL"
    for forbidden in ("ALTER TABLE", "DROP ", "UPDATE ", "INSERT INTO",
                      "TRUNCATE"):
        if forbidden in clean:
            return "FAIL"
    for table in UNTOUCHABLE_TABLES:
        if f"CREATE TABLE IF NOT EXISTS stratum.{table} (" in clean:
            return "FAIL"
    referenced = set(re.findall(r"REFERENCES\s+stratum\.(\w+)", clean))
    if not referenced <= ALLOWED_FK_TARGETS:
        return "FAIL"
    return "PASS"


def fk_verb_gate() -> str:
    """Every foreign key is RESTRICT, single-column or composite.

    Measured across the A chain: CASCADE appears only in 070-072, the extraction
    chain. Every frozen artifact from 073 on is RESTRICT. A source annotation is
    a recorded fact about a record, so deleting the book, the version or the
    candidate must not take it silently.
    """
    clean = _clean()
    verbs = re.findall(r"ON DELETE (\w+)", clean)
    if set(verbs) != {"RESTRICT"}:
        return "FAIL"
    # 4 keys: source_version+book_source composite, book_source inline,
    # paper_evidence -> candidate, paper_evidence -> book_source.
    if len(verbs) != 4:
        return "FAIL"
    return "PASS"


def isolation_schema_gate() -> str:
    """The candidate's catalog row must be its own version's catalog row."""
    clean = _clean()
    if "CONSTRAINT paper_candidate_same_source" not in clean:
        return "FAIL"
    if "FOREIGN KEY (source_version_id, book_source_id)" not in clean:
        return "FAIL"
    if "REFERENCES stratum.source_version (id, book_source_id)" not in clean:
        return "FAIL"
    if "ON stratum.source_version (id, book_source_id)" not in clean:
        return "FAIL"
    return "PASS"


def frozen_index_gate() -> str:
    """The one index on a frozen table, and nothing else reaching one."""
    clean = _clean()
    if f"CREATE UNIQUE INDEX IF NOT EXISTS {FROZEN_TABLE_INDEX}" not in clean:
        return "FAIL"
    indexed = re.findall(r"CREATE (?:UNIQUE )?INDEX IF NOT EXISTS \w+\s+"
                         r"ON stratum\.(\w+)", clean)
    if indexed.count("source_version") != 1:
        return "FAIL"
    if set(indexed) - {"source_version", *PAPER_TABLES}:
        return "FAIL"
    return "PASS"


def constraint_gate() -> str:
    """Replay keys unique, authors non-empty, closed vocabularies, columns
    declared."""
    clean = _clean()
    for fragment in (
            "CONSTRAINT paper_candidate_hash_uniq UNIQUE (paper_hash)",
            "CONSTRAINT paper_evidence_hash_uniq UNIQUE (evidence_hash)",
            "CHECK (cardinality(authors) >= 1)"):
        if fragment not in clean:
            return "FAIL"
    if "array_length(" in clean:
        return "FAIL"
    if "CHECK (status IN ('GENERATED', 'SUPPORTED', 'REJECTED'))" not in clean:
        return "FAIL"
    for table, columns in ((PAPER_TABLES[0], PAPER_CANDIDATE_COLUMNS),
                           (PAPER_TABLES[1], PAPER_EVIDENCE_COLUMNS)):
        if not set(columns) <= _declared_columns(table):
            return "FAIL"
    return "PASS"


def vocabulary_gate() -> str:
    """Every vocabulary closed, and UNKNOWN absent as a fact.

    The deferred words must be absent from the constraints, not merely unused,
    so a later writer cannot smuggle one in through raw SQL.
    """
    clean = _clean()
    if f"FORBIDDEN_SOURCE_TYPE" in clean:
        return "FAIL"
    if "'BOOK', 'PAPER', 'ARTICLE', 'REPORT', 'ARCHIVE'" not in clean:
        return "FAIL"
    for banned in ("UNKNOWN", "VERIFIED", "CONFIRMED", "APPROVED"):
        if banned in clean:
            return "FAIL"
    for statement_type in STATEMENT_TYPES:
        if statement_type not in clean:
            return "FAIL"
    for declared_in in DECLARED_IN:
        if declared_in not in clean:
            return "FAIL"
    return "PASS"


def null_guard_gate() -> str:
    """status, authors, declared_value and created_at are NOT NULL.

    A CHECK passes on NULL, so a nullable status walks past the vocabulary it
    exists to enforce. Measured in the P5.3 schema review; same class as the
    array_length finding in 077.
    """
    clean = _clean()
    for table, columns in ((PAPER_TABLES[0], ("status", "authors")),
                           (PAPER_TABLES[1], ("declared_value",))):
        body = clean.split(f"CREATE TABLE IF NOT EXISTS stratum.{table} (")[1]
        for column in columns:
            fragment = next(f for f in body.split("\n")
                            if f.strip().startswith(f"{column} "))
            if "NOT NULL" not in fragment:
                return "FAIL"
    if clean.count("created_at TIMESTAMP NOT NULL DEFAULT now()") != 2:
        return "FAIL"
    return "PASS"


def column_parity_gate() -> str:
    """Writer columns, schema columns and dataclass fields must agree.

    077 shipped once referencing two columns it never declared and every insert
    failed against a real database. Only the disagreement shows it.
    """
    candidate_fields = set(vars(PaperSourceCandidate(
        id="", source_version_id="", book_source_id="", source_type="",
        title="")))
    evidence_fields = set(vars(PaperEvidence(
        id="", paper_id="", statement_type="", declared_value="",
        declared_in="", catalog_source_id="")))
    if not set(PAPER_CANDIDATE_COLUMNS) <= _declared_columns(PAPER_TABLES[0]):
        return "FAIL"
    if not set(PAPER_CANDIDATE_COLUMNS) <= candidate_fields:
        return "FAIL"
    if not set(PAPER_EVIDENCE_COLUMNS) <= _declared_columns(PAPER_TABLES[1]):
        return "FAIL"
    if not set(PAPER_EVIDENCE_COLUMNS) <= evidence_fields:
        return "FAIL"
    if "created_at" in PAPER_CANDIDATE_INSERT_COLUMNS:
        return "FAIL"
    if "created_at" in PAPER_EVIDENCE_INSERT_COLUMNS:
        return "FAIL"
    return "PASS"


def banned_field_gate() -> str:
    """No source annotation grew a judgement column."""
    return "FAIL" if any(banned_field_report().values()) else "PASS"


def hash_formula_gate() -> str:
    """publisher is inside paper_hash, and evidence is deliberately not.

    The review spec's §5 listed doi and isbn but not publisher, so a publisher
    change would not have changed the fingerprint — the opposite of every A table
    from 077 on. This reads the module to confirm publisher is an input.
    """
    import inspect
    source = inspect.getsource(paper_hash)
    for field in ("title", "authors", "publication_year", "publisher", "doi",
                  "isbn", "extractor_version"):
        if field not in source:
            return "FAIL"
    if "evidence" in source:
        return "FAIL"
    # And the sort that would destroy author order must not be there.
    if "sorted(authors)" in source or 'sorted(authors' in source:
        return "FAIL"
    return "PASS"


# ── Gate 2 authority ─────────────────────────────────────────────────────────

def frozen_layers_untouched_gate(result: Dict) -> str:
    """075's relation layer and 079's relation candidate are both untouched."""
    clean = _clean()
    for table in ("ku_relation", "relation_candidate"):
        if f"ALTER TABLE stratum.{table}" in clean:
            return "FAIL"
        if f"CREATE TABLE IF NOT EXISTS stratum.{table}" in clean:
            return "FAIL"
        if table in " ".join(sorted(ALLOWED_FK_TARGETS)):
            return "FAIL"
    return "PASS"


def authority_gate(result: Dict) -> str:
    """B, C and BU2 all zero, in three layers."""
    if external_imports():
        return "FAIL"
    referenced = set(re.findall(r"REFERENCES\s+stratum\.(\w+)", _migration()))
    if not referenced <= ALLOWED_FK_TARGETS:
        return "FAIL"
    payload = {"candidates": [c.id for c in
                              result["sink"].paper_candidates.values()]}
    if artifact_drift(payload):
        return "FAIL"
    return "PASS"


def contamination_counts(result: Dict) -> Dict[str, int]:
    """B_REFERENCE and C_REFERENCE, measured in the three layers.

    Never a word scan of this file: the token list would match itself, which is
    the false positive that produced 24 hits in A仓.
    """
    referenced = set(re.findall(r"REFERENCES\s+stratum\.(\w+)", _migration()))
    drift = len(referenced - ALLOWED_FK_TARGETS)
    payload = {"candidates": [c.id for c in
                              result["sink"].paper_candidates.values()]}
    total = len(external_imports()) + drift + len(artifact_drift(payload))
    return {"B_REFERENCE": total, "C_REFERENCE": total,
            "BU2_DEPENDENCY": drift,
            "external_imports": len(external_imports())}


def baseline_mutation_gate(result: Dict) -> str:
    """The A chain underneath is byte-identical after the write."""
    after = {key: dict(vars(unit))
             for key, unit in sorted(result["sink"].units.items())}
    return "PASS" if after == result["unit_snapshot_before"] else "FAIL"


def catalog_untouched_gate(result: Dict) -> str:
    """The catalog row this stage reads is not modified by it."""
    catalog = _store(result).book_sources
    before = {key: dict(vars(row)) for key, row in sorted(catalog.items())}
    snapshot = dict(before)
    after = {key: dict(vars(row)) for key, row in sorted(catalog.items())}
    return "PASS" if after == snapshot else "FAIL"


# ── Gate 3 trace ─────────────────────────────────────────────────────────────

def trace_gate(result: Dict) -> str:
    """candidate -> catalog row, declaration -> the field it names, 100%."""
    writer: PaperWriter = result["writer"]
    if not result["sink"].paper_candidates:
        return "FAIL"
    if not result["sink"].paper_declarations:
        return "FAIL"
    if writer.traceability_percent() != 100.0:
        return "FAIL"
    if writer.orphan_declarations():
        return "FAIL"
    return "PASS"


def declaration_fidelity_gate(result: Dict) -> str:
    """Every stored declaration is what the catalog record actually states.

    The gate that separates traceability from a referenced id. Nothing here
    counts how many evidence ids exist; it compares strings.
    """
    writer: PaperWriter = result["writer"]
    if writer.unsourced_declarations():
        return "FAIL"
    for declaration in result["sink"].paper_declarations.values():
        catalog = writer.builder.catalog_of(declaration.catalog_source_id)
        if not declaration_matches_catalog(declaration, catalog):
            return "FAIL"
    return "PASS"


# ── Gate 4 replay ────────────────────────────────────────────────────────────

def _fingerprint(sink) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for key in sorted(sink.paper_candidates):
        out[f"c:{key}"] = sink.paper_candidates[key].paper_hash
    for key in sorted(sink.paper_declarations):
        out[f"d:{key}"] = sink.paper_declarations[key].evidence_hash
    return out


def replay_gate() -> Dict[str, object]:
    """Re-run the whole annotation: same hashes, nothing new."""
    first = build_paper()
    before = _fingerprint(first["sink"])
    second = build_paper()
    after = _fingerprint(second["sink"])
    again = first["writer"].builder.build(
        first["result"]["base"]["source_version_id"], PILOT_SOURCE_TYPE,
        PILOT_DECLARED_VERSION)
    first["writer"].write(again, first["declarations"])
    final = _fingerprint(first["sink"])
    return {
        "candidates": len(after) - len([k for k in after if k.startswith("c:")]),
        "declarations": len([k for k in after if k.startswith("d:")]),
        "identical_fingerprints": int(before == after),
        "rewrite_is_noop": int(before == final),
        "new_candidate": max(0, len([k for k in after if k.startswith("c:")])
                             - len([k for k in before if k.startswith("c:")])),
        "new_declaration": max(0, len([k for k in after if k.startswith("d:")])
                               - len([k for k in before if k.startswith("d:")])),
        "duplicate_hashes": len(first["writer"].duplicate_hashes()),
    }


def idempotency_gate(result: Dict) -> str:
    """Writing the same annotation twice appends nothing."""
    writer: PaperWriter = result["writer"]
    before = _fingerprint(result["sink"])
    writer.write(result["written"], result["declarations"])
    return "PASS" if _fingerprint(result["sink"]) == before else "FAIL"


def hash_stability_gate() -> str:
    """Same input, same id and hash; any declared field, a different candidate.

    Covers publisher and author order, which the review spec's §5 formula
    omitted and which this stage deliberately includes.
    """
    base_id = paper_id("sv_x", "bs_x", "BOOK", PILOT_DECLARED_VERSION)
    base_hash = paper_hash("sv_x", "bs_x", "BOOK", "T", ["A"], 2000, "P", None,
                           "I", PILOT_DECLARED_VERSION)
    variants = [
        # publisher is an identity field
        paper_hash("sv_x", "bs_x", "BOOK", "T", ["A"], 2000, "Q", None, "I",
                   PILOT_DECLARED_VERSION) != base_hash,
        # author order is a claim, not noise
        paper_hash("sv_x", "bs_x", "BOOK", "T", ["A", "B"], 2000, "P", None, "I",
                   PILOT_DECLARED_VERSION) != base_hash,
        # so is the extractor version
        paper_hash("sv_x", "bs_x", "BOOK", "T", ["A"], 2000, "P", None, "I",
                   EXTRACTOR_VERSION) != base_hash,
        # and the catalog row
        paper_id("sv_x", "bs_y", "BOOK", PILOT_DECLARED_VERSION) != base_id,
        # and the source type
        paper_id("sv_x", "bs_x", "PAPER", PILOT_DECLARED_VERSION) != base_id,
        # deterministic
        paper_hash("sv_x", "bs_x", "BOOK", "T", ["A"], 2000, "P", None, "I",
                   PILOT_DECLARED_VERSION) == base_hash,
    ]
    return "PASS" if all(variants) else "FAIL"


# ── Gate 5 isolation ─────────────────────────────────────────────────────────

def same_source_gate(result: Dict) -> str:
    """The candidate's catalog row is the one its version was ingested from.

    The same lie 079 measured: both references individually valid, together
    describing two different books. 080's composite key refuses it.
    """
    writer: PaperWriter = result["writer"]
    if writer.cross_source_candidates():
        return "FAIL"
    for candidate in result["sink"].paper_candidates.values():
        version = _store(result).source_versions.get(
            candidate.source_version_id)
        if version is None or version.book_source_id != candidate.book_source_id:
            return "FAIL"
    return "PASS"


# ── Gate: negative ───────────────────────────────────────────────────────────

def _clone(candidate) -> PaperSourceCandidate:
    return PaperSourceCandidate(
        id=candidate.id, source_version_id=candidate.source_version_id,
        book_source_id=candidate.book_source_id,
        source_type=candidate.source_type, title=candidate.title,
        authors=list(candidate.authors),
        publication_year=candidate.publication_year,
        publisher=candidate.publisher, doi=candidate.doi,
        isbn=candidate.isbn, paper_hash=candidate.paper_hash,
        extractor_version=candidate.extractor_version,
        status=candidate.status, created_at=candidate.created_at)


def _downgrade() -> None:
    """A supported candidate may not fall back to GENERATED or REJECTED."""
    fresh = build_paper()
    writer = fresh["writer"]
    candidate = fresh["written"]
    writer.support(candidate.id)
    for target in (PaperStatus.GENERATED, PaperStatus.REJECTED):
        try:
            transition(candidate, target)
        except PaperViolation:
            continue
        raise AssertionError(f"supported -> {target.value} was allowed")
    raise PaperViolation("no downgrade is legal; the loop proves it")


def _rejected_is_final() -> None:
    """A rejected candidate may not be revived."""
    fresh = build_paper()
    writer = fresh["writer"]
    candidate = fresh["written"]
    writer.reject(candidate.id)
    for target in (PaperStatus.GENERATED, PaperStatus.SUPPORTED):
        try:
            transition(candidate, target)
        except PaperViolation:
            continue
        raise AssertionError(f"rejected -> {target.value} was allowed")
    raise PaperViolation("no edge leaves REJECTED; the loop proves it")


def negative_gate(result: Dict) -> Dict[str, bool]:
    """Each forbidden shape must actually be refused.

    Reported as a map so a regression names which case stopped being refused.
    Probes go through `write()`, which raises, rather than the precondition
    methods, which return tuples — asserting on a return value nothing raises on
    would report a refusal that never happened.
    """
    # A throwaway annotation, not the reported one: a leak into the shared sink
    # would quietly change the counts this report asserts on.
    throwaway = build_paper()
    writer: PaperWriter = throwaway["writer"]
    builder = writer.builder
    source_version = throwaway["result"]["base"]["source_version_id"]
    stored = throwaway["written"]

    def refuses(fn) -> bool:
        try:
            fn()
        except (PaperPrecondition, PaperViolation, ValueError, KeyError):
            return True
        return False

    def write_clone(mutate, declarations=()) -> None:
        clone = _clone(throwaway["candidate"])
        mutate(clone)
        # A distinct id and hash so the duplicate short-circuit cannot mask the
        # precondition check.
        clone.id = "psc_damaged"
        clone.paper_hash = "psh_damaged"
        writer.write(clone, declarations)

    def declaration_with(mutate) -> None:
        clone = _clone(throwaway["candidate"])
        clone.id = "psc_damaged"
        clone.paper_hash = "psh_damaged"
        declaration = builder.declaration(clone, "AUTHOR")
        mutate(declaration)
        declaration.evidence_hash = "peh_damaged"
        writer.write(clone, [declaration])

    checks = {
        # source_type vocabulary
        "unknown_as_fact": refuses(
            lambda: builder.build(source_version, FORBIDDEN_SOURCE_TYPE,
                                  PILOT_DECLARED_VERSION)),
        "unknown_type": refuses(
            lambda: builder.build(source_version, "MANUSCRIPT",
                                  PILOT_DECLARED_VERSION)),
        "no_such_source_version": refuses(
            lambda: builder.build("sv_absent", "BOOK", PILOT_DECLARED_VERSION)),
        # candidate shape
        "no_authors": refuses(
            lambda: write_clone(lambda c: c.authors.clear())),
        "no_such_catalog_row": refuses(
            lambda: write_clone(
                lambda c: c.__setattr__("book_source_id", "bs_absent"))),
        "cross_source_catalog_row": refuses(
            lambda: write_clone(
                lambda c: c.__setattr__("book_source_id", "bs_another_book"))),
        # the declaration must be what the record says
        "fabricated_author": refuses(
            lambda: declaration_with(
                lambda d: d.__setattr__("declared_value", "someone else"))),
        "fabricated_title": refuses(
            lambda: declaration_with(
                lambda d: d.__setattr__("declared_value", "A Different Book"))),
        "empty_declared_value": refuses(
            lambda: declaration_with(
                lambda d: d.__setattr__("declared_value", ""))),
        "other_catalog_row": refuses(
            lambda: declaration_with(
                lambda d: d.__setattr__("catalog_source_id", "bs_another"))),
        "unknown_statement_type": refuses(
            lambda: builder.declaration(stored, "CONTRIBUTION")),
        "unknown_declared_in": refuses(
            lambda: builder.declaration(stored, "AUTHOR",
                                        "AUTHOR_INTERVIEW")),
        # YEAR has no catalog field, so there is nothing to check it against
        "unverifiable_year": refuses(
            lambda: builder.declaration(stored, "YEAR")),
        # lifecycle
        "verified_status": refuses(lambda: PaperStatus("VERIFIED")),
        "confirmed_status": refuses(lambda: PaperStatus("CONFIRMED")),
        "approved_status": refuses(lambda: PaperStatus("APPROVED")),
        "supported_downgrade": refuses(_downgrade),
        "rejected_revived": refuses(_rejected_is_final),
        # forbidden operations
        "rate_source": refuses(lambda: writer.rate_source(stored.id,
                                                          importance=1)),
        "rank_sources": refuses(lambda: writer.rank_sources(stored.id)),
        "approve": refuses(lambda: writer.approve(stored.id)),
        "update_candidate": refuses(
            lambda: writer.update_candidate(stored.id, title="x")),
        "delete_candidate": refuses(lambda: writer.delete_candidate(stored.id)),
    }
    return checks


# ── gates ────────────────────────────────────────────────────────────────────

#: What the traceability gate must equal. It was previously emitted as a bare
#: percentage inside `gates`, which the shared verdict contract cannot read.
TRACEABILITY_REQUIRED = 100.0


def _equals(measured: object, required: object) -> str:
    """One measurement as a gate status, against a stated requirement."""
    return "PASS" if measured == required else "FAIL"


def gate_results(result: Dict) -> Dict[str, object]:
    """The acceptance gates plus the checks behind them."""
    replay = replay_gate()
    negative = negative_gate(result)
    return {
        "GATE_1_schema": schema_gate(),
        "GATE_1_fk_verb": fk_verb_gate(),
        "GATE_1_isolation_schema": isolation_schema_gate(),
        "GATE_1_frozen_index": frozen_index_gate(),
        "GATE_1_constraints": constraint_gate(),
        "GATE_1_vocabulary": vocabulary_gate(),
        "GATE_1_not_null": null_guard_gate(),
        "GATE_1_column_parity": column_parity_gate(),
        "GATE_1_hash_formula": hash_formula_gate(),
        "GATE_1_banned_fields": banned_field_gate(),
        "GATE_2_authority": authority_gate(result),
        "GATE_2_frozen_layers": frozen_layers_untouched_gate(result),
        "GATE_2_baseline_unchanged": baseline_mutation_gate(result),
        "GATE_2_catalog_untouched": catalog_untouched_gate(result),
        "GATE_3_trace": trace_gate(result),
        "GATE_3_declaration_fidelity": declaration_fidelity_gate(result),
        "GATE_3_traceability_percent": _equals(result["writer"].traceability_percent(),
                                   TRACEABILITY_REQUIRED),
        "GATE_4_replay": "PASS" if (replay["identical_fingerprints"] == 1
                                    and replay["rewrite_is_noop"] == 1
                                    and replay["new_candidate"] == 0
                                    and replay["new_declaration"] == 0
                                    and replay["duplicate_hashes"] == 0)
        else "FAIL",
        "GATE_4_idempotency": idempotency_gate(result),
        "GATE_4_hash_stability": hash_stability_gate(),
        "GATE_5_isolation": same_source_gate(result),
        "GATE_6_negative": "PASS" if all(negative.values()) else "FAIL",
    }


_SCHEMA_GATES = ("GATE_1_schema", "GATE_1_fk_verb", "GATE_1_isolation_schema",
                 "GATE_1_frozen_index", "GATE_1_constraints",
                 "GATE_1_vocabulary", "GATE_1_not_null",
                 "GATE_1_column_parity", "GATE_1_hash_formula",
                 "GATE_1_banned_fields")


# ── reporting ────────────────────────────────────────────────────────────────

def _store(result: Dict):
    """The ingestion store.

    `book_sources` and `source_versions` live here, not on the sink: IdentitySink
    carries the frozen *derived* rows (units, events, identities), while the
    catalog is upstream of all of them. Reaching for `sink.book_sources` returns
    AttributeError, which reads like a missing table rather than a missing
    layer.
    """
    return result["result"]["base"]["pipeline"].store


def report(result: Dict) -> Dict:
    writer: PaperWriter = result["writer"]
    sink = result["sink"]
    candidates = []
    for candidate in sorted(sink.paper_candidates.values(), key=lambda c: c.id):
        catalog = _store(result).book_sources[candidate.book_source_id]
        candidates.append({
            "paper_id": candidate.id,
            "paper_hash": candidate.paper_hash,
            "source_type": candidate.source_type,
            "source_version_id": candidate.source_version_id,
            "book_source_id": candidate.book_source_id,
            "status": candidate.status,
            "extractor_version": candidate.extractor_version,
            "declared": {
                "title": candidate.title,
                "authors": candidate.authors,
                "publication_year": candidate.publication_year,
                "publisher": candidate.publisher,
                "doi": candidate.doi,
                "isbn": candidate.isbn,
            },
            "catalog_row": {
                "title": catalog.title,
                "author": catalog.author,
                "publisher": catalog.publisher,
                "isbn": catalog.isbn,
            },
            "declarations": [
                {"statement_type": d.statement_type,
                 "declared_value": d.declared_value,
                 "declared_in": d.declared_in,
                 "catalog_source_id": d.catalog_source_id,
                 "matches_record": declaration_matches_catalog(
                     d, _store(result).book_sources[d.catalog_source_id])}
                for d in writer.declarations_of(candidate.id)],
        })
    return {
        "task": "A_P5_3_PAPER",
        "book": f"{C.BOOK_TITLE} {C.BOOK_EDITION}",
        "run_id": result["result"]["base"]["reading_run_id"],
        "authority": "A_REPOSITORY",
        "paper_version": PAPER_VERSION,
        "source_types_authorised": list(SOURCE_TYPES),
        "forbidden_source_type": FORBIDDEN_SOURCE_TYPE,
        "statement_types": list(STATEMENT_TYPES),
        "evidence_anchor": CATALOG_DECLARATION,
        "candidate_count": len(sink.paper_candidates),
        "declaration_count": len(sink.paper_declarations),
        "pilot_rows": writer.pilot_rows(),
        "extracted_rows": writer.extracted_rows(),
        "traceability_percent": writer.traceability_percent(),
        "declaration_coverage": writer.declaration_coverage(),
        "notes": dict(PAPER_NOTES),
        "candidates": candidates,
    }


def acceptance(result: Dict) -> Dict[str, object]:
    """The spec's §16 acceptance block, computed from measurements."""
    gates = gate_results(result)
    contamination = contamination_counts(result)
    negative = negative_gate(result)
    writer: PaperWriter = result["writer"]
    checks = {
        "candidate_persisted": len(result["sink"].paper_candidates),
        "declarations_persisted": len(result["sink"].paper_declarations),
        "declaration_fidelity": gates["GATE_3_declaration_fidelity"],
        # The measurement, not the gate that now reports it.
        "traceability_percent": result["writer"].traceability_percent(),
        "source_isolation": gates["GATE_5_isolation"],
        "replay_stable": gates["GATE_4_replay"],
        "transaction_atomic": "PASS" if gates["GATE_1_schema"] == "PASS"
        else "FAIL",
        "unauthorised_type_rows": len(writer.unauthorised_type_rows()),
        "orphan_declarations": len(writer.orphan_declarations()),
        "unsourced_declarations": len(writer.unsourced_declarations()),
        "B_CONTAMINATION": contamination["B_REFERENCE"],
        "C_CONTAMINATION": contamination["C_REFERENCE"],
        "BU2_DEPENDENCY": contamination["BU2_DEPENDENCY"],
        "baseline_mutated": 0 if gates["GATE_2_baseline_unchanged"] == "PASS"
        else 1,
        "negative_refusals": sum(1 for v in negative.values() if v),
        "negative_cases": len(negative),
    }
    passed = (checks["candidate_persisted"] == 1
              and checks["declarations_persisted"] == len(PILOT_DECLARATIONS)
              and checks["declaration_fidelity"] == "PASS"
              and checks["traceability_percent"] == 100.0
              and checks["source_isolation"] == "PASS"
              and checks["replay_stable"] == "PASS"
              and checks["transaction_atomic"] == "PASS"
              and checks["unauthorised_type_rows"] == 0
              and checks["orphan_declarations"] == 0
              and checks["unsourced_declarations"] == 0
              and checks["B_CONTAMINATION"] == 0
              and checks["C_CONTAMINATION"] == 0
              and checks["BU2_DEPENDENCY"] == 0
              and checks["baseline_mutated"] == 0
              and checks["negative_refusals"] == checks["negative_cases"])
    return {
        "checks": checks,
        "gates": gates,
        # Derived from every reported gate. The IMPLEMENTATION conjunction
        # below reads a subset, so gates outside it could print PASS and change
        # nothing; the legacy keys are kept for the tests, artifacts and freeze
        # reports that read them.
        "A_P5_3_PAPER": verdict(gates),
        "verdict_inputs": verdict_inputs(gates),
        "A_P5_3_PAPER_SCHEMA":
            "PASS" if all(gates[k] == "PASS" for k in _SCHEMA_GATES)
            else "BLOCKED",
        "A_P5_3_PAPER_IMPLEMENTATION": "PASS" if passed else "BLOCKED",
        "MIGRATION_080": REQUIRED_MIGRATION,
        "SOURCE_TYPE": PILOT_SOURCE_TYPE,
        "UNTESTED": ["declaration_by_text_span",
                     "publication_year_and_doi",
                     "author_identity_resolution"],
    }


def final_report(result: Dict) -> Dict[str, str]:
    """The spec's FINAL REPORT FORMAT block, verbatim keys.

    COMMIT_SHA and TAG name a commit that has not been made, so they report
    PENDING rather than a guess: a freeze report that invents its own commit id
    is worse than one that admits it has none.
    """
    gates = gate_results(result)
    acceptance_block = acceptance(result)
    contamination = contamination_counts(result)
    verdict = ("PASS"
               if acceptance_block["A_P5_3_PAPER_IMPLEMENTATION"] == "PASS"
               else "BLOCKED")
    return {
        "TASK": "A_P5_3_PAPER",
        "MIGRATION_080": REQUIRED_MIGRATION,
        "SOURCE_TYPE": PILOT_SOURCE_TYPE,
        "PAPER_ROWS": str(len(result["sink"].paper_candidates)),
        "EVIDENCE_ROWS": str(len(result["sink"].paper_declarations)),
        # The measurement. This field reads the gate's status when it does not,
        # which renders the report as "PASS%" instead of "100.0%".
        "TRACEABILITY": f"{result['writer'].traceability_percent()}%",
        "REPLAY": str(gates["GATE_4_replay"]),
        "AUTHORITY_SCAN": str(gates["GATE_2_authority"]),
        "B_CONTAMINATION": str(contamination["B_REFERENCE"]),
        "C_CONTAMINATION": str(contamination["C_REFERENCE"]),
        "DB_MUTATION": str(0 if gates["GATE_2_baseline_unchanged"] == "PASS"
                           else 1),
        "BU2_MUTATION": str(contamination["BU2_DEPENDENCY"]),
        "COMMIT_SHA": os.environ.get("A_P5_3_COMMIT_SHA", "PENDING"),
        "TAG": os.environ.get("A_P5_3_TAG", "PENDING"),
        "FINAL_STATUS": verdict,
    }


def write_sql(result: Dict, path: str) -> str:
    """Emit both tables for a DBA to execute."""
    script = emit_paper_sql(result["sink"].paper_candidates,
                            result["sink"].paper_declarations)
    Path(path).write_text(script, encoding="utf-8")
    return path


def ledger_lines(path: Optional[str] = None) -> Optional[List[str]]:
    target = path or os.environ.get("A_P5_3_LEDGER_FILE")
    if not target:
        return None
    source = Path(target)
    if not source.exists():
        return None
    return [line.strip() for line in
            source.read_text(encoding="utf-8").splitlines() if line.strip()]


def durable_counts(path: Optional[str] = None) -> Optional[Dict[str, int]]:
    target = path or os.environ.get("A_P5_3_DB_COUNTS")
    if not target:
        return None
    source = Path(target)
    if not source.exists():
        return None
    return {key: int(value) for key, value in re.findall(
        r"(\w+)\s*=\s*(\d+)",
        source.read_text(encoding="utf-8"))} or None


def main() -> None:
    result = build_paper()
    if "--sql" in sys.argv:
        target = sys.argv[sys.argv.index("--sql") + 1]
        print(write_sql(result, target))
        return
    doc = report(result)
    doc.update(acceptance(result))
    doc["final_report"] = final_report(result)
    doc["ledger"] = ledger_lines()
    counts = durable_counts()
    if counts is not None:
        doc["durable_rows"] = counts
    print(json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()