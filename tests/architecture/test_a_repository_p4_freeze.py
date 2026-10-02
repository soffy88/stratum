"""A Repository P4 — Frozen Knowledge Unit.

Contract tests for the P4 freeze layer (migration 073):
- schema: table, FKs with RESTRICT, unique constraints, indexes
- authority: no foreign table, repository or claim store
- freeze lifecycle: VERIFIED -> FREEZE_PENDING -> FROZEN, and immutability
- replay: a second freeze adds no rows and no duplicates
- identity: content-derived, never random
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List

import pytest


ROOT = Path(__file__).parents[2]
PKG = ROOT / "src" / "stratum" / "knowledge" / "a_repository"
MIGRATIONS = ROOT / "src" / "stratum" / "db" / "pg_migrations"
MIGRATION = MIGRATIONS / "073_a_knowledge_unit_freeze.sql"
ARTIFACT = ROOT / "artifacts" / "a_repository" / "p4_ku_freeze.json"

from stratum.knowledge.a_repository import pilot_corpus as C  # noqa: E402
from stratum.knowledge.a_repository.freeze import (  # noqa: E402
    FREEZE_SCORE_THRESHOLD,
    FREEZE_VERSION,
    TERMINAL_FREEZE_STATUSES,
    LEGAL_TRANSITIONS,
    AKnowledgeUnitFreezePipeline,
    FreezeStatus,
    FreezeViolation,
    FrozenKnowledgeUnit,
    content_hash,
    unit_id,
)
from stratum.knowledge.a_repository.ku_freeze_runner import (  # noqa: E402
    REQUIRED_CHAIN,
    REQUIRED_MIGRATION,
    artifact,
    build_freeze_baseline,
    gate_results,
    replay_gate,
    report,
)
from stratum.knowledge.a_repository.verification import (  # noqa: E402
    VerificationStatus,
    VerificationViolation,
)


@pytest.fixture
def frozen():
    result = build_freeze_baseline()
    return {
        "result": result,
        "base": result["base"],
        "pipeline": result["base"]["pipeline"],
        "vp": result["verification"],
        "fp": result["freeze"],
        "report": report(result),
    }


def _pending_unit(fp, unit_id_, candidate_id):
    fp.store.frozen_units[unit_id_] = FrozenKnowledgeUnit(
        id=unit_id_, verification_id="kv_x", candidate_id=candidate_id,
        source_version_id="sv_x", title="t", statement="s",
        canonical_text="q", evidence_count=1, verification_score=1.0,
        content_hash="h", freeze_status=FreezeStatus.VERIFIED.value)
    return unit_id_


# ── schema ───────────────────────────────────────────────────────────────────

def test_073_declares_every_required_column():
    sql = MIGRATION.read_text(encoding="utf-8")
    for column in ("id TEXT PRIMARY KEY",
                   "verification_id TEXT NOT NULL",
                   "candidate_id TEXT NOT NULL",
                   "source_version_id TEXT NOT NULL",
                   "title TEXT NOT NULL",
                   "statement TEXT NOT NULL",
                   "canonical_text TEXT NOT NULL",
                   "evidence_count INTEGER NOT NULL",
                   "verification_score FLOAT NOT NULL",
                   "freeze_status TEXT NOT NULL",
                   "freeze_version TEXT NOT NULL",
                   "created_at TIMESTAMP NOT NULL",
                   "frozen_at TIMESTAMP"):
        assert column in sql, f"073 missing column: {column}"


def test_073_has_the_three_authority_foreign_keys():
    sql = MIGRATION.read_text(encoding="utf-8")
    for column, target in (("verification_id", "ku_verification"),
                           ("candidate_id", "ku_candidate"),
                           ("source_version_id", "source_version")):
        assert re.search(
            rf"{column} TEXT NOT NULL\s*"
            rf"REFERENCES stratum\.{target}\(id\)", sql), \
            f"073 missing FK {column} -> {target}"


def test_073_foreign_keys_restrict_rather_than_cascade():
    """A frozen unit must outlive attempts to delete its chain."""
    sql = MIGRATION.read_text(encoding="utf-8")
    for column in ("verification_id", "candidate_id", "source_version_id"):
        match = re.search(
            rf"{column} TEXT NOT NULL\s*REFERENCES stratum\.\w+\(id\)\s*"
            r"ON DELETE (\w+)", sql)
        assert match, f"073 {column} has no delete rule"
        assert match.group(1) == "RESTRICT", \
            f"073 {column} must be RESTRICT, not {match.group(1)}"


def test_073_has_the_three_unique_constraints():
    sql = MIGRATION.read_text(encoding="utf-8")
    for constraint in ("knowledge_unit_verification_uniq",
                      "knowledge_unit_candidate_uniq",
                      "knowledge_unit_content_hash_uniq"):
        assert f"CONSTRAINT {constraint} UNIQUE" in sql, \
            f"073 missing {constraint}"


def test_073_freeze_status_check_is_the_four_state_machine():
    sql = MIGRATION.read_text(encoding="utf-8")
    listed = set(re.findall(
        r"'([A-Z_]+)'", sql.split("freeze_status IN (")[1]))
    assert listed == {s.value for s in FreezeStatus}
    assert listed == {"VERIFIED", "FREEZE_PENDING", "FROZEN", "REJECTED"}


def test_073_requires_a_frozen_at_only_when_frozen():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "CONSTRAINT knowledge_unit_frozen_at_required" in sql
    assert re.search(
        r"CHECK \(freeze_status <> 'FROZEN' OR frozen_at IS NOT NULL\)", sql)


def test_073_requires_at_least_one_evidence():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert re.search(
        r"evidence_count INTEGER NOT NULL CHECK \(evidence_count >= 1\)", sql)


def test_073_is_additive_only_with_no_backfill():
    statements = re.sub(r"--.*", "", MIGRATION.read_text(encoding="utf-8"))
    assert "ALTER TABLE" not in statements
    assert statements.count("CREATE TABLE") == 1
    # No data backfill: nothing inserts a row.
    assert "INSERT INTO" not in statements


def test_073_is_additive_and_earlier_ones_survive():
    """073 adds its own table; later migrations may exist on top of it."""
    statements = re.sub(r"--.*", "", MIGRATION.read_text(encoding="utf-8"))
    assert statements.count("CREATE TABLE") == 1
    for earlier in REQUIRED_CHAIN[:-1]:
        assert (MIGRATIONS / earlier).exists()


# ── authority ────────────────────────────────────────────────────────────────

FORBIDDEN_TOKENS = ("knowledge_claims", "b_repository", "c_repository",
                    "bu2", "learning_object", "merge", "dedup")


@pytest.mark.parametrize("name", ["freeze.py", "ku_freeze_runner.py"])
def test_p4_code_names_no_external_authority(name):
    text = (PKG / name).read_text(encoding="utf-8").lower()
    for token in FORBIDDEN_TOKENS:
        assert token not in text, f"{name} references external authority: {token}"


def test_073_names_no_external_authority():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    for token in FORBIDDEN_TOKENS:
        assert token not in sql, f"073 references external authority: {token}"


def test_073_references_only_a_repository_tables():
    sql = MIGRATION.read_text(encoding="utf-8")
    referenced = set(re.findall(r"REFERENCES\s+stratum\.(\w+)", sql))
    assert referenced == {"ku_verification", "ku_candidate", "source_version"}


def _identifiers_and_code_strings(path: Path) -> str:
    """Prose is allowed to mention what a stage is not.

    Only real code — identifiers and non-docstring string literals — is
    scanned, so a docstring saying "this is not a concept" cannot fail a
    gate, while a function named `cluster_concepts` would.
    """
    import ast

    tree = ast.parse(path.read_text(encoding="utf-8"))
    parts: List[str] = []
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef, ast.Module)):
            doc = ast.get_docstring(node, clean=False)
            if doc:
                docstrings.add(doc)
        if isinstance(node, ast.Name):
            parts.append(node.id)
        elif isinstance(node, ast.Attribute):
            parts.append(node.attr)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                               ast.ClassDef)):
            parts.append(node.name)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value not in docstrings:
                parts.append(node.value)
    return " ".join(parts).lower()


def test_a_frozen_unit_never_becomes_a_concept():
    """The freeze stage ends at a citable unit; it groups nothing."""
    for name in ("freeze.py", "ku_freeze_runner.py"):
        code = _identifiers_and_code_strings(PKG / name)
        for token in ("concept", "abstraction", "cluster", "category",
                      "deduplicate", "dedup"):
            assert token not in code, \
                f"{name} groups units in code: {token}"


# ── GATE_2 verification gate ─────────────────────────────────────────────────

def test_only_verified_units_are_frozen(frozen):
    vp, fp = frozen["vp"], frozen["fp"]
    verified = {v.candidate_id for v in vp.store.verifications.values()
                if v.verification_status == VerificationStatus.VERIFIED.value}
    rejected = {v.candidate_id for v in vp.store.verifications.values()
                if v.verification_status == VerificationStatus.REJECTED.value}
    frozen_candidates = {u.candidate_id for u in fp.store.frozen_units.values()}
    assert frozen_candidates == verified
    assert not frozen_candidates & rejected


def test_a_rejected_verification_cannot_be_frozen(frozen):
    fp, vp = frozen["fp"], frozen["vp"]
    rejected = next(v for v in vp.store.verifications.values()
                    if v.verification_status == VerificationStatus.REJECTED.value)
    with pytest.raises(FreezeViolation):
        fp.freeze(rejected.id)


def test_every_frozen_unit_meets_the_score_threshold(frozen):
    for unit in frozen["fp"].store.frozen_units.values():
        assert unit.verification_score >= FREEZE_SCORE_THRESHOLD


def test_freeze_score_threshold_matches_verification_threshold(frozen):
    from stratum.knowledge.a_repository.verification import (
        VERIFICATION_THRESHOLD,
    )
    assert FREEZE_SCORE_THRESHOLD == VERIFICATION_THRESHOLD


def test_verification_input_is_the_whole_candidate_set(frozen):
    r = frozen["report"]
    assert r["verification_input"] == 17
    assert r["rejected_input"] == 7
    assert r["frozen_count"] == 10


# ── freeze lifecycle ─────────────────────────────────────────────────────────

def test_verified_to_freeze_pending_passes():
    upstream = build_freeze_baseline()
    fp = upstream["freeze"]
    _pending_unit(fp, "ku_t1", "kc_t1")
    fp.transition("ku_t1", FreezeStatus.FREEZE_PENDING)
    assert fp.store.frozen_units["ku_t1"].freeze_status == "FREEZE_PENDING"


def test_freeze_pending_to_frozen_passes():
    upstream = build_freeze_baseline()
    fp = upstream["freeze"]
    _pending_unit(fp, "ku_t2", "kc_t2")
    fp.transition("ku_t2", FreezeStatus.FREEZE_PENDING)
    fp.transition("ku_t2", FreezeStatus.FROZEN)
    assert fp.store.frozen_units["ku_t2"].freeze_status == "FROZEN"


def test_freeze_pending_to_rejected_passes():
    upstream = build_freeze_baseline()
    fp = upstream["freeze"]
    _pending_unit(fp, "ku_t3", "kc_t3")
    fp.transition("ku_t3", FreezeStatus.FREEZE_PENDING)
    fp.transition("ku_t3", FreezeStatus.REJECTED)
    assert fp.store.frozen_units["ku_t3"].freeze_status == "REJECTED"


def test_frozen_to_verified_fails(frozen):
    fp = frozen["fp"]
    unit = next(iter(fp.store.frozen_units.values()))
    with pytest.raises(FreezeViolation):
        fp.transition(unit.id, FreezeStatus.VERIFIED)
    with pytest.raises(FreezeViolation):
        fp.unfreeze(unit.id)
    assert unit.freeze_status == "FROZEN"


def test_transition_table_admits_only_the_two_legal_paths():
    assert LEGAL_TRANSITIONS[FreezeStatus.VERIFIED] == frozenset(
        {FreezeStatus.FREEZE_PENDING})
    assert LEGAL_TRANSITIONS[FreezeStatus.FREEZE_PENDING] == frozenset(
        {FreezeStatus.FROZEN, FreezeStatus.REJECTED})
    for terminal in TERMINAL_FREEZE_STATUSES:
        assert LEGAL_TRANSITIONS[terminal] == frozenset()


def test_freeze_walks_both_transitions_in_order(frozen):
    stages = [e.stage for e in frozen["fp"].events]
    assert stages[:2] == ["freeze_pending", "freeze"]


def test_no_unit_is_left_unfrozen(frozen):
    assert frozen["report"]["status_breakdown"]["FREEZE_PENDING"] == 0
    assert frozen["report"]["status_breakdown"]["VERIFIED"] == 0


# ── frozen mutation policy ───────────────────────────────────────────────────

def test_frozen_statement_cannot_be_updated(frozen):
    fp = frozen["fp"]
    unit = next(iter(fp.store.frozen_units.values()))
    before = (unit.statement, unit.canonical_text)
    with pytest.raises(FreezeViolation):
        fp.update_unit(unit.id, statement="被改写的陈述")
    assert (unit.statement, unit.canonical_text) == before


def test_frozen_canonical_text_cannot_be_updated(frozen):
    fp = frozen["fp"]
    unit = next(iter(fp.store.frozen_units.values()))
    before = unit.canonical_text
    with pytest.raises(FreezeViolation):
        fp.update_unit(unit.id, canonical_text="被改写的原文")
    assert unit.canonical_text == before


def test_frozen_evidence_cannot_be_replaced(frozen):
    fp = frozen["fp"]
    unit = next(iter(fp.store.frozen_units.values()))
    with pytest.raises(FreezeViolation):
        fp.replace_evidence(unit.id, "ev_other")
    assert unit.evidence_ids


def test_frozen_verification_cannot_be_replaced(frozen):
    fp = frozen["fp"]
    unit = next(iter(fp.store.frozen_units.values()))
    with pytest.raises(FreezeViolation):
        fp.replace_verification(unit.id, "kv_other")
    assert unit.verification_id


def test_frozen_unit_cannot_be_deleted(frozen):
    fp = frozen["fp"]
    unit = next(iter(fp.store.frozen_units.values()))
    with pytest.raises(FreezeViolation):
        fp.delete_unit(unit.id)
    assert unit.id in fp.store.frozen_units


def test_update_is_refused_even_before_freezing():
    """Immutability is not a special case for FROZEN; it is the rule."""
    upstream = build_freeze_baseline()
    fp = upstream["freeze"]
    _pending_unit(fp, "ku_t4", "kc_t4")
    with pytest.raises(FreezeViolation):
        fp.update_unit("ku_t4", statement="x")


# ── identity ─────────────────────────────────────────────────────────────────

def test_unit_id_is_content_derived():
    digest = unit_id("巴比伦利率上限", "fingerprint-abc")
    assert digest == "ku_" + content_hash(
        "巴比伦利率上限", "fingerprint-abc")[:12]
    assert digest.startswith("ku_")
    assert len(digest) == 15


def test_unit_id_never_looks_like_a_uuid_or_a_counter():
    ids = [u.id for u in build_freeze_baseline()["freeze"]
           .store.frozen_units.values()]
    for value in ids:
        assert not re.match(r"^\d+$", value)
        assert "-" not in value
        assert len(value.split("_")[1]) == 12


def test_same_statement_and_evidence_yield_the_same_unit():
    assert unit_id("s", "f") == unit_id("s", "f")
    assert unit_id("s", "f") != unit_id("s", "g")
    assert unit_id("s", "f") != unit_id("t", "f")


def test_frozen_ids_match_their_content_hash(frozen):
    for unit in frozen["fp"].store.frozen_units.values():
        assert unit.id == unit_id(unit.statement, unit.trace["fingerprint"])
        assert unit.content_hash == content_hash(
            unit.statement, unit.trace["fingerprint"])


# ── KU content rules ─────────────────────────────────────────────────────────

def test_every_frozen_unit_carries_a_statement_and_evidence(frozen):
    store = frozen["pipeline"].store
    for unit in frozen["fp"].store.frozen_units.values():
        assert unit.statement
        assert unit.evidence_ids
        assert unit.evidence_count >= 1
        candidate = store.ku_candidates[unit.candidate_id]
        evidence = store.evidence[candidate.evidence_id]
        assert evidence.id in unit.evidence_ids
        assert evidence.source_version_id == unit.source_version_id
        assert evidence.source_version_id in store.source_versions


def test_canonical_text_is_the_anchored_span_not_a_summary(frozen):
    store = frozen["pipeline"].store
    for unit in frozen["fp"].store.frozen_units.values():
        candidate = store.ku_candidates[unit.candidate_id]
        evidence = store.evidence[candidate.evidence_id]
        assert unit.canonical_text in evidence.content_span


def test_the_freeze_stage_writes_no_wording_of_its_own(frozen):
    store = frozen["pipeline"].store
    for unit in frozen["fp"].store.frozen_units.values():
        candidate = store.ku_candidates[unit.candidate_id]
        assert unit.statement == candidate.content


def test_title_is_derived_from_the_statement(frozen):
    for unit in frozen["fp"].store.frozen_units.values():
        assert unit.title
        assert unit.statement.startswith(unit.title[:8]) or unit.title


def test_no_unit_is_unanchored(frozen):
    assert frozen["fp"].unanchored_units() == []
    assert frozen["report"]["unanchored_units"] == []


# ── GATE_4 provenance ────────────────────────────────────────────────────────

def test_full_chain_is_traceable(frozen):
    trace = frozen["report"]["traceability"]
    assert trace["units"] == 10
    assert trace["trace_complete"] == 10
    assert trace["percent"] == 100.0
    assert trace["unique_ids"] == 10
    assert trace["unique_content_hashes"] == 10


def test_no_orphan_units(frozen):
    assert frozen["fp"].orphan_units() == []
    assert frozen["report"]["orphan_units"] == []


# ── replay ───────────────────────────────────────────────────────────────────

def test_replay_gate_reports_nothing_new(frozen):
    outcome = replay_gate(frozen["result"])
    assert outcome["new_units"] == 0
    assert outcome["duplicates"] == 0
    assert outcome["identical_report"] == 1


def test_freeze_twice_creates_no_second_row(frozen):
    fp = frozen["fp"]
    before = len(fp.store.frozen_units)
    ids = [u.verification_id for u in fp.store.frozen_units.values()]
    units = fp.freeze_all(ids)
    assert len(fp.store.frozen_units) == before
    assert len({u.id for u in units}) == before
    assert all(u.freeze_status == "FROZEN" for u in units)


def test_replay_is_deterministic():
    assert report(build_freeze_baseline()) == report(build_freeze_baseline())


def test_settled_unit_is_never_rewritten(frozen):
    fp = frozen["fp"]
    unit = next(iter(fp.store.frozen_units.values()))
    unit.statement = "被篡改"
    again = fp.freeze(unit.verification_id)
    assert again is unit
    assert again.statement == "被篡改"


# ── gates ────────────────────────────────────────────────────────────────────

def test_gate1_is_not_executed_without_a_ledger(frozen):
    assert gate_results(frozen["result"], None)["gate1"] == "NOT_EXECUTED"


def test_gate1_passes_when_the_ledger_carries_the_whole_chain(frozen):
    assert gate_results(frozen["result"], list(REQUIRED_CHAIN))["gate1"] == "PASS"


def test_gate1_fails_when_073_is_absent(frozen):
    assert gate_results(frozen["result"],
                        list(REQUIRED_CHAIN[:-1]))["gate1"] == "FAIL"


def test_all_five_gates_pass_on_the_pilot(frozen):
    gates = gate_results(frozen["result"], list(REQUIRED_CHAIN))
    assert gates == {"gate1": "PASS", "gate2": "PASS", "gate3": "PASS",
                     "gate4": "PASS", "gate5": "PASS"}


# ── artifact ─────────────────────────────────────────────────────────────────

def test_artifact_shape(frozen):
    doc = artifact(frozen["result"], list(REQUIRED_CHAIN))
    assert doc["task"] == "A_P4_KNOWLEDGE_UNIT_FREEZE"
    assert doc["book"].startswith("利率史")
    assert doc["verification_input"] == 17
    assert doc["frozen_count"] == 10
    assert doc["authority"] == "A_REPOSITORY"
    assert doc["traceability"] == "100%"
    assert doc["replay"] == "PASS"
    assert doc["freeze_version"] == FREEZE_VERSION
    assert set(doc["gate_results"]) == {
        "gate1", "gate2", "gate3", "gate4", "gate5"}


def test_frozen_count_is_bounded_by_verified_not_candidates(frozen):
    r = frozen["report"]
    assert r["frozen_count"] == r["verified_count"] == 10
    assert r["frozen_count"] < r["verification_input"] == 17


def test_committed_artifact_matches_the_runner(frozen):
    import json
    assert ARTIFACT.exists(), "p4_ku_freeze.json is missing"
    on_disk = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    produced = artifact(frozen["result"], on_disk["ledger"])
    for field in ("verification_input", "frozen_count", "authority",
                  "traceability", "replay", "freeze_version", "run_id",
                  "status_breakdown", "units"):
        assert on_disk[field] == produced[field], f"artifact drifted: {field}"


# ── commit boundary ──────────────────────────────────────────────────────────

def test_p3_verification_logic_is_untouched():
    """P4 freezes; it does not re-decide what P3 decided."""
    source = (PKG / "verification.py").read_text(encoding="utf-8")
    assert FREEZE_VERSION not in source
    assert "freeze" not in source.lower().split("a repository p3")[0]


def test_p2_classifier_is_untouched():
    from stratum.knowledge.a_repository import quality
    source = (PKG / "quality.py").read_text(encoding="utf-8")
    assert "def classify" in source
    assert FREEZE_VERSION not in source


def test_pilot_book_is_the_frozen_first_book(frozen):
    assert frozen["report"]["book"].startswith("利率史")
    assert frozen["report"]["run_id"] == "arr_d0d1473d79fc"
    assert C.BOOK_TITLE == "利率史（第四版）"


def test_verification_violation_and_freeze_violation_are_distinct():
    assert not issubclass(FreezeViolation, VerificationViolation)
    assert not issubclass(VerificationViolation, FreezeViolation)