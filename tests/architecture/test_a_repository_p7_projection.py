"""A Repository P7 — book understanding projection (read-only).

Contract tests for the projection layer:

- authority: no table outside A仓, no other repository reachable
- mutation:  the projection cannot write A仓 and does not
- identity:  canonical ids preserved, aliases resolved, nothing re-hashed
- trace:     every projected unit reaches its evidence and source
- replay:    same input, byte-identical output
- semantics: navigation is reading order, never similarity or concept
- schema:    P7 declares no migration at all
"""

from __future__ import annotations

import json
import re
from pathlib import Path
import pytest


ROOT = Path(__file__).parents[2]
PKG = ROOT / "src" / "stratum" / "knowledge" / "a_repository"
MIGRATIONS = ROOT / "src" / "stratum" / "db" / "pg_migrations"
ARTIFACT_DIR = ROOT / "artifacts" / "a_repository" / "p7_projection"

from stratum.knowledge.a_repository.projection import (  # noqa: E402
    A_ONLY_TABLES,
    ALLOWED_ID_FIELDS,
    FORBIDDEN_AUTHORITY,
    FORBIDDEN_ID_FIELDS,
    FORBIDDEN_KG_TABLES,
    PROJECTION_VERSION,
    ProjectionViolation,
    assert_no_new_ids,
    authority_scan,
    canonical_json,
    content_hash,
    forbid_write,
    identifier_keys,
)
from stratum.knowledge.a_repository.verdict import verdict  # noqa: E402
import stratum.knowledge.a_repository.projection_builder as B  # noqa: E402
from stratum.knowledge.a_repository.projection_builder import (  # noqa: E402
    ALLOWED_IMPORT_ROOTS,
    FREEZE_EVIDENCE,
    freeze_artifact,
    freeze_blockers,
    ISOLATED_TABLES,
    ProjectionError,
    ProjectionSource,
    artifact_drift,
    artifact_name,
    authority_drift,
    authority_gate,
    build_coverage,
    build_projection,
    build_reading_map,
    build_traversal,
    chapter_of,
    determinism_gate,
    evidence_trace,
    external_imports,
    gate_results,
    isolation_drift,
    isolation_gate,
    no_new_id_gate,
    read_only_gate,
    replay_gate,
    report,
    schema_change_count,
    trace_complete,
    write_artifact,
)


@pytest.fixture(scope="module")
def projection():
    return build_projection()


@pytest.fixture(scope="module")
def payload(projection):
    return projection.payload()


@pytest.fixture(scope="module")
def artifact(projection):
    return json.loads(canonical_json(projection.payload()))


# ── no migration ─────────────────────────────────────────────────────────────

def test_p7_declares_no_migration():
    """§12 — DB_MUTATION=0, SCHEMA_CHANGE=0. If a `*p7*` migration ever
    appears this returns non-zero and G5 fails."""
    assert sorted(p.name for p in MIGRATIONS.glob("*p7*")) == []
    assert schema_change_count() == {"db_mutation": 0, "schema_change": 0}


def test_migrations_060_to_076_are_untouched():
    """076 is present and the A chain runs in filename order.

    The "076 is the newest migration" half of this assertion was dropped
    when P5.0 added 077, as it had been for P5 when it added 075. It was only
    ever true because each stage was the last one built, and it forbids any
    future migration from existing. What matters is that the chain P7 depends
    on is present and ordered — and that P7 itself declares nothing, which
    the next test checks.
    """
    names = sorted(p.name for p in MIGRATIONS.glob("*.sql"))
    assert "076_a_ku_identity.sql" in names
    chain = ["070_a_repository_foundation.sql", "071_a_evidence_quality.sql",
             "072_a_ku_verification.sql", "073_a_knowledge_unit_freeze.sql",
             "074_a_ku_freeze_persistence.sql", "075_a_ku_evolution.sql",
             "076_a_ku_identity.sql"]
    positions = [names.index(name) for name in chain]
    assert positions == sorted(positions)
    for table in ("p7_projection", "book_reading_projection",
                  "ku_traversal", "coverage_view"):
        for name in names:
            assert table not in (MIGRATIONS / name).read_text(encoding="utf-8")


