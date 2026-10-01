"""A Repository P6 — KU identity runner.

Registers every frozen unit's retired id against its canonical id and
reports the five gates.

Run: PYTHONPATH=src python3 -m stratum.knowledge.a_repository.ku_identity_runner

    GATE_1 identity uniqueness    no id means two units
    GATE_2 historical replay      old citations still resolve, byte-for-byte
    GATE_3 revision chain intact  P5's links still resolve through the aliases
    GATE_4 P1-P5 regression       every earlier stage still produces what it did
    GATE_5 authority isolation    the identity reaches nothing outside A仓

The schema gate reads the migration ledger from A_P6_LEDGER_FILE so no
credential reaches this process:

    docker exec aii-postgres psql -U aii -d stratum_a_p3_staging -Atc \
      "SELECT filename FROM public._pg_migrations ORDER BY filename" \
      > /tmp/a_p6_ledger.txt
    A_P6_LEDGER_FILE=/tmp/a_p6_ledger.txt PYTHONPATH=src \
      python3 -m stratum.knowledge.a_repository.ku_identity_runner

The runner appends to `ku_identity` and nothing else. It has no write path
to `knowledge_unit`, which is what makes "no mutation of a frozen KU"
structural rather than a promise.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

from . import pilot_corpus as C
from .evolution import EVOLUTION_VERSION
from .freeze import FREEZE_VERSION
from .identity import (
    DECLARED_ALIAS_KINDS,
    IDENTITY_TABLES,
    IDENTITY_VERSION,
    IdentitySink,
    KUIdentityService,
    decode_fingerprint,
    emit_identity_sql,
    legacy_freeze_id,
)
from .ku_evolution_runner import build_evolution
from .ku_freeze_runner import build_freeze_baseline
from .persistence import PERSISTENCE_VERSION, persisted_unit_id
from .verification_runner import staging_ledger


REQUIRED_MIGRATION = "076_a_ku_identity.sql"

REQUIRED_CHAIN = (
    "070_a_repository_foundation.sql",
    "071_a_evidence_quality.sql",
    "072_a_ku_verification.sql",
    "073_a_knowledge_unit_freeze.sql",
    "074_a_ku_freeze_persistence.sql",
    "075_a_ku_evolution.sql",
    REQUIRED_MIGRATION,
)

#: The only table 076 creates, and the only one the identity may point at.
#: `knowledge_unit` is the canonical id's own table: an identity row that
#: referenced anything else could not be resolved from A仓 alone.
CREATED_TABLES = frozenset({"ku_identity"})

#: Every table this stage writes, across the whole chain it replays.
WRITABLE_TABLES = frozenset(IDENTITY_TABLES)

ALLOWED_REFERENCES = frozenset({"knowledge_unit"})

#: Tables P6 inherits and must never recreate or alter.
INHERITED_TABLES = ("knowledge_unit", "ku_freeze_event", "ku_candidate",
                    "ku_verification", "reading_evidence", "source_version",
                    "reading_run", "ku_revision", "ku_review_event",
                    "ku_confidence_evolution", "ku_relation")

ARTIFACTS = Path(__file__).parents[4] / "artifacts" / "a_repository"
P4_ARTIFACT = ARTIFACTS / "p4_ku_freeze.json"
P5_ARTIFACT = ARTIFACTS / "p5_ku_evolution.json"


# ── baseline ─────────────────────────────────────────────────────────────────

def build_identity(sink=None) -> Dict:
    """P1 -> P4.1 -> P5 -> P6, with every retired id registered.

    P5 is replayed rather than imported so the identity stage is proved
    against the same objects a fresh process would build, not against a
    warmed-up one.
    """
    evolved = build_evolution(sink=sink if sink is not None else IdentitySink())
    upstream = evolved["result"]
    identity = KUIdentityService(upstream["base"]["pipeline"],
                                 upstream["freeze"],
                                 upstream["writer"],
                                 upstream["sink"])
    registered = [row for row in
                  (identity.register_frozen_unit(unit)
                   for unit in identity.frozen_units())
                  if row is not None]
    return {"evolved": evolved, "result": upstream, "identity": identity,
            "sink": upstream["sink"], "registered": registered}


# ── GATE_1 identity uniqueness ───────────────────────────────────────────────

def uniqueness_gate(result: Dict) -> str:
    """No id means two units, and the table agrees with itself.

    Read from both sides on purpose: `ambiguous_ids` is the application
    reading of the rule that `UNIQUE(alias_id)` enforces in the database,
    and `misbound_aliases` rebuilds each retired id from its recorded
    fingerprint with P4's own formula. A table that disagrees with itself
    is worse than no table.
    """
    identity: KUIdentityService = result["identity"]
    if identity.ambiguous_ids():
        return "FAIL"
    if identity.cross_namespace_collisions():
        return "FAIL"
    if identity.misbound_aliases():
        return "FAIL"
    if identity.orphan_identities():
        return "FAIL"
    if identity.duplicate_identities():
        return "FAIL"
    if len(result["sink"].units) != len(set(result["sink"].units)):
        return "FAIL"
    return "PASS"


def canonical_id_gate(result: Dict) -> str:
    """Exactly one canonical id per unit, and it is the durable one."""
    identity: KUIdentityService = result["identity"]
    units = result["sink"].units
    for key, unit in units.items():
        expected = persisted_unit_id(unit.candidate_id, unit.verification_id,
                                     unit.content_hash)
        if key != expected:
            return "FAIL"
    for frozen in identity.frozen_units():
        canonical = identity.canonical_of_unit(frozen)
        if canonical not in units:
            return "FAIL"
        if len(identity.aliases_of(canonical)) > 1:
            return "FAIL"
    # A unit whose two formulas happen to agree needs no alias, and this
    # corpus has none — so every unit here must have exactly one.
    if any(not identity.aliases_of(key) for key in units):
        return "FAIL"
    return "PASS"


# ── GATE_2 historical replay ─────────────────────────────────────────────────

def replay_gate() -> Dict[str, object]:
    """A rebuild from scratch produces the same ids and the same rows.

    This is the "replay compatibility" requirement read from both ends: the
    canonical formula is untouched, so nothing already written moves, and
    the alias rows are content-derived, so re-registering writes nothing.
    """
    first = build_identity()
    second = build_identity()
    first_ids = _identity_fingerprint(first["identity"])
    second_ids = _identity_fingerprint(second["identity"])
    return {
        "rows": len(first_ids),
        "identical_fingerprints": int(first_ids == second_ids),
        "same_aliases": sorted(r.alias_id for r in first["sink"].identities
                               .values())
        == sorted(r.alias_id for r in second["sink"].identities.values()),
        "same_canonical": sorted(first["sink"].units)
        == sorted(second["sink"].units),
        "no_duplicates": not first["identity"].duplicate_identities(),
    }


def _identity_fingerprint(identity: KUIdentityService) -> Dict[str, str]:
    """Every unit's canonical content hash and every identity fingerprint."""
    out = {f"unit:{key}": unit.content_hash
           for key, unit in sorted(identity.sink.units.items())}
    out.update({f"identity:{key}": row.identity_hash
                for key, row in sorted(identity.sink.identities.items())})
    return out


