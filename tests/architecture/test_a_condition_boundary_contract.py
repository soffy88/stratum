"""A Repository P5.0 — condition / boundary candidate layer.

Contract tests, and the gate that authorises migration 077:

- schema      two tables, closed vocabularies, column parity
- authority   the frozen baseline is untouched by extraction and by writing
- evidence    every candidate reaches an evidence row and a source version
- anchoring   every statement is verbatim from the span it came from
- guard       a tendency or a causal connective is refused, not down-weighted
- isolation   three layers, reusing P7's gates — never a word scan
- replay      re-extracting appends nothing

Run before 077 is applied:

    python3 -m pytest tests/architecture/test_a_condition_boundary_contract.py -q
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
MIGRATION = MIGRATIONS / "077_a_condition_boundary.sql"
ARTIFACTS = ROOT / "artifacts" / "a_repository"

from stratum.knowledge.a_repository.condition_boundary import (  # noqa: E402
    ACTOR_DISQUALIFIERS,
    ACTOR_MARKERS,
    BOUNDARY_COLUMNS,
    CONDITION_BOUNDARY_TABLES,
    CONDITION_BOUNDARY_VERSION,
    CONDITION_COLUMNS,
    CAUSAL_WORDS,
    NOT_YET_EXTRACTABLE_BOUNDARY_TYPES,
    NOT_YET_EXTRACTABLE_CONDITION_TYPES,
    TENDENCY_WORDS,
    TIME_DISQUALIFIERS,
    TIME_MARKERS,
    BoundaryCandidate,
    BoundaryType,
    CandidateStatus,
    ConditionBoundaryPrecondition,
    ConditionBoundarySink,
    ConditionBoundaryViolation,
    ConditionBoundaryExtractor,
    ConditionCandidate,
    ConditionType,
    anchor_confidence,
    boundary_hash,
    boundary_id,
    clause_around,
    condition_constraint_boundary_guard,
    condition_hash,
    condition_id,
    emit_condition_boundary_sql,
)
from stratum.knowledge.a_repository.condition_boundary_runner import (  # noqa: E402
    A_ONLY_TABLES,
    UNTOUCHABLE_TABLES,
    acceptance,
    baseline_invariance_gate,
    column_parity_gate,
    evidence_gate,
    extraction_purity_gate,
    gate_results,
    idempotency_gate,
    isolation_gate,
    ku_mutation_gate,
    replay_gate,
    report,
    run_extraction,
    traceability_percent,
    unit_snapshot,
    upstream_untouched_gate,
    verification_logic_gate,
    vocabulary_gate,
)
from stratum.knowledge.a_repository.projection_builder import (  # noqa: E402
    artifact_drift,
    external_imports,
)


@pytest.fixture(scope="module")
def run():
    return run_extraction()


@pytest.fixture(scope="module")
def result(run):
    return run["result"]


@pytest.fixture(scope="module")
def sink(run):
    return run["sink"]


@pytest.fixture(scope="module")
def writer(run):
    return run["writer"]


@pytest.fixture(scope="module")
def units(run):
    return run["units"]


def _fresh() -> Dict:
    return run_extraction()


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def _clean() -> str:
    return re.sub(r"--[^\n]*", "", _sql())


def _table_body(text: str, table: str) -> str:
    block = re.sub(r"--[^\n]*", "",
                   text.split(f"CREATE TABLE IF NOT EXISTS stratum.{table}")[1])
    start = block.index("(") + 1
    depth, out = 1, []
    for char in block[start:]:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                break
        out.append(char)
    return "".join(out)


def _declared_columns(table: str) -> set:
    body = _table_body(_clean(), table)
    parts, depth, current = [], 0, []
    for char in body:
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


# ── schema ───────────────────────────────────────────────────────────────────

def test_tables_exist():
    """`tables_exist` — both CREATE TABLE IF NOT EXISTS statements."""
    clean = _clean()
    for table in A_ONLY_TABLES:
        assert f"CREATE TABLE IF NOT EXISTS stratum.{table} (" in clean


def test_fk_valid():
    """`fk_valid` — exactly one foreign key, onto knowledge_unit, RESTRICT."""
    clean = _clean()
    references = re.findall(r"REFERENCES\s+stratum\.(\w+)\(id\)"
                            r"\s+ON DELETE (\w+)", clean)
    assert references == [("knowledge_unit", "RESTRICT")] * 2


def test_indexes_valid():
    """`indexes_valid` — one per table by unit and by type, GIN by evidence."""
    clean = _clean()
    for table in A_ONLY_TABLES:
        assert f"ON stratum.{table}(knowledge_unit_id)" in clean
        assert f"idx_{table}_type" in clean
        assert "USING GIN (evidence_ids)" in clean
    assert len(re.findall(r"CREATE INDEX IF NOT EXISTS", clean)) == 6


def test_column_parity():
    """Every column the writer emits, the schema declares.

    077 referenced two columns it never declared and every insert failed
    against a real database. Reading either file does not catch it.
    """
    assert column_parity_gate() == "PASS"
    for table, columns in (("ku_condition_candidate", CONDITION_COLUMNS),
                           ("ku_boundary_candidate", BOUNDARY_COLUMNS)):
        assert set(columns) <= _declared_columns(table)
    for column in ("condition_hash", "boundary_hash"):
        assert column in _clean()


def test_077_touches_nothing_it_inherits():
    """§10 — only CREATE. No ALTER, DROP, UPDATE or backfill."""
    assert upstream_untouched_gate() == "PASS"
    clean = _clean()
    for forbidden in ("ALTER TABLE", "DROP ", "UPDATE ", "INSERT INTO",
                      "TRUNCATE"):
        assert forbidden not in clean
    for table in UNTOUCHABLE_TABLES:
        assert f"CREATE TABLE IF NOT EXISTS stratum.{table} (" not in clean


def test_condition_type_vocabulary_is_two_values():
    block = _clean().split(
        "CREATE TABLE IF NOT EXISTS stratum.ku_condition_candidate")[1]
    declared = set(re.findall(r"'([A-Z_]+)'", block.split("CHECK")[1]))
    assert declared == {"ACTOR", "TIME"}
    assert declared == {t.value for t in ConditionType}


def test_boundary_type_vocabulary_is_two_values():
    block = _clean().split(
        "CREATE TABLE IF NOT EXISTS stratum.ku_boundary_candidate")[1]
    declared = set(re.findall(r"'([A-Z_]+)'", block.split("CHECK")[1]))
    assert declared == {"TIME_LIMIT", "ACTOR_LIMIT"}
    assert declared == {t.value for t in BoundaryType}


def test_vocabulary_gate_is_deterministic():
    """It compares the two vocabularies separately.

    It previously held them in a `set` of tuples and `pop()`ed, which assigns
    them in arbitrary order and made the gate fail at random.
    """
    for _ in range(5):
        assert vocabulary_gate() == "PASS"


def test_the_three_unextractable_factors_are_not_in_the_schema():
    """§3 — STATE / LOCATION / PREREQUISITE have no extractor, so they are
    not admitted to the CHECK."""
    clean = _clean()
    for name in NOT_YET_EXTRACTABLE_CONDITION_TYPES:
        assert f"'{name}'" not in clean
        assert name not in {t.value for t in ConditionType}
    for name in NOT_YET_EXTRACTABLE_BOUNDARY_TYPES:
        assert f"'{name}'" not in clean
        assert name not in {t.value for t in BoundaryType}


def test_status_has_no_verified():
    """A reading of a span is not a verdict about the world."""
    assert {s.value for s in CandidateStatus} == {
        "GENERATED", "SUPPORTED", "REJECTED"}
    clean = _clean()
    assert "'VERIFIED'" not in clean


def test_confidence_is_bounded_by_the_schema():
    clean = _clean()
    assert clean.count(
        "CHECK (confidence >= 0.0 AND confidence <= 1.0)") == 2


def test_evidence_ids_must_be_non_empty():
    """`TEXT[]` cannot carry a foreign key, so the array length is the only
    database-side guarantee available.

    cardinality(), not array_length(). Measured against a live database while
    applying 077: `array_length(ARRAY[]::text[], 1)` is NULL, a CHECK passes
    when its expression is NULL, so the array_length guard accepted the very
    empty array it existed to reject. `cardinality()` returns 0 there, so
    `0 >= 1` is false and the row is refused.
    """
    clean = _clean()
    assert clean.count("CHECK (cardinality(evidence_ids) >= 1)") == 2
    assert "array_length(evidence_ids" not in clean


def test_statement_must_be_non_blank():
    clean = _clean()
    assert clean.count("CHECK (length(btrim(statement)) > 0)") == 2


# ── authority ────────────────────────────────────────────────────────────────

def test_frozen_ku_immutable(run, result, sink):
    """`frozen_ku_immutable` — no unit row changed, none disappeared."""
    assert ku_mutation_gate(run) == "PASS"
    after = unit_snapshot(sink)
    for unit_id, row in run["before_snapshot"].items():
        assert after[unit_id] == row
    assert len(after) == len(run["before_snapshot"])


def test_the_extractor_alone_changes_nothing(run):
    """Before any write, so the extractor is caught even if the write path
    would mask it."""
    assert verification_logic_gate(run) == "PASS"
    assert run["after_extract"] == run["before_snapshot"]


def test_baseline_invariance(run):
    assert baseline_invariance_gate(run) == "PASS"
    assert run["after_write"] == run["before_snapshot"]


def test_extraction_purity():
    assert extraction_purity_gate() == "PASS"


def test_the_module_holds_no_dml():
    source = (PKG / "condition_boundary.py").read_text(encoding="utf-8")
    code = re.sub(r'""".*?"""', "", source, flags=re.DOTALL)
    code = re.sub(r"^\s*#.*$", "", code, flags=re.MULTILINE)
    assert not re.search(r"^[ \t]*(INSERT|UPDATE|DELETE|DROP)\b", code,
                         re.MULTILINE)


def test_the_writer_cannot_change_a_verification(writer):
    with pytest.raises(ConditionBoundaryViolation, match="never touches"):
        writer.update_verification("anything")


def test_the_writer_cannot_mutate_a_candidate(writer):
    for method in ("update_candidate", "delete_candidate", "merge_candidates",
                   "promote"):
        with pytest.raises(ConditionBoundaryViolation):
            getattr(writer, method)("kcc_whatever")


def test_nothing_promotes_to_verified(writer):
    """A仓 does not declare an interpretation true."""
    with pytest.raises(ConditionBoundaryViolation, match="no VERIFIED"):
        writer.promote("kcc_whatever")


def test_a_superseded_unit_is_not_extracted(units):
    """A superseded unit's successor carries the reading, matching P7."""
    from stratum.knowledge.a_repository.ku_identity_runner import build_identity
    chain = build_identity()
    superseded = {r.prior_unit_id for r in chain["sink"].revisions.values()}
    assert superseded
    for unit in units:
        assert unit.id not in superseded