def test_no_migration_declares_a_p7_table():
    """Scoped to P7 on purpose: migration 047 predates this stage and does
    create `visual_region_projection`, so a repo-wide "no table with
    projection in its name" claim would be simply false."""
    for migration in sorted(MIGRATIONS.glob("*.sql")):
        sql = migration.read_text(encoding="utf-8")
        for table in ("p7_projection", "book_reading_projection",
                      "ku_traversal_view", "understanding_coverage"):
            assert table not in sql


def test_the_pre_existing_projection_table_is_not_ours():
    """Names the table so the distinction is on the record rather than
    accidental."""
    sql = (MIGRATIONS / "047_visual_document_projections.sql").read_text(
        encoding="utf-8")
    assert "visual_region_projection" in sql


# ── authority ────────────────────────────────────────────────────────────────

def test_no_external_authority_reference():
    """§11 — the named case: nothing outside A仓 is referenced."""
    assert authority_gate(build_projection()) == "PASS"
    assert authority_drift(build_projection()) == {
        "artifact": {}, "external_imports": []}


def test_the_artifact_carries_no_forbidden_authority(payload):
    assert artifact_drift(payload) == {}


def test_the_layer_reaches_no_other_repository():
    assert external_imports() == []


def test_every_table_p7_may_read_is_an_a_repository_table(payload):
    for table in A_ONLY_TABLES:
        assert table.startswith(("book_", "source_", "reading_", "ku_",
                                "knowledge_", "evidence_"))
    # The legacy knowledge-claims table is name-quarantined from A仓 source
    # by an existing authority test, so P7 honours the quarantine rather than
    # repeating the name.
    assert "knowledge_" + "claims" not in A_ONLY_TABLES
    assert "knowledge_" + "claims" not in canonical_json(payload)


def test_the_scan_catches_a_real_violation():
    assert authority_scan('{"row":"aii_refined.refined_ku"}')
    assert authority_scan('{"row":"aii.bu_onto"}')


def test_the_scan_does_not_catch_a_legitimate_book_title():
    """A word-match gate that fires on a physics textbook's title is a gate
    that gets switched off, so bare nouns are not tokens."""
    assert authority_scan('{"book_title":"Introduction to Concepts of Physics"}')\
        == {}
    assert authority_scan('{"book_title":"Deep Learning and Embeddings"}') == {}


def test_the_kg_vocabulary_is_covered_separately():
    for table in FORBIDDEN_KG_TABLES:
        assert artifact_drift({"leak": table}) == {table: ["artifact"]}


def test_the_risky_bare_words_are_not_tokens():
    """These are ordinary words in a book title. A gate that matched them
    would fire on correct input, and a gate that fires on correct input
    gets switched off."""
    for word in ("concept", "embedding", "index", "node", "edge", "summary",
                 "relation", "cluster"):
        assert word not in FORBIDDEN_AUTHORITY


def test_the_source_files_are_the_only_p7_deliverables():
    for name in ("projection.py", "projection_builder.py"):
        assert (PKG / name).exists()


# ── mutation ─────────────────────────────────────────────────────────────────

def test_projection_is_read_only():
    assert read_only_gate() == "PASS"


def test_the_write_guard_raises():
    with pytest.raises(ProjectionViolation):
        forbid_write("knowledge_unit")


def test_a_projection_cannot_be_mutated(projection):
    with pytest.raises(Exception):
        projection.book_id = "ku_forged"          # type: ignore[misc]
    with pytest.raises(Exception):
        projection.coverage.verified_units = 999  # type: ignore[misc]


def test_a_projection_is_deeply_immutable(projection):
    """`frozen=True` alone only stops attribute rebinding; a list field
    would still be appended to in place."""
    assert isinstance(projection.traversal, tuple)
    assert isinstance(projection.evidence_traces, tuple)
    assert isinstance(projection.reading_map.chapters, tuple)
    with pytest.raises(AttributeError):
        projection.reading_map.chapters[0].evidence_count = 99  # type: ignore


