"""A Repository P5.3 — paper / source metadata annotation.

Contract tests for the source-annotation layer (migration 080):

- Schema        tables, FK completeness, RESTRICT only, closed vocabularies,
                replay keys, NOT NULL guards, catalog tie
- Authority     no judgement column, no B / C / BU2, frozen layers untouched
- Evidence      every declaration is what the catalog record actually states
- Replay        same input same hash, re-running appends nothing
- Isolation     the catalog row is the one its version was ingested from
- Lifecycle     generated->supported, generated->rejected, nothing terminal moves
- Pilot         declared rows are never mistaken for extracted ones

The traceability tests here compare strings against a record. They do not count
evidence ids, because an id existing is not a declaration being true.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict

import pytest


ROOT = Path(__file__).parents[2]
PKG = ROOT / "src" / "stratum" / "knowledge" / "a_repository"
MIGRATIONS = ROOT / "src" / "stratum" / "db" / "pg_migrations"
MIGRATION = MIGRATIONS / "080_a_paper_source.sql"
ARTIFACT = ROOT / "artifacts" / "a_repository" / "p5_3_paper.json"

from stratum.knowledge.a_repository.paper_writer import (  # noqa: E402
    CATALOG_DECLARATION,
    CATALOG_FIELD_FOR,
    DECLARED_IN,
    EXTRACTOR_VERSION,
    FORBIDDEN_SOURCE_TYPE,
    LEGAL_STATUS_TRANSITIONS,
    PAPER_BANNED_FIELDS,
    PAPER_CANDIDATE_COLUMNS,
    PAPER_CANDIDATE_INSERT_COLUMNS,
    PAPER_EVIDENCE_COLUMNS,
    PAPER_EVIDENCE_INSERT_COLUMNS,
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
    banned_field_report,
    declaration_matches_catalog,
    emit_paper_sql,
    evidence_hash,
    paper_hash,
    paper_id,
    transition,
)
from stratum.knowledge.a_repository.paper_runner import (  # noqa: E402
    ALLOWED_FK_TARGETS,
    FROZEN_TABLE_INDEX,
    PILOT_DECLARATIONS,
    PILOT_SOURCE_TYPE,
    REQUIRED_MIGRATION,
    UNTOUCHABLE_TABLES,
    acceptance,
    authority_gate,
    banned_field_gate,
    baseline_mutation_gate,
    build_paper,
    catalog_untouched_gate,
    column_parity_gate,
    constraint_gate,
    contamination_counts,
    declaration_fidelity_gate,
    final_report,
    fk_verb_gate,
    frozen_index_gate,
    frozen_layers_untouched_gate,
    gate_results,
    hash_formula_gate,
    hash_stability_gate,
    idempotency_gate,
    isolation_schema_gate,
    negative_gate,
    null_guard_gate,
    report,
    same_source_gate,
    schema_gate,
    trace_gate,
    vocabulary_gate,
    write_sql,
)
from stratum.knowledge.a_repository.projection_builder import (  # noqa: E402
    artifact_drift,
    external_imports,
)


@pytest.fixture(scope="module")
def paper():
    return build_paper()


@pytest.fixture(scope="module")
def writer(paper):
    return paper["writer"]


@pytest.fixture(scope="module")
def store(paper):
    return paper["result"]["base"]["pipeline"].store


def _fresh() -> Dict:
    return build_paper()


def _clean() -> str:
    return re.sub(r"--[^\n]*", "",
                  MIGRATION.read_text(encoding="utf-8"))


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


# ── Schema ───────────────────────────────────────────────────────────────────

def test_paper_tables_exist():
    clean = _clean()
    for table in PAPER_TABLES:
        assert f"CREATE TABLE IF NOT EXISTS stratum.{table} (" in clean
    assert schema_gate() == "PASS"


def test_paper_fk_only_A():
    """Every foreign key lands on an A table, and every one is RESTRICT."""
    clean = _clean()
    referenced = set(re.findall(r"REFERENCES\s+stratum\.(\w+)", clean))
    assert referenced <= ALLOWED_FK_TARGETS
    assert referenced == {"source_version", "book_source",
                          "paper_source_candidate"}
    assert fk_verb_gate() == "PASS"
    assert set(re.findall(r"ON DELETE (\w+)", clean)) == {"RESTRICT"}


def test_fk_is_complete():
    """Four keys: the version, the catalog row, the candidate, the record."""
    clean = _clean()
    assert clean.count("REFERENCES stratum.source_version") == 1
    assert clean.count("REFERENCES stratum.book_source") == 2
    assert clean.count(
        "REFERENCES stratum.paper_source_candidate") == 1
    assert isolation_schema_gate() == "PASS"


def test_source_type_closed():
    """Five types, and UNKNOWN absent as a fact.

    UNKNOWN_AS_FACT is banned by the spec and absent here: an unreadable source
    is a read state, and a column that could hold it would let "we could not
    tell" be stored as "it is a book".
    """
    clean = _clean()
    assert "'BOOK', 'PAPER', 'ARTICLE', 'REPORT', 'ARCHIVE'" in clean
    assert vocabulary_gate() == "PASS"
    assert SOURCE_TYPES == ("BOOK", "PAPER", "ARTICLE", "REPORT", "ARCHIVE")
    assert FORBIDDEN_SOURCE_TYPE not in SOURCE_TYPES


def test_status_vocabulary_has_no_judgement_word():
    clean = _clean()
    assert "CHECK (status IN ('GENERATED', 'SUPPORTED', 'REJECTED'))" in clean
    assert {s.value for s in PaperStatus} == {"GENERATED", "SUPPORTED",
                                              "REJECTED"}
    for banned in ("VERIFIED", "CONFIRMED", "APPROVED"):
        assert banned not in {s.value for s in PaperStatus}


def test_statement_type_and_declared_in_closed():
    clean = _clean()
    assert vocabulary_gate() == "PASS"
    for statement_type in STATEMENT_TYPES:
        assert statement_type in clean
    for declared_in in DECLARED_IN:
        assert declared_in in clean
    assert STATEMENT_TYPES == ("AUTHOR", "TITLE", "PUBLICATION", "YEAR",
                               "IDENTIFIER")


def test_hash_unique(writer):
    clean = _clean()
    assert "CONSTRAINT paper_candidate_hash_uniq UNIQUE (paper_hash)" in clean
    assert "CONSTRAINT paper_evidence_hash_uniq UNIQUE (evidence_hash)" in clean
    assert constraint_gate() == "PASS"
    assert writer.duplicate_hashes() == []


def test_authors_non_empty_uses_cardinality():
    """cardinality, not array_length.

    Measured in 077: array_length of an empty array is NULL and a CHECK passes
    on NULL, so an array_length guard accepts the array it exists to reject.
    """
    clean = _clean()
    assert "CHECK (cardinality(authors) >= 1)" in clean
    assert "array_length(" not in clean


def test_no_such_catalog_row_is_a_blocker():
    """status, authors and declared_value are NOT NULL.

    A CHECK passes on NULL, so a nullable status walks past the vocabulary it
    exists to enforce.
    """
    assert null_guard_gate() == "PASS"


def test_created_at_has_a_default_so_the_insert_omits_it():
    clean = _clean()
    assert clean.count("created_at TIMESTAMP NOT NULL DEFAULT now()") == 2
    assert column_parity_gate() == "PASS"
    assert "created_at" in PAPER_CANDIDATE_COLUMNS
    assert "created_at" not in PAPER_CANDIDATE_INSERT_COLUMNS
    assert "created_at" not in PAPER_EVIDENCE_INSERT_COLUMNS


def test_column_parity():
    """Writer columns, schema columns and dataclass fields must agree."""
    assert column_parity_gate() == "PASS"
    candidate_fields = set(vars(PaperSourceCandidate(
        id="", source_version_id="", book_source_id="", source_type="",
        title="")))
    evidence_fields = set(vars(PaperEvidence(
        id="", paper_id="", statement_type="", declared_value="",
        declared_in="", catalog_source_id="")))
    assert set(PAPER_CANDIDATE_COLUMNS) <= candidate_fields
    assert set(PAPER_EVIDENCE_COLUMNS) <= evidence_fields


def test_publisher_is_inside_the_hash_and_authors_are_not_sorted():
    """The review spec's §5 omitted publisher; author order is a fact."""
    import inspect
    source = inspect.getsource(paper_hash)
    assert "publisher" in source
    assert "sorted" not in source
    assert hash_formula_gate() == "PASS"


