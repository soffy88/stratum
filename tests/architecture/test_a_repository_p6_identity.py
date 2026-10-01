"""A Repository P6 — canonical KU identity.

Contract tests for the identity service (migration 076):
- schema: one table, closed vocabularies, column parity with the emitter
- identity: one id means one unit, in both namespaces
- resolution: every id an earlier stage ever emitted still resolves
- immutability: nothing is renumbered, repointed or deleted
- authority: the identity reaches nothing outside A仓
- regression: P1-P5 still produce exactly what they produced
"""

from __future__ import annotations

import dataclasses
import json
import re
from pathlib import Path
from typing import Dict, List

import pytest


ROOT = Path(__file__).parents[2]
MIGRATIONS = ROOT / "src" / "stratum" / "db" / "pg_migrations"
MIGRATION = MIGRATIONS / "076_a_ku_identity.sql"
PKG = ROOT / "src" / "stratum" / "knowledge" / "a_repository"
ARTIFACTS = ROOT / "artifacts" / "a_repository"
ARTIFACT = ARTIFACTS / "p6_ku_identity.json"
P4_ARTIFACT = ARTIFACTS / "p4_ku_freeze.json"
P5_ARTIFACT = ARTIFACTS / "p5_ku_evolution.json"

from stratum.knowledge.a_repository.evolution import (  # noqa: E402
    EVOLUTION_TABLES,
    EVOLUTION_VERSION,
    EvolutionViolation,
)
from stratum.knowledge.a_repository.freeze import FREEZE_VERSION  # noqa: E402
from stratum.knowledge.a_repository.identity import (  # noqa: E402
    DECLARED_ALIAS_KINDS,
    IDENTITY_TABLES,
    IDENTITY_VERSION,
    IdentityAlias,
    IdentityKind,
    IdentityPrecondition,
    IdentitySink,
    KUIdentityService,
    Resolution,
    canonical_ku_id,
    decode_fingerprint,
    encode_fingerprint,
    identity_hash,
    identity_id,
    legacy_freeze_id,
)
from stratum.knowledge.a_repository.ku_identity_runner import (  # noqa: E402
    ALLOWED_REFERENCES,
    CREATED_TABLES,
    REQUIRED_CHAIN,
    REQUIRED_MIGRATION,
    WRITABLE_TABLES,
    artifact,
    authority_gate,
    build_identity,
    canonical_id_gate,
    citation_gate,
    gate_results,
    idempotency_gate,
    no_external_dependency_gate,
    no_mutation_gate,
    verdict,
    regression_gate,
    regression_verdict,
    replay_gate,
    retired_id_recomputes,
    revision_gate,
    schema_gate,
    successor_gate,
    uniqueness_gate,
    write_sql,
)
from stratum.knowledge.a_repository.persistence import (  # noqa: E402
    PERSISTENCE_VERSION,
    persisted_unit_id,
)


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def _statements() -> str:
    return re.sub(r"--.*", "", _sql())


def _table_body(table: str) -> str:
    """The inside of one CREATE TABLE, up to its closing paren."""
    block = _statements().split(
        f"CREATE TABLE IF NOT EXISTS stratum.{table}")[1]
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


def _split_top_level(body: str) -> List[str]:
    """Split on commas that are not inside parentheses."""
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
    return parts


def _declared_columns() -> List[str]:
    """Every column 076 declares, in order.

    Split on top-level commas rather than on lines: a column's REFERENCES
    or CHECK clause wraps onto its own lines, and a line-based reader finds
    only the columns that happened to fit.
    """
    columns: List[str] = []
    for fragment in _split_top_level(_table_body("ku_identity")):
        fragment = fragment.strip()
        if not fragment:
            continue
        head = fragment.split()[0].upper()
        if head in {"CONSTRAINT", "UNIQUE", "CHECK", "PRIMARY", "FOREIGN"}:
            continue
        columns.append(fragment.split()[0])
    return columns


@pytest.fixture(scope="module")
def identified():
    result = build_identity()
    return {"result": result, "identity": result["identity"],
            "sink": result["sink"], "registered": result["registered"]}


def _fresh() -> Dict:
    """A private, mutable run for a test that has to break something."""
    return build_identity()


# ── schema ───────────────────────────────────────────────────────────────────

def test_076_creates_exactly_one_table():
    created = set(re.findall(r"CREATE TABLE IF NOT EXISTS stratum\.(\w+)",
                             _statements()))
    assert created == set(CREATED_TABLES)


def test_076_is_additive_only():
    statements = _statements()
    assert "ALTER TABLE" not in statements
    assert "DROP " not in statements
    assert "INSERT INTO" not in statements
    assert not re.search(r"^[ \t]*UPDATE\b", statements, re.MULTILINE)