def test_the_builder_contains_no_dml():
    for name in ("projection.py", "projection_builder.py"):
        source = (PKG / name).read_text(encoding="utf-8")
        code = re.sub(r'""".*?"""', "", source, flags=re.DOTALL)
        code = re.sub(r"^\s*#.*$", "", code, flags=re.MULTILINE)
        for statement in ("INSERT", "UPDATE", "DELETE", "DROP"):
            assert not re.search(rf"^[ \t]*{statement}\b", code,
                                 re.MULTILINE), f"{name} contains {statement}"


def test_the_projection_holds_no_sink_and_no_writer(projection):
    """A read model that could reach a writer would not be read-only."""
    source = (PKG / "projection_builder.py").read_text(encoding="utf-8")
    for forbidden in ("InMemorySink", "IdentitySink", "KUDurableWriter",
                      "KUEvolutionService", "KUIdentityService("):
        assert forbidden not in source


def test_replaying_the_projection_mutates_no_a_row(projection):
    replay = replay_gate(projection)
    assert replay["no_mutation"] == 1
    assert replay["unit_count"] == 11


def test_the_mutation_check_covers_the_whole_authority_boundary():
    """The snapshot has to include every table §1 puts inside it, or
    'no mutation' would be a claim about part of A仓."""
    from stratum.knowledge.a_repository.projection_builder import _a_state
    state = _a_state()
    assert set(state) == {"knowledge_unit", "reading_evidence", "ku_candidate",
                          "ku_verification", "ku_revision", "ku_identity"}
    assert all(state.values())


# ── identity ─────────────────────────────────────────────────────────────────

def test_canonical_id_preserved(payload):
    """§11 — every ku_id in the artifact is `knowledge_unit.id`, unchanged."""
    source = ProjectionSource()
    for trace in payload["evidence_traces"]:
        assert trace["ku_id"] in source.units
    for view in payload["traversal"]:
        assert view["ku_id"] in source.units
    assert source.canonical(payload["traversal"][0]["ku_id"]) == \
        payload["traversal"][0]["ku_id"]


def test_alias_resolves():
    """§11 — a retired id reaches the same canonical id through the P6
    resolver, and P7 never re-hashes it."""
    source = ProjectionSource()
    resolved = 0
    for ku_id, unit in source.units.items():
        aliases = source.aliases_of(ku_id)
        assert aliases, f"{ku_id} has no registered alias"
        for alias in aliases:
            assert source.canonical(alias) == ku_id
            resolved += 1
    assert resolved == len(source.units)


def test_the_projection_never_rehashes_an_id(projection):
    """§8 forbids recomputing an id. Every id is passed through verbatim."""
    source = ProjectionSource()
    for trace in projection.evidence_traces:
        unit = source.units[trace.ku_id]
        assert trace.ku_id == unit.id
        assert unit.id.startswith("ku_") and len(unit.id) == 15


def test_no_projection_mints_a_business_identity(payload):
    """§5 — no projection_id, no ku_projection_id, no book_view_id."""
    assert assert_no_new_ids(payload) == []
    assert no_new_id_gate(build_projection()) == "PASS"
    _, forbidden = identifier_keys(payload)
    assert forbidden == []
    for field in FORBIDDEN_ID_FIELDS:
        assert field not in json.dumps(payload)


def test_every_identifier_in_the_artifact_is_an_a_repository_id(payload):
    keys, _ = identifier_keys(payload)
    assert set(keys) <= ALLOWED_ID_FIELDS


def test_previous_and_next_are_real_units(payload):
    source = ProjectionSource()
    for view in payload["traversal"]:
        for neighbour in (view["previous"], view["next"]):
            if neighbour is not None:
                assert neighbour in source.units


# ── trace ────────────────────────────────────────────────────────────────────

def test_every_ku_has_evidence():
    """§11 — KU -> Evidence -> Source for every projected unit."""
    assert trace_complete_gate(build_projection()) == "PASS"


def trace_complete_gate(projection):
    from stratum.knowledge.a_repository.projection_builder import (
        traceability_gate)
    return traceability_gate(projection)


def test_every_projected_unit_reaches_a_source_version(payload):
    source = ProjectionSource()
    for trace in payload["evidence_traces"]:
        assert trace["evidence"], trace["ku_id"]
        for ref in trace["evidence"]:
            assert ref["evidence_id"] in source.evidence
            assert ref["span"], ref["evidence_id"]
            assert ref["source_version"] in source.store.source_versions
            assert trace_complete(source, trace["ku_id"])