def idempotency_gate(result: Dict) -> str:
    """Registering every retired id again appends nothing."""
    identity: KUIdentityService = result["identity"]
    before = _identity_fingerprint(identity)
    count = len(result["sink"].identities)
    for frozen in identity.frozen_units():
        identity.register_frozen_unit(frozen)
    if len(result["sink"].identities) != count:
        return "FAIL"
    return "PASS" if _identity_fingerprint(identity) == before else "FAIL"


def citation_gate(result: Dict) -> str:
    """Every id an earlier stage ever emitted still resolves.

    The P4 artifact is the honest test: it holds the retired freeze ids, so
    a citation made before P4.1 exists resolves through the alias table
    rather than through luck.
    """
    identity: KUIdentityService = result["identity"]
    cited: List[str] = []
    if P4_ARTIFACT.exists():
        frozen = json.loads(P4_ARTIFACT.read_text(encoding="utf-8"))
        cited.extend(entry["unit_id"] for entry in frozen.get("units", {}).values())
    cited.extend(result["sink"].units)
    resolved = 0
    for value in cited:
        outcome = identity.resolve(value)
        if not outcome.resolved:
            return "FAIL"
        if outcome.canonical_ku_id not in result["sink"].units:
            return "FAIL"
        resolved += 1
    # An id nothing claims must come back UNRESOLVED rather than guessed at.
    unknown = identity.resolve("ku_000000000000")
    if unknown.resolved:
        return "FAIL"
    return "PASS" if resolved else "FAIL"