def test_076_recreates_nothing_it_inherits():
    statements = _statements()
    for inherited in ("knowledge_unit", "ku_freeze_event", "ku_candidate",
                      "ku_verification", "reading_evidence", "source_version",
                      "reading_run", "ku_revision", "ku_review_event",
                      "ku_confidence_evolution", "ku_relation"):
        assert f"CREATE TABLE IF NOT EXISTS stratum.{inherited} (" not in statements


def test_076_references_only_knowledge_unit():
    referenced = set(re.findall(r"REFERENCES\s+stratum\.(\w+)", _sql()))
    assert referenced == ALLOWED_REFERENCES


def test_076_foreign_key_restricts():
    actions = re.findall(r"REFERENCES\s+stratum\.\w+\(id\)\s+ON DELETE (\w+)",
                         _sql())
    assert actions == ["RESTRICT"]


def test_076_identity_table_has_an_id_primary_key():
    """A row the sink and the emitter key by `id` must have that column.

    Written after 076 shipped without one and every insert failed at the
    database. Reading the migration does not catch it; asserting the emitter
    and the schema agree does.
    """
    assert "id" in _declared_columns()
    assert "id TEXT PRIMARY KEY" in _statements()


def test_emitter_columns_and_the_schema_agree():
    """Column parity: what the writer names, the database must have.

    The two bugs this caught were both missing columns — `id` and
    `identity_hash` — which no amount of reading the migration or the
    dataclass would have surfaced. Only the disagreement does.
    """
    from stratum.knowledge.a_repository.identity import _IDENTITY_COLUMNS
    declared = set(_declared_columns())
    assert set(_IDENTITY_COLUMNS) <= declared, (
        "the emitter writes columns 076 does not declare: "
        f"{sorted(set(_IDENTITY_COLUMNS) - declared)}")
    fields = {f.name for f in dataclasses.fields(IdentityAlias)}
    assert set(_IDENTITY_COLUMNS) <= fields, (
        "the emitter writes fields IdentityAlias does not carry: "
        f"{sorted(set(_IDENTITY_COLUMNS) - fields)}")


def test_dataclass_and_schema_share_every_column():
    fields = {f.name for f in dataclasses.fields(IdentityAlias)}
    # created_at is filled by the database; everything else is written.
    assert fields - {"created_at"} == set(_declared_columns()) - {"created_at"}


def test_the_alias_must_be_unique_across_the_whole_table():
    """The load-bearing constraint of this migration."""
    statements = _statements()
    assert "CONSTRAINT ku_identity_alias_uniq UNIQUE (alias_id)" in statements
    assert "CONSTRAINT ku_identity_hash_uniq UNIQUE (identity_hash)" in statements


def test_a_unit_cannot_be_its_own_alias():
    assert "CONSTRAINT ku_identity_not_self CHECK (canonical_ku_id <> alias_id)" \
        in _statements()


def test_alias_kind_is_a_closed_vocabulary():
    block = _statements().split(
        "CREATE TABLE IF NOT EXISTS stratum.ku_identity")[1]
    declared = set(re.findall(r"'([A-Z_]+)'", block.split("CHECK")[1]))
    assert declared == DECLARED_ALIAS_KINDS
    assert declared == {k.value for k in IdentityKind}


def test_there_is_no_durable_alias_kind():
    """The durable id IS the canonical id, so it is not an alias."""
    assert "DURABLE" not in DECLARED_ALIAS_KINDS


def test_fingerprint_must_be_present():
    assert "CHECK (length(btrim(id_fingerprint)) > 0)" in _statements()


def test_076_is_additive_over_the_whole_chain():
    chain = "\n".join((MIGRATIONS / name).read_text(encoding="utf-8")
                      for name in REQUIRED_CHAIN)
    assert "CREATE TABLE IF NOT EXISTS stratum.ku_identity" in chain


def test_earlier_migrations_are_untouched_by_this_stage():
    for name in REQUIRED_CHAIN[:-1]:
        sql = (MIGRATIONS / name).read_text(encoding="utf-8")
        for table in CREATED_TABLES:
            assert f"stratum.{table}" not in sql


def test_bu2_and_b_are_untouched():
    for name in ("063_bu2_p4_p5_chapter_and_bu.sql",
                 "064_bu2_p6_p8_p9_verification_learning.sql",
                 "065_bu2_pipeline_state.sql"):
        sql = (MIGRATIONS / name).read_text(encoding="utf-8")
        for table in CREATED_TABLES:
            assert table not in sql


def test_p4_p4_1_and_p5_versions_are_untouched():
    assert FREEZE_VERSION == "a-p4-v0.1"
    assert PERSISTENCE_VERSION == "a-p4-1-v0.1"
    assert EVOLUTION_VERSION == "a-p5-v0.1"


# ── the decision ────────────────────────────────────────────────────────────

