"""A Repository P5.4 — constraint annotation.

Contract tests for the constraint layer (migration 081):

- Schema        table, FK completeness, RESTRICT only, closed vocabularies,
                replay key, no new index on a frozen table
- Quote         DECISION=SPAN_ONLY — every quoted field is a literal substring
                of its own span, and the KU statement is never the source
- Authority     no advice column, no B / C / BU2, frozen layers untouched
- Replay        same input same hash, re-running appends nothing
- Isolation     the unit is of the annotation's own source version
- Lifecycle     generated->supported, generated->rejected, nothing terminal moves
- Pilot         one row, declared, with coverage reported per type

The quote tests are the point of this stage: they assert that a field exists
inside the book's own span, not that some identifier points at a row.
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
MIGRATION = MIGRATIONS / "081_a_constraint_candidate.sql"
ARTIFACT = ROOT / "artifacts" / "a_repository" / "p5_4_constraint.json"

from stratum.knowledge.a_repository.constraint_runner import (  # noqa: E402
    ALLOWED_FK_TARGETS,
    MEASURED_REJECTIONS,
    PILOT_CONSTRAINT,
    REUSED_FROZEN_INDEX,
    REQUIRED_MIGRATION,
    UNANCHORED_SPANS,
    UNTOUCHABLE_TABLES,
    acceptance,
    authority_gate,
    banned_field_gate,
    baseline_mutation_gate,
    build_constraint,
    column_parity_gate,
    constraint_gate,
    contamination_counts,
    coverage_gate,
    final_report,
    fk_verb_gate,
    frozen_layers_untouched_gate,
    gate_results,
    hash_ordering_gate,
    hash_stability_gate,
    idempotency_gate,
    index_reuse_gate,
    isolation_schema_gate,
    ku_statement_not_evidence_gate,
    negative_gate,
    quote_authority_gate,
    report,
    same_source_gate,
    schema_gate,
    trace_gate,
    vocabulary_gate,
    write_sql,
)
from stratum.knowledge.a_repository.constraint_writer import (  # noqa: E402
    ADVISORY_MARKERS,
    CONSTRAINT_BANNED_FIELDS,
    CONSTRAINT_COLUMNS,
    CONSTRAINT_INSERT_COLUMNS,
    CONSTRAINT_TYPES,
    PILOT_DECLARED_VERSION,
    EXTRACTOR_VERSION,
    SOFT_MARKERS,
    ConstraintCandidate,
    ConstraintPrecondition,
    ConstraintSink,
    ConstraintStatus,
    ConstraintViolation,
    banned_field_report,
    emit_constraint_sql,
    evidence_span,
    field_is_quoted,
    transition,
    unquoted_fields,
)
from stratum.knowledge.a_repository.projection_builder import (  # noqa: E402
    artifact_drift,
    external_imports,
)


@pytest.fixture(scope="module")
def constraint():
    return build_constraint()


@pytest.fixture(scope="module")
def writer(constraint):
    return constraint["writer"]


@pytest.fixture(scope="module")
def store(constraint):
    return constraint["result"]["base"]["pipeline"].store


def _fresh() -> Dict:
    return build_constraint()


def _clean() -> str:
    return re.sub(r"--[^\n]*", "",
                  MIGRATION.read_text(encoding="utf-8"))


def _clone(candidate) -> ConstraintCandidate:
    return ConstraintCandidate(
        id=candidate.id, source_version_id=candidate.source_version_id,
        knowledge_unit_id=candidate.knowledge_unit_id,
        constraint_type=candidate.constraint_type, subject=candidate.subject,
        predicate=candidate.predicate, object=candidate.object,
        evidence_ids=list(candidate.evidence_ids), boundary=candidate.boundary,
        constraint_hash=candidate.constraint_hash,
        extractor_version=candidate.extractor_version,
        status=candidate.status, created_at=candidate.created_at)


# ── Schema ───────────────────────────────────────────────────────────────────

def test_constraint_table_exists():
    clean = _clean()
    assert "CREATE TABLE IF NOT EXISTS stratum.constraint_candidate (" in clean
    assert schema_gate() == "PASS"


def test_constraint_fk_only_A():
    """Every foreign key lands on an A table, and every one is RESTRICT."""
    clean = _clean()
    referenced = set(re.findall(r"REFERENCES\s+stratum\.(\w+)", clean))
    assert referenced <= ALLOWED_FK_TARGETS
    assert referenced == {"source_version", "knowledge_unit"}
    assert fk_verb_gate() == "PASS"
    assert set(re.findall(r"ON DELETE (\w+)", clean)) == {"RESTRICT"}


def test_no_bu2_b_or_c_fk():
    clean = _clean().lower()
    for foreign in ("bu_onto", "chapter_bu", "bu_learning_state",
                    "aii_refined", "refined_ku", "learning_objective",
                    "knowledge_claim", "concept"):
        assert f"references stratum.{foreign}" not in clean


def test_closed_vocabularies():
    """constraint_type closed to three, status closed, no judgement word."""
    clean = _clean()
    assert "CHECK (constraint_type IN ('HARD', 'SOFT', 'SELF_DEFINED'))" in clean
    assert "CHECK (status IN ('GENERATED', 'SUPPORTED', 'REJECTED'))" in clean
    assert vocabulary_gate() == "PASS"
    assert CONSTRAINT_TYPES == ("HARD", "SOFT", "SELF_DEFINED")
    for banned in ("VERIFIED", "CONFIRMED", "APPROVED"):
        assert banned not in clean
        assert banned not in {s.value for s in ConstraintStatus}


def test_constraint_hash_unique(writer):
    clean = _clean()
    assert "CONSTRAINT constraint_candidate_hash_uniq UNIQUE (constraint_hash)" \
        in clean
    assert constraint_gate() == "PASS"
    assert writer.duplicate_hashes() == []


def test_same_source_is_db_enforced_not_service_only(constraint, writer):
    """§8 forbids service-only enforcement, and a CHECK cannot do it.

    The tie needs knowledge_unit, which a CHECK may not read, so it is a
    composite key. This reads the file to confirm the composite form rather than
    trusting the comment.
    """
    clean = _clean()
    assert isolation_schema_gate() == "PASS"
    assert "FOREIGN KEY (knowledge_unit_id, source_version_id)" in clean
    assert "REFERENCES stratum.knowledge_unit (id, source_version_id)" in clean
    assert same_source_gate(constraint) == "PASS"
    assert writer.cross_source_candidates() == []


def test_no_index_is_added_to_a_frozen_table():
    """§8 lists the knowledge_unit index as required; 079 already made it.

    Creating it again would be a duplicate index on a frozen table, so this
    asserts the opposite of what a reader might expect to see.
    """
    clean = _clean()
    assert index_reuse_gate() == "PASS"
    indexed = set(re.findall(r"ON stratum\.(\w+)", clean))
    assert indexed == {"constraint_candidate"}
    assert REUSED_FROZEN_INDEX not in \
        [l for l in clean.splitlines() if "CREATE" in l][0]


def test_081_touches_nothing_it_inherits():
    clean = _clean()
    for forbidden in ("ALTER TABLE", "DROP ", "UPDATE ", "INSERT INTO",
                      "TRUNCATE"):
        assert forbidden not in clean
    for table in UNTOUCHABLE_TABLES:
        assert f"CREATE TABLE IF NOT EXISTS stratum.{table} (" not in clean


def test_created_at_has_a_default_so_the_insert_omits_it():
    clean = _clean()
    assert "created_at TIMESTAMP NOT NULL DEFAULT now()" in clean
    assert column_parity_gate() == "PASS"
    assert "created_at" in CONSTRAINT_COLUMNS
    assert "created_at" not in CONSTRAINT_INSERT_COLUMNS


def test_column_parity():
    fields = set(vars(ConstraintCandidate(
        id="", source_version_id="", knowledge_unit_id="", constraint_type="",
        subject="", predicate="", object="")))
    assert set(CONSTRAINT_COLUMNS) <= fields


def test_evidence_array_uses_cardinality_not_array_length():
    clean = _clean()
    assert "CHECK (cardinality(evidence_ids) >= 1)" in clean
    assert "array_length(" not in clean


def test_quoted_fields_are_non_empty():
    """NOT NULL plus a btrim check.

    These only stop the degenerate row. The real gate is that each field is a
    substring of the span, which a CHECK cannot state.
    """
    clean = _clean()
    assert "CHECK (length(btrim(subject)) > 0)" in clean
    assert "CHECK (length(btrim(predicate)) > 0)" in clean
    assert "CHECK (length(btrim(object)) > 0)" in clean


def test_evidence_ids_are_sorted_before_hashing():
    """Traversal order is not a claim."""
    assert hash_ordering_gate() == "PASS"


def test_no_advice_column_grew():
    """A constraint records a stated limit, not what anyone ought to do.

    "合理利率应该低于20%" is advice; a column that could hold advice would let
    A仓 give it.
    """
    assert not any(banned_field_report().values())
    assert banned_field_gate() == "PASS"
    for name in CONSTRAINT_BANNED_FIELDS:
        assert not hasattr(ConstraintCandidate, name)
        assert name not in CONSTRAINT_COLUMNS
    for banned in ("recommendation", "advice", "should", "optimal",
                   "normative"):
        assert banned not in CONSTRAINT_COLUMNS


def test_earlier_migrations_are_untouched():
    for name in ("077_a_condition_boundary.sql", "078_a_mechanism_chain.sql",
                 "079_a_relation_candidate.sql", "080_a_paper_source.sql"):
        sql = (MIGRATIONS / name).read_text(encoding="utf-8")
        assert "constraint_candidate" not in sql


# ── Quote authority — DECISION=SPAN_ONLY ─────────────────────────────────────

def test_every_field_is_a_literal_substring_of_the_span(constraint, store):
    """The single rule this stage exists for."""
    assert quote_authority_gate(constraint) == "PASS"
    candidate = constraint["written"]
    span = evidence_span(store.evidence[candidate.evidence_ids[0]])
    assert span == "贷款的利息被限制为不得超过每年8.333%"
    for name, value in (("subject", candidate.subject),
                        ("predicate", candidate.predicate),
                        ("object", candidate.object),
                        ("boundary", candidate.boundary)):
        assert value in span, f"{name}={value!r} is not in the span"
    assert field_is_quoted(candidate, span)
    assert unquoted_fields(candidate, span) == []


def test_the_ku_statement_is_never_the_quotation_source(constraint):
    """The decision, asserted in the negative direction.

    For the pilot unit the statement says 罗马法定利率上限：8.333%/年 while the
    span says 贷款的利息被限制为不得超过每年8.333%. So 法定利率上限 and 8.333%/年
    are available in the statement and absent from the span — and none of them
    is quoted.
    """
    assert ku_statement_not_evidence_gate(constraint) == "PASS"
    unit = constraint["sink"].units[PILOT_CONSTRAINT["knowledge_unit_id"]]
    statement = unit.statement
    candidate = constraint["written"]
    assert "法定利率上限" in statement
    assert candidate.subject != "法定利率上限"
    for value in (candidate.subject, candidate.predicate, candidate.object,
                  candidate.boundary):
        assert value not in ("法定利率上限", "8.333%/年")


def test_a_field_absent_from_the_span_is_refused():
    """The Babylon cap, refused by the rule rather than by a comment.

    Its span states 银子贷款按重量计算每年20% — a rate, with no 上限, no 不得超过
    and no 禁止. Typing it HARD would mean importing the cap framing from the KU
    statement, which is a derived constraint.
    """
    fresh = _fresh()
    builder = fresh["writer"].builder
    span = builder.span_of("ku_639e79172556")
    assert span == "银子贷款按重量计算每年20%"
    assert "上限" not in span
    assert "不得超过" not in span
    candidate = builder.build(
        source_version_id=fresh["result"]["base"]["source_version_id"],
        unit_id="ku_639e79172556", constraint_type="HARD",
        subject="利息", predicate="不得超过", obj="20%", boundary=None,
        extractor_version=PILOT_DECLARED_VERSION)
    # 利息 is absent as well — the span is about 银子贷款 — and 20% *is*
    # present, as 每年20%.
    assert unquoted_fields(candidate, span) == ["subject", "predicate"]
    with pytest.raises(ConstraintPrecondition, match="FIELD_NOT_IN_SPAN"):
        fresh["writer"].write(candidate)


def test_the_span_is_read_not_the_statement(store):
    """evidence_span resolves both names the value has across 070.

    content_span on the in-memory row, content in the database. If a rename in
    either layer went unnoticed, the symptom would be a quote gate refusing
    everything for a reason nobody can see.
    """
    evidence = next(iter(store.evidence.values()))
    assert evidence_span(evidence) is not None
    assert evidence_span(None) is None


def test_every_row_has_evidence(constraint, writer):
    for candidate in constraint["sink"].constraint_candidates.values():
        assert candidate.evidence_ids
    assert writer.unquoted_candidates() == []


def test_evidence_source_matches_source_version(constraint, writer, store):
    """Every evidence id is a real row of the annotation's own book."""
    for candidate in constraint["sink"].constraint_candidates.values():
        for evidence_id in candidate.evidence_ids:
            evidence = store.evidence[evidence_id]
            assert evidence.source_version_id == candidate.source_version_id