def test_evidence_is_deliberately_not_in_the_hash():
    """New evidence for the same source is new evidence, not a new source.

    The review spec's §5 omitted evidence while its §9 listed it as part of the
    replay key. This resolves that in favour of §5 and says so in a test.
    """
    import inspect
    assert "evidence" not in inspect.getsource(paper_hash)
    base = paper_hash("sv", "bs", "BOOK", "T", ["A"], 2000, "P", None, "I",
                      PILOT_DECLARED_VERSION)
    other = evidence_hash("psc_x", "AUTHOR", "A", CATALOG_DECLARATION, "bs")
    assert other != base


def test_the_frozen_table_takes_one_index_and_nothing_else():
    clean = _clean()
    assert f"CREATE UNIQUE INDEX IF NOT EXISTS {FROZEN_TABLE_INDEX}" in clean
    assert frozen_index_gate() == "PASS"
    assert "ALTER TABLE" not in clean
    indexed = set(re.findall(r"ON stratum\.(\w+)", clean))
    assert indexed <= {"source_version", *PAPER_TABLES}


def test_080_touches_nothing_it_inherits():
    clean = _clean()
    for forbidden in ("ALTER TABLE", "DROP ", "UPDATE ", "INSERT INTO",
                      "TRUNCATE"):
        assert forbidden not in clean
    for table in UNTOUCHABLE_TABLES:
        assert f"CREATE TABLE IF NOT EXISTS stratum.{table} (" not in clean