# ── evidence ─────────────────────────────────────────────────────────────────

def test_condition_requires_evidence(writer):
    candidate = ConditionCandidate(
        id="kcc_x", knowledge_unit_id="ku_x", condition_type="ACTOR",
        statement="演员", evidence_ids=[])
    ok, failed = writer.preconditions(candidate)
    assert not ok
    assert "NO_EVIDENCE" in failed
    with pytest.raises(ConditionBoundaryPrecondition):
        writer.write(candidate)


def test_boundary_requires_evidence(writer):
    candidate = BoundaryCandidate(
        id="kbc_x", knowledge_unit_id="ku_x", boundary_type="TIME_LIMIT",
        statement="截至某年", evidence_ids=[])
    ok, failed = writer.preconditions(candidate)
    assert not ok
    assert "NO_EVIDENCE" in failed


def test_an_orphan_evidence_id_is_refused(writer, sink):
    candidate = ConditionCandidate(
        id="kcc_y", knowledge_unit_id=next(iter(sink.units)),
        condition_type="ACTOR", statement="演员",
        evidence_ids=["ev_does_not_exist"])
    ok, failed = writer.preconditions(candidate)
    assert not ok
    assert "ORPHAN_EVIDENCE" in failed


def test_every_candidate_reaches_a_source_version(run):
    assert traceability_percent(run) == 100.0
    assert evidence_gate(run) == "PASS"


