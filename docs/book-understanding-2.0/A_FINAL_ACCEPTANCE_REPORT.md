# A仓 final acceptance report — P5 Evolution → P7

BASELINE=stratum-a-p5-evolution-freeze, stratum-a-p7-freeze
SCOPE=all A仓 gates reachable from those two freezes
METHOD=every gate re-run live, merged, verdict derived by the shared contract

```
FINAL VERDICT = PASS
gate_count   = 29
not executed = none
failed       = none
unknown      = none
contract     = FAIL > BLOCKED > PASS; derived from gate_results, no hardcoded gate list
```

The verdict is not written down anywhere in this repository. It is computed
from the 29 gates below by `verdict.py`, the same function
P5 Evolution, P6 and P7 each use for their own layer.

## The gates

| layer | gate | status |
|---|---|---|
| `P5_EVOLUTION` | `G1_traceability` | PASS |
| `P5_EVOLUTION` | `G2_immutability` | PASS |
| `P5_EVOLUTION` | `G3_revision` | PASS |
| `P5_EVOLUTION` | `G4_replay` | PASS |
| `P5_EVOLUTION` | `G5_authority` | PASS |
| `P5_EVOLUTION` | `G6_durability` | PASS |
| `P5_EVOLUTION` | `idempotency` | PASS |
| `P5_EVOLUTION` | `schema` | PASS |
| `P6_IDENTITY` | `G1_canonical_id` | PASS |
| `P6_IDENTITY` | `G1_identity_uniqueness` | PASS |
| `P6_IDENTITY` | `G2_citations_resolve` | PASS |
| `P6_IDENTITY` | `G2_historical_replay` | PASS |
| `P6_IDENTITY` | `G2_retired_id_recomputes` | PASS |
| `P6_IDENTITY` | `G3_revision_chain` | PASS |
| `P6_IDENTITY` | `G3_successor_walk` | PASS |
| `P6_IDENTITY` | `G4_regression` | PASS |
| `P6_IDENTITY` | `G4_stage_versions` | PASS |
| `P6_IDENTITY` | `G5_authority` | PASS |
| `P6_IDENTITY` | `G5_no_external_dependency` | PASS |
| `P6_IDENTITY` | `G5_no_mutation` | PASS |
| `P6_IDENTITY` | `idempotency` | PASS |
| `P6_IDENTITY` | `schema` | PASS |
| `P7_PROJECTION` | `G1_authority` | PASS |
| `P7_PROJECTION` | `G1_no_new_id` | PASS |
| `P7_PROJECTION` | `G1_read_only` | PASS |
| `P7_PROJECTION` | `G2_traceability` | PASS |
| `P7_PROJECTION` | `G3_determinism` | PASS |
| `P7_PROJECTION` | `G4_replay` | PASS |
| `P7_PROJECTION` | `G5_isolation` | PASS |

## The derivation responds

A verdict that cannot go wrong is not a verdict. Four controls, run against the
same function:

```
as measured, 29 gates all PASS      -> PASS
one gate injected FAIL              -> FAIL
schema gate left unevidenced        -> BLOCKED
one unrecognised status             -> BLOCKED
empty gate set                      -> BLOCKED
```

And every reported gate is counted, per layer, with no escape:

```
P5_EVOLUTION    reported= 8  counted= 8
P6_IDENTITY     reported=14  counted=14
P7_PROJECTION   reported= 7  counted= 7
```

That last line is the whole point of this exercise. It is the check P5 Evolution
and P6 both failed — 8 reported and 6 counted, then 14 reported and 12 counted
— and P7's own `GATE_ORDER` listed 5 names beside 7 returned gates. A gate that
is printed to the reader and left out of the outcome is a gate that cannot fail
the stage.

## Authority audit

```
tables written by the chain            21, every one an A table in `stratum`
writes outside the stratum schema      0
migrations changed since the P5 tag    0 files
A migration fingerprints               13/13 unchanged
  070 179e9e26c17f13e6   071 6116f929ff5976a5   072 7a210f1130389037
  073 4285c1be7a6c4a0c   074 9d3651f35668ddd3   075 b29432e8340faedc
  076 2b9de6b42e1c1d87   077 fe4d613f5bb95508   078 ed963f7e82854b04
  079 58910b307ea79b1f   080 6215e46078709bc8   081 0e9ebc2ddc443412
  082 db3aa8f3f7673c20
destructive statements in the A chain  0
```

The emitted SQL writes **unqualified** table names under
`SET search_path TO stratum, public`. The writes therefore resolve to the A
schema because `stratum` comes first in the path, not because each statement
names it. All 21 targets were confirmed to exist in `stratum`, and all 21 are
among the A tables — but the qualification is a property of the search path
rather than of the statements, and that is worth stating rather than leaving to
be discovered.

## Regression

```
CURRENT_FAILURES - BASELINE_FAILURES = EMPTY
```

Compared by test id against a clean worktree, not by count. The ambient
baseline of 48 failures and 169 errors is unchanged and unrelated to A仓.

## Carried, not closed

Two things the final verdict does **not** cover, stated here so it cannot be
mistaken for a pass:

1. **`P5_0_CONDITION` cannot be verified from a clean checkout.** Its contract
   test is untracked, so `--verify` cannot run it and its gates have not been
   re-measured. It is not among the layers above, and this report does not
   claim it.
2. **P7's acceptance check C5 was too broad.** It counted `%projection%` OR
   `%p7%` tables and got 0, true on staging and false on a complete database
   where migrations 047-049 contribute three tables belonging to other
   subsystems. It passed for the wrong reason. The invariant P7 claims — it
   declares no table — holds on both databases when measured as `*p7*` plus
   `schema_change_count()`.

Also unchanged and still open: the five items in `A_P5_FREEZE_REPORT.md`, the
limits in `A_P7_BOOK_UNDERSTANDING_PROJECTION_SPEC.md` §15, and the P5 spec's
own §11 known limitations. `reading_status` is still always `READING`, and
`last_run_id` is still last-by-id rather than by time.

## Evidence

```
A_FINAL_CHAIN_ACCEPTANCE.md    apply from zero, replay x3, interrupt/resume
A_P5_FREEZE_REPORT.md          P5 Evolution re-freeze, 12 negative probes
A_P7_FREEZE_REPORT.md          P7 verdict defects and read-only cross-check
A_DEPENDENCY_CLOSURE_AUDIT.md  closure per layer, tool blind spots, P5_0 gap
TEST_BASELINE.md               failure sets, and the WIP-only extra pass
```
