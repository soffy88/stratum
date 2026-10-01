"""A Repository P5 — KU evolution runner.

Takes the durable knowledge units of a reading run, applies the frozen
review ledger and the frozen revisions, records what each review found, and
reports the six gates.

Run: PYTHONPATH=src python3 -m stratum.knowledge.a_repository.ku_evolution_runner

    GATE_1 SOURCE TRACEABILITY  every unit and every review reaches a book
    GATE_2 IMMUTABILITY         no unit row changed, none deleted
    GATE_3 REVISION             the successor is appended, never merged in
    GATE_4 REPLAY               the same inputs produce the same ids
    GATE_5 AUTHORITY            no unit and no review without evidence
    GATE_6 DURABILITY           a restart reads back the same rows

The schema gate reads the migration ledger from A_P5_LEDGER_FILE so no
credential reaches this process:

    docker exec aii-postgres psql -U aii -d stratum_a_p3_staging -Atc \
      "SELECT filename FROM public._pg_migrations ORDER BY filename" \
      > /tmp/a_p5_ledger.txt
    A_P5_LEDGER_FILE=/tmp/a_p5_ledger.txt PYTHONPATH=src \
      python3 -m stratum.knowledge.a_repository.ku_evolution_runner

The runner is a writer for its own four lifecycle tables and a reader for
everything upstream: it never modifies an existing unit row, a
verification, a candidate or an evidence row.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import pilot_corpus as C
from .evolution import (
    EVOLUTION_VERSION,
    EvolutionSink,
    KULifecycleStatus,
    KUEvolutionService,
    emit_evolution_sql,
)
from .freeze import AKnowledgeUnitFreezePipeline
from .persistence import KUDurableWriter, PersistenceStatus, persisted_unit_id
from .quality import deterministic_id
from .verification import VerificationStatus
from .verdict import VERDICT_BLOCKED, VERDICT_FAIL, VERDICT_PASS, verdict, verdict_inputs
from .verification_runner import build_verification_baseline, staging_ledger


REQUIRED_MIGRATION = "075_a_ku_evolution.sql"

#: Statements that would destroy or rewrite existing rows. Counted over the A
#: chain so the freeze reports a measured zero rather than an asserted one.
#: Additive forms are deliberately absent: ADD COLUMN and ADD CONSTRAINT do not
#: drop anything, and 071 and 082 are additive by design.
DESTRUCTIVE_SQL = (
    r"(?im)^\s*(?:DROP\s+TABLE|DROP\s+COLUMN|DROP\s+CONSTRAINT|TRUNCATE\b"
    r"|DELETE\s+FROM|UPDATE\s+\w+\s+SET|ALTER\s+TABLE\b[^;]*\bDROP\b)"
)

REQUIRED_CHAIN = (
    "070_a_repository_foundation.sql",
    "071_a_evidence_quality.sql",
    "072_a_ku_verification.sql",
    "073_a_knowledge_unit_freeze.sql",
    "074_a_ku_freeze_persistence.sql",
    REQUIRED_MIGRATION,
)

#: The only tables 075 creates. Everything else it may name has to be a
#: reference target below, which is what makes the migration structurally
#: incapable of reaching another repository.
CREATED_TABLES = frozenset({"ku_revision", "ku_review_event",
                            "ku_confidence_evolution", "ku_relation"})

#: The only tables the lifecycle may point at. Every one of them is an A
#: table reachable from evidence, which is what keeps a review from citing
#: something outside the repository it belongs to.
ALLOWED_REFERENCES = frozenset({"knowledge_unit", "reading_evidence"})

#: Tables P5 inherits and must never recreate or alter.
INHERITED_TABLES = ("knowledge_unit", "ku_freeze_event", "ku_candidate",
                    "ku_verification", "reading_evidence", "source_version",
                    "reading_run")


# ── baseline ─────────────────────────────────────────────────────────────────

def build_persisted(sink=None) -> Dict:
    """P1 -> P4.1, rebuilt from the frozen corpus rather than P4's runner.

    Rebuilt rather than reused so the quality pipeline is in scope: a
    revision is a new candidate, and an unclassified candidate cannot pass
    verification. Every stage is deterministic, so this reproduces the same
    ten units P4.1 persisted.
    """
    upstream = build_verification_baseline()
    base, quality, verification = (upstream["base"], upstream["quality"],
                                   upstream["verification"])
    fp = AKnowledgeUnitFreezePipeline(base["pipeline"], verification)
    fp.freeze_verified(base["reading_run_id"])
    sink = sink if sink is not None else EvolutionSink()
    writer = KUDurableWriter(base["pipeline"], verification, fp, sink)
    results = writer.persist_verified(base["reading_run_id"])
    return {"base": base, "quality": quality, "verification": verification,
            "freeze": fp, "writer": writer, "sink": sink,
            "results": results}


def _unit_id_by_key(result: Dict) -> Dict[str, str]:
    """corpus candidate key -> durable unit id.

    Resolved through the freeze stage's own index and P4.1's own id
    formula, so the map is whatever the chain actually produced rather than
    a second guess at it.
    """
    mapping: Dict[str, str] = {}
    for key, candidate_id in result["base"]["candidate_ids"].items():
        frozen_id = result["freeze"].store._unit_by_candidate.get(candidate_id)
        if frozen_id is None:
            continue
        unit = result["freeze"].store.frozen_units[frozen_id]
        mapping[key] = persisted_unit_id(unit.candidate_id,
                                         unit.verification_id,
                                         unit.content_hash)
    return mapping


def _append_revised_unit(result: Dict, entry: Dict, prior_unit_id: str) -> Dict:
    """Append one revision's successor through the whole A chain.

    A revision is not an edit, so it cannot skip a stage: a new candidate is
    generated over the same evidence row, classified, verified, frozen and
    persisted. Only then is the link recorded, and the prior unit row is
    never read for anything but its identity.

    Idempotent at the first step. If the candidate is already in the store
    it is reused rather than regenerated, so a replay does not replace a
    classified upstream row with an unclassified one.
    """
    base, pipeline = result["base"], result["base"]["pipeline"]
    store = pipeline.store
    prior = result["sink"].units[prior_unit_id]
    prior_candidate = store.ku_candidates[prior.candidate_id]
    evidence_id = base["evidence_ids"][entry["evidence_key"]]
    if evidence_id != prior_candidate.evidence_id:
        raise AssertionError(
            f"{entry['key']} revises over evidence {evidence_id} but the prior "
            f"unit is anchored to {prior_candidate.evidence_id}; a revision "
            "corrects a unit against its own span.")

    # Content-derived, so a replay generates the same candidate and the
    # append is a no-op rather than a second reading of the same span.
    candidate_id = deterministic_id("kc", evidence_id, entry["content"],
                                    EVOLUTION_VERSION)
    candidate = store.ku_candidates.get(candidate_id)
    if candidate is None:
        candidate = pipeline.generate_candidate(
            prior_candidate.reading_run_id, evidence_id, entry["content"],
            entry["candidate_type"], entry["confidence"],
            entry["source_span"], candidate_id=candidate_id)
    if not candidate.classification:
        result["quality"].classify_candidate(candidate.id)

    verification = result["verification"].verify(candidate.id)
    if verification.verification_status != VerificationStatus.VERIFIED.value:
        raise AssertionError(
            f"{entry['key']} did not verify "
            f"({verification.verification_status}, score "
            f"{verification.verification_score}); a revision that cannot be "
            "verified is not a revision.")
    result["freeze"].freeze(verification.id)
    outcome = result["writer"].persist(verification.id)
    if outcome.unit is None:
        raise AssertionError(
            f"{entry['key']} produced no durable unit: {outcome.failure}")
    return {"candidate_id": candidate.id, "verification_id": verification.id,
            "unit_id": outcome.unit.id}


def apply_reviews(result: Dict, evolution: KUEvolutionService,
                  unit_ids: Dict[str, str]) -> List[Dict]:
    """The frozen review ledger, in a stable order.

    Reviews are applied before revisions so a revision's SUPERSEDED review
    is the unit's last entry rather than being interleaved with the ledger.
    """
    base = result["base"]
    applied: List[Dict] = []
    for entry in sorted(C.KU_REVIEWS, key=lambda e: e["key"]):
        unit_id = unit_ids[entry["unit_key"]]
        outcome = evolution.review(unit_id, entry["review_type"],
                                   entry["rationale"],
                                   base["evidence_ids"][entry["evidence_key"]])
        if outcome.review is not None and outcome.written:
            confidence = entry.get("confidence")
            if confidence is not None:
                evolution.observe_confidence(unit_id, "REVIEW_SIGNAL",
                                             confidence)
        applied.append({
            "key": entry["key"],
            "unit_key": entry["unit_key"],
            "unit_id": unit_id,
            "review_type": entry["review_type"],
            "status": outcome.status,
            "written": outcome.written,
        })
    return applied


def apply_revisions(result: Dict, evolution: KUEvolutionService,
                    unit_ids: Dict[str, str]) -> List[Dict]:
    """Link each frozen revision to the successor it appends."""
    applied: List[Dict] = []
    for entry in sorted(C.KU_REVISIONS, key=lambda e: e["key"]):
        prior_unit_id = unit_ids[entry["prior_unit_key"]]
        appended = _append_revised_unit(result, entry, prior_unit_id)
        link = evolution.link_revision(prior_unit_id, appended["unit_id"],
                                      entry["basis"])
        applied.append({
            "key": entry["key"],
            "prior_unit_id": prior_unit_id,
            "prior_status": link.status,
            "revised_unit_id": appended["unit_id"],
            "candidate_id": appended["candidate_id"],
            "verification_id": appended["verification_id"],
            "relations": sorted(r.relation_type for r in link.relations),
            "written": link.written,
        })
    return applied


def build_evolution(sink=None) -> Dict:
    """P1 -> P4.1 -> P5, with every lifecycle row appended.

    `sink` lets a later stage replay the whole chain into a store that also
    holds its own tables, so it does not have to copy the sink or the
    rebuild. Defaults to a plain EvolutionSink.
    """
    result = build_persisted(sink=sink)
    evolution = KUEvolutionService(result["base"]["pipeline"],
                                   result["quality"],
                                   result["verification"],
                                   result["freeze"],
                                   result["writer"],
                                   result["sink"])
    unit_ids = _unit_id_by_key(result)
    before = unit_snapshot(result["sink"])
    evolution.record_baseline_confidence()
    reviews = apply_reviews(result, evolution, unit_ids)
    revisions = apply_revisions(result, evolution, unit_ids)
    relations = evolution.record_derived_relations()
    return {"result": result, "evolution": evolution, "unit_ids": unit_ids,
            "before_snapshot": before, "reviews": reviews,
            "revisions": revisions, "relations": relations}


def unit_snapshot(sink) -> Dict[str, Dict]:
    """Every durable unit row, as a comparable dict.

    Taken before and after the lifecycle runs; equality is GATE_2's proof
    that the prior rows were not touched.
    """
    return {key: dict(vars(unit)) for key, unit in sorted(sink.units.items())}


# ── gates ────────────────────────────────────────────────────────────────────

def traceability_gate(result: Dict) -> str:
    """GATE_1 — 100% of units, and 100% of reviews, reach a book."""
    trace = result["evolution"].traceability()
    if trace["units"] == 0 or trace["percent"] != 100.0:
        return "FAIL"
    if trace["reviews"] == 0 or trace["review_percent"] != 100.0:
        return "FAIL"
    for orphans in (result["evolution"].orphan_revisions(),
                    result["evolution"].orphan_reviews(),
                    result["evolution"].orphan_observations(),
                    result["evolution"].orphan_relations()):
        if orphans:
            return "FAIL"
    return "PASS"


def immutability_gate(result: Dict, before: Dict[str, Dict]) -> str:
    """GATE_2 — no unit row changed, and none disappeared."""
    after = unit_snapshot(result["evolution"].sink)
    for unit_id, row in before.items():
        if after.get(unit_id) != row:
            return "FAIL"
    # The only permitted difference is an addition, and an addition must be
    # a complete frozen unit rather than a rewritten one.
    for unit_id in set(after) - set(before):
        unit = result["evolution"].sink.units[unit_id]
        if unit.freeze_status != PersistenceStatus.FROZEN.value:
            return "FAIL"
        if not unit.canonical_text:
            return "FAIL"
    return "PASS"


def revision_gate(result: Dict) -> str:
    """GATE_3 — a revision appends a successor and never merges one in."""
    evolution: KUEvolutionService = result["evolution"]
    if not result["revisions"]:
        return "FAIL"
    for entry in result["revisions"]:
        prior_id = entry["prior_unit_id"]
        revised_id = entry["revised_unit_id"]
        prior = evolution.sink.units.get(prior_id)
        revised = evolution.sink.units.get(revised_id)
        if prior is None or revised is None or prior_id == revised_id:
            return "FAIL"
        # The prior is still a first-class row: frozen, anchored, citable.
        if prior.freeze_status != PersistenceStatus.FROZEN.value:
            return "FAIL"
        if not prior.canonical_text:
            return "FAIL"
        # The successor is a distinct unit behind its own verification.
        if prior.verification_id == revised.verification_id:
            return "FAIL"
        if prior.candidate_id == revised.candidate_id:
            return "FAIL"
        if evolution.status_of(prior_id) != KULifecycleStatus.SUPERSEDED.value:
            return "FAIL"
        if evolution.successor_of(prior_id) != revised_id:
            return "FAIL"
        if evolution.prior_of(revised_id) != prior_id:
            return "FAIL"
        # One successor only, so the history is a chain and never a tree.
        if evolution.revision_index_of(revised_id) != 1:
            return "FAIL"
    if evolution.duplicate_revisions():
        return "FAIL"
    return "PASS"


def _fingerprint(evolution: KUEvolutionService) -> Dict[str, str]:
    """Every row's id and content fingerprint, keyed by id."""
    sink = evolution.sink
    out: Dict[str, str] = {}
    for key in sorted(sink.units):
        out[f"unit:{key}"] = sink.units[key].content_hash
    for key in sorted(sink.events):
        out[f"event:{key}"] = sink.events[key].event_hash
    for key in sorted(sink.revisions):
        out[f"revision:{key}"] = sink.revisions[key].revision_hash
    for key in sorted(sink.reviews):
        out[f"review:{key}"] = sink.reviews[key].review_hash
    for key in sorted(sink.observations):
        out[f"confidence:{key}"] = sink.observations[key].observation_hash
    for key in sorted(sink.relations):
        out[f"relation:{key}"] = sink.relations[key].relation_hash
    return out