def test_no_orphans(writer):
    assert writer.orphan_conditions() == []
    assert writer.orphan_boundaries() == []


def test_an_anchored_statement_is_a_substring_of_its_span(writer, sink):
    """The check that makes "source-grounded" mean something."""
    assert writer.misanchored_statements() == []
    for row in list(sink.conditions.values()) + list(sink.boundaries.values()):
        unit = sink.units[row.knowledge_unit_id]
        assert row.statement in unit.canonical_text


def test_a_paraphrased_statement_is_detected(writer, sink):
    row = next(iter(sink.conditions.values()))
    original = row.statement
    row.statement = "大致意思是这个"          # a paraphrase
    try:
        assert writer.misanchored_statements() == [row.id]
    finally:
        row.statement = original
    assert writer.misanchored_statements() == []


def test_extraction_never_writes_prose():
    """Every statement must occur in the source span of the unit it is
    attached to — checked across the whole extraction, not per row."""
    extracted = run_extraction()["extracted"]
    chain_sink = run_extraction()["sink"]
    for row in extracted["conditions"] + extracted["boundaries"]:
        unit = chain_sink.units[row.knowledge_unit_id]
        assert row.statement in unit.canonical_text


# ── the guard ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("word", TENDENCY_WORDS)
def test_a_tendency_is_refused_in_a_condition(word):
    with pytest.raises(ConditionBoundaryPrecondition, match="tendency"):
        condition_constraint_boundary_guard(f"{word}可以放贷", "condition")