def test_no_judgement_column_grew():
    """A source annotation records what a record says, not how good it is."""
    assert not any(banned_field_report().values())
    assert banned_field_gate() == "PASS"
    for name in PAPER_BANNED_FIELDS:
        assert not hasattr(PaperSourceCandidate, name)
        assert not hasattr(PaperEvidence, name)
        assert name not in PAPER_CANDIDATE_COLUMNS
        assert name not in PAPER_EVIDENCE_COLUMNS
    for banned in ("importance", "quality", "truth", "confidence_score"):
        assert banned not in PAPER_CANDIDATE_COLUMNS


def test_earlier_migrations_are_untouched():
    for name in ("075_a_ku_evolution.sql", "077_a_condition_boundary.sql",
                 "078_a_mechanism_chain.sql",
                 "079_a_relation_candidate.sql"):
        sql = (MIGRATIONS / name).read_text(encoding="utf-8")
        for table in PAPER_TABLES:
            assert table not in sql


# ── Evidence ─────────────────────────────────────────────────────────────────

def test_paper_metadata_traceable(paper, writer, store):
    """candidate -> catalog row, declaration -> the field it names, 100%."""
    assert trace_gate(paper) == "PASS"
    assert writer.traceability_percent() == 100.0
    for declaration in paper["sink"].paper_declarations.values():
        catalog = store.book_sources[declaration.catalog_source_id]
        assert declaration_matches_catalog(declaration, catalog)
        field_name = CATALOG_FIELD_FOR[declaration.statement_type]
        assert field_name is not None
        assert str(getattr(catalog, field_name)) == declaration.declared_value