def test_traceability_is_measured_as_a_substring_test(constraint, writer):
    """"An id exists" is not "the words are the book's"."""
    assert trace_gate(constraint) == "PASS"
    assert writer.traceability_percent() == 100.0


def test_advisory_wording_is_refused():
    """A recommendation is not a constraint, whatever the source calls it."""
    assert ADVISORY_MARKERS
    for marker in ("应该", "建议", "推荐"):
        assert marker in ADVISORY_MARKERS


# ── Authority ────────────────────────────────────────────────────────────────

def test_no_B_dependency():
    assert contamination_counts(_fresh())["B_REFERENCE"] == 0
    clean = _clean().lower()
    for foreign in ("aii_refined", "refined_ku", "refined_concept"):
        assert foreign not in clean


def test_no_C_dependency():
    """Import graph and artifact, the two layers this project uses.

    The forbidden table names are deliberately not restated in any src/ file:
    tests/integration/test_a_authority_freeze.py word-scans this package for
    them, so naming them — even in a guard list — is the violation that test
    exists to catch. authority_gate() carries both checks.
    """
    assert contamination_counts(_fresh())["C_REFERENCE"] == 0
    assert external_imports() == []
    assert authority_gate(_fresh()) == "PASS"


def test_no_BU2_dependency():
    assert authority_gate(_fresh()) == "PASS"
    assert contamination_counts(_fresh())["BU2_DEPENDENCY"] == 0