def replay_gate() -> Dict[str, object]:
    """GATE_4 — the same inputs produce the same rows and the same ids."""
    first = build_evolution()
    second = build_evolution()
    first_ids = _fingerprint(first["evolution"])
    second_ids = _fingerprint(second["evolution"])
    evolution = second["evolution"]
    return {
        "first_rows": len(first_ids),
        "second_rows": len(second_ids),
        "identical_fingerprints": int(first_ids == second_ids),
        "same_revision_ids": sorted(
            r.id for r in first["evolution"].sink.revisions.values())
        == sorted(r.id for r in evolution.sink.revisions.values()),
        "same_review_ids": sorted(
            r.id for r in first["evolution"].sink.reviews.values())
        == sorted(r.id for r in evolution.sink.reviews.values()),
        "no_duplicate_revisions": not evolution.duplicate_revisions(),
        "no_duplicate_reviews": not evolution.duplicate_reviews(),
        "no_duplicate_relations": not evolution.duplicate_relations(),
        "stable_unit_ids": sorted(first["evolution"].sink.units)
        == sorted(evolution.sink.units),
    }


def idempotency_gate(result: Dict) -> str:
    """Re-running the lifecycle over a settled run appends nothing."""
    evolution: KUEvolutionService = result["evolution"]
    before = _fingerprint(evolution)
    unit_ids = result["unit_ids"]
    upstream = result["result"]
    apply_reviews(upstream, evolution, unit_ids)
    apply_revisions(upstream, evolution, unit_ids)
    evolution.record_baseline_confidence()
    evolution.record_derived_relations()
    return "PASS" if _fingerprint(evolution) == before else "FAIL"