def test_evidence_required(paper, writer):
    """Every candidate carries at least one declaration."""
    assert paper["sink"].paper_declarations
    assert writer.orphan_declarations() == []
    for candidate in paper["sink"].paper_candidates.values():
        assert writer.declarations_of(candidate.id)


def test_declaration_fidelity_gate(paper):
    """The gate that separates traceability from a referenced id."""
    assert declaration_fidelity_gate(paper) == "PASS"
    assert paper["writer"].unsourced_declarations() == []


def test_a_declaration_the_record_does_not_make_is_refused():
    """The strongest guard on a fabricated quote: it cannot be expressed."""
    fresh = _fresh()
    store = fresh["result"]["base"]["pipeline"].store
    declaration = fresh["writer"].builder.declaration(fresh["candidate"],
                                                      "AUTHOR")
    assert declaration_matches_catalog(
        declaration, store.book_sources[declaration.catalog_source_id])
    declaration.declared_value = "someone else"
    ok, failed = fresh["writer"].declaration_preconditions(
        declaration, fresh["candidate"])
    assert ok is False
    assert "DECLARATION_NOT_IN_RECORD" in failed


def test_a_declaration_cannot_be_written_for_another_record():
    fresh = _fresh()
    declaration = fresh["writer"].builder.declaration(fresh["candidate"],
                                                      "AUTHOR")
    declaration.catalog_source_id = "bs_another"
    ok, failed = fresh["writer"].declaration_preconditions(
        declaration, fresh["candidate"])
    assert ok is False
    assert "DECLARATION_OTHER_CATALOG_ROW" in failed


def test_the_year_declaration_is_refused_because_there_is_no_field():
    """YEAR is in the vocabulary and cannot be declared from a catalog row.

    A仓 holds no publication year anywhere, so there is no field for a YEAR
    declaration to equal. Writing one would store an unverifiable sentence.
    """
    assert CATALOG_FIELD_FOR["YEAR"] is None
    fresh = _fresh()
    with pytest.raises(PaperPrecondition, match="no year field"):
        fresh["writer"].builder.declaration(fresh["candidate"], "YEAR")
    assert fresh["writer"].declaration_coverage()["YEAR"] is False


def test_the_pilot_declares_only_what_the_record_states(paper, writer):
    """Four of five statement types, and the fifth is reported as a gap."""
    coverage = writer.declaration_coverage()
    assert sorted(k for k, v in coverage.items() if v) == sorted(
        PILOT_DECLARATIONS)
    assert coverage["YEAR"] is False
    assert len(PILOT_DECLARATIONS) == 4


def test_authors_are_stored_verbatim_not_split(paper, store):
    """Splitting the author string is identity resolution — out of scope.

    LIMITATION-2 says author identity resolution is not performed, so the
    catalog's single author field is stored as one element rather than two
    names parsed out of it.
    """
    catalog = next(iter(store.book_sources.values()))
    assert paper["written"].authors == [catalog.author]
    assert len(paper["written"].authors) == 1


def test_the_catalog_row_is_not_modified_by_this_stage(paper):
    assert catalog_untouched_gate(paper) == "PASS"


# ── Lifecycle ────────────────────────────────────────────────────────────────

def test_generated_supported():
    fresh = _fresh()
    candidate = fresh["written"]
    assert candidate.status == PaperStatus.GENERATED.value
    supported = fresh["writer"].support(candidate.id)
    assert supported.status == PaperStatus.SUPPORTED.value


def test_generated_rejected():
    fresh = _fresh()
    rejected = fresh["writer"].reject(fresh["written"].id)
    assert rejected.status == PaperStatus.REJECTED.value