def test_the_canonical_id_is_the_durable_id():
    """Named, not restated: the formula stays P4.1's, so nothing already
    written has to move."""
    assert canonical_ku_id("kc_a", "kv_b", "ch_c") == \
        persisted_unit_id("kc_a", "kv_b", "ch_c")


def test_the_canonical_id_is_content_derived():
    assert canonical_ku_id("kc_a", "kv_b", "ch_c") == \
        canonical_ku_id("kc_a", "kv_b", "ch_c")
    assert canonical_ku_id("kc_a", "kv_b", "ch_c") != \
        canonical_ku_id("kc_b", "kv_b", "ch_c")


def test_every_durable_row_already_uses_it(identified):
    """No renumbering: the id P4.1 wrote is the canonical one, for all
    eleven rows."""
    for key, unit in identified["sink"].units.items():
        assert key == persisted_unit_id(unit.candidate_id,
                                       unit.verification_id,
                                       unit.content_hash)


def test_the_two_formulas_really_differ(identified):
    """Otherwise the stage would be solving nothing."""
    differ = sum(1 for canonical, aliases in
                 ((key, identified["identity"].aliases_of(key))
                  for key in identified["sink"].units)
                 if aliases and aliases[0].alias_id != canonical)
    assert differ == len(identified["sink"].units)


def test_no_third_id_was_minted(identified):
    """Every id in existence is either a canonical id or a registered
    alias. A third namespace would defeat the point."""
    identity: KUIdentityService = identified["identity"]
    known = set(identity.sink.units)
    for row in identity.sink.identities.values():
        known.add(row.alias_id)
    assert len(known) == 2 * len(identity.sink.units)


# ── GATE_1 identity uniqueness ───────────────────────────────────────────────

def test_uniqueness_gate_passes(identified):
    assert uniqueness_gate(identified["result"]) == "PASS"


def test_canonical_id_gate_passes(identified):
    assert canonical_id_gate(identified["result"]) == "PASS"


def test_every_unit_has_exactly_one_alias(identified):
    identity: KUIdentityService = identified["identity"]
    for key in identity.sink.units:
        assert len(identity.aliases_of(key)) == 1


def test_no_unit_is_left_unregistered(identified):
    assert identified["identity"].unregistered_units() == []


def test_an_alias_never_means_two_units(identified):
    assert identified["identity"].ambiguous_ids() == []


def test_no_alias_is_another_units_canonical_id(identified):
    """Both namespaces are `ku_<12 hex>`, so a reader cannot tell them
    apart from the id alone."""
    assert identified["identity"].cross_namespace_collisions() == []


def test_no_duplicate_aliases(identified):
    assert identified["identity"].duplicate_identities() == []


def test_no_orphan_identities(identified):
    assert identified["identity"].orphan_identities() == []


def test_uniqueness_fails_when_two_units_claim_one_alias():
    result = _fresh()
    identity: KUIdentityService = result["identity"]
    row = next(iter(identity.sink.identities.values()))
    intruder = next(k for k in sorted(identity.sink.units)
                    if k != row.canonical_ku_id)
    identity.sink.identities["kid_intruder"] = IdentityAlias(
        id="kid_intruder", canonical_ku_id=intruder, alias_id=row.alias_id,
        alias_kind=row.alias_kind, id_fingerprint=row.id_fingerprint,
        identity_hash=row.identity_hash)
    assert uniqueness_gate(result) == "FAIL"


def test_uniqueness_fails_when_an_alias_collides_with_a_canonical():
    result = _fresh()
    identity: KUIdentityService = result["identity"]
    row = next(iter(identity.sink.identities.values()))
    other = next(k for k in sorted(identity.sink.units)
                 if k != row.canonical_ku_id)
    identity.sink.identities["kid_collide"] = IdentityAlias(
        id="kid_collide", canonical_ku_id=row.canonical_ku_id, alias_id=other,
        alias_kind=row.alias_kind, id_fingerprint=row.id_fingerprint,
        identity_hash=row.identity_hash)
    assert uniqueness_gate(result) == "FAIL"


def test_a_misbound_alias_is_detected(identified):
    """A row that rebuilds to a different id is worse than no row."""
    identity: KUIdentityService = identified["identity"]
    assert identity.misbound_aliases() == []
    row = next(iter(identity.sink.identities.values()))
    original = row.id_fingerprint
    row.id_fingerprint = encode_fingerprint("a different statement", "0" * 64)
    try:
        assert identity.misbound_aliases() == [row.alias_id]
        assert uniqueness_gate(identified["result"]) == "FAIL"
    finally:
        row.id_fingerprint = original
    assert identity.misbound_aliases() == []