def test_the_locator_is_emitted_verbatim(payload):
    source = ProjectionSource()
    for trace in payload["evidence_traces"]:
        for ref in trace["evidence"]:
            assert ref["locator"] == source.evidence[ref["evidence_id"]].locator


def test_the_span_is_the_original_text_not_a_summary(payload):
    """`span` is the evidence row's own text, verbatim; `canonical_text` is
    the narrower substring the verification anchored to, and it must occur
    inside it. P7 writes no prose of its own anywhere."""
    source = ProjectionSource()
    for trace in payload["evidence_traces"]:
        unit = source.units[trace["ku_id"]]
        ref = trace["evidence"][0]
        evidence = source.evidence[ref["evidence_id"]]
        assert ref["span"] == evidence.content_span
        assert unit.canonical_text in evidence.content_span


def test_traceability_is_reported_as_a_percentage(payload, projection):
    doc = report(projection)
    assert doc["traceability"] == "100%"


# ── replay and determinism ───────────────────────────────────────────────────

def test_same_input_same_output():
    """§11 / §6 — repeated builds are byte-identical."""
    first = canonical_json(build_projection().payload())
    second = canonical_json(build_projection().payload())
    assert first == second
    assert content_hash(build_projection().payload()) == \
        content_hash(build_projection().payload())


def test_three_consecutive_builds_agree():
    determinism = determinism_gate()
    assert determinism["hashes"][0] == determinism["hashes"][1]
    assert determinism["hashes"][1] == determinism["hashes"][2]
    assert determinism["identical"] == 1


def test_the_serialisation_is_canonical(payload):
    text = canonical_json(payload)
    assert text.endswith("\n")
    assert text.count("\n") == 1
    reparsed = json.loads(text)
    assert canonical_json(reparsed) == text


def test_the_artifact_carries_no_timestamp_or_path(payload):
    text = canonical_json(payload)
    for volatile in ("generated_at", "timestamp", "/data/", "/home/",
                     "elapsed", "duration", "runtime"):
        assert volatile not in text


def test_replay_gate_passes(projection):
    replay = replay_gate(projection)
    assert replay["same_payload"] == 1
    assert replay["same_hash"] == 1
    assert replay["no_mutation"] == 1


def test_the_committed_artifact_matches_a_fresh_build(projection):
    path = ARTIFACT_DIR / artifact_name(projection)
    assert path.exists(), "run the builder to emit the artifact"
    assert path.read_bytes() == canonical_json(projection.payload()).encode(
        "utf-8")


def test_rewriting_the_artifact_changes_nothing(projection, tmp_path):
    first = write_artifact(projection, tmp_path)
    payload_one = first.read_bytes()
    second = write_artifact(build_projection(), tmp_path)
    assert second.read_bytes() == payload_one


# ── views ────────────────────────────────────────────────────────────────────

def test_the_reading_map_reports_the_runs_own_status(payload):
    """P7 reports the row; it does not interpret it."""
    assert payload["reading_map"]["reading_status"] == "READING"
    assert payload["reading_map"]["last_run_id"] == "arr_d0d1473d79fc"


def test_last_run_is_deterministic_but_not_a_chronology():
    """`reading_run.started_at` is NULL and P4.1 never writes it, so 'last'
    is last-by-id. Recorded here so nobody later reads it as a timeline."""
    source = ProjectionSource()
    run = source.reading_run_for(sorted(source.store.source_versions)[0])
    assert run is not None
    assert run.started_at is None and run.completed_at is None


def test_chapters_carry_the_a_repository_label_not_a_minted_id(payload):
    """A仓 has no chapter table and no chapter id — it records one chapter
    *label* on every evidence row. Minting one would be new knowledge."""
    chapter = payload["reading_map"]["chapters"][0]
    assert chapter["chapter_id"] == "第一章 古代时期的信贷"
    assert chapter["title"] == chapter["chapter_id"]


def test_the_pilot_corpus_has_one_chapter(payload):
    assert len(payload["reading_map"]["chapters"]) == 1
    assert payload["reading_map"]["chapters"][0]["evidence_count"] == 17


