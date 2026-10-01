# A P7 BOOK UNDERSTANDING PROJECTION — FREEZE REPORT

TASK=A_P7_BOOK_UNDERSTANDING_PROJECTION
AUTHORITY=A_REPOSITORY
BASELINE=A_P6_IDENTITY_CANONICALIZATION
STATUS=IN_PROGRESS (spec committed; runner and verdict land in STEP 7)

This report is opened before the freeze, not written after it. What follows is
the audit that reopened the stage and the evidence gathered so far; the closing
section is added only when every gate has run.

## WHY THIS STAGE WAS AUDITED

P5 Evolution and P6 were both reopened for the same defect: a verdict that
reported gates it did not count. Comparing them found it twice. P7 had not been
compared against either, so it was compared now.

## DEFECT_1_PARALLEL_GATE_LIST_ALREADY_DRIFTED

`projection_builder.py` defined a hardcoded list next to the gates it reported:

```
gate_results() returns   7   G1_authority G1_no_new_id G1_read_only
                                G2_traceability G3_determinism
                                G4_replay G5_isolation
GATE_ORDER                5   G1_authority G2_traceability
                                G3_determinism G4_replay G5_isolation
missing from the list      2   G1_no_new_id, G1_read_only
```

The list was already wrong on the day it was written, not after some later
change. Two gates — the ones asserting that P7 invents no new identity and that
it writes nothing — were reported to the reader and absent from the list that
orders them. This is precisely the mechanism the shared `verdict.py` docstring
warns about: a parallel list is the thing that lets reported gates fall outside
the outcome, and it drifts the moment a gate is added.

## DEFECT_2_NO_VERDICT_AT_ALL

`report()` emitted `gates` but no verdict. Every other layer derives one. P7
could print seven PASS strings and nothing would say whether the stage passed,
because nothing read them.

Both are the same class of problem, so both are fixed in one place: the verdict
comes from `gate_results()` via the shared contract, and `GATE_ORDER` is
deleted rather than corrected. Correcting a list of five to a list of seven
would leave the mechanism in place for the eighth.

## STEP 5_SPEC_AUDIT

The spec existed but was untracked. Two factual claims in it were checked before
committing it rather than after:

```
claim                                   found
"ledger 仍是 7 条、最新 076"             FALSE — 13 migrations, newest 082
"七张 A 表 (11/12/1/5/15/2/11)"          STALE — nine tables now, counts above
"projection/p7 相关表数量为 0"            TRUE — 0 of 22 tables in `stratum`
"tests ... 71 passed"                    TRUE — 71 passed
```

The ledger claim was not falsified by any edit to P7. The A chain moved on
underneath it: P5 and P6 extended 070–076 to 070–082. A freeze document that
asserts a database fact has to be re-checked against the database at freeze
time, because the chain it measured is not the chain that now exists.

## CARRIED FORWARD FROM THE SPEC

Two limits the spec already stated, repeated here so they are not lost:

- `reading_status` is always `READING`; the chain never advanced it.
- `last_run_id` is the last **by id**, not by time, because P4.1's emitter does
  not write `reading_run.started_at` / `completed_at`.

The five pilot-corpus limits in §15, the read-only structural argument in §15,
and the tiebreak-has-no-meaning note in §4.3 all stand unchanged.

## DB_ACCEPTANCE_FOR_THIS_STAGE

Spec §5 forbids P7 from touching a database, so "migrate, replay, resume" has
nothing to act on. Acceptance for P7 is a **read-only cross-check**: the
projection's per-chapter `ku_count` / `evidence_count` / `verified_count` and
every identity it emits are compared against the rows actually present in
`stratum_a_p3_staging`. Nothing is written. The full-chain migrate / replay /
interrupt-and-resume evidence belongs to the final acceptance, where the A
chain is applied to a clean database and P7 is rebuilt after each replay.
