# A P7 BOOK UNDERSTANDING PROJECTION — FREEZE REPORT

TASK=A_P7_BOOK_UNDERSTANDING_PROJECTION
AUTHORITY=A_REPOSITORY
BASELINE=A_P6_IDENTITY_CANONICALIZATION
STATUS=FROZEN

This report is opened before the freeze, not written after it. The first
half is the audit that reopened the stage; the second half is the evidence
gathered once the defects were fixed.

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

## FIX_THE_TWO_DEFECTS

`GATE_ORDER` deleted; `report()` now derives its verdict from the mapping
`gate_results()` returns, via the same `verdict.py` contract P5 Evolution and P6
use. All three layers now decide their outcome the same way.

The old test iterated `GATE_ORDER`, so it checked five of seven gates, then
swept the remainder with a loop permitting `NOT_EXECUTED` — a gate that never
ran still satisfied a test called "all five gates pass". It now names every gate
and permits none to be unevidenced.

### Four mutations, all caught

```
reintroduce GATE_ORDER                         caught
drop the verdict from the report               caught
drop the verdict key                           caught
subset the gates fed to the verdict            caught, after one more test
```

The fourth nearly slipped, and it is the one worth remembering. Feeding a
five-gate subset to `verdict()` **looks correct whenever every gate passes**,
because two gates and seven gates both yield PASS. It was caught only by
breaking `G1_no_new_id` — a gate the deleted list never named. That is the P5/P6
defect in its exact shape: a gate reported to the reader and left out of the
thing that decides the outcome. A test comparing the report's verdict against
`verdict(gates)` cannot see it.

## DB_ACCEPTANCE — read-only cross-check

Spec §5 forbids P7 from touching a database, so there is nothing to migrate,
replay or resume for this stage. Instead every number the artifact asserts was
recomputed from `stratum_a_p3_staging` and compared. Nothing was written.

```
#   check                                              artifact   database
C1  knowledge_unit rows                                 —          11
C1  traversal units + superseded_units                  10 + 1     11
C2  reading_evidence rows                              17         17
C3  evidence_quality rows                              —          17
C4  reading_run id                                     arr_d0d1473d79fc   same
C4  source_version id                                  sv_f548f51a5df5   same
C5  projection/p7 tables in schema                     0          0
C6  baseline anchor                                    —          11/12/1/11
C7  distinct candidate_id across units                 —          11
C8  units not superseded                               10         10
                                                          10/10
```

### C7 needs explaining, because 11 ≠ 10 on its face

The artifact reports `ku_count` 10; the table holds 11 units, each with its own
`candidate_id`. Both numbers are right, and the difference is the revision:

```
superseded unit   ku_59cb9040d0f0   candidate kc_378111b6120b
its successor     ku_10fef8f2ffa4   candidate kc_696d452b1fb2
units not superseded                     10
distinct candidate_id on those           10
```

The reading map counts units that are not superseded, and the superseded unit
holds a candidate id of its own — so the successor is not a re-labelling of the
row it replaced. That is a fact about the chain, reported as
`superseded_units: 1`, not an adjustment made to make a number fit.

The superseded status lives in the review ledger, not in
`knowledge_unit.freeze_status`: all 11 rows read `FROZEN`, and SUPERSEDED is
folded from `ku_review_event`. An earlier attempt at this cross-check filtered
`knowledge_unit.freeze_status='ACTIVE'` and returned 0, which is what sent me
looking — a first guess at a column's values is not evidence.

## FREEZE_GATE

Same refusal P5 Evolution needed, for the same reason. Writing
`artifacts/a_repository/p7_projection/p7_freeze.json` requires the gates to
reach PASS **and** `dependency_closure` and `db_acceptance` to be recorded.
Absent evidence stays `UNVERIFIED`.

The P5 freeze gate was first written to check only the evidence and let a
blocked layer through; it is not repeated here. Verified by mutation: removing
the verdict check from `freeze_blockers()` fails 2 tests.

`declared_migrations` is 0 **by design** — P7 declares no table — so it is
reported as a design fact rather than a measurement. The A chain the projection
reads *is* measured: 13 fingerprints, 0 destructive statements, recorded so a
read-only stage can still say which rows it read.

## OUTCOME

```
A_P7_PROJECTION_FREEZE   = PASS
gates                     = 7/7 PASS, verdict derived, 0 not executed
declared_migrations       = 0        schema_change = 0   db_mutation = 0
chain_read                = 13       destructive_in_chain_read = 0
db_acceptance             = PASS     read-only cross-check, 10/10
tests                     = 81       architecture 966 passed, 6 skipped
BASE_SHA                  = 5c33a2dc602a22855da4dec65eb472861381f2d5
```

`base_sha` is the parent commit, the tree this evidence was measured against.

### Carried forward, unchanged

The limits the spec already stated are not erased by this freeze:

- `reading_status` is always `READING`; the chain never advanced it.
- `last_run_id` is the last **by id**, not by time — P4.1's emitter does not
  write `reading_run.started_at` / `completed_at`.
- Traversal tiebreak on `evidence_id` carries no meaning. It is stable and
  content-derived so replay agrees, and a reader must not read meaning into it.
- One chapter, five sections in the pilot corpus, so `chapters` has length 1 and
  `same_chapter_units` is all 10 units. A fact about the corpus, not a limit of
  the view.
- `resolve()` still scans alias rows, as P6's does.

### Open elsewhere, not fixed here

`P5_0_CONDITION`'s contract test is untracked, so its gates cannot be verified
from a clean checkout. See `A_DEPENDENCY_CLOSURE_AUDIT.md`. It does not block
this stage but must not be treated as closed in the final acceptance.