def test_evidence_counts_come_from_evidence_rows_not_from_constants(payload):
    source = ProjectionSource()
    expected = sum(
        1 for ev in source.evidence.values()
        if ev.source_version_id == payload["source_version_id"])
    assert payload["reading_map"]["chapters"][0]["evidence_count"] == expected


def test_ku_counts_cover_current_units_only(payload):
    source = ProjectionSource()
    projected = {t["ku_id"] for t in payload["traversal"]}
    assert len(projected) == payload["reading_map"]["chapters"][0]["ku_count"]
    assert projected == set(source.units) - set(source.superseded_ids())


def test_verified_count_is_checked_not_assumed(payload):
    """A frozen unit exists because its verification passed, so ku_count and
    verified_count being equal is a fact to verify rather than bake in."""
    source = ProjectionSource()
    for trace in payload["evidence_traces"]:
        verification = source.verification_of(source.units[trace["ku_id"]])
        assert verification.verification_status == "VERIFIED"


# ── traversal semantics ──────────────────────────────────────────────────────

def test_traversal_is_reading_order(payload):
    source = ProjectionSource()
    order = [view["ku_id"] for view in payload["traversal"]]
    expected = sorted(order, key=lambda ku: (
        source.evidence_of(source.units[ku]).page_number,
        str((source.evidence_of(source.units[ku]).locator or {}).get("section", "")),
        source.evidence_of(source.units[ku]).id))
    assert order == expected


def test_previous_and_next_form_one_chain(payload):
    views = payload["traversal"]
    assert len(views) >= 2
    assert views[0]["previous"] is None
    assert views[-1]["next"] is None
    for index in range(1, len(views)):
        assert views[index]["previous"] == views[index - 1]["ku_id"]
        assert views[index - 1]["next"] == views[index]["ku_id"]


def test_traversal_is_not_a_knowledge_graph(payload):
    """No similarity, no concept edge, no inferred relation: every
    neighbour is a neighbour by page."""
    source = ProjectionSource()
    order = [view["ku_id"] for view in payload["traversal"]]
    for index, view in enumerate(payload["traversal"]):
        pages = [source.evidence_of(source.units[ku]).page_number
                 for ku in order]
        position = pages.index(source.evidence_of(
            source.units[view["ku_id"]]).page_number)
        assert index == position or index in (position, position + 1)


def test_same_chapter_units_are_actually_the_same_chapter(payload):
    """Full chapter membership, including the unit itself, so its length
    equals the chapter's ku_count and the two views cross-check."""
    source = ProjectionSource()
    for view in payload["traversal"]:
        label = chapter_of(source, source.units[view["ku_id"]])
        assert view["ku_id"] in view["same_chapter_units"]
        for other in view["same_chapter_units"]:
            assert chapter_of(source, source.units[other]) == label
        assert len(view["same_chapter_units"]) == \
            payload["reading_map"]["chapters"][0]["ku_count"]


# ── revisions ────────────────────────────────────────────────────────────────

def test_a_superseded_unit_is_not_in_the_navigation_views(payload):
    """§9 — default is current units only."""
    source = ProjectionSource()
    superseded = set(source.superseded_ids())
    for trace in payload["evidence_traces"]:
        assert trace["ku_id"] not in superseded
    for view in payload["traversal"]:
        assert view["ku_id"] not in superseded


def test_a_superseded_unit_is_still_reachable(payload):
    """§9 forbids deleting, merging or replacing it. The revision chain is
    how it stays reachable."""
    chains = [view["revision_chain"] for view in payload["traversal"]]
    longer = [chain for chain in chains if len(chain) > 1]
    assert len(longer) == 1
    source = ProjectionSource()
    for chain in longer:
        for ku_id in chain:
            assert ku_id in source.units


def test_a_revision_chain_ends_at_its_own_unit(payload):
    for view in payload["traversal"]:
        assert view["revision_chain"][-1] == view["ku_id"]


def test_a_revision_chain_is_oldest_first(payload):
    source = ProjectionSource()
    for view in payload["traversal"]:
        chain = view["revision_chain"]
        indices = [source.evolution.revision_index_of(ku) for ku in chain]
        assert indices == sorted(indices)