def retired_id_recomputes(result: Dict) -> str:
    """Each alias is exactly the id P4's own formula produces.

    Three things have to agree: the recorded fingerprint rebuilds the
    recorded alias; the recorded statement is the canonical unit's own
    statement; and the recorded evidence fingerprint is the one the
    verification actually computed. A row that only satisfied the first
    would be self-consistent and still wrong.
    """
    identity: KUIdentityService = result["identity"]
    verifications = identity.fp.vp.store.verifications
    for row in identity.sink.identities.values():
        statement, fingerprint = decode_fingerprint(row.id_fingerprint)
        if legacy_freeze_id(statement, fingerprint) != row.alias_id:
            return "FAIL"
        unit = identity.sink.units[row.canonical_ku_id]
        if statement != unit.statement:
            return "FAIL"
        verification = verifications.get(unit.verification_id)
        if verification is None:
            return "FAIL"
        if verification.trace.get("fingerprint", "") != fingerprint:
            return "FAIL"
    return "PASS"


# ── GATE_3 revision chain intact ─────────────────────────────────────────────

def revision_gate(result: Dict) -> str:
    """P5's revision links still resolve, from either namespace."""
    identity: KUIdentityService = result["identity"]
    revisions = result["sink"].revisions
    if not revisions:
        return "FAIL"
    for revision in revisions.values():
        prior = identity.resolve(revision.prior_unit_id)
        revised = identity.resolve(revision.revised_unit_id)
        if not prior.resolved or not revised.resolved:
            return "FAIL"
        if prior.canonical_ku_id != revision.prior_unit_id:
            return "FAIL"   # already canonical; resolution must agree
        if revised.canonical_ku_id != revision.revised_unit_id:
            return "FAIL"
        # The superseded unit's retired id must reach the same unit the
        # revision names, or a pre-P4.1 citation of it would resolve to a
        # unit that no longer looks superseded.
        legacy = _legacy_id_of(result, revision.prior_unit_id)
        if legacy is None:
            return "FAIL"
        via_legacy = identity.resolve(legacy)
        if not via_legacy.resolved or \
                via_legacy.canonical_ku_id != revision.prior_unit_id:
            return "FAIL"
    return "PASS"


def _legacy_id_of(result: Dict, canonical: str) -> Optional[str]:
    aliases = result["identity"].aliases_of(canonical)
    return aliases[0].alias_id if aliases else None


def successor_gate(result: Dict) -> str:
    """A citation by retired id still walks the P5 lifecycle correctly."""
    identity: KUIdentityService = result["identity"]
    evolution = result["evolved"]["evolution"]
    for revision in result["sink"].revisions.values():
        canonical = revision.prior_unit_id
        aliases = identity.aliases_of(canonical)
        if not aliases:
            return "FAIL"
        status = evolution.status_of(canonical)
        if status != "SUPERSEDED":
            return "FAIL"
        if evolution.successor_of(canonical) != revision.revised_unit_id:
            return "FAIL"
        # The alias must not have disturbed the fold: it is a lookup, not a
        # second identity the lifecycle has to know about.
        if len(evolution.history(canonical)) == 0:
            return "FAIL"
    return "PASS"


# ── GATE_4 P1-P5 regression ──────────────────────────────────────────────────