def test_supported_to_generated_blocked():
    """Both SUPPORTED and REJECTED are final.

    A仓 corrects by appending a new candidate under a new hash, never by
    downgrading one in place.
    """
    assert LEGAL_STATUS_TRANSITIONS[PaperStatus.SUPPORTED] == frozenset()
    assert LEGAL_STATUS_TRANSITIONS[PaperStatus.REJECTED] == frozenset()
    fresh = _fresh()
    candidate = fresh["written"]
    fresh["writer"].support(candidate.id)
    for target in (PaperStatus.GENERATED, PaperStatus.REJECTED):
        with pytest.raises(PaperViolation, match="final"):
            transition(candidate, target)
    assert candidate.status == PaperStatus.SUPPORTED.value


def test_a_rejected_candidate_is_not_revived():
    fresh = _fresh()
    candidate = fresh["writer"].reject(fresh["written"].id)
    for target in (PaperStatus.GENERATED, PaperStatus.SUPPORTED):
        with pytest.raises(PaperViolation, match="final"):
            transition(candidate, target)


def test_support_requires_a_declaration():
    fresh = _fresh()
    candidate = fresh["candidate"]
    bare = _clone(candidate)
    bare.id = "psc_bare"
    bare.paper_hash = "psh_bare"
    fresh["writer"].write(bare)
    with pytest.raises(PaperPrecondition, match="no declaration"):
        fresh["writer"].support(bare.id)


def test_nothing_can_be_mutated_deleted_or_judged(writer, paper):
    stored = paper["written"].id
    with pytest.raises(PaperViolation, match="cannot be updated"):
        writer.update_candidate(stored, title="x")
    with pytest.raises(PaperViolation, match="cannot be deleted"):
        writer.delete_candidate(stored)
    with pytest.raises(PaperViolation, match="how good the source"):
        writer.rate_source(stored, importance=1)
    with pytest.raises(PaperViolation, match="does not rank"):
        writer.rank_sources(stored)
    with pytest.raises(PaperViolation, match="APPROVED"):
        writer.approve(stored)
    with pytest.raises(PaperViolation, match="never touches"):
        writer.update_verification("anything")


# ── Replay ───────────────────────────────────────────────────────────────────

def test_same_hash_no_duplicate():
    """Re-running writes nothing, and a second run is byte-identical."""
    fresh = _fresh()
    assert idempotency_gate(fresh) == "PASS"
    assert gate_results(_fresh())["GATE_4_replay"] == "PASS"
    assert fresh["writer"].duplicate_hashes() == []


def test_hash_stability():
    """Same input, same hash. Any declared field, a different candidate."""
    assert hash_stability_gate() == "PASS"
    base = paper_hash("sv", "bs", "BOOK", "T", ["A"], 2000, "P", None, "I",
                      PILOT_DECLARED_VERSION)
    assert paper_hash("sv", "bs", "BOOK", "T", ["A"], 2000, "P", None, "I",
                      PILOT_DECLARED_VERSION) == base
    # publisher, year and isbn are all identity fields
    assert paper_hash("sv", "bs", "BOOK", "T", ["A"], 2000, "Q", None, "I",
                      PILOT_DECLARED_VERSION) != base
    assert paper_hash("sv", "bs", "BOOK", "T", ["A"], 2001, "P", None, "I",
                      PILOT_DECLARED_VERSION) != base
    assert paper_hash("sv", "bs", "BOOK", "T", ["A"], 2000, "P", None, "J",
                      PILOT_DECLARED_VERSION) != base
    # author order is a claim
    assert paper_hash("sv", "bs", "BOOK", "T", ["B", "A"], 2000, "P", None, "I",
                      PILOT_DECLARED_VERSION) != base
    # the extractor version is a claim
    assert paper_hash("sv", "bs", "BOOK", "T", ["A"], 2000, "P", None, "I",
                      EXTRACTOR_VERSION) != base
    assert paper_id("sv", "bs", "BOOK", PILOT_DECLARED_VERSION).startswith(
        "psc_")
    assert base.startswith("psh_")