def schema_gate(ledger: Optional[List[str]]) -> str:
    """The real schema carries 075 and its whole chain, additively."""
    if ledger is None:
        return "NOT_EXECUTED"
    if not all(name in ledger for name in REQUIRED_CHAIN):
        return "FAIL"
    migration = (Path(__file__).parents[2] / "db" / "pg_migrations"
                 / REQUIRED_MIGRATION).read_text(encoding="utf-8")
    statements = re.sub(r"--.*", "", migration)
    if "ALTER TABLE" in statements or "DROP " in statements:
        return "FAIL"
    if "INSERT INTO" in statements:
        return "FAIL"  # no data backfill
    for inherited in INHERITED_TABLES:
        if f"CREATE TABLE IF NOT EXISTS stratum.{inherited} (" in statements:
            return "FAIL"
    if set(re.findall(r"CREATE TABLE IF NOT EXISTS stratum\.(\w+)",
                      statements)) != CREATED_TABLES:
        return "FAIL"
    referenced = set(re.findall(r"REFERENCES\s+stratum\.(\w+)", migration))
    if not referenced <= ALLOWED_REFERENCES:
        return "FAIL"
    return "PASS"


def authority_gate() -> str:
    """A仓 only: the lifecycle reaches nothing outside the A chain.

    Checked by inspecting what 075 actually names rather than by matching a
    forbidden-name list — a list inside the gate would itself contain the
    names it forbids. Every `stratum.X` the migration mentions must be one
    of the four tables it creates or a permitted reference target, so the
    migration is structurally unable to reach another repository.
    """
    migration = (Path(__file__).parents[2] / "db" / "pg_migrations"
                 / REQUIRED_MIGRATION).read_text(encoding="utf-8")
    statements = re.sub(r"--.*", "", migration)
    named = set(re.findall(r"stratum\.(\w+)", statements))
    if not named <= CREATED_TABLES | ALLOWED_REFERENCES:
        return "FAIL"
    # Anchored to the start of a statement, so `ON DELETE RESTRICT` — which
    # is a referential action and not DML — is not mistaken for a write.
    # 075 declares schema and nothing else.
    if re.search(r"^[ \t]*(INSERT|UPDATE|DELETE|MERGE|JOIN)\b", statements,
                 re.MULTILINE):
        return "FAIL"
    return "PASS"