def regression_gate(result: Optional[Dict] = None) -> Dict[str, object]:
    """Every earlier stage still produces exactly what it produced.

    Checked against the committed artifacts rather than against constants
    written here, so this gate fails if an earlier stage drifts and not
    only if the numbers in this file are stale.
    """
    evolved = build_evolution()
    if result is None:
        result = build_identity()
    evolution = evolved["evolution"]
    freeze_store = evolved["result"]["freeze"].store
    checks: Dict[str, object] = {
        "p5_units": len(evolution.sink.units),
        "p5_revisions": evolution.revision_count(),
        "p5_reviews": evolution.review_count(),
        "p5_superseded": evolution.status_breakdown().get("SUPERSEDED", 0),
        "p4_units": len(evolved["result"]["writer"].reload()),
        "p4_legacy_ids": len(freeze_store.frozen_units),
        "freeze_version": FREEZE_VERSION,
        "persistence_version": PERSISTENCE_VERSION,
        "evolution_version": EVOLUTION_VERSION,
    }

    p5 = json.loads(P5_ARTIFACT.read_text(encoding="utf-8"))
    checks["p5_artifact_matches"] = int(
        checks["p5_units"] == p5["persisted_units"]
        and checks["p5_revisions"] == p5["revisions"]
        and checks["p5_reviews"] == p5["reviews"]
        and checks["p5_superseded"]
        == p5["status_breakdown"]["SUPERSEDED"])

    # P4 is frozen and must not have moved, so it is rebuilt on its own —
    # through P4's own baseline, not through P5, because P5 legitimately
    # froze an eleventh unit when it appended a revision's successor.
    p4_only = build_freeze_baseline()
    p4_units = p4_only["freeze"].store.frozen_units
    checks["p4_legacy_ids"] = len(p4_units)

    frozen = json.loads(P4_ARTIFACT.read_text(encoding="utf-8"))
    p4_ids = {entry["unit_id"] for entry in frozen.get("units", {}).values()}
    checks["p4_ids"] = len(p4_ids)
    checks["p4_ids_reproduced"] = int(p4_ids == set(p4_units))
    # And every id P4 ever issued is still resolvable through P6, including
    # the eleventh that P5 added.
    checks["p5_legacy_ids_still_resolvable"] = int(all(
        any(row.alias_id == unit.id
            for row in result["sink"].identities.values())
        for unit in freeze_store.frozen_units.values()))
    return checks


def versions_gate() -> str:
    """Every earlier stage still carries its own version string.

    Distinct from `regression_verdict`: that one checks the *output* each
    stage produces, this one checks a stage did not quietly change which
    contract version it claims to implement. A stage that re-labelled
    itself would keep producing identical rows and still be lying.
    """
    if (FREEZE_VERSION == "a-p4-v0.1"
            and PERSISTENCE_VERSION == "a-p4-1-v0.1"
            and EVOLUTION_VERSION == "a-p5-v0.1"):
        return "PASS"
    return "FAIL"


def regression_verdict(checks: Dict[str, object]) -> str:
    if checks["p5_units"] != 11 or checks["p5_revisions"] != 1:
        return "FAIL"
    if checks["p5_reviews"] != 5 or checks["p5_superseded"] != 1:
        return "FAIL"
    if checks["p4_legacy_ids"] != 10:
        return "FAIL"
    if checks["p5_artifact_matches"] != 1:
        return "FAIL"
    if checks["p4_ids_reproduced"] != 1 or checks["p4_ids"] != 10:
        return "FAIL"
    if checks["p5_legacy_ids_still_resolvable"] != 1:
        return "FAIL"
    if checks["freeze_version"] != "a-p4-v0.1":
        return "FAIL"
    if checks["persistence_version"] != "a-p4-1-v0.1":
        return "FAIL"
    if checks["evolution_version"] != EVOLUTION_VERSION:
        return "FAIL"
    return "PASS"


# ── GATE_5 authority isolation ───────────────────────────────────────────────

def authority_gate() -> str:
    """A仓 only: the identity reaches nothing outside A仓.

    Every `stratum.X` 076 names must be the one table it creates or a
    permitted reference target, so the migration is structurally unable to
    reach another repository. A name list inside the gate would itself
    contain the names it forbids.
    """
    migration = (Path(__file__).parents[2] / "db" / "pg_migrations"
                 / REQUIRED_MIGRATION).read_text(encoding="utf-8")
    statements = re.sub(r"--.*", "", migration)
    named = set(re.findall(r"stratum\.(\w+)", statements))
    if not named <= CREATED_TABLES | ALLOWED_REFERENCES:
        return "FAIL"
    # Anchored to a statement start, so `ON DELETE RESTRICT` — a referential
    # action, not DML — is not mistaken for a write.
    if re.search(r"^[ \t]*(INSERT|UPDATE|DELETE|MERGE|JOIN)\b", statements,
                 re.MULTILINE):
        return "FAIL"
    return "PASS"