@pytest.mark.parametrize("word", CAUSAL_WORDS)
def test_a_causal_connective_is_refused_in_a_condition(word):
    with pytest.raises(ConditionBoundaryPrecondition, match="mechanism"):
        condition_constraint_boundary_guard(f"{word}债权人存在", "condition")


def test_a_tendency_is_refused_in_a_boundary():
    with pytest.raises(ConditionBoundaryPrecondition, match="tendency"):
        condition_constraint_boundary_guard("大多数时候不适用", "boundary")


def test_a_checkable_qualifier_is_accepted():
    """The proposal's own worked example passes."""
    condition_constraint_boundary_guard("商人在某时期可以……", "condition")
    condition_constraint_boundary_guard("公元前18世纪……", "condition")


def test_an_empty_statement_is_refused():
    with pytest.raises(ConditionBoundaryPrecondition):
        condition_constraint_boundary_guard("   ", "condition")


def test_an_unknown_guard_kind_is_refused():
    with pytest.raises(ConditionBoundaryPrecondition, match="guard kind"):
        condition_constraint_boundary_guard("x", "constraint")


def test_constraint_separation_is_directional():
    """A tendency is refused in a condition. That is what makes the
    condition/constraint split checkable rather than a naming convention —
    and the guard is never applied to a constraint candidate, which is where
    tendencies belong."""
    assert condition_constraint_boundary_guard.__doc__
    with pytest.raises(ConditionBoundaryPrecondition):
        condition_constraint_boundary_guard("通常情况下不超过33.333%",
                                            "condition")


# ── clause extraction ────────────────────────────────────────────────────────

def test_clause_is_cut_at_delimiters():
    span = "在大约公元前1800年，古代巴比伦王朝的第一个国王汉谟拉比"
    assert clause_around(span, "国王") == "古代巴比伦王朝的第一个国王汉谟拉比"
    assert clause_around(span, "公元前") == "在大约公元前1800年"


def test_clause_is_verbatim():
    span = "雅典出现了一次经济危机"
    clause = clause_around(span, "雅典")
    assert clause in span


def test_clause_of_an_absent_marker_is_empty():
    assert clause_around("雅典出现了一次经济危机", "罗马") == ""


def test_anchor_confidence_falls_with_ambiguity():
    assert anchor_confidence("索伦的法典", "索伦") == 1.0
    assert anchor_confidence("索伦与索伦", "索伦") < 1.0
    assert anchor_confidence("索" * 20, "索") >= 0.5