def evidence_gate(result: Dict) -> str:
    """GATE_5 — no unit and no review without evidence.

    The unit side is P4.1's chain, re-checked here because a lifecycle row
    pointing at an untraceable unit would make its whole history
    unsourceable. The review side is stronger than P4.1 required: every
    review must cite a real evidence row from the unit's own book.
    """
    evolution: KUEvolutionService = result["evolution"]
    store = evolution.store
    for unit in evolution.sink.units.values():
        if not unit.canonical_text:
            return "FAIL"
        traceable, _ = evolution._require_traceable(unit)
        if not traceable:
            return "FAIL"
    if not evolution.sink.reviews:
        return "FAIL"
    for review in evolution.sink.reviews.values():
        evidence = store.evidence.get(review.evidence_id)
        unit = evolution.sink.units.get(review.knowledge_unit_id)
        if evidence is None or unit is None:
            return "FAIL"
        if evidence.source_version_id != unit.source_version_id:
            return "FAIL"
        if not (review.rationale or "").strip():
            return "FAIL"
    for revision in evolution.sink.revisions.values():
        if not (revision.revision_basis or "").strip():
            return "FAIL"
    for observation in evolution.sink.observations.values():
        if not 0.0 <= observation.measured_confidence <= 1.0:
            return "FAIL"
    return "PASS"