def test_the_artifact_carries_no_contamination(constraint):
    payload = {"constraints": [c.id for c in
                               constraint["sink"].constraint_candidates.values()]}
    assert artifact_drift(payload) == {}


def test_the_baseline_underneath_is_untouched(constraint):
    assert baseline_mutation_gate(constraint) == "PASS"


def test_the_frozen_layers_are_untouched():
    """077's empty boundary table and every later layer are left alone."""
    assert frozen_layers_untouched_gate() == "PASS"
    clean = _clean()
    for table in ("ku_condition_candidate", "ku_boundary_candidate",
                  "ku_relation", "relation_candidate",
                  "paper_source_candidate"):
        assert table not in clean


def test_verification_logic_still_untouched():
    from stratum.knowledge.a_repository.verification import (
        AVerificationPipeline)
    assert AVerificationPipeline.required_slots("FACT") == (
        "ANCHORED", "SUBJECT", "PREDICATE", "OBJECT")


# ── Replay ───────────────────────────────────────────────────────────────────

def test_same_hash_idempotent():
    """Re-running writes nothing."""
    fresh = _fresh()
    assert idempotency_gate(fresh) == "PASS"
    assert gate_results(_fresh())["GATE_5_replay"] == "PASS"
    assert fresh["writer"].duplicate_hashes() == []