def test_declaration_hash_is_its_own_replay_key():
    fresh = _fresh()
    declaration = fresh["writer"].builder.declaration(fresh["candidate"],
                                                      "AUTHOR")
    assert declaration.evidence_hash == evidence_hash(
        declaration.paper_id, declaration.statement_type,
        declaration.declared_value, declaration.declared_in,
        declaration.catalog_source_id)
    assert declaration.evidence_hash.startswith("peh_")
    assert declaration.id == declaration.evidence_hash


def test_the_emitted_script_is_idempotent(paper):
    script = emit_paper_sql(paper["sink"].paper_candidates,
                            paper["sink"].paper_declarations)
    lines = [line for line in script.splitlines()
             if line.startswith("INSERT INTO")]
    assert len(lines) == 5          # 1 candidate + 4 declarations
    assert "ON CONFLICT (paper_hash) DO NOTHING;" in script
    assert "ON CONFLICT (evidence_hash) DO NOTHING;" in script
    assert script.count("BEGIN;") == 1 and script.count("COMMIT;") == 1
    assert "ARRAY[" in script


def test_the_script_is_byte_identical_on_a_rerun(tmp_path):
    first = write_sql(_fresh(), str(tmp_path / "a.sql"))
    second = write_sql(_fresh(), str(tmp_path / "b.sql"))
    assert Path(first).read_bytes() == Path(second).read_bytes()


# ── Isolation ────────────────────────────────────────────────────────────────

def test_source_isolation(paper, writer, store):
    """The catalog row is the one its own version was ingested from."""
    assert same_source_gate(paper) == "PASS"
    assert writer.cross_source_candidates() == []
    for candidate in paper["sink"].paper_candidates.values():
        version = store.source_versions[candidate.source_version_id]
        assert version.book_source_id == candidate.book_source_id


def test_cross_source_catalog_row_blocked():
    fresh = _fresh()
    clone = _clone(fresh["candidate"])
    clone.book_source_id = "bs_another_book"
    clone.id = "psc_cross"
    clone.paper_hash = "psh_cross"
    with pytest.raises(PaperPrecondition):
        fresh["writer"].write(clone)


def test_title_not_from_the_record_is_refused():
    """The candidate's fields come from the record, not from the caller."""
    fresh = _fresh()
    clone = _clone(fresh["candidate"])
    clone.title = "A Different Book"
    clone.id = "psc_title"
    clone.paper_hash = "psh_title"
    with pytest.raises(PaperPrecondition):
        fresh["writer"].write(clone)


def test_empty_authors_blocked():
    fresh = _fresh()
    clone = _clone(fresh["candidate"])
    clone.authors.clear()
    clone.id = "psc_noauthors"
    clone.paper_hash = "psh_noauthors"
    with pytest.raises(PaperPrecondition):
        fresh["writer"].write(clone)


# ── Authority ────────────────────────────────────────────────────────────────

def test_no_B_dependency():
    assert contamination_counts(_fresh())["B_REFERENCE"] == 0
    clean = _clean().lower()
    for foreign in ("aii_refined", "refined_ku", "refined_concept"):
        assert foreign not in clean


def test_no_C_dependency():
    assert contamination_counts(_fresh())["C_REFERENCE"] == 0
    assert external_imports() == []
    source = (PKG / "paper_writer.py").read_text(encoding="utf-8")
    code = re.sub(r'""".*?"""', "", source, flags=re.DOTALL)
    for foreign in ("learning_progress", "mastery", "learning_card",
                    "knowledge_claim", "learning_objective"):
        assert foreign not in code


def test_no_BU2_dependency():
    assert authority_gate(_fresh()) == "PASS"
    clean = _clean().lower()
    for foreign in ("bu_onto", "chapter_bu", "bu_learning_state"):
        assert f"references stratum.{foreign}" not in clean
    assert contamination_counts(_fresh())["BU2_DEPENDENCY"] == 0