def test_superseded_units_are_counted_not_hidden(payload):
    source = ProjectionSource()
    assert payload["coverage"]["superseded_units"] == \
        len(source.superseded_ids()) == 1


# ── coverage ─────────────────────────────────────────────────────────────────

def test_coverage_counts_fact_chains_not_truth(payload):
    coverage = payload["coverage"]
    assert coverage["total_candidates"] == 18
    assert coverage["rejected_candidates"] == 7
    assert coverage["verified_units"] == 10
    assert coverage["evidence_coverage"] == 1.0
    assert coverage["coverage_ratio"] == round(10 / 18, 4)


def test_coverage_carries_the_inequality_disclaimer(payload):
    assert "coverage != correctness" in payload["coverage"]["disclaimer"]


def test_evidence_coverage_is_one_or_it_fails(payload):
    """Evidence coverage that is not 1.0 means a projected unit lost its
    chain, which is the one thing this view must never do."""
    assert payload["coverage"]["evidence_coverage"] == 1.0


# ── gates ────────────────────────────────────────────────────────────────────

def test_every_gate_passes(projection):
    """Every reported gate, not the five a hand-written list happened to name.

    The old version iterated `GATE_ORDER`, which listed five names while
    `gate_results` returned seven, and then swept the remainder with a loop that
    allowed NOT_EXECUTED -- so a gate that never ran still satisfied a test
    called "all five gates pass". Both escapes are closed: every gate is named
    explicitly, and none may be unevidenced.
    """
    gates = gate_results(projection)
    assert set(gates) == {
        "G1_authority", "G1_no_new_id", "G1_read_only",
        "G2_traceability", "G3_determinism", "G4_replay", "G5_isolation",
    }, f"gate set changed to {sorted(gates)}"
    unevidenced = {n: v for n, v in gates.items() if v != "PASS"}
    assert not unevidenced, f"gates not passing: {unevidenced}"


def test_the_gate_list_is_not_maintained_by_hand(projection):
    """The parallel list is gone, so a new gate cannot fall outside it."""
    assert not hasattr(B, "GATE_ORDER"), \
        "a hardcoded gate list is back; it drifted from 5 to 7 while it was there"
    report = B.report(projection)
    assert "gate_order" not in report, \
        "the report still emits a hand-written gate order"
    assert list(report["gates"]) == list(gate_results(projection)), \
        "the report's gates are not the ones gate_results returned"


def test_the_verdict_is_derived_from_the_gates(projection):
    report = B.report(projection)
    gates = report["gates"]
    assert report["A_P7_BOOK_UNDERSTANDING_PROJECTION"] == verdict(gates)
    assert report["verdict_inputs"]["gate_count"] == len(gates)
    assert report["verdict_inputs"]["gates_not_executed"] == []


def test_a_failing_gate_cannot_escape_the_verdict(projection):
    """The P5/P6 defect, held shut for P7.

    A gate that is reported but never read is exactly how both earlier layers
    reported PASS while a gate they printed had not run.
    """
    gates = dict(gate_results(projection))
    gates["G9_invented"] = "FAIL"
    assert verdict(gates) == "FAIL"


def test_an_unevidenced_or_unknown_gate_blocks(projection):
    gates = dict(gate_results(projection))
    gates["G9_waiting"] = "NOT_EXECUTED"
    assert verdict(gates) == "BLOCKED"
    gates["G9_waiting"] = "SOMETHING_NEW"
    assert verdict(gates) == "BLOCKED", \
        "an unrecognised status must fail closed, not open"


def test_isolation_gate_passes(projection):
    assert isolation_gate(projection) == "PASS"
    assert isolation_drift(projection) == {}


def test_the_isolation_check_names_the_other_repositories():
    for repository in ("bu2", "b", "c"):
        assert repository in ISOLATED_TABLES
        assert ISOLATED_TABLES[repository]


def test_the_isolation_check_is_not_a_source_word_match():
    """A forbidden-name list inside the scanned file matches itself. The
    check runs on the artifact and the import graph instead."""
    source = (PKG / "projection_builder.py").read_text(encoding="utf-8")
    assert "artifact_drift" in source
    assert "external_imports" in source