def test_hash_stability():
    """Same input, same hash. Any quoted field, a new annotation."""
    assert hash_stability_gate() == "PASS"


def test_the_emitted_script_is_idempotent(constraint):
    script = emit_constraint_sql(constraint["sink"].constraint_candidates)
    lines = [line for line in script.splitlines()
             if line.startswith("INSERT INTO")]
    assert len(lines) == 1
    assert "ON CONFLICT (constraint_hash) DO NOTHING;" in script
    assert script.count("BEGIN;") == 1 and script.count("COMMIT;") == 1


def test_the_script_is_byte_identical_on_a_rerun(tmp_path):
    first = write_sql(_fresh(), str(tmp_path / "a.sql"))
    second = write_sql(_fresh(), str(tmp_path / "b.sql"))
    assert Path(first).read_bytes() == Path(second).read_bytes()


# ── Isolation ────────────────────────────────────────────────────────────────

def test_cross_book_unit_blocked():
    fresh = _fresh()
    clone = _clone(fresh["candidate"])
    clone.source_version_id = "sv_another_book"
    clone.id = "cnc_cross"
    clone.constraint_hash = "cnh_cross"
    with pytest.raises(ConstraintPrecondition, match="CROSS_SOURCE_UNIT"):
        fresh["writer"].write(clone)