def test_a_clause_matching_two_factors_is_recorded_once():
    """One clause read once, not once per factor that lands in it."""
    span = "古代巴比伦王朝的第一个国王汉谟拉比"
    extractor = ConditionBoundaryExtractor.__new__(ConditionBoundaryExtractor)
    rows = extractor.conditions_for("ku_x", span, ["ev_x"])
    assert len(rows) == 1
    assert len({row.statement for row in rows}) == len(rows)


# ── marker vocabularies ──────────────────────────────────────────────────────

def test_the_p3_actor_false_positive_is_withdrawn():
    """法典 is what a ruler modifies, not the ruler. Harmless as a boolean
    slot, wrong as a statement."""
    assert "法典" in ACTOR_DISQUALIFIERS
    assert not any("法典" in marker for marker in ACTOR_MARKERS)


def test_the_p3_time_false_positive_is_withdrawn():
    """年 makes every rate look like a time expression."""
    assert not any(marker == "年" for marker in TIME_MARKERS)
    assert "每年" in TIME_DISQUALIFIERS
    assert not any("每年" in marker for marker in TIME_MARKERS)


def test_the_time_disqualifier_is_documented_as_inert():
    """A guard with no current instance is labelled as such rather than
    left to look load-bearing."""
    source = (PKG / "condition_boundary.py").read_text(encoding="utf-8")
    assert "Currently **inert**" in source


def test_markers_are_a_narrowing_of_p3_not_a_second_vocabulary():
    from stratum.knowledge.a_repository.verification import (
        ACTOR_MARKERS as P3_ACTORS, TIME_MARKERS as P3_TIMES)
    assert set(ACTOR_MARKERS) <= set(P3_ACTORS)
    assert set(TIME_MARKERS) <= set(P3_TIMES) | {"古代", "中世纪"}
    # 古代 / 中世纪 are additions, so say so: they are not a subset.
    added = set(TIME_MARKERS) - set(P3_TIMES)
    assert added == {"古代", "中世纪"}


# ── identity ─────────────────────────────────────────────────────────────────

def test_ids_are_content_derived():
    assert condition_id("ku_a", "ACTOR", "演员") == \
        condition_id("ku_a", "ACTOR", "演员")
    assert condition_id("ku_a", "ACTOR", "演员") != \
        condition_id("ku_a", "TIME", "演员")
    assert boundary_id("ku_a", "TIME_LIMIT", "截至") == \
        boundary_id("ku_a", "TIME_LIMIT", "截至")


def test_hashes_cover_the_evidence_set():
    assert condition_hash("ku_a", "ACTOR", "s", ["ev_1"]) == \
        condition_hash("ku_a", "ACTOR", "s", ["ev_1"])
    assert condition_hash("ku_a", "ACTOR", "s", ["ev_1", "ev_2"]) == \
        condition_hash("ku_a", "ACTOR", "s", ["ev_2", "ev_1"])
    assert condition_hash("ku_a", "ACTOR", "s", ["ev_1"]) != \
        condition_hash("ku_a", "ACTOR", "s", ["ev_2"])


def test_row_ids_match_their_content(sink):
    for row in sink.conditions.values():
        assert row.id == condition_id(row.knowledge_unit_id,
                                      row.condition_type, row.statement)
        assert row.condition_hash == condition_hash(
            row.knowledge_unit_id, row.condition_type, row.statement,
            row.evidence_ids)
    for row in sink.boundaries.values():
        assert row.id == boundary_id(row.knowledge_unit_id,
                                     row.boundary_type, row.statement)
        assert row.boundary_hash == boundary_hash(
            row.knowledge_unit_id, row.boundary_type, row.statement,
            row.evidence_ids)


def test_no_id_is_a_uuid_or_a_timestamp(sink):
    for row in list(sink.conditions.values()) + list(sink.boundaries.values()):
        assert row.id.startswith(("kcc_", "kbc_"))
        assert len(row.id) == 16


# ── replay ───────────────────────────────────────────────────────────────────

def test_replaying_appends_nothing(run):
    replay = replay_gate()
    assert replay["identical_fingerprints"] == 1
    assert replay["rebuild_identical"] == 1
    assert replay["NEW_CONDITION"] == 0
    assert replay["NEW_BOUNDARY"] == 0


def test_idempotency_gate(run):
    assert idempotency_gate(run) == "PASS"


