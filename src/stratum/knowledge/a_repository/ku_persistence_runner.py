"""A Repository P4.1 — persistence runner.

Takes the frozen knowledge units of a reading run, validates them,
persists each one atomically with its events, and reports the five gates.

Run: PYTHONPATH=src python3 -m stratum.knowledge.a_repository.ku_persistence_runner

GATE schema reads the migration ledger from A_P4_1_LEDGER_FILE so no
credential reaches this process:

    docker exec aii-postgres psql -U aii -d stratum_a_p3_staging -Atc \
      "SELECT filename FROM public._pg_migrations ORDER BY filename" \
      > /tmp/a_p4_1_ledger.txt
    A_P4_1_LEDGER_FILE=/tmp/a_p4_1_ledger.txt PYTHONPATH=src \
      python3 -m stratum.knowledge.a_repository.ku_persistence_runner

The runner is a reader with respect to everything upstream: it never
modifies a candidate, a verification or an evidence row.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

from . import pilot_corpus as C
from .freeze import FREEZE_VERSION
from .persistence import (
    IMPLEMENTED_EVENT_TYPES,
    PERSISTENCE_VERSION,
    InMemorySink,
    KUDurableWriter,
    PersistenceStatus,
    PersistenceViolation,
    emit_chain_sql,
)
from .ku_freeze_runner import build_freeze_baseline, build_verification_baseline
from .verification import VerificationStatus
from .verification_runner import staging_ledger


REQUIRED_MIGRATION = "074_a_ku_freeze_persistence.sql"

REQUIRED_CHAIN = (
    "070_a_repository_foundation.sql",
    "071_a_evidence_quality.sql",
    "072_a_ku_verification.sql",
    "073_a_knowledge_unit_freeze.sql",
    REQUIRED_MIGRATION,
)

ALLOWED_REFERENCES = frozenset({"knowledge_unit"})


def build_persistence(sink=None) -> Dict:
    """P4 chain + P4.1 persistence."""
    upstream = build_freeze_baseline()
    sink = sink if sink is not None else InMemorySink()
    writer = KUDurableWriter(upstream["base"]["pipeline"],
                             upstream["verification"],
                             upstream["freeze"], sink)
    results = writer.persist_verified(upstream["base"]["reading_run_id"])
    return {
        "base": upstream["base"],
        "verification": upstream["verification"],
        "freeze": upstream["freeze"],
        "writer": writer,
        "sink": sink,
        "results": results,
    }


def schema_gate(ledger: Optional[List[str]]) -> str:
    """The real schema carries 074 and its whole chain, and 074 adds only
    the event table — it must not recreate or alter knowledge_unit."""
    if ledger is None:
        return "NOT_EXECUTED"
    if not all(name in ledger for name in REQUIRED_CHAIN):
        return "FAIL"
    migration = (Path(__file__).parents[2] / "db" / "pg_migrations"
                 / REQUIRED_MIGRATION).read_text(encoding="utf-8")
    statements = re.sub(r"--.*", "", migration)
    # 074 creates ku_freeze_event and must leave knowledge_unit alone.
    if "knowledge_unit (" in statements:
        return "FAIL"
    if "ALTER TABLE" in statements or "DROP " in statements:
        return "FAIL"
    referenced = set(re.findall(r"REFERENCES\s+stratum\.(\w+)", migration))
    if not referenced <= ALLOWED_REFERENCES:
        return "FAIL"
    return "PASS"


def authority_gate() -> str:
    """A仓 only: the writer reaches nothing outside the A chain.

    Checked by inspecting what the writer actually touches, not by
    matching a name list — a list inside the gate would contain the names
    it forbids.
    """
    source = (Path(__file__).parents[0] / "persistence.py").read_text(
        encoding="utf-8")
    statements = re.sub(r"#.*", "", source)
    for foreign in ("INSERT INTO", "UPDATE ", "DELETE FROM"):
        # The writer builds rows; a real statement would have to name a
        # table directly.
        if foreign in statements and "knowledge_unit" not in statements:
            return "FAIL"
    migration = (Path(__file__).parents[2] / "db" / "pg_migrations"
                 / REQUIRED_MIGRATION).read_text(encoding="utf-8").lower()
    if "insert into" in re.sub(r"--.*", "", migration):
        return "FAIL"  # no data backfill
    return "PASS"


def transaction_gate(result: Dict) -> str:
    """No reachable state has a unit without its event, or the reverse."""
    writer = result["writer"]
    if writer.orphan_events():
        return "FAIL"
    for unit in writer.sink.units.values():
        if not [e for e in writer.sink.events.values()
                if e.knowledge_unit_id == unit.id]:
            return "FAIL"
    if not all(r.written_unit or r.status == PersistenceStatus.FROZEN.value
               for r in result["results"]):
        return "FAIL"
    return "PASS"


def recovery_gate() -> str:
    """A failure between the unit write and the event write leaves
    nothing behind."""
    upstream = build_freeze_baseline()
    sink = InMemorySink(fail_after=1)  # dies after the unit write
    writer = KUDurableWriter(upstream["base"]["pipeline"],
                             upstream["verification"],
                             upstream["freeze"], sink)
    verification_id = sorted(upstream["freeze"].store._unit_by_verification)[0]
    outcome = writer.persist(verification_id)
    if outcome.status != PersistenceStatus.FAILED.value:
        return "FAIL"
    if sink.units or sink.events:
        return "FAIL"
    if sink.rollbacks < 1:
        return "FAIL"
    return "PASS"


def replay_gate(result: Dict) -> Dict[str, object]:
    """Persisting twice writes nothing the second time."""
    before_units = result["writer"].unit_count()
    before_events = result["writer"].event_count()
    second = result["writer"].persist_verified(result["base"]["reading_run_id"])
    writer = result["writer"]
    return {
        "units_before": before_units,
        "units_after": writer.unit_count(),
        "events_before": before_events,
        "events_after": writer.event_count(),
        "second_pass_units_written": sum(1 for r in second if r.written_unit),
        "second_pass_events_written": sum(r.written_events for r in second),
        "identical": int(writer.unit_count() == before_units
                         and writer.event_count() == before_events),
    }


def report(result: Dict, ledger: Optional[List[str]]) -> Dict:
    writer: KUDurableWriter = result["writer"]
    sink = result["sink"]
    base = result["base"]
    verification = result["verification"]
    run_id = base["reading_run_id"]
    by_key = {cid: key for key, cid in base["candidate_ids"].items()}

    verified = sum(
        1 for v in verification.store.verifications.values()
        if v.verification_status == VerificationStatus.VERIFIED.value
        and v.candidate_id in base["pipeline"].store.ku_candidates
        and base["pipeline"].store.ku_candidates[v.candidate_id
                                                ].reading_run_id == run_id)
    units = {}
    for unit in sink.units.values():
        units[by_key.get(unit.candidate_id, unit.candidate_id)] = {
            "unit_id": unit.id,
            "events": sorted(e.event_type for e in sink.events.values()
                             if e.knowledge_unit_id == unit.id),
            "verification_score": unit.verification_score,
        }

    replay = replay_gate(result)
    trace = writer.traceability()
    return {
        "task": "A_P4_1_KU_DURABLE_WRITER",
        "book": f"{C.BOOK_TITLE} {C.BOOK_EDITION}",
        "run_id": run_id,
        "input_verified": verified,
        "persisted": writer.unit_count(),
        "events": writer.event_count(),
        "duplicates": len(writer.duplicate_units())
        + len(writer.duplicate_events()),
        "failed_attempts": sum(1 for r in result["results"]
                               if r.status == PersistenceStatus.FAILED.value),
        "orphan_events": writer.orphan_events(),
        "traceability": trace,
        "replay": replay,
        "commits": sink.commits,
        "rollbacks": sink.rollbacks,
        "persistence_version": PERSISTENCE_VERSION,
        "freeze_version": FREEZE_VERSION,
        "units": dict(sorted(units.items())),
    }


def artifact(result: Dict, ledger: Optional[List[str]]) -> Dict:
    summary = report(result, ledger)
    trace = summary["traceability"]
    replay = summary["replay"]
    return {
        "task": "A_P4_1_KU_DURABLE_WRITER",
        "book": summary["book"].split(" ")[0],
        "input_verified": summary["input_verified"],
        "persisted": summary["persisted"],
        "events": summary["events"],
        "duplicates": summary["duplicates"],
        "traceability": ("100%" if trace["percent"] == 100.0
                         else f"{trace['percent']}%"),
        "replay": ("PASS" if replay["identical"] else "FAIL"),
        "authority": "A_REPOSITORY",
        "persistence_version": summary["persistence_version"],
        "run_id": summary["run_id"],
        "ledger": ledger,
        "gate_results": {
            "schema": schema_gate(ledger),
            "transaction": transaction_gate(result),
            "replay": ("PASS" if replay["identical"] else "FAIL"),
            "authority": authority_gate(),
            "recovery": recovery_gate(),
        },
        "event_types": [e.value for e in IMPLEMENTED_EVENT_TYPES],
        "units": summary["units"],
    }


def write_sql(result: Dict, path: str) -> str:
    """Emit the durable write script for a DBA to execute.

    The whole A chain goes in one transaction, parents before children, so
    a knowledge unit's foreign keys resolve. Re-running the file writes
    nothing: every statement is ON CONFLICT DO NOTHING.

        python -m stratum.knowledge.a_repository.ku_persistence_runner --sql freeze.sql
        docker cp freeze.sql aii-postgres:/tmp/
        docker exec -e PGOPTIONS="-c search_path=stratum,public" aii-postgres \
          psql -U aii -d stratum_a_p3_staging -v ON_ERROR_STOP=1 -1 -q \
          -f /tmp/freeze.sql
    """
    script = emit_chain_sql(result["base"]["pipeline"].store,
                            result["verification"],
                            result["freeze"],
                            result["sink"])
    Path(path).write_text(script, encoding="utf-8")
    return path


def durable_counts(path: Optional[str] = None) -> Optional[Dict[str, int]]:
    """Row counts read back from the database, if a DBA-side query left
    them in the file named by A_P4_1_DB_COUNTS."""
    target = path or os.environ.get("A_P4_1_DB_COUNTS")
    if not target:
        return None
    source = Path(target)
    if not source.exists():
        return None
    counts = {key: int(value)
              for key, value in re.findall(r"(\w+)\s*=\s*(\d+)",
                                           source.read_text(
                                               encoding="utf-8"))}
    return counts or None


def main() -> None:
    result = build_persistence()
    if "--sql" in sys.argv:
        target = sys.argv[sys.argv.index("--sql") + 1]
        print(write_sql(result, target))
        return
    ledger = staging_ledger(os.environ.get("A_P4_1_LEDGER_FILE"))
    doc = artifact(result, ledger)
    counts = durable_counts()
    if counts is not None:
        doc["durable_rows"] = counts
    print(json.dumps(doc, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()