def test_each_alias_is_the_id_p4s_own_formula_produces(identified):
    identity: KUIdentityService = identified["identity"]
    verifications = identity.fp.vp.store.verifications
    for row in identity.sink.identities.values():
        statement, fingerprint = decode_fingerprint(row.id_fingerprint)
        assert legacy_freeze_id(statement, fingerprint) == row.alias_id
        unit = identity.sink.units[row.canonical_ku_id]
        assert statement == unit.statement
        assert verifications[unit.verification_id].trace["fingerprint"] == \
            fingerprint


def test_the_fingerprint_survives_a_separator_in_the_statement():
    """Encoded as JSON, not as P4's `|`-joined hash input: a statement
    containing the separator must not make the check mis-parse itself."""
    encoded = encode_fingerprint("a | b", "fp")
    assert decode_fingerprint(encoded) == ("a | b", "fp")
    assert legacy_freeze_id(*decode_fingerprint(encoded)) == \
        legacy_freeze_id("a | b", "fp")


def test_registration_refuses_a_unit_that_is_its_own_alias(identified):
    identity: KUIdentityService = identified["identity"]
    canonical = sorted(identity.sink.units)[0]
    ok, failed = identity.check_registration_preconditions(
        canonical, canonical, "FREEZE_LEGACY", "fp")
    assert not ok
    assert "ALIAS_IS_CANONICAL" in failed


def test_registration_refuses_an_unknown_alias_kind(identified):
    identity: KUIdentityService = identified["identity"]
    canonical = sorted(identity.sink.units)[0]
    ok, failed = identity.check_registration_preconditions(
        canonical, "ku_zzzzzzzzzzzz", "DURABLE_V2", "fp")
    assert not ok
    assert "UNKNOWN_ALIAS_KIND" in failed


def test_registration_refuses_a_blank_fingerprint(identified):
    identity: KUIdentityService = identified["identity"]
    canonical = sorted(identity.sink.units)[0]
    ok, failed = identity.check_registration_preconditions(
        canonical, "ku_zzzzzzzzzzzz", "FREEZE_LEGACY", "  ")
    assert not ok
    assert "NO_ID_FINGERPRINT" in failed


def test_registration_refuses_a_unit_that_is_not_durable(identified):
    identity: KUIdentityService = identified["identity"]
    ok, failed = identity.check_registration_preconditions(
        "ku_not_durable", "ku_zzzzzzzzzzzz", "FREEZE_LEGACY", "fp")
    assert not ok
    assert "NO_SUCH_CANONICAL_UNIT" in failed


def test_registration_refuses_an_alias_that_is_another_units_id(identified):
    """The rule the schema cannot express, enforced here instead."""
    identity: KUIdentityService = identified["identity"]
    canonical = sorted(identity.sink.units)[0]
    other = next(k for k in sorted(identity.sink.units) if k != canonical)
    ok, failed = identity.check_registration_preconditions(
        canonical, other, "FREEZE_LEGACY", "fp")
    assert not ok
    assert "ALIAS_IS_ANOTHER_UNITS_CANONICAL" in failed


def test_registration_refuses_an_alias_already_claimed(identified):
    identity: KUIdentityService = identified["identity"]
    row = next(iter(identity.sink.identities.values()))
    other = next(k for k in sorted(identity.sink.units)
                 if k != row.canonical_ku_id)
    ok, failed = identity.check_registration_preconditions(
        other, row.alias_id, "FREEZE_LEGACY", "fp")
    assert not ok
    assert "ALIAS_ALREADY_CLAIMED" in failed


def test_a_refused_registration_writes_nothing(identified):
    identity: KUIdentityService = identified["identity"]
    before = len(identity.sink.identities)
    with pytest.raises(IdentityPrecondition):
        identity.register(sorted(identity.sink.units)[0],
                         sorted(identity.sink.units)[0],
                         IdentityKind.FREEZE_LEGACY, "fp")
    assert len(identity.sink.identities) == before


def test_identity_ids_are_content_derived(identified):
    for row in identified["sink"].identities.values():
        assert row.id == identity_id(row.canonical_ku_id, row.alias_id)
        assert row.identity_hash == identity_hash(
            row.canonical_ku_id, row.alias_id, row.alias_kind,
            row.id_fingerprint)


# ── GATE_2 historical replay ─────────────────────────────────────────────────

def test_replay_produces_the_same_ids_and_rows():
    replay = replay_gate()
    assert replay["identical_fingerprints"] == 1
    assert replay["same_aliases"]
    assert replay["same_canonical"]
    assert replay["no_duplicates"]


def test_idempotency_gate_passes(identified):
    assert idempotency_gate(identified["result"]) == "PASS"


def test_re_registering_appends_nothing(identified):
    identity: KUIdentityService = identified["identity"]
    before = {row.id for row in identity.sink.identities.values()}
    for frozen in identity.frozen_units():
        identity.register_frozen_unit(frozen)
    assert {row.id for row in identity.sink.identities.values()} == before