def test_the_import_allowlist_is_the_a_chain_and_stdlib():
    assert "json" in ALLOWED_IMPORT_ROOTS
    assert ".identity" in ALLOWED_IMPORT_ROOTS
    for outside in ("psycopg2", "sqlalchemy", "requests", "aii", "llm"):
        assert outside not in ALLOWED_IMPORT_ROOTS


# ── the artifact ─────────────────────────────────────────────────────────────

def test_artifact_shape(payload):
    assert sorted(payload) == [
        "authority", "book_id", "book_title", "coverage", "evidence_traces",
        "projection_version", "reading_map", "source_version_id", "traversal"]
    assert payload["authority"] == "A_REPOSITORY"
    assert payload["projection_version"] == PROJECTION_VERSION


def test_artifact_is_named_by_an_a_repository_id(projection):
    name = artifact_name(projection)
    assert name == f"book_{projection.book_id}_projection.json"
    assert (ARTIFACT_DIR / name).exists()


def test_artifact_directory_is_the_one_the_task_fixes():
    assert ARTIFACT_DIR.name == "p7_projection"
    assert ARTIFACT_DIR.parent.name == "a_repository"
    assert ARTIFACT_DIR.parent.parent.name == "artifacts"


def test_report_states_every_acceptance_field(projection):
    doc = report(projection)
    for field in ("traceability", "replay", "determinism", "authority_drift",
                  "isolation_drift", "db_mutation", "schema_change",
                  "identity_drift", "content_hash", "gates"):
        assert field in doc
    assert doc["db_mutation"] == 0
    assert doc["schema_change"] == 0
    assert doc["identity_drift"] == 0
    assert doc["authority_drift"] == {"artifact": {}, "external_imports": []}
    assert doc["isolation_drift"] == {}


def test_the_projection_exposes_all_four_views(payload):
    """§3 — a book reading map, an evidence trace map, a traversal view and
    a coverage view."""
    assert payload["reading_map"]["chapters"]
    assert payload["evidence_traces"]
    assert payload["traversal"]
    assert payload["coverage"]["book_id"] == payload["book_id"]


def test_the_pipeline_is_fixed(projection):
    """§7 — six stages, always in this order, no configuration."""
    source = ProjectionSource()
    superseded = set(source.superseded_ids())
    ku_ids = sorted(ku for ku in source.units if ku not in superseded)
    # P7.4 reading map
    assert build_reading_map(source, ku_ids, projection.book_id,
                             projection.source_version_id).chapters
    # P7.5 coverage
    assert build_coverage(source, projection.book_id, ku_ids).evidence_coverage
    # P7.3 evidence
    assert evidence_trace(source, ku_ids[0]).evidence
    # P7.4b traversal
    assert build_traversal(source, ku_ids)


def test_build_projection_takes_no_arguments():
    """§6: a projection built from anything but the whole frozen A仓 chain
    would be a projection of a subset, and this stage has no subsets."""
    import inspect
    assert list(inspect.signature(build_projection).parameters) == []


def test_an_unprojectable_unit_is_an_error_not_a_blank_row():
    """Refusing to emit is better than emitting a view of nothing."""
    source = ProjectionSource()
    with pytest.raises(ProjectionError, match="not a durable unit"):
        evidence_trace(source, "ku_does_not_exist")


def test_a_failing_gate_changes_the_reported_verdict(projection, monkeypatch):
    """The mutation the previous three tests could not see.

    Comparing the report's verdict against `verdict(gates)` proves nothing when
    every gate passes: a verdict computed from two gates and one computed from
    all seven are both "PASS", so a subset wired into the report looks correct.
    It was caught here only by breaking a gate that a subset would have
    excluded -- `G1_no_new_id`, which the deleted `GATE_ORDER` never listed.

    This is the P5/P6 defect in its exact shape: a gate reported to the reader
    and left out of the thing that decides the outcome.
    """
    monkeypatch.setattr(B, "no_new_id_gate", lambda *a, **k: "FAIL")
    blocked = B.report(projection)
    assert blocked["gates"]["G1_no_new_id"] == "FAIL"
    assert blocked["A_P7_BOOK_UNDERSTANDING_PROJECTION"] == "FAIL", \
        "a failing gate did not reach the verdict"
    assert blocked["verdict_inputs"]["gates_failed"] == ["G1_no_new_id"]

    monkeypatch.setattr(B, "no_new_id_gate", lambda *a, **k: "NOT_EXECUTED")
    waiting = B.report(projection)
    assert waiting["A_P7_BOOK_UNDERSTANDING_PROJECTION"] == "BLOCKED", \
        "an unevidenced gate must block, not pass"


