"""A Repository P4 — freeze runner.

Runs the freeze stage over the frozen P1→P2→P3 baseline and reports the
five gates. Deterministic, resumable, idempotent.

Run: PYTHONPATH=src python3 -m stratum.knowledge.a_repository.ku_freeze_runner

GATE_1 needs a database ledger. The ledger is read from the file named by
A_P4_LEDGER_FILE, which a DBA-side query produces, so no credential ever
reaches this process:

    docker exec aii-postgres psql -U aii -d stratum_a_p3_staging -Atc \
      "SELECT filename FROM public._pg_migrations ORDER BY filename" \
      > /tmp/a_p4_ledger.txt
    A_P4_LEDGER_FILE=/tmp/a_p4_ledger.txt PYTHONPATH=src \
      python3 -m stratum.knowledge.a_repository.ku_freeze_runner
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional

from . import pilot_corpus as C
from .freeze import (
    FREEZE_SCORE_THRESHOLD,
    FREEZE_VERSION,
    AKnowledgeUnitFreezePipeline,
    FreezeStatus,
)
from .verification import VerificationStatus
from .verification_runner import (
    build_verification_baseline,
    staging_ledger,
)


def _build_verification_baseline() -> Dict:
    """Kept as a module-level seam for tests and for callers that want the
    P3 chain without the freeze stage."""
    return build_verification_baseline()


REQUIRED_MIGRATION = "073_a_knowledge_unit_freeze.sql"

#: The only tables a frozen unit may point at. A frozen unit is a
#: projection of A仓 evidence, so every foreign key lands here; nothing
#: else is reachable from this migration.
ALLOWED_REFERENCES = frozenset(
    {"ku_verification", "ku_candidate", "source_version"})

#: The migrations a frozen unit depends on. 073 without its predecessors
#: would have no table to reference.
REQUIRED_CHAIN = (
    "070_a_repository_foundation.sql",
    "071_a_evidence_quality.sql",
    "072_a_ku_verification.sql",
    REQUIRED_MIGRATION,
)


def build_freeze_baseline() -> Dict:
    """P3 chain + P4 freeze decisions."""
    upstream = build_verification_baseline()
    base, verification = upstream["base"], upstream["verification"]
    fp = AKnowledgeUnitFreezePipeline(base["pipeline"], verification)
    fp.freeze_verified(base["reading_run_id"])
    return {"base": base, "verification": verification, "freeze": fp}


def gate_results(result: Dict, ledger: Optional[List[str]]) -> Dict[str, str]:
    """The five gates. A gate that cannot be evidenced is NOT_EXECUTED."""
    fp: AKnowledgeUnitFreezePipeline = result["freeze"]
    verification = result["verification"]
    run_id = result["base"]["reading_run_id"]

    # GATE_1 — the real schema carries 073 and its chain.
    if ledger is None:
        gate1 = "NOT_EXECUTED"
    elif all(name in ledger for name in REQUIRED_CHAIN):
        gate1 = "PASS"
    else:
        gate1 = "FAIL"

    # GATE_2 — only passed verifications became units.
    units = fp._units(run_id)
    verified_ids = {
        v.id for v in verification.store.verifications.values()
        if v.verification_status == VerificationStatus.VERIFIED.value}
    rejected_candidates = {
        v.candidate_id for v in verification.store.verifications.values()
        if v.verification_status == VerificationStatus.REJECTED.value}
    gate2 = ("PASS"
             if units
             and all(u.verification_id in verified_ids for u in units)
             and all(u.verification_score >= FREEZE_SCORE_THRESHOLD
                     for u in units)
             and not rejected_candidates & {u.candidate_id for u in units}
             else "FAIL")

    # GATE_3 — authority, checked structurally.
    #
    # This gate inspects what 073 actually references rather than scanning
    # for English words: a name list inside the gate would itself contain
    # the names it forbids. Every foreign key must land on an A table, and
    # the migration must not backfill.
    sql_path = (Path(__file__).parents[2] / "db" / "pg_migrations"
                / REQUIRED_MIGRATION)
    migration = sql_path.read_text(encoding="utf-8")
    referenced = set(re.findall(r"REFERENCES\s+stratum\.(\w+)", migration))
    statements = re.sub(r"--.*", "", migration)
    gate3 = ("PASS"
             if referenced <= ALLOWED_REFERENCES
             and "ALTER TABLE" not in statements
             and "INSERT INTO" not in statements
             else "FAIL")

    # GATE_4 — full chain traceable, every unit anchored.
    trace = fp.traceability(run_id)
    gate4 = ("PASS"
             if trace["units"]
             and trace["trace_complete"] == trace["units"]
             and trace["percent"] == 100.0
             and trace["unique_ids"] == trace["units"]
             and not fp.unanchored_units()
             else "FAIL")

    # GATE_5 — replay freezes nothing twice.
    replay = replay_gate(result)
    gate5 = ("PASS" if replay["new_units"] == 0
             and replay["duplicates"] == 0 else "FAIL")

    return {"gate1": gate1, "gate2": gate2, "gate3": gate3,
            "gate4": gate4, "gate5": gate5}


def replay_gate(result: Dict) -> Dict[str, int]:
    """GATE_5 — run the whole chain again over the same inputs."""
    before = report(result)
    again = build_freeze_baseline()
    after = report(again)
    return {
        "new_units": after["frozen_count"] - before["frozen_count"],
        "duplicates": after["traceability"]["units"]
        - after["traceability"]["unique_ids"],
        "identical_report": int(before == after),
    }


def report(result: Dict) -> Dict:
    fp: AKnowledgeUnitFreezePipeline = result["freeze"]
    run_id = result["base"]["reading_run_id"]
    by_key = {cid: key for key, cid in result["base"]["candidate_ids"].items()}

    units = {}
    for unit in fp._units(run_id):
        units[by_key.get(unit.candidate_id, unit.candidate_id)] = {
            "unit_id": unit.id,
            "canonical_text": unit.canonical_text,
            "evidence_count": unit.evidence_count,
            "verification_score": unit.verification_score,
        }

    return {
        "task": "A_P4_KNOWLEDGE_UNIT_FREEZE",
        "book": f"{C.BOOK_TITLE} {C.BOOK_EDITION}",
        "run_id": run_id,
        "verification_input": fp.verified_input(run_id),
        "verified_count": fp.verified_input(run_id) - fp.rejected_input(run_id),
        "rejected_input": fp.rejected_input(run_id),
        "frozen_count": fp.frozen_count(run_id),
        "status_breakdown": fp.status_breakdown(run_id),
        "freeze_score_threshold": FREEZE_SCORE_THRESHOLD,
        "orphan_units": fp.orphan_units(),
        "unanchored_units": fp.unanchored_units(),
        "traceability": fp.traceability(run_id),
        "freeze_version": FREEZE_VERSION,
        "units": dict(sorted(units.items())),
    }


def artifact(result: Dict, ledger: Optional[List[str]]) -> Dict:
    """The evidence artifact required by the spec."""
    summary = report(result)
    gates = gate_results(result, ledger)
    trace = summary["traceability"]
    return {
        "task": "A_P4_KNOWLEDGE_UNIT_FREEZE",
        "book": summary["book"].split(" ")[0],
        "verification_input": summary["verification_input"],
        "frozen_count": summary["frozen_count"],
        "authority": "A_REPOSITORY",
        "traceability": ("100%" if trace["percent"] == 100.0
                         else f"{trace['percent']}%"),
        "replay": ("PASS" if gates["gate5"] == "PASS" else gates["gate5"]),
        "run_id": summary["run_id"],
        "freeze_version": summary["freeze_version"],
        "ledger": ledger,
        "gate_results": gates,
        "status_breakdown": summary["status_breakdown"],
        "units": summary["units"],
    }


def main() -> None:
    result = build_freeze_baseline()
    ledger = staging_ledger(os.environ.get("A_P4_LEDGER_FILE"))
    print(json.dumps(artifact(result, ledger),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()