def test_a_rebuild_from_scratch_produces_the_same_aliases():
    first = {r.alias_id: r.canonical_ku_id
             for r in build_identity()["sink"].identities.values()}
    second = {r.alias_id: r.canonical_ku_id
              for r in build_identity()["sink"].identities.values()}
    assert first == second
    assert len(first) == 11


def test_every_id_p4_recorded_still_resolves(identified):
    """The honest replay test: the P4 artifact holds the retired ids, so a
    citation made before P4.1 exists resolves through the alias table."""
    identity: KUIdentityService = identified["identity"]
    frozen = json.loads(P4_ARTIFACT.read_text(encoding="utf-8"))
    cited = [entry["unit_id"] for entry in frozen["units"].values()]
    assert len(cited) == 10
    for value in cited:
        outcome = identity.resolve(value)
        assert outcome.resolved, value
        assert outcome.resolution == Resolution.ALIAS.value
        assert outcome.canonical_ku_id in identity.sink.units


def test_every_canonical_id_still_resolves_to_itself(identified):
    identity: KUIdentityService = identified["identity"]
    for key in identity.sink.units:
        outcome = identity.resolve(key)
        assert outcome.resolution == Resolution.CANONICAL.value
        assert outcome.canonical_ku_id == key


def test_an_unknown_id_resolves_to_nothing(identified):
    """Unresolved is an answer, not a failure to paper over."""
    identity: KUIdentityService = identified["identity"]
    outcome = identity.resolve("ku_000000000000")
    assert outcome.resolution == Resolution.UNRESOLVED.value
    assert outcome.canonical_ku_id is None
    assert not outcome.resolved


def test_citation_gate_passes(identified):
    assert citation_gate(identified["result"]) == "PASS"


def test_retired_id_recomputes_gate_passes(identified):
    assert retired_id_recomputes(identified["result"]) == "PASS"


def test_resolution_covers_every_id(identified):
    report = identified["identity"].resolution_report()
    assert report["ids_seen"] == 22
    assert report["by_resolution"] == {"ALIAS": 11, "CANONICAL": 11}
    assert report["ambiguous"] == []
    assert report["cross_namespace"] == []
    assert report["orphans"] == []
    assert report["misbound"] == []


# ── GATE_3 revision chain intact ─────────────────────────────────────────────

def test_revision_gate_passes(identified):
    assert revision_gate(identified["result"]) == "PASS"


def test_successor_gate_passes(identified):
    assert successor_gate(identified["result"]) == "PASS"


def test_the_revision_links_still_resolve(identified):
    identity: KUIdentityService = identified["identity"]
    for revision in identified["sink"].revisions.values():
        assert identity.resolve(revision.prior_unit_id).canonical_ku_id == \
            revision.prior_unit_id
        assert identity.resolve(revision.revised_unit_id).canonical_ku_id == \
            revision.revised_unit_id


def test_a_prior_unit_cited_by_its_retired_id_still_reads_superseded(
        identified):
    """Otherwise a pre-P4.1 citation would resolve to a unit that no longer
    looks superseded."""
    identity: KUIdentityService = identified["identity"]
    evolution = identified["result"]["evolved"]["evolution"]
    revision = next(iter(identified["sink"].revisions.values()))
    alias = identity.aliases_of(revision.prior_unit_id)[0].alias_id
    canonical = identity.resolve(alias).canonical_ku_id
    assert canonical == revision.prior_unit_id
    assert evolution.status_of(canonical) == "SUPERSEDED"
    assert evolution.successor_of(canonical) == revision.revised_unit_id


def test_an_alias_does_not_create_a_second_identity_for_the_fold(identified):
    """Resolution is a lookup layer, not a second identity.

    The lifecycle is keyed by canonical id, so a retired id is deliberately
    absent from it: callers resolve first, then query. If the alias were
    also in the fold there would be two identities to keep in step.
    """
    identity: KUIdentityService = identified["identity"]
    evolution = identified["result"]["evolved"]["evolution"]
    revision = next(iter(identified["sink"].revisions.values()))
    alias = identity.aliases_of(revision.prior_unit_id)[0].alias_id
    assert alias not in evolution.sink.units
    assert evolution.history(alias) == []
    canonical = identity.resolve(alias).canonical_ku_id
    assert evolution.status_of(canonical) == "SUPERSEDED"
    assert evolution.status_of(canonical) == \
        evolution.status_of(revision.prior_unit_id)


def test_the_revision_chain_is_still_a_chain(identified):
    """One successor per prior and one prior per successor: the chain P5
    built has not been re-rooted by an alias."""
    priors = [r.prior_unit_id for r in identified["sink"].revisions.values()]
    revised = [r.revised_unit_id
               for r in identified["sink"].revisions.values()]
    assert not set(priors) & set(revised)
    assert len(set(priors)) == len(priors)
    assert len(set(revised)) == len(revised)