def test_two_runs_produce_the_same_rows():
    first = run_extraction()["sink"]
    second = run_extraction()["sink"]
    assert sorted(first.conditions) == sorted(second.conditions)
    assert sorted(first.boundaries) == sorted(second.boundaries)


def test_no_duplicate_candidates(writer):
    assert writer.duplicate_candidates() == []


# ── isolation ────────────────────────────────────────────────────────────────

def test_isolation_uses_three_layers(run):
    """§11 — reuse P7's gates. A word scan returns 24 hits, all of them
    A仓's own guard lists."""
    assert isolation_gate(run) == "PASS"
    assert external_imports() == []
    assert artifact_drift({"conditions": sorted(run["sink"].conditions)}) == {}


def test_this_file_is_not_word_scanned():
    """The runner must not scan its own source for forbidden names."""
    source = (PKG / "condition_boundary_runner.py").read_text(encoding="utf-8")
    body = source[source.index("def contamination_counts"):]
    assert "external_imports" in body
    assert "artifact_drift" in body


def test_earlier_migrations_are_untouched():
    for name in ("073_a_knowledge_unit_freeze.sql",
                 "074_a_ku_freeze_persistence.sql",
                 "075_a_ku_evolution.sql", "076_a_ku_identity.sql"):
        sql = (MIGRATIONS / name).read_text(encoding="utf-8")
        for table in CONDITION_BOUNDARY_TABLES:
            assert table not in sql


def test_verification_and_freeze_logic_are_untouched():
    """`required_slots()` is the load-bearing one. Measured: two more
    required slots would drop a perfect FACT from 4/4 to 4/6 = 0.667,
    below the 0.8 threshold, flipping all 11 frozen-verified candidates."""
    from stratum.knowledge.a_repository.verification import (
        AVerificationPipeline)
    assert AVerificationPipeline.required_slots("FACT") == (
        "ANCHORED", "SUBJECT", "PREDICATE", "OBJECT")
    assert AVerificationPipeline.required_slots("EVENT") == (
        "ANCHORED", "ACTOR", "TIME", "ACTION")
    assert AVerificationPipeline.required_slots("CONCEPT") == (
        "ANCHORED", "DEFINITION_SPAN")


# ── the result ───────────────────────────────────────────────────────────────

def test_the_boundary_table_is_empty_and_that_is_correct():
    """0/10 frozen spans carry a limit marker. Reported, not engineered
    around: no span in the pilot states a boundary."""
    assert len(_fresh()["sink"].boundaries) == 0


def test_conditions_were_produced(sink):
    assert len(sink.conditions) > 0
    assert {row.condition_type for row in sink.conditions.values()} <= \
        {"ACTOR", "TIME"}


def test_every_condition_is_attached_to_a_current_unit(sink, units):
    current = {unit.id for unit in units}
    for row in sink.conditions.values():
        assert row.knowledge_unit_id in current


def test_report_shape(run):
    doc = report(run)
    assert doc["task"] == "A_P5_0_CONDITION_BOUNDARY"
    assert doc["mode"] == "ADDITIVE_ONLY"
    assert doc["authority"] == "A_REPOSITORY"
    assert doc["extractor_version"] == CONDITION_BOUNDARY_VERSION
    assert doc["condition_candidates"] == len(run["sink"].conditions)
    assert doc["boundary_candidates"] == 0


def test_acceptance_block(run):
    doc = acceptance(run)
    checks = doc["checks"]
    assert doc["A_P5_0_CONDITION_BOUNDARY"] == "PASS"
    assert checks["FROZEN_KU_MUTATION"] == 0
    assert checks["VERIFICATION_LOGIC_MUTATION"] == 0
    assert checks["EVIDENCE_TRACEABILITY"] == 100.0
    assert checks["ORPHAN"] == 0
    assert checks["REPLAY"] == "PASS"
    assert checks["B_CONTAMINATION"] == 0
    assert checks["C_CONTAMINATION"] == 0


def test_all_gates_pass(run):
    gates = gate_results(run)
    for name, value in gates.items():
        assert value in {"PASS", 0, 100.0}, f"{name}={value}"


