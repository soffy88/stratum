"""The A仓 acceptance verdict contract.

One place, because more than one layer needs it and a copy per layer is a copy
that drifts. P6 found that its verdict read a hardcoded list of gate names
instead of the gates it reported, so nine gates could print PASS or FAIL without
affecting the outcome — and a gate that never executed still produced a PASS.
P5-evolution had the same defect and was found by comparing the two.

    FAIL > BLOCKED > PASS

Why three states and not two:

  PASS     every reported gate ran and passed. Evidence of merit.
  BLOCKED  evidence was unavailable — a gate did not execute, or the set was
           empty. **Not** evidence of merit, and never reported as such.
  FAIL     a gate ran and failed. Positive evidence of breakage, which
           outranks missing evidence: reporting "blocked" would understate it.

Two properties this contract is required to hold, and which the tests assert:

  * No hardcoded gate list. The verdict is computed from whatever mapping the
    layer's `gate_results()` returned, so a gate added later cannot escape it.
  * An unrecognised status is BLOCKED, not PASS. A new gate status someone
    forgets to handle must fail closed rather than open.

This module deliberately imports nothing. It was extracted from
`ku_identity_runner` after a circular import appeared once a second layer
wanted the same contract: the two runners call each other, so a shared rule
placed in either one cannot be imported by the other.
"""

from __future__ import annotations

from typing import Dict, Mapping, Set


VERDICT_PASS = "PASS"
VERDICT_FAIL = "FAIL"
VERDICT_BLOCKED = "BLOCKED"

#: Statuses a gate may report. `NOT_EXECUTED` is what `gate_results` returns
#: when it cannot evidence a gate; anything outside this set is treated as
#: BLOCKED so an unknown status fails closed.
GATE_PASS = "PASS"
GATE_FAIL = "FAIL"
GATE_NOT_EXECUTED = "NOT_EXECUTED"


def verdict(gates: Mapping[str, str]) -> str:
    """The single authority for an acceptance verdict.

    Derived from the gates themselves. There is deliberately no companion tuple
    of gate names: a parallel list is exactly the mechanism by which reported
    gates fall outside the verdict, and it can drift the moment a gate is added.

        all PASS              -> PASS
        any FAIL              -> FAIL
        else any NOT_EXECUTED -> BLOCKED
        empty set             -> BLOCKED
        unknown status        -> BLOCKED
    """
    if not gates:
        return VERDICT_BLOCKED
    statuses: Set[str] = set(gates.values())
    if GATE_FAIL in statuses:
        return VERDICT_FAIL
    if GATE_NOT_EXECUTED in statuses:
        return VERDICT_BLOCKED
    if statuses == {GATE_PASS}:
        return VERDICT_PASS
    # An unrecognised status is not evidence of merit.
    return VERDICT_BLOCKED


def verdict_inputs(gates: Mapping[str, str]) -> Dict[str, object]:
    """The evidence behind a verdict, for a freeze artifact.

    Recorded so a reader can see *why* a verdict came out as it did, rather than
    being handed a single word. Which gates ran, which did not, and which are
    outside the contract are all named.
    """
    statuses = sorted(set(gates.values()))
    unknown = [name for name, value in gates.items()
               if value not in (GATE_PASS, GATE_FAIL, GATE_NOT_EXECUTED)]
    return {
        "verdict": verdict(gates),
        "gate_count": len(gates),
        "statuses_present": statuses,
        "gates_not_executed": sorted(
            name for name, value in gates.items()
            if value == GATE_NOT_EXECUTED),
        "gates_failed": sorted(
            name for name, value in gates.items() if value == GATE_FAIL),
        "gates_unknown_status": sorted(unknown),
        "contract": "FAIL > BLOCKED > PASS; derived from gate_results, "
                    "no hardcoded gate list",
    }