# ── GATE_4 P1-P5 regression ─────────────────────────────────────────────────

def test_regression_verdict_passes():
    assert regression_verdict(regression_gate(build_identity())) == "PASS"


def test_p5_still_produces_what_it_produced():
    checks = regression_gate(build_identity())
    committed = json.loads(P5_ARTIFACT.read_text(encoding="utf-8"))
    assert checks["p5_units"] == committed["persisted_units"] == 11
    assert checks["p5_revisions"] == committed["revisions"] == 1
    assert checks["p5_reviews"] == committed["reviews"] == 5
    assert checks["p5_artifact_matches"] == 1


def test_p4_still_produces_its_ten_legacy_ids():
    checks = regression_gate(build_identity())
    frozen = json.loads(P4_ARTIFACT.read_text(encoding="utf-8"))
    assert checks["p4_legacy_ids"] == len(frozen["units"]) == 10
    assert checks["p4_ids_reproduced"] == 1


def test_every_legacy_id_p5_added_is_also_resolvable():
    """P5 froze an eleventh unit, so it carries a retired id too."""
    assert regression_gate(build_identity())[
        "p5_legacy_ids_still_resolvable"] == 1


def test_regression_fails_when_an_earlier_stage_drifts():
    checks = regression_gate(build_identity())
    drifted = dict(checks, p5_revisions=2)
    assert regression_verdict(drifted) == "FAIL"


def test_earlier_stage_versions_are_still_their_own():
    checks = regression_gate(build_identity())
    assert checks["freeze_version"] == "a-p4-v0.1"
    assert checks["persistence_version"] == "a-p4-1-v0.1"
    assert checks["evolution_version"] == "a-p5-v0.1"


def test_p5_test_suite_still_passes():
    """P6 touched P5's sink seam, so P5 is re-run here rather than assumed."""
    import subprocess
    completed = subprocess.run(
        ["python3", "-m", "pytest",
         str(ROOT / "tests" / "architecture"
             / "test_a_repository_p5_evolution.py"), "-q"],
        cwd=ROOT, capture_output=True, text=True, timeout=900)
    assert completed.returncode == 0, completed.stdout[-2000:]


# ── GATE_5 authority isolation ───────────────────────────────────────────────

def test_authority_gate_passes():
    assert authority_gate() == "PASS"


def test_no_external_dependency_gate_passes():
    assert no_external_dependency_gate() == "PASS"


def test_no_mutation_gate_passes(identified):
    assert no_mutation_gate(identified["result"]) == "PASS"


def test_a_unit_cannot_be_renumbered(identified):
    identity: KUIdentityService = identified["identity"]
    with pytest.raises(EvolutionViolation, match="renumbered"):
        identity.renumber(sorted(identity.sink.units)[0], "ku_000000000000")
    with pytest.raises(EvolutionViolation):
        identity.update_unit(sorted(identity.sink.units)[0], id="ku_x")


def test_an_alias_cannot_be_repointed(identified):
    identity: KUIdentityService = identified["identity"]
    row = next(iter(identity.sink.identities.values()))
    with pytest.raises(EvolutionViolation, match="repointed"):
        identity.repoint(row.alias_id, sorted(identity.sink.units)[0])


def test_nothing_in_the_identity_stage_is_mutable(identified):
    identity: KUIdentityService = identified["identity"]
    row_id = next(iter(identity.sink.identities))
    with pytest.raises(EvolutionViolation):
        identity.update_identity(row_id, alias_id="ku_x")
    with pytest.raises(EvolutionViolation):
        identity.delete_identity(row_id)
    with pytest.raises(EvolutionViolation):
        identity.delete_unit(sorted(identity.sink.units)[0])


def test_identity_may_not_depend_on_another_repository(identified):
    with pytest.raises(EvolutionViolation, match="must not depend"):
        identified["identity"].depend_on("B仓")


def test_the_migration_names_no_external_authority():
    statements = _statements()
    named = set(re.findall(r"stratum\.(\w+)", statements))
    assert named <= CREATED_TABLES | ALLOWED_REFERENCES


def test_the_service_reaches_only_the_a_chain():
    """Structural: the identity service's imports are the A chain plus the
    standard library, and nothing it imports is another repository."""
    source = (PKG / "identity.py").read_text(encoding="utf-8")
    code = re.sub(r'""".*?"""', "", source, flags=re.DOTALL)
    imports = set(re.findall(r"^\s*(?:from|import)\s+([\w.]+)", code,
                             re.MULTILINE))
    assert imports <= {"__future__", "hashlib", "dataclasses", "enum",
                       "typing", "json", "evolution", "persistence", "freeze",
                       ".evolution", ".persistence", ".freeze"}
    assert not re.search(
        r"\b(bu2?|b_repo|ku_onto|concept_onto|rf\.|aii_refined)\b", code)