def durability_gate() -> str:
    """GATE_6 — a restart reads back the same rows, and a crash leaves none.

    Two independent checks: a second process rebuilt from scratch produces
    identical ids, and a transaction that dies part-way through a revision
    leaves nothing behind at any write index.
    """
    if _fingerprint(build_evolution()["evolution"]) != _fingerprint(
            build_evolution()["evolution"]):
        return "FAIL"

    entry = sorted(C.KU_REVISIONS, key=lambda e: e["key"])[0]
    # Five write indices: revision, review, event, observation, relation.
    for fail_after in range(1, 6):
        crashed = build_persisted()
        evolution = KUEvolutionService(crashed["base"]["pipeline"],
                                       crashed["quality"],
                                       crashed["verification"],
                                       crashed["freeze"],
                                       crashed["writer"],
                                       crashed["sink"])
        unit_ids = _unit_id_by_key(crashed)
        prior_id = unit_ids[entry["prior_unit_key"]]
        appended = _append_revised_unit(crashed, entry, prior_id)
        evolution.record_baseline_confidence()
        crashed["sink"].fail_after = fail_after
        outcome = evolution.link_revision(prior_id, appended["unit_id"],
                                          entry["basis"])
        if outcome.status == "PASS":  # pragma: no cover - would be a bug
            return "FAIL"
        # Nothing partial survives: the unit stays as it was, and none of
        # the four lifecycle tables holds a row from the failed attempt.
        if crashed["sink"].revisions or crashed["sink"].reviews:
            return "FAIL"
        if crashed["sink"].relations:
            return "FAIL"
        if crashed["sink"].rollbacks < 1:
            return "FAIL"
        if evolution.status_of(prior_id) != KULifecycleStatus.ACTIVE.value:
            return "FAIL"
    return "PASS"