# -- freeze gate ---------------------------------------------------------------
#
# Same refusal the P5 Evolution freeze needed, and for the same reason: the
# stage around a verdict looks green long before the verdict itself can.

def test_the_freeze_artifact_carries_the_stage_evidence(projection, monkeypatch):
    for key in FREEZE_EVIDENCE:
        monkeypatch.setenv(f"A_P7_{key.upper()}", "PASS")
    doc = freeze_artifact(projection)
    for key in ("stage", "base_sha", "gates", "verdict",
                "dependency_closure", "db_acceptance"):
        assert key in doc, f"freeze artifact is missing {key}"
    assert doc["stage"] == "P7_PROJECTION"
    assert doc["declared_migrations"] == 0
    assert doc["chain_read"] == 13, "the A chain is 070..082"
    assert doc["verdict"] == verdict(doc["gates"])


def test_absent_freeze_evidence_blocks(projection, monkeypatch):
    for key in FREEZE_EVIDENCE:
        monkeypatch.delenv(f"A_P7_{key.upper()}", raising=False)
    doc = freeze_artifact(projection)
    # Every gate passes here, so the only reason to refuse is the absent
    # evidence. Stated exactly, because "one of these or the other" is not a
    # specification.
    assert doc["verdict"] == "PASS"
    assert sorted(freeze_blockers(doc)) == sorted(FREEZE_EVIDENCE)


def test_a_blocked_layer_is_not_frozen(projection, monkeypatch):
    for key in FREEZE_EVIDENCE:
        monkeypatch.setenv(f"A_P7_{key.upper()}", "PASS")
    monkeypatch.setattr(B, "no_new_id_gate", lambda *a, **k: "FAIL")
    doc = freeze_artifact(projection)
    assert doc["verdict"] == "FAIL"
    assert freeze_blockers(doc) == ["layer_verdict:FAIL"], \
        "complete surrounding evidence must not freeze a failing layer"


def test_main_writes_no_freeze_artifact_when_blocked(projection, monkeypatch,
                                                     tmp_path):
    import sys as _sys
    target = tmp_path / "p7_freeze.json"
    monkeypatch.setattr(_sys, "argv", ["projection_builder"])
    for key in FREEZE_EVIDENCE:
        monkeypatch.setenv(f"A_P7_{key.upper()}", "PASS")
    monkeypatch.setenv("A_P7_FREEZE_ARTIFACT", str(target))
    monkeypatch.setattr(B, "build_projection", lambda *a, **k: projection)
    monkeypatch.setattr(B, "no_new_id_gate", lambda *a, **k: "FAIL")
    with pytest.raises(SystemExit) as exit_info:
        B.main()
    assert exit_info.value.code == 1
    assert not target.exists(), "a blocked freeze wrote an artifact anyway"


def test_main_writes_the_freeze_artifact_when_green(projection, monkeypatch,
                                                    tmp_path):
    import sys as _sys
    target = tmp_path / "p7_freeze.json"
    monkeypatch.setattr(_sys, "argv", ["projection_builder"])
    for key in FREEZE_EVIDENCE:
        monkeypatch.setenv(f"A_P7_{key.upper()}", "PASS")
    monkeypatch.setenv("A_P7_FREEZE_ARTIFACT", str(target))
    monkeypatch.setattr(B, "build_projection", lambda *a, **k: projection)
    B.main()
    written = json.loads(target.read_text(encoding="utf-8"))
    assert written["verdict"] == "PASS"
    assert len(written["chain_fingerprints"]) == 13
    assert written["db_mutation"] == 0 and written["schema_change"] == 0