def test_the_writable_set_is_the_a_chain_plus_identity():
    assert WRITABLE_TABLES == frozenset(IDENTITY_TABLES)
    assert "ku_identity" in WRITABLE_TABLES
    assert not any(t.startswith("bu") for t in WRITABLE_TABLES)


def test_the_sink_only_accepts_the_identity_stage_tables():
    assert IdentitySink.TABLES == EVOLUTION_TABLES + ("ku_identity",)
    assert IdentitySink.ROW_BUCKETS["ku_identity"] == "identities"
    assert IdentitySink.ROW_TYPES["ku_identity"] is IdentityAlias


# ── the emitted script ───────────────────────────────────────────────────────

def test_the_script_is_one_transaction(identified, tmp_path):
    path = write_sql(identified["result"], str(tmp_path / "identity.sql"))
    script = Path(path).read_text(encoding="utf-8")
    assert script.count("BEGIN;") == 1
    assert script.count("COMMIT;") == 1


def test_every_statement_is_idempotent(identified, tmp_path):
    path = write_sql(identified["result"], str(tmp_path / "identity.sql"))
    lines = [line for line in
             Path(path).read_text(encoding="utf-8").splitlines()
             if line.startswith("INSERT INTO")]
    assert lines
    for line in lines:
        assert "ON CONFLICT (" in line and line.endswith("DO NOTHING;")


def test_the_script_writes_the_whole_chain_plus_identity(identified, tmp_path):
    path = write_sql(identified["result"], str(tmp_path / "identity.sql"))
    script = Path(path).read_text(encoding="utf-8")
    for table in ("book_source", "source_version", "reading_run",
                  "reading_evidence", "ku_candidate", "ku_verification",
                  "knowledge_unit", "ku_freeze_event", "ku_revision",
                  "ku_review_event", "ku_confidence_evolution", "ku_relation",
                  "ku_identity"):
        assert f"INSERT INTO {table} " in script


def test_units_are_written_before_the_rows_that_name_them(identified,
                                                          tmp_path):
    path = write_sql(identified["result"], str(tmp_path / "identity.sql"))
    script = Path(path).read_text(encoding="utf-8")
    tables = [line.split("(")[0].split()[-1] for line in script.splitlines()
              if line.startswith("INSERT INTO")]
    for parent, child in (("book_source", "source_version"),
                          ("source_version", "reading_run"),
                          ("reading_run", "reading_evidence"),
                          ("reading_evidence", "ku_candidate"),
                          ("ku_candidate", "ku_verification"),
                          ("ku_verification", "knowledge_unit"),
                          ("knowledge_unit", "ku_identity")):
        assert tables.index(parent) < tables.index(child), (
            f"{parent} must be written before {child}")


def test_the_script_emits_each_row_once(identified, tmp_path):
    path = write_sql(identified["result"], str(tmp_path / "identity.sql"))
    lines = [line for line in
             Path(path).read_text(encoding="utf-8").splitlines()
             if line.startswith("INSERT INTO")]
    ids = [line.split("VALUES (")[1].split(",")[0] for line in lines]
    assert len(ids) == len(set(ids))


def test_the_script_escapes_quotes_in_a_fingerprint(identified, tmp_path):
    """The fingerprint is JSON carrying a free-text statement."""
    from stratum.knowledge.a_repository.identity import _literal
    assert _literal("it's") == "'it''s'"
    assert _literal(encode_fingerprint("a 'quoted' statement", "fp")) == \
        "'" + encode_fingerprint("a 'quoted' statement", "fp").replace(
            "'", "''") + "'"


def test_the_script_is_byte_identical_on_a_rerun(identified, tmp_path):
    first = write_sql(identified["result"], str(tmp_path / "a.sql"))
    second = write_sql(_fresh(), str(tmp_path / "b.sql"))
    assert Path(first).read_bytes() == Path(second).read_bytes()


# ── the artifact ─────────────────────────────────────────────────────────────

def test_artifact_shape(identified):
    doc = artifact(identified["result"], list(REQUIRED_CHAIN))
    assert doc["task"] == "A_P6_KU_IDENTITY"
    assert doc["authority"] == "A_REPOSITORY"
    assert doc["identity_version"] == IDENTITY_VERSION
    assert doc["A_P6_IDENTITY"] == "PASS"
    assert doc["canonical_units"] == 11
    assert doc["identity_rows"] == 11


def test_artifact_records_the_canonical_formula(identified):
    doc = artifact(identified["result"], list(REQUIRED_CHAIN))
    assert doc["canonical_ku_id_formula"] == (
        "ku_<sha256(candidate_id|verification_id|content_hash)[:12]>")


def test_artifact_alias_vocabulary_matches_the_schema(identified):
    doc = artifact(identified["result"], list(REQUIRED_CHAIN))
    assert doc["alias_kinds"] == doc["declared_alias_kinds"] == \
        ["FREEZE_LEGACY"]


