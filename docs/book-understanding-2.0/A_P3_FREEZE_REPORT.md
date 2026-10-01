# A P3 FREEZE REPORT — KU Candidate 验证层

TASK=STRATUM_A_REPOSITORY_P3_KU_VERIFICATION
BASELINE=stratum-a-p2-evidence-quality-v0.1 (COMMIT=5fd748e)

## PIPELINE

```
ReadingEvidence → EvidenceQuality → KU Candidate → KU Verified
                                          (P2)          (P3)
```

A仓 fact authority is unchanged. A verified unit is still a fact unit;
grouping units into concepts stays out of A仓.

## SCHEMA

SCHEMA=072

- `src/stratum/db/pg_migrations/072_a_ku_verification.sql`
- ADD ONLY: one new table, `stratum.ku_verification`
- `ALTER TABLE` count: 0 — no existing A table is altered
- migrations 060-071 not edited
- FK `candidate_id → stratum.ku_candidate(id)` UNIQUE
- `verification_trace JSONB NOT NULL`
- status CHECK = {PENDING, VERIFIED, REJECTED}, asserted equal to the
  Python enum

## CANDIDATES_VERIFIED

CANDIDATES_VERIFIED=10/17

- book: 利率史（第四版）, 第一章 古代时期的信贷
- reading_run: arr_d0d1473d79fc
- candidates decided: 17/17 (PENDING remaining: 0)
- VERIFIED: 10
- REJECTED: 7, every one with a reason and a trace

### Why 7 were rejected

| Reason | Count | Reading |
|---|---|---|
| `MISSING_DEFINITION_SPAN` | 6 | P2 typed these `CONCEPT`, but none contains a definitional marker |
| `MISSING_SUBJECT`, `MISSING_PREDICATE`, `MISSING_OBJECT` | 1 | `kc_babylon_grain_rate_cap`, quote `谷物贷款每年33.333%` — a bare rate with no relation word |

The six `CONCEPT` rejections are a **P2 defect surfacing, not a P3
failure**. P2's classifier is a marker heuristic that tests numeric
markers before concept and event branches, so propositional candidates
like `巴比伦允许土地、动产及人身作为债务抵押` are labelled `CONCEPT`. P3
then correctly observes that the span defines nothing and refuses it.
Fixing this belongs in P2's classifier; P2 is frozen, so the defect is
recorded rather than patched.

## TRACEABILITY

TRACEABILITY=PASS

- candidate → evidence → reading run → source version → content hash
- 17/17 decisions resolve to a source version with a content hash
- 100%
- `orphan_verifications`: 0

## AUTHORITY_SCAN

AUTHORITY_SCAN=PASS

- `verification.py`, `verification_runner.py` and migration 072 name no
  foreign table, no foreign repository, and no grouping or
  duplicate-elimination vocabulary
- 072 references only `stratum.ku_candidate`
- the frozen P1 authority scan still passes over the whole package
- a decision reads only the candidate, its evidence chain and the rules
  recorded in the trace

## REPLAY

REPLAY=PASS

- `report(build_verification_baseline())` identical across runs
- second run: 0 new rows, 17 existing, 0 new events
- verification ids content-derived from candidate id + verifier version
- a settled decision is returned unchanged, never re-derived
- second-run ids equal first-run ids

## LIFECYCLE

LIFECYCLE=PASS

- `PENDING → VERIFIED` legal
- `PENDING → REJECTED` legal
- `VERIFIED → PENDING` refused (`VerificationViolation`)
- `REJECTED → VERIFIED` refused (`VerificationViolation`)
- both terminal states have an empty transition set

## TEST

- tests/architecture/test_a_repository_p3_verification.py: 34 passed
- tests/architecture/test_a_repository_p2_quality.py: 33 passed
- tests/architecture/test_a_repository_contract.py: 22 passed
- tests/integration/test_a_authority_freeze.py: 22 passed
- tests/integration/test_a_p1_real_book.py: 11 passed
- A-suite total: 122 passed

Coverage required by the spec — schema (table, FK, status CHECK),
authority (forbidden-token scan, chain-only reads, no-quality and
broken-trace rejection), lifecycle (all four transitions), replay (same
id, no new rows, no new events, settled row never rewritten) — plus
semantic integrity per kind.

## DB_MUTATION

DB_MUTATION=072 only (written, not executed)

- all execution in-memory (`InMemoryAStore`); no DB access
- no migration was run against any database
- BU2_MUTATION=0, B_MUTATION=0

## ACCEPTANCE GATES

| Gate | Result |
|---|---|
| P3_GATE_1 — 072 applied in staging | **NOT EXECUTED** — no staging target, no DB client available |
| P3_GATE_2 — authority, A only | PASS |
| P3_GATE_3 — pipeline, 17/17 processed | PASS (17/17 decided) |
| P3_GATE_4 — trace 100% | PASS |
| P3_GATE_5 — replay noop | PASS |

The draft's pilot target of ≥17 VERIFIED is **not met** at 10/17. §8 of
the draft permits REJECTED provided each carries a reason and a trace,
which holds for all 7.

## OPEN ITEM

The VERIFIED/REJECTED split is sensitive to the marker vocabulary in
`verification.py`, which the draft did not supply. `kc_babylon_grain_rate_cap`
is rejected purely because `谷物贷款每年33.333%` contains no word from
`PREDICATE_MARKERS`; its sibling `kc_babylon_silver_rate_cap` verifies
only because its quote contains `计算`. The vocabulary was left as
written rather than widened to raise the count. Extending it is a
lexical decision that belongs to the owner of this spec, and widening it
to make a number look better would make the gate meaningless.

STATUS=FROZEN (pending P3_GATE_1)