def test_an_unfrozen_unit_is_blocked():
    """§5 requires a frozen knowledge_unit, so an unanchored span cannot land."""
    fresh = _fresh()
    clone = _clone(fresh["candidate"])
    clone.knowledge_unit_id = "ku_not_a_unit"
    clone.id = "cnc_unfrozen"
    clone.constraint_hash = "cnh_unfrozen"
    with pytest.raises(ConstraintPrecondition, match="NO_SUCH_UNIT"):
        fresh["writer"].write(clone)


# ── Lifecycle ────────────────────────────────────────────────────────────────

def test_generated_supported():
    fresh = _fresh()
    candidate = fresh["written"]
    assert candidate.status == ConstraintStatus.GENERATED.value
    supported = fresh["writer"].support(candidate.id)
    assert supported.status == ConstraintStatus.SUPPORTED.value


def test_generated_rejected():
    fresh = _fresh()
    rejected = fresh["writer"].reject(fresh["written"].id)
    assert rejected.status == ConstraintStatus.REJECTED.value


def test_supported_to_generated_blocked():
    """Both SUPPORTED and REJECTED are final."""
    fresh = _fresh()
    candidate = fresh["written"]
    fresh["writer"].support(candidate.id)
    for target in (ConstraintStatus.GENERATED, ConstraintStatus.REJECTED):
        with pytest.raises(ConstraintViolation, match="final"):
            transition(candidate, target)
    assert candidate.status == ConstraintStatus.SUPPORTED.value


def test_a_rejected_candidate_is_not_revived():
    fresh = _fresh()
    candidate = fresh["writer"].reject(fresh["written"].id)
    for target in (ConstraintStatus.GENERATED, ConstraintStatus.SUPPORTED):
        with pytest.raises(ConstraintViolation, match="final"):
            transition(candidate, target)