def test_the_emitted_script_is_one_transaction(run, tmp_path):
    script = emit_condition_boundary_sql(
        run["upstream"]["base"]["pipeline"].store,
        run["sink"].conditions, run["sink"].boundaries)
    assert script.count("BEGIN;") == 1
    assert script.count("COMMIT;") == 1
    assert script.index("BEGIN;") < script.index("COMMIT;")


def test_every_emitted_statement_is_idempotent(run):
    script = emit_condition_boundary_sql(
        run["upstream"]["base"]["pipeline"].store,
        run["sink"].conditions, run["sink"].boundaries)
    lines = [line for line in script.splitlines()
             if line.startswith("INSERT INTO")]
    assert lines
    for line in lines:
        assert "ON CONFLICT (" in line and line.endswith("DO NOTHING;")


def test_the_script_writes_arrays_as_sql_arrays(run):
    script = emit_condition_boundary_sql(
        run["upstream"]["base"]["pipeline"].store,
        run["sink"].conditions, run["sink"].boundaries)
    assert "ARRAY[" in script
    assert "'ev_" in script


def test_the_script_is_byte_identical_on_a_rerun(run, tmp_path):
    from stratum.knowledge.a_repository.condition_boundary_runner import (
        write_sql)
    first = write_sql(run, str(tmp_path / "a.sql"))
    second = write_sql(run_extraction(), str(tmp_path / "b.sql"))
    assert Path(first).read_bytes() == Path(second).read_bytes()


# ── the sink ────────────────────────────────────────────────────────────────

def test_the_sink_carries_the_whole_chain():
    """One sink means one transaction can carry units, identities and
    candidates together."""
    from stratum.knowledge.a_repository.identity import IDENTITY_TABLES
    sink = ConditionBoundarySink()
    for table in IDENTITY_TABLES:
        assert table in sink.TABLES
    for table in CONDITION_BOUNDARY_TABLES:
        assert table in sink.TABLES


def test_the_sink_refuses_a_table_it_does_not_own():
    sink = ConditionBoundarySink()
    with pytest.raises(ConditionBoundaryViolation):
        sink.commit([("bu_onto", {"id": "x"})])


def test_the_sink_discards_a_partial_transaction():
    sink = ConditionBoundarySink(fail_after=1)
    with pytest.raises(RuntimeError):
        sink.commit([
            ("ku_condition_candidate",
             {"id": "kcc_1", "knowledge_unit_id": "ku_a",
              "condition_type": "ACTOR", "statement": "s",
              "evidence_ids": ["ev_a"], "extractor_version": "v",
              "confidence": 1.0, "condition_hash": "h",
              "status": "GENERATED", "created_at": "v"}),
            ("ku_boundary_candidate",
             {"id": "kbc_1", "knowledge_unit_id": "ku_a",
              "boundary_type": "TIME_LIMIT", "statement": "s",
              "evidence_ids": ["ev_a"], "extractor_version": "v",
              "confidence": 1.0, "boundary_hash": "h",
              "status": "GENERATED", "created_at": "v"})])
    assert sink.conditions == {} and sink.boundaries == {}
    assert sink.rollbacks == 1


# ── the authorisation gate for 077 ───────────────────────────────────────────

def test_architecture_tests_authorise_077(run):
    """§10 — 077 is applied only after this suite is green. Asserted here as
    a single gate so the ordering is a fact, not a habit."""
    gates = gate_results(run)
    assert upstream_untouched_gate() == "PASS"
    assert vocabulary_gate() == "PASS"
    assert column_parity_gate() == "PASS"
    assert gates["GATE_A_frozen_ku_immutable"] == "PASS"
    assert gates["GATE_C_isolation"] == "PASS"


def test_the_committed_artifact_matches_a_fresh_run():
    path = ARTIFACTS / "p5_0_condition_boundary.json"
    assert path.exists(), "run condition_boundary_runner to emit the artifact"
    committed = json.loads(path.read_text(encoding="utf-8"))
    fresh = report(run_extraction())
    for key in ("condition_candidates", "boundary_candidates",
                "condition_types", "boundary_types",
                "units_considered", "units_with_a_condition",
                "extractor_version"):
        assert committed[key] == fresh[key], key
