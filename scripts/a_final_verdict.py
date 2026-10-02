"""The A仓 final verdict, computed from every layer's own gates.

    python -m scripts.a_final_verdict [--json]

Eight layers report gates: P5.0, P5.1-P5.5, P5 Evolution, P6 Identity and P7
Projection. Each derives its own verdict from its own `gate_results`, by the
shared contract in `verdict.py`. This script adds nothing to that: it runs each
layer, collects the gates they report, merges them under a layer prefix, and
applies the same function to the union. There is no list of gate names here,
because a list is the mechanism by which a reported gate falls outside the
outcome.

Why this exists separately from the layers. Three layers were reopened for
reporting gates they did not count -- P5 Evolution 8 reported and 6 counted, P6
14 and 12, P7 returned 7 beside a hand-written list of 5 -- and each of those
defects was invisible from inside the layer that had it. It took comparing one
layer's report against another's to see them. A final acceptance that reads one
layer's verdict and calls the chain verified would repeat the mistake at the
largest possible scale, so the chain verdict is derived the same way the layers
are: from the gates, all of them, at once.

A layer whose gates are not all strings is reported, not repaired. `verdict`
treats an unrecognised value as BLOCKED, so a measurement smuggled back into a
gate mapping blocks the chain rather than being quietly coerced into a pass.
That is the intended behaviour and the reason seven gates were converted and six
duplicate detail dicts were removed rather than coerced.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stratum.knowledge.a_repository.verdict import (  # noqa: E402
    VERDICT_BLOCKED,
    verdict,
    verdict_inputs,
)

ROOT = Path(__file__).resolve().parents[1]
PKG = "stratum.knowledge.a_repository"

#: Every layer that reports gates, in migration order. The module name is the
#: runner; each is executed exactly as the freeze process executes it.
LAYERS: Dict[str, str] = {
    "P5_0_CONDITION_BOUNDARY": "condition_boundary_runner",
    "P5_1_MECHANISM": "mechanism_runner",
    "P5_2_RELATION": "relation_runner",
    "P5_3_PAPER": "paper_runner",
    "P5_4_CONSTRAINT": "constraint_runner",
    "P5_5_PAPER_EVIDENCE_FK": "paper_evidence_fk_runner",
    "P5_EVOLUTION": "ku_evolution_runner",
    "P6_IDENTITY": "ku_identity_runner",
    "P7_PROJECTION": "projection_builder",
}

#: Layers whose `schema` gate reads a migration ledger. Without one they report
#: NOT_EXECUTED and the chain blocks, which is correct: a gate that was waiting
#: on evidence has not passed.
LEDGER_LAYERS = ("P5_EVOLUTION", "P6_IDENTITY")

#: Environment the runners need. A_P5_BASE_SHA / A_P7_BASE_SHA are absent on
#: purpose: they name a freeze's parent commit and say nothing about gates.
BASE_ENV = {
    "PYTHONPATH": str(ROOT / "src"),
    "A_P5_LEDGER_FILE": os.environ.get("A_P5_LEDGER_FILE", ""),
    "A_P6_LEDGER_FILE": os.environ.get("A_P5_LEDGER_FILE", ""),
}


def run_layer(layer: str, module: str) -> Tuple[Dict[str, object], str]:
    """One layer's gate mapping, and its raw verdict key if it exposes one."""
    env = dict(os.environ)
    env.update(BASE_ENV)
    if layer not in LEDGER_LAYERS:
        # only the two schema-gated layers may keep an inherited path
        env.pop("A_P5_LEDGER_FILE", None)
        env.pop("A_P6_LEDGER_FILE", None)
    done = subprocess.run([sys.executable, "-m", f"{PKG}.{module}"],
                          capture_output=True, text=True, env=env, timeout=1800,
                          cwd=ROOT)
    if done.returncode != 0 or "{" not in done.stdout:
        return {}, (done.stderr.strip().splitlines() or ["no output"])[-1]
    doc = json.loads(done.stdout[done.stdout.index("{"):])
    gates = doc.get("gate_results") or doc.get("gates") or {}
    own = ""
    for key, value in doc.items():
        if key.startswith("A_P") and isinstance(value, str) \
                and value in ("PASS", "FAIL", "BLOCKED"):
            own = key
            break
    return gates, own


def collect() -> Tuple[Dict[str, str], List[Dict[str, object]]]:
    merged: Dict[str, str] = {}
    report: List[Dict[str, object]] = []
    for layer, module in LAYERS.items():
        gates, own = run_layer(layer, module)
        if not gates:
            report.append({"layer": layer, "module": module, "reported": 0,
                           "counted": 0, "verdict_key": own, "error": True})
            merged[f"{layer}:__unavailable__"] = VERDICT_BLOCKED
            continue
        merged.update({f"{layer}:{name}": value
                       for name, value in gates.items()})
        # Counted after the merge, by looking the keys up rather than assuming
        # the update took. A prefixed name cannot collide between layers, so
        # this is a check that two layers cannot quietly share a gate name --
        # not a check that `dict.update` worked.
        counted = sum(1 for name in gates if f"{layer}:{name}" in merged)
        report.append({"layer": layer, "module": module,
                       "reported": len(gates), "counted": counted,
                       "verdict_key": own,
                       "verdict": verdict(gates),
                       "non_string": sorted(name for name, value in gates.items()
                                            if not isinstance(value, str))})
    return merged, report


def main() -> int:
    merged, report = collect()
    evidence = verdict_inputs(merged)

    if "--json" in sys.argv:
        print(json.dumps({"layers": report, "verdict_inputs": evidence,
                          "merged": merged}, ensure_ascii=False, indent=2))
        return 0 if evidence["verdict"] == "PASS" else 1

    print(f"FINAL VERDICT   {evidence['verdict']}")
    print(f"gate_count      {evidence['gate_count']}")
    print(f"not executed    {evidence['gates_not_executed'] or 'none'}")
    print(f"failed          {evidence['gates_failed'] or 'none'}")
    print(f"unknown status  {evidence['gates_unknown_status'] or 'none'}")
    print()
    print(f"{'layer':26} {'reported':>8} {'counted':>8}  {'verdict':8} key")
    for row in report:
        if row.get("error"):
            print(f"{row['layer']:26} {'0':>8} {'0':>8}  UNAVAILABLE "
                  f"{row['module']}: {row.get('verdict_key')}")
            continue
        flag = "" if row["reported"] == row["counted"] else "  <-- ESCAPED"
        print(f"{row['layer']:26} {row['reported']:>8} {row['counted']:>8}  "
              f"{row['verdict']:8} {row['verdict_key']}{flag}")
        for name in row["non_string"]:
            print(f"{'':26} non-string gate: {name}")
    print()
    print("reported == counted for every layer"
          if all(r["reported"] == r["counted"] and not r.get("error")
                 for r in report)
          else "*** A LAYER REPORTED A GATE IT DID NOT COUNT ***")
    return 0 if evidence["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())