def test_nothing_can_be_mutated_deleted_or_derived(writer, constraint):
    stored = constraint["written"].id
    with pytest.raises(ConstraintViolation, match="cannot be updated"):
        writer.update_candidate(stored, subject="x")
    with pytest.raises(ConstraintViolation, match="cannot be deleted"):
        writer.delete_candidate(stored)
    with pytest.raises(ConstraintViolation, match="does not derive"):
        writer.derive_constraint(stored)
    with pytest.raises(ConstraintViolation, match="ought"):
        writer.recommend(stored, rate=0.05)
    with pytest.raises(ConstraintViolation, match="authority to merge"):
        writer.merge_constraints("cnc_a", "cnc_b")
    with pytest.raises(ConstraintViolation, match="enforcement"):
        writer.enforce(stored)
    with pytest.raises(ConstraintViolation, match="never touches"):
        writer.update_verification("anything")


# ── Pilot ────────────────────────────────────────────────────────────────────

def test_one_row_and_it_is_declared(constraint, writer):
    """One honest row, not a set padded to look fuller."""
    assert len(constraint["sink"].constraint_candidates) == 1
    assert writer.pilot_rows()
    assert writer.extracted_rows() == [], \
        "this stage ships no extractor; nothing may claim to be extracted"
    candidate = constraint["written"]
    assert candidate.extractor_version == PILOT_DECLARED_VERSION
    assert candidate.extractor_version != EXTRACTOR_VERSION


def test_type_coverage_reports_what_was_exercised(constraint, writer):
    """HARD yes; SOFT and SELF_DEFINED no — and that is the decision."""
    coverage = writer.type_coverage()
    assert coverage == {"HARD": True, "SOFT": False, "SELF_DEFINED": False}
    assert coverage_gate(constraint) == "PASS"
    # The vocabulary that would define a SOFT constraint is absent from the
    # corpus, which is why SOFT is unexercised rather than untried.
    assert SOFT_MARKERS


def test_the_pilot_is_the_stated_cap_not_the_babylon_one(constraint, store):
    candidate = constraint["written"]
    assert candidate.constraint_type == "HARD"
    assert candidate.knowledge_unit_id == "ku_15a527238f5c"
    span = evidence_span(store.evidence[candidate.evidence_ids[0]])
    assert span == "贷款的利息被限制为不得超过每年8.333%"
    assert candidate.predicate == "被限制为不得超过"
    # The rejected alternative, recorded rather than dropped silently.
    assert "ku_639e79172556" in MEASURED_REJECTIONS
    assert "上限" in MEASURED_REJECTIONS["ku_639e79172556"]


def test_the_measured_rejections_are_recorded_with_reasons():
    """Nothing is dropped quietly: every absent span says why."""
    assert len(MEASURED_REJECTIONS) >= 5
    for unit_id, reason in MEASURED_REJECTIONS.items():
        assert unit_id.startswith("ku_")
        assert len(reason) > 20, f"{unit_id} has no stated reason"
    assert UNANCHORED_SPANS, "unanchored spans should be listed"
    assert any("33.333" in s for s in UNANCHORED_SPANS)


def test_the_untested_things_are_declared_not_hidden(constraint):
    """Named in the report rather than quietly absent."""
    doc = acceptance(constraint)
    assert set(doc["UNTESTED"]) == {
        "soft_constraint_extraction", "self_defined_constraint",
        "constraint_completeness", "legal_correctness",
        "advisory_wording_in_corpus"}


# ── negative ─────────────────────────────────────────────────────────────────

def test_negative_gate_refuses_every_case(constraint):
    """Each forbidden shape is refused, and each one is named."""
    checks = negative_gate(constraint)
    assert all(checks.values()), [k for k, v in checks.items() if not v]
    for name in ("ku_statement_not_quoted", "boundary_not_in_span",
                 "predicate_not_in_span", "subject_not_in_span",
                 "object_not_in_span", "invented_boundary", "unknown_type",
                 "cross_source_unit", "no_evidence", "cross_book_evidence",
                 "supported_downgrade", "rejected_revived", "derive_constraint",
                 "recommend"):
        assert name in checks


# ── the test contract ────────────────────────────────────────────────────────