def test_the_artifact_carries_no_contamination(paper):
    payload = {"candidates": [c.id for c in
                              paper["sink"].paper_candidates.values()]}
    assert artifact_drift(payload) == {}


def test_the_baseline_underneath_is_untouched(paper):
    assert baseline_mutation_gate(paper) == "PASS"


def test_the_frozen_layers_are_untouched():
    """075's relation layer and 079's relation candidate are both left alone."""
    assert frozen_layers_untouched_gate(_fresh()) == "PASS"
    clean = _clean()
    assert "ku_relation" not in clean
    assert "relation_candidate" not in clean


def test_verification_logic_still_untouched():
    from stratum.knowledge.a_repository.verification import (
        AVerificationPipeline)
    assert AVerificationPipeline.required_slots("FACT") == (
        "ANCHORED", "SUBJECT", "PREDICATE", "OBJECT")


# ── Pilot ────────────────────────────────────────────────────────────────────

def test_pilot_declared_separate_from_extractor(paper, writer):
    """Pilot data is not extraction evidence, and the two stay distinct."""
    pilot = writer.pilot_rows()
    extracted = writer.extracted_rows()
    assert pilot, "the pilot candidate should be labelled pilot-declared"
    assert extracted == [], \
        "this stage ships no extractor; nothing may claim to be extracted"
    for candidate_id in pilot:
        row = paper["sink"].paper_candidates[candidate_id]
        assert row.extractor_version == PILOT_DECLARED_VERSION
        assert row.extractor_version != EXTRACTOR_VERSION


def test_the_pilot_is_the_frozen_book(paper, store):
    catalog = next(iter(store.book_sources.values()))
    assert paper["written"].title == catalog.title
    assert paper["written"].publisher == catalog.publisher
    assert paper["written"].isbn == catalog.isbn
    assert paper["written"].source_type == PILOT_SOURCE_TYPE == "BOOK"


def test_the_pilot_is_not_called_an_extraction(paper):
    doc = report(paper)
    assert doc["extracted_rows"] == []
    assert doc["pilot_rows"]
    assert doc["source_types_authorised"] == list(SOURCE_TYPES)
    assert doc["forbidden_source_type"] == FORBIDDEN_SOURCE_TYPE
    assert doc["evidence_anchor"] == CATALOG_DECLARATION
    for candidate in doc["candidates"]:
        for declaration in candidate["declarations"]:
            assert declaration["matches_record"] is True


def test_the_untested_things_are_declared_not_hidden(paper):
    """Three things this stage does not establish, named in the report."""
    doc = acceptance(paper)
    assert set(doc["UNTESTED"]) == {"declaration_by_text_span",
                                    "publication_year_and_doi",
                                    "author_identity_resolution"}


# ── negative ─────────────────────────────────────────────────────────────────

def test_negative_gate_refuses_every_case(paper):
    """Each forbidden shape is refused, and each one is named."""
    checks = negative_gate(paper)
    assert all(checks.values()), [k for k, v in checks.items() if not v]
    for name in ("unknown_as_fact", "unknown_type", "fabricated_author",
                 "fabricated_title", "unverifiable_year",
                 "supported_downgrade", "rejected_revived", "rate_source",
                 "rank_sources", "approve"):
        assert name in checks


# ── the test contract ────────────────────────────────────────────────────────

def test_review_checklist():
    """The spec's §12 checklist, as one gate."""
    clean = _clean()
    assert schema_gate() == "PASS"                # tables exist, additive
    assert fk_verb_gate() == "PASS"               # FK only A, RESTRICT
    assert vocabulary_gate() == "PASS"            # source_type closed
    assert null_guard_gate() == "PASS"            # NOT NULL guards
    assert constraint_gate() == "PASS"            # hash unique, authors
    assert column_parity_gate() == "PASS"
    assert hash_formula_gate() == "PASS"          # publisher in, evidence out
    assert banned_field_gate() == "PASS"          # no ranking field
    referenced = set(re.findall(r"REFERENCES\s+stratum\.(\w+)", clean))
    assert not {"bu_onto", "chapter_bu"} & referenced        # no BU2 FK
    assert not any(r.endswith("_onto") for r in referenced)  # no B / C FK