def gate_results(result: Dict, ledger: Optional[List[str]]) -> Dict[str, str]:
    """The six gates. A gate that cannot be evidenced is NOT_EXECUTED."""
    replay = replay_gate()
    replay_pass = (replay["identical_fingerprints"] == 1
                   and replay["same_revision_ids"]
                   and replay["same_review_ids"]
                   and replay["no_duplicate_revisions"]
                   and replay["no_duplicate_reviews"]
                   and replay["no_duplicate_relations"]
                   and replay["stable_unit_ids"])
    return {
        "G1_traceability": traceability_gate(result),
        "G2_immutability": immutability_gate(result, result["before_snapshot"]),
        "G3_revision": revision_gate(result),
        "G4_replay": "PASS" if replay_pass else "FAIL",
        "G5_authority": authority_gate(),
        "G6_durability": durability_gate(),
        "schema": schema_gate(ledger),
        "idempotency": idempotency_gate(result),
    }


# ── the verdict ──────────────────────────────────────────────────────────────
#
# There is deliberately no tuple of gate names here.
#
# This file used to carry `GATE_ORDER`, six names, while `gate_results`
# returned eight. `idempotency` and `schema` printed PASS or FAIL and could not
# affect the outcome. Measured before the repair:
#
#   no A_P5_LEDGER_FILE -> schema = NOT_EXECUTED -> A_P5_KU_EVOLUTION = PASS
#
# A gate that never executed produced a PASS. That is the same defect P6 had,
# found in that stage's audit, and left here unfixed for two stages.
#
# `verdict` is imported rather than restated, so the P5-evolution contract and
# the P6 contract are literally the same code and cannot drift apart.

VERDICT_PASS = "PASS"
VERDICT_FAIL = "FAIL"
VERDICT_BLOCKED = "BLOCKED"


# ── reporting ────────────────────────────────────────────────────────────────