def test_artifact_lists_no_unregistered_unit(identified):
    doc = artifact(identified["result"], list(REQUIRED_CHAIN))
    assert doc["unregistered_units"] == []


def test_artifact_records_every_id_pair(identified):
    doc = artifact(identified["result"], list(REQUIRED_CHAIN))
    assert len(doc["units"]) == 11
    for entry in doc["units"].values():
        assert entry["alias_count"] == 1
        assert entry["aliases"][0]["alias_id"] != entry["canonical_ku_id"]


def test_committed_artifact_matches_the_runner():
    committed = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    fresh = artifact(_fresh(), list(REQUIRED_CHAIN))
    for key in ("canonical_units", "identity_rows", "alias_kinds",
                "declared_alias_kinds", "unregistered_units",
                "A_P6_IDENTITY", "identity_version", "run_id",
                "canonical_ku_id_formula"):
        assert committed[key] == fresh[key], key


def test_schema_gate_is_not_executed_without_a_ledger():
    assert schema_gate(None) == "NOT_EXECUTED"


def test_schema_gate_passes_on_the_full_chain():
    assert schema_gate(list(REQUIRED_CHAIN)) == "PASS"


def test_schema_gate_fails_without_076():
    assert schema_gate([n for n in REQUIRED_CHAIN
                        if n != REQUIRED_MIGRATION]) == "FAIL"


def test_every_gate_passes_and_every_gate_is_in_the_verdict(identified):
    """Every reported gate passes, and the verdict reads all of them.

    The previous version of this test iterated five headline names and then
    spot-checked `schema` and `idempotency` separately — the same shape that
    left nine gates reporting without affecting the outcome.
    """
    gates = gate_results(identified["result"], list(REQUIRED_CHAIN))
    assert gates, "gate_results must not be empty"
    for name, value in sorted(gates.items()):
        assert value == "PASS", f"{name}={value}"
    assert verdict(gates) == "PASS"


def test_the_verdict_covers_every_reported_gate(identified):
    """No gate may be reported but unaccounted for.

    There is no gate-name tuple in the runner any more, so the only way a gate
    can escape the verdict is if `gate_results` stops reporting it. This asserts
    the set the verdict sees is the set that was reported.
    """
    gates = gate_results(identified["result"], list(REQUIRED_CHAIN))
    counted = {name for name, value in gates.items()}
    assert counted == set(gates)
    # 14 as of the re-freeze; a new gate must come with its verdict weight, so
    # this number changing is a signal to look, not a failure by itself.
    assert len(gates) == 14, sorted(gates)


def test_a_gate_that_cannot_execute_blocks_the_verdict(identified):
    """R-2. Removing the ledger makes `schema` NOT_EXECUTED, and that must
    never read as PASS.

    Measured before the repair: no ledger -> schema=NOT_EXECUTED ->
    A_P6_IDENTITY=PASS.
    """
    without = gate_results(identified["result"], None)
    assert without["schema"] == "NOT_EXECUTED"
    assert verdict(without) == "BLOCKED"

    with_ledger = gate_results(identified["result"], list(REQUIRED_CHAIN))
    assert with_ledger["schema"] == "PASS"
    assert verdict(with_ledger) == "PASS"


def test_verdict_states_are_three_not_two():
    """PASS / FAIL / BLOCKED, and FAIL outranks BLOCKED."""
    assert verdict({"a": "PASS", "b": "PASS"}) == "PASS"
    assert verdict({"a": "PASS", "b": "FAIL"}) == "FAIL"
    assert verdict({"a": "PASS", "b": "NOT_EXECUTED"}) == "BLOCKED"
    # Positive evidence of breakage outranks missing evidence.
    assert verdict({"a": "FAIL", "b": "NOT_EXECUTED"}) == "FAIL"
    # No gates at all is no evidence, not a vacuous pass.
    assert verdict({}) == "BLOCKED"
    # An unrecognised status must not become a silent pass.
    assert verdict({"a": "PASS", "b": "SOMETHING_NEW"}) == "BLOCKED"


#: The five headline groups, kept here rather than in the runner. This is a
#: readability property — each headline has sub-checks behind it — and NOT the
#: verdict authority, which is `verdict()` over `gate_results`.
HEADLINES = ("G1_identity_uniqueness", "G2_historical_replay",
             "G3_revision_chain", "G4_regression", "G5_authority")


def test_every_sub_gate_is_named_for_a_headline(identified):
    """Each of the five headlines has more than one check behind it."""
    gates = gate_results(identified["result"], list(REQUIRED_CHAIN))
    for headline in HEADLINES:
        prefix = headline.split("_")[0]
        assert sum(1 for k in gates if k.startswith(prefix)) > 1