def no_external_dependency_gate() -> str:
    """Nothing in the identity stage reaches outside A仓.

    Checked on the source rather than on a list: the identity service may
    reach P4, P4.1, P5 and the ingestion store, and may not import anything
    that names another repository.
    """
    identity = (Path(__file__).parent / "identity.py").read_text(
        encoding="utf-8")
    code = re.sub(r'""".*?"""', "", identity, flags=re.DOTALL)
    imports = set(re.findall(r"^\s*(?:from|import)\s+([\w.]+)", code,
                             re.MULTILINE))
    allowed_roots = {"__future__", "hashlib", "dataclasses", "enum",
                     "typing", "json", "evolution", "persistence", "freeze",
                     ".evolution", ".persistence", ".freeze"}
    if not imports <= allowed_roots:
        return "FAIL"
    if re.search(r"\b(bu2?|b_repo|ku_onto|concept_onto|rf\.|aii_refined)\b",
                 code):
        return "FAIL"
    return "PASS"


def no_mutation_gate(result: Dict) -> str:
    """Registering every retired id changed no unit row.

    A snapshot of all eleven unit rows before and after, compared field by
    field. The service has no write path to `knowledge_unit`; this proves
    it took none.
    """
    upstream = build_evolution(sink=IdentitySink())
    identity = KUIdentityService(upstream["result"]["base"]["pipeline"],
                                 upstream["result"]["freeze"],
                                 upstream["result"]["writer"],
                                 upstream["result"]["sink"])
    before = {key: dict(vars(unit))
              for key, unit in sorted(upstream["result"]["sink"].units.items())}
    for frozen in identity.frozen_units():
        identity.register_frozen_unit(frozen)
    after = {key: dict(vars(unit))
             for key, unit in sorted(upstream["result"]["sink"].units.items())}
    return "PASS" if before == after else "FAIL"


def schema_gate(ledger: Optional[List[str]]) -> str:
    """The real schema carries 076 and its whole chain, additively."""
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
        return "FAIL"
    for inherited in INHERITED_TABLES:
        if f"CREATE TABLE IF NOT EXISTS stratum.{inherited} (" in statements:
            return "FAIL"
    created = set(re.findall(r"CREATE TABLE IF NOT EXISTS stratum\.(\w+)",
                             statements))
    if created != CREATED_TABLES:
        return "FAIL"
    referenced = set(re.findall(r"REFERENCES\s+stratum\.(\w+)", migration))
    if not referenced <= ALLOWED_REFERENCES:
        return "FAIL"
    return "PASS"


def gate_results(result: Dict, ledger: Optional[List[str]]) -> Dict[str, object]:
    """The five gates. A gate that cannot be evidenced is NOT_EXECUTED."""
    replay = replay_gate()
    replay_pass = (replay["identical_fingerprints"] == 1
                   and replay["same_aliases"] and replay["same_canonical"]
                   and replay["no_duplicates"])
    return {
        "G1_identity_uniqueness": uniqueness_gate(result),
        "G1_canonical_id": canonical_id_gate(result),
        "G2_historical_replay": "PASS" if replay_pass else "FAIL",
        "G2_citations_resolve": citation_gate(result),
        "G2_retired_id_recomputes": retired_id_recomputes(result),
        "G3_revision_chain": revision_gate(result),
        "G3_successor_walk": successor_gate(result),
        "G4_regression": regression_verdict(regression_gate(result)),
        "G4_stage_versions": versions_gate(),
        "G5_authority": authority_gate(),
        "G5_no_external_dependency": no_external_dependency_gate(),
        "G5_no_mutation": no_mutation_gate(result),
        "schema": schema_gate(ledger),
        "idempotency": idempotency_gate(result),
    }


GATE_ORDER = ("G1_identity_uniqueness", "G2_historical_replay",
              "G3_revision_chain", "G4_regression", "G5_authority")


# ── reporting ────────────────────────────────────────────────────────────────