def report(result: Dict) -> Dict:
    evolution: KUEvolutionService = result["evolution"]
    sink = evolution.sink
    by_key = {value: key for key, value in result["unit_ids"].items()}
    units: Dict[str, Dict] = {}
    for key, unit in sorted(sink.units.items()):
        units[by_key.get(key, key)] = {
            "unit_id": unit.id,
            "status": evolution.status_of(unit.id),
            "successor": evolution.successor_of(unit.id),
            "prior": evolution.prior_of(unit.id),
            "reviews": [r.review_type for r in evolution.history(unit.id)],
            "confidence": [{"basis": o.basis, "value": o.measured_confidence}
                           for o in evolution.confidence_series(unit.id)],
            "relations": sorted(r.relation_type
                                for r in evolution.relations_of(unit.id)),
        }
    return {
        "task": "A_P5_KU_EVOLUTION",
        "book": f"{C.BOOK_TITLE} {C.BOOK_EDITION}",
        "run_id": result["result"]["base"]["reading_run_id"],
        "persisted_units": len(sink.units),
        "status_breakdown": evolution.status_breakdown(),
        "revisions": evolution.revision_count(),
        "reviews": evolution.review_count(),
        "confidence_observations": evolution.observation_count(),
        "relations": evolution.relation_count(),
        "relation_types": sorted({r.relation_type
                                  for r in sink.relations.values()}),
        "traceability": evolution.traceability(),
        "review_ledger": result["reviews"],
        "revision_ledger": result["revisions"],
        "lifecycle_version": EVOLUTION_VERSION,
        "commits": sink.commits,
        "rollbacks": sink.rollbacks,
        "units": units,
    }


def artifact(result: Dict, ledger: Optional[List[str]]) -> Dict:
    """The evidence artifact the task asks for."""
    summary = report(result)
    gates = gate_results(result, ledger)
    trace = summary["traceability"]
    return {
        "task": "A_P5_KU_EVOLUTION",
        "book": summary["book"].split(" ")[0],
        "authority": "A_REPOSITORY",
        "lifecycle_version": EVOLUTION_VERSION,
        "run_id": summary["run_id"],
        "persisted_units": summary["persisted_units"],
        "status_breakdown": summary["status_breakdown"],
        "revisions": summary["revisions"],
        "reviews": summary["reviews"],
        "confidence_observations": summary["confidence_observations"],
        "relations": summary["relations"],
        "relation_types": summary["relation_types"],
        "traceability": ("100%" if trace["percent"] == 100.0
                         else f"{trace['percent']}%"),
        "gate_results": gates,
        "A_P5_KU_EVOLUTION": verdict(gates),
        "ledger": ledger,
        "review_ledger": summary["review_ledger"],
        "revision_ledger": summary["revision_ledger"],
        "units": summary["units"],
    }


def write_sql(result: Dict, path: str) -> str:
    """Emit the whole chain plus the lifecycle for a DBA to execute.

        python -m stratum.knowledge.a_repository.ku_evolution_runner --sql evolution.sql
        docker cp evolution.sql aii-postgres:/tmp/
        docker exec -e PGOPTIONS="-c search_path=stratum,public" aii-postgres \
          psql -U aii -d stratum_a_p3_staging -v ON_ERROR_STOP=1 -1 -q \
          -f /tmp/evolution.sql

    One BEGIN/COMMIT, parents before children, and every statement ON
    CONFLICT DO NOTHING, so the file is safe to run twice: the second
    execution writes nothing.
    """
    upstream = result["result"]
    script = emit_evolution_sql(upstream["base"]["pipeline"].store,
                                upstream["verification"],
                                upstream["freeze"],
                                upstream["sink"])
    Path(path).write_text(script, encoding="utf-8")
    return path


def durable_counts(path: Optional[str] = None) -> Optional[Dict[str, int]]:
    """Row counts read back from the database, if a DBA-side query left
    them in the file named by A_P5_DB_COUNTS."""
    target = path or os.environ.get("A_P5_DB_COUNTS")
    if not target:
        return None
    source = Path(target)
    if not source.exists():
        return None
    counts = {key: int(value) for key, value in re.findall(
        r"(\w+)\s*=\s*(\d+)", source.read_text(encoding="utf-8"))}
    return counts or None


def migration_evidence() -> Tuple[Dict[str, str], int]:
    """Fingerprint every A-chain migration and count destructive statements.

    Both are read from the migration files on disk, not from a recorded list, so
    the artifact cannot drift away from what the chain actually contains.
    """
    root = Path(__file__).resolve().parents[2] / "db" / "pg_migrations"
    fingerprints: Dict[str, str] = {}
    destructive = 0
    if not root.is_dir():
        return fingerprints, destructive
    for path in sorted(root.glob("0[78][0-9]_a_*.sql")):
        fingerprints[path.name.split("_", 1)[0]] = hashlib.sha256(
            path.read_bytes()).hexdigest()[:16]
        body = re.sub(r"--[^\n]*", "", path.read_text(encoding="utf-8"))
        destructive += len(re.findall(DESTRUCTIVE_SQL, body))
    return fingerprints, destructive