def test_review_checklist():
    """§16's checklist, as one gate."""
    clean = _clean()
    assert schema_gate() == "PASS"              # table exists
    assert fk_verb_gate() == "PASS"             # FK all RESTRICT
    assert vocabulary_gate() == "PASS"          # closed vocabularies
    assert constraint_gate() == "PASS"          # hash unique, evidence non-empty
    assert index_reuse_gate() == "PASS"         # no new frozen index
    assert banned_field_gate() == "PASS"        # no recommendation field
    referenced = set(re.findall(r"REFERENCES\s+stratum\.(\w+)", clean))
    assert not {"bu_onto", "chapter_bu"} & referenced        # no BU2 FK
    assert not any(r.endswith("_onto") for r in referenced)  # no B / C FK


def test_all_gates_pass(constraint):
    gates = gate_results(constraint)
    for name, value in gates.items():
        if isinstance(value, dict):
            continue
        assert value == "PASS", f"{name}={value}"


def test_acceptance_block(constraint):
    doc = acceptance(constraint)
    checks = doc["checks"]
    assert doc["A_P5_4_CONSTRAINT_SCHEMA"] == "PASS"
    assert doc["A_P5_4_CONSTRAINT_IMPLEMENTATION"] == "PASS"
    assert doc["MIGRATION_081"] == REQUIRED_MIGRATION
    assert doc["TYPE_COVERAGE"] == {"HARD": True, "SOFT": False,
                                    "SELF_DEFINED": False}
    assert checks["constraint_persisted"] == 1
    assert checks["fields_quoted_from_span"] == "PASS"
    assert checks["traceability_percent"] == 100.0
    assert checks["source_isolation"] == "PASS"
    assert checks["replay_stable"] == "PASS"
    assert checks["transaction_atomic"] == "PASS"
    assert checks["unauthorised_type_rows"] == 0
    assert checks["cross_source_candidates"] == 0
    assert checks["B_CONTAMINATION"] == 0
    assert checks["C_CONTAMINATION"] == 0
    assert checks["BU2_DEPENDENCY"] == 0
    assert checks["baseline_mutated"] == 0
    assert checks["negative_refusals"] == checks["negative_cases"]


def test_final_report_block(constraint):
    """§FINAL REPORT FORMAT keys, present and honest."""
    block = final_report(constraint)
    for key in ("TASK", "MIGRATION_081", "CONSTRAINT_ROWS", "TRACEABILITY",
                "REPLAY", "AUTHORITY_SCAN", "B_CONTAMINATION",
                "C_CONTAMINATION", "DB_MUTATION", "BU2_MUTATION",
                "COMMIT_SHA", "TAG", "FINAL_STATUS"):
        assert key in block, key
    assert block["TASK"] == "A_P5_4_CONSTRAINT"
    assert block["FINAL_STATUS"] == "PASS"
    assert block["MIGRATION_081"] == REQUIRED_MIGRATION
    assert block["CONSTRAINT_ROWS"] == "1"
    assert block["TRACEABILITY"] == "100.0%"
    assert block["REPLAY"] == "PASS"
    assert block["B_CONTAMINATION"] == "0"
    assert block["C_CONTAMINATION"] == "0"
    assert block["DB_MUTATION"] == "0"
    assert block["BU2_MUTATION"] == "0"


def test_committed_artifact_matches_a_fresh_run():
    assert ARTIFACT.exists(), "run constraint_runner to emit the artifact"
    committed = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    fresh = report(_fresh())
    for key in ("constraint_count", "pilot_rows", "extracted_rows",
                "traceability_percent", "constraint_version",
                "constraint_types_declared", "quote_authority",
                "type_coverage", "measured_rejections", "unanchored_spans"):
        assert committed[key] == fresh[key], key
    assert committed["constraints"] == fresh["constraints"]


def test_the_converted_percent_gate_reports_a_real_measurement(constraint):
    """`GATE_4_traceability_percent` is a status now. Assert the number it stands for too,
    or a PASS would say nothing about traceability."""
    assert gate_results(constraint)["GATE_4_traceability_percent"] == "PASS"
    assert constraint["writer"].traceability_percent() == 100.0