def test_all_gates_pass(paper):
    gates = gate_results(paper)
    for name, value in gates.items():
        if isinstance(value, dict):
            continue
        assert value == "PASS", f"{name}={value}"


def test_acceptance_block(paper):
    doc = acceptance(paper)
    checks = doc["checks"]
    assert doc["A_P5_3_PAPER_SCHEMA"] == "PASS"
    assert doc["A_P5_3_PAPER_IMPLEMENTATION"] == "PASS"
    assert doc["MIGRATION_080"] == REQUIRED_MIGRATION
    assert doc["SOURCE_TYPE"] == "BOOK"
    assert checks["candidate_persisted"] == 1
    assert checks["declarations_persisted"] == len(PILOT_DECLARATIONS)
    assert checks["declaration_fidelity"] == "PASS"
    assert checks["traceability_percent"] == 100.0
    assert checks["source_isolation"] == "PASS"
    assert checks["replay_stable"] == "PASS"
    assert checks["transaction_atomic"] == "PASS"
    assert checks["unauthorised_type_rows"] == 0
    assert checks["orphan_declarations"] == 0
    assert checks["unsourced_declarations"] == 0
    assert checks["B_CONTAMINATION"] == 0
    assert checks["C_CONTAMINATION"] == 0
    assert checks["BU2_DEPENDENCY"] == 0
    assert checks["baseline_mutated"] == 0
    assert checks["negative_refusals"] == checks["negative_cases"]


def test_final_report_block(paper):
    """The spec's FINAL REPORT FORMAT keys, present and honest."""
    block = final_report(paper)
    for key in ("TASK", "MIGRATION_080", "SOURCE_TYPE", "PAPER_ROWS",
                "EVIDENCE_ROWS", "TRACEABILITY", "REPLAY", "AUTHORITY_SCAN",
                "B_CONTAMINATION", "C_CONTAMINATION", "DB_MUTATION",
                "BU2_MUTATION", "COMMIT_SHA", "TAG", "FINAL_STATUS"):
        assert key in block, key
    assert block["TASK"] == "A_P5_3_PAPER"
    assert block["FINAL_STATUS"] == "PASS"
    assert block["MIGRATION_080"] == REQUIRED_MIGRATION
    assert block["SOURCE_TYPE"] == "BOOK"
    assert block["PAPER_ROWS"] == "1"
    assert block["EVIDENCE_ROWS"] == str(len(PILOT_DECLARATIONS))
    assert block["TRACEABILITY"] == "100.0%"
    assert block["REPLAY"] == "PASS"
    assert block["B_CONTAMINATION"] == "0"
    assert block["C_CONTAMINATION"] == "0"
    assert block["DB_MUTATION"] == "0"
    assert block["BU2_MUTATION"] == "0"


def test_committed_artifact_matches_a_fresh_run():
    assert ARTIFACT.exists(), "run paper_runner to emit the artifact"
    committed = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    fresh = report(_fresh())
    for key in ("candidate_count", "declaration_count", "pilot_rows",
                "extracted_rows", "traceability_percent", "paper_version",
                "source_types_authorised", "statement_types",
                "evidence_anchor", "declaration_coverage"):
        assert committed[key] == fresh[key], key
    assert committed["candidates"] == fresh["candidates"]


def test_the_converted_percent_gate_reports_a_real_measurement(paper):
    """`GATE_3_traceability_percent` is a status now. Assert the number it stands for too,
    or a PASS would say nothing about traceability."""
    assert gate_results(paper)["GATE_3_traceability_percent"] == "PASS"
    assert paper["writer"].traceability_percent() == 100.0