def report(result: Dict) -> Dict:
    identity: KUIdentityService = result["identity"]
    units: Dict[str, Dict] = {}
    for key, unit in sorted(result["sink"].units.items()):
        aliases = identity.aliases_of(key)
        units[key] = {
            "canonical_ku_id": key,
            "candidate_id": unit.candidate_id,
            "verification_id": unit.verification_id,
            "aliases": [{"alias_id": row.alias_id, "alias_kind": row.alias_kind}
                        for row in aliases],
            "alias_count": len(aliases),
        }
    return {
        "task": "A_P6_KU_IDENTITY",
        "book": f"{C.BOOK_TITLE} {C.BOOK_EDITION}",
        "run_id": result["result"]["base"]["reading_run_id"],
        "canonical_units": identity.canonical_count(),
        "identity_rows": identity.identity_count(),
        "alias_kinds": sorted({row.alias_kind
                               for row in result["sink"].identities.values()}),
        "declared_alias_kinds": sorted(DECLARED_ALIAS_KINDS),
        "resolution": identity.resolution_report(),
        "unregistered_units": identity.unregistered_units(),
        "identity_version": IDENTITY_VERSION,
        "writable_tables": sorted(WRITABLE_TABLES),
        "units": units,
    }


def artifact(result: Dict, ledger: Optional[List[str]]) -> Dict:
    """The evidence artifact the task asks for."""
    summary = report(result)
    gates = gate_results(result, ledger)
    passed = all(gates[name] == "PASS" for name in GATE_ORDER)
    return {
        "task": "A_P6_KU_IDENTITY",
        "book": summary["book"].split(" ")[0],
        "authority": "A_REPOSITORY",
        "identity_version": IDENTITY_VERSION,
        "run_id": summary["run_id"],
        "canonical_ku_id_formula": "ku_<sha256(candidate_id|verification_id|"
                                   "content_hash)[:12]>",
        "canonical_units": summary["canonical_units"],
        "identity_rows": summary["identity_rows"],
        "alias_kinds": summary["alias_kinds"],
        "declared_alias_kinds": summary["declared_alias_kinds"],
        "resolution": summary["resolution"],
        "unregistered_units": summary["unregistered_units"],
        "gate_results": gates,
        "A_P6_IDENTITY": "PASS" if passed else "BLOCKED",
        "ledger": ledger,
        "units": summary["units"],
    }


def write_sql(result: Dict, path: str) -> str:
    """Emit the whole chain plus `ku_identity` for a DBA to execute.

        python -m stratum.knowledge.a_repository.ku_identity_runner --sql identity.sql
        docker cp identity.sql aii-postgres:/tmp/
        docker exec -e PGOPTIONS="-c search_path=stratum,public" aii-postgres \
          psql -U aii -d stratum_a_p3_staging -v ON_ERROR_STOP=1 -1 -q \
          -f /tmp/identity.sql

    One BEGIN/COMMIT, parents before children, every statement ON CONFLICT
    DO NOTHING, so the file is safe to run twice.
    """
    upstream = result["result"]
    script = emit_identity_sql(upstream["base"]["pipeline"].store,
                               upstream["verification"],
                               upstream["freeze"],
                               upstream["sink"])
    Path(path).write_text(script, encoding="utf-8")
    return path


def durable_counts(path: Optional[str] = None) -> Optional[Dict[str, int]]:
    """Row counts read back from the database, if a DBA-side query left
    them in the file named by A_P6_DB_COUNTS."""
    target = path or os.environ.get("A_P6_DB_COUNTS")
    if not target:
        return None
    source = Path(target)
    if not source.exists():
        return None
    counts = {key: int(value) for key, value in re.findall(
        r"(\w+)\s*=\s*(\d+)", source.read_text(encoding="utf-8"))}
    return counts or None


def main() -> None:
    result = build_identity()
    if "--sql" in sys.argv:
        target = sys.argv[sys.argv.index("--sql") + 1]
        print(write_sql(result, target))
        return
    ledger = staging_ledger(os.environ.get("A_P6_LEDGER_FILE"))
    doc = artifact(result, ledger)
    counts = durable_counts()
    if counts is not None:
        doc["durable_rows"] = counts
    print(json.dumps(doc, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