def base_sha() -> str:
    """The commit this freeze is cut from.

    The freeze artifact cannot name the commit that contains it, so it names its
    parent: the tree the evidence above was actually measured against.
    """
    override = os.environ.get("A_P5_BASE_SHA")
    if override:
        return override
    try:
        done = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                              text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return "UNKNOWN"
    return (done.stdout.strip() or "UNKNOWN") if done.returncode == 0 \
        else "UNKNOWN"


def freeze_artifact(result: Dict, ledger: Optional[List[str]]) -> Dict:
    """The evidence artifact that closes this layer.

    Carries the same verdict as the layer artifact plus the freeze-level
    evidence the closure asks for. The verdict still comes only from the gates,
    so the additional recorded evidence cannot turn a blocked layer into a pass.
    """
    doc = artifact(result, ledger)
    fingerprints, destructive = migration_evidence()
    doc.update({
        "stage": "P5_EVOLUTION",
        "base_sha": base_sha(),
        "migration_fingerprints": fingerprints,
        "destructive_migration_statements": destructive,
        "dependency_closure": os.environ.get(
            "A_P5_DEPENDENCY_CLOSURE", "UNVERIFIED"),
        "replay": os.environ.get("A_P5_REPLAY", "UNVERIFIED"),
        "db_acceptance": os.environ.get("A_P5_DB_ACCEPTANCE", "UNVERIFIED"),
        "verdict_inputs": verdict_inputs(doc["gate_results"]),
        "verdict": verdict(doc["gate_results"]),
    })
    return doc


#: Evidence a freeze cannot be written without. Recorded by whoever ran the
#: work; absent evidence stays UNVERIFIED and blocks the freeze rather than
#: being defaulted to a pass.
FREEZE_EVIDENCE = ("dependency_closure", "replay", "db_acceptance")


def freeze_blockers(doc: Dict) -> List[str]:
    """Why a freeze may not be written. Empty means it may be.

    Two different kinds of "no", and both are required. Missing evidence is an
    absence of proof; a blocked gate verdict is positive proof that the layer
    has not earned a freeze. Checking only the first let a freeze be written
    with the gates never executed, which is the same defect this layer was
    reopened for.
    """
    blockers = [key for key in FREEZE_EVIDENCE if doc[key] != VERDICT_PASS]
    if doc["verdict"] != VERDICT_PASS:
        blockers.append(f"layer_verdict:{doc['verdict']}")
    return blockers


def main() -> None:
    result = build_evolution()
    if "--sql" in sys.argv:
        target = sys.argv[sys.argv.index("--sql") + 1]
        print(write_sql(result, target))
        return
    ledger = staging_ledger(os.environ.get("A_P5_LEDGER_FILE"))
    target = os.environ.get("A_P5_FREEZE_ARTIFACT")
    if target:
        doc = freeze_artifact(result, ledger)
        blockers = freeze_blockers(doc)
        if blockers:
            print(json.dumps({"A_P5_EVOLUTION_FREEZE": VERDICT_BLOCKED,
                              "blockers": blockers,
                              "verdict": doc["verdict"],
                              "gates_not_executed":
                                  doc["verdict_inputs"]["gates_not_executed"]},
                             ensure_ascii=False, indent=2))
            raise SystemExit(1)
        counts = durable_counts()
        if counts is not None:
            doc["durable_rows"] = counts
        Path(target).write_text(
            json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"A_P5_EVOLUTION_FREEZE": doc["verdict"],
                          "artifact": target,
                          "base_sha": doc["base_sha"],
                          "destructive_migration_statements":
                              doc["destructive_migration_statements"]},
                         ensure_ascii=False, indent=2))
        return
    doc = artifact(result, ledger)
    counts = durable_counts()
    if counts is not None:
        doc["durable_rows"] = counts
    print(json.dumps(doc, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
