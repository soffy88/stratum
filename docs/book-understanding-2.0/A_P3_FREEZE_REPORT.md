# A P3 FREEZE REPORT — KU Verification 执行版

TASK=STRATUM_A_REPOSITORY_P3_KNOWLEDGE_UNIT_VERIFICATION
BASELINE=stratum-a-p2-evidence-quality-v0.1 (5fd748e)
PRIOR_DRAFT=5c9a03a

## MIGRATION_072

MIGRATION_072=PASS

- applied to `stratum_a_p3_staging` on the `aii-postgres` instance
- ledger verified by query, not asserted by hand:
  `070`, `071`, `072_a_ku_verification.sql`
- FK `candidate_id → ku_candidate(id)` ON DELETE CASCADE, confirmed
- three indexes present, plus the unique constraint's own index
- `ALTER TABLE` count 0; 072 remains the newest migration; 060–071 not
  edited
- the shared `aii_kg` database was not touched — its ledger still ends at
  `066_bu2_p4_p9_repair.sql`

Staging was rebuilt from scratch and 070→071→072 re-applied against the
final migration text, so the gate validates what is committed rather than
an earlier draft of the file.

## CANDIDATES_VERIFIED

CANDIDATES_VERIFIED=10/17

- book: 利率史（第四版） 第四版, 第一章 古代时期的信贷
- reading_run: arr_d0d1473d79fc
- candidates decided 17/17; PENDING 0, VERIFYING 0
- VERIFIED 10, REJECTED 7
- **false positives: 0**
- threshold 0.8, `verification_score = min(definition, trace, source, quality)`

| Rejected | definition_score | trace / source / quality | failed check |
|---|---|---|---|
| `kc_babylon_collateral_scope` | 0.50 | 1.00 / 1.00 / 1.00 | `definition_check` |
| `kc_credit_neolithic_origin` | 0.50 | 1.00 / 1.00 / 1.00 | `definition_check` |
| `kc_credit_precedes_writing` | 0.50 | 1.00 / 1.00 / 1.00 | `definition_check` |
| `kc_rome_servitude_allowed` | 0.50 | 1.00 / 1.00 / 1.00 | `definition_check` |
| `kc_solon_debt_relief` | 0.50 | 1.00 / 1.00 / 1.00 | `definition_check` |
| `kc_written_contract_required` | 0.50 | 1.00 / 1.00 / 1.00 | `definition_check` |
| `kc_babylon_grain_rate_cap` | 0.25 | 1.00 / 1.00 / 1.00 | `definition_check` |

Every rejection names the check that failed. All ten verified units score
1.000 on all four checks.

Six rejections are P2's `CONCEPT` mislabelling surfacing, not a P3 failure:
P2 tests numeric markers first, so propositional candidates get typed
`CONCEPT`, and GATE_3 correctly observes they define nothing. The seventh
is a lexicon gap — see the spec's known limits.

10/17 is accepted. Verification correctness outranks pass count.

## TRACEABILITY

TRACEABILITY=PASS

- 17/17 candidates resolve to evidence and a content hash — 100%
- 17 unique fingerprints, 0 duplicates
- candidate → evidence → reading run → source version → content hash

## AUTHORITY_SCAN

AUTHORITY_SCAN=PASS

- `verification.py`, `verification_runner.py` and migration 072 contain
  none of: `knowledge_claims`, `b_repository`, `c_repository`, `bu2`,
  `learning_object`, `graph`, `merge`, `dedup`
- 072 references exactly one table: `ku_candidate`
- the frozen P1 authority scan still passes over the whole package

## REPLAY

REPLAY=PASS

- 0 new candidates, 0 new verification rows, 0 duplicates
- identical report across independent runs
- 0 new events on the second pass
- verification ids content-derived from candidate id + verifier version
- a settled verdict is returned unchanged, never re-derived

## ACCEPTANCE GATES

| Gate | Result |
|---|---|
| P3_GATE_1 — 072 in the real schema | PASS |
| P3_GATE_2 — candidate integrity | PASS |
| P3_GATE_3 — verification quality | PASS |
| P3_GATE_4 — anchor verification | PASS |
| P3_GATE_5 — replay safety | PASS |

## TEST

- tests/architecture/test_a_repository_p3_verification.py: 49 passed
- tests/architecture/test_a_repository_p2_quality.py: 33 passed
- tests/architecture/test_a_repository_contract.py: 22 passed
- tests/integration/test_a_authority_freeze.py: 22 passed
- tests/integration/test_a_p1_real_book.py: 11 passed
- A-suite total: 137 passed

State machine coverage: `PENDING→VERIFYING`, `VERIFYING→VERIFIED`,
`VERIFYING→REJECTED` pass; `VERIFIED→REJECTED`, `VERIFIED→PENDING`,
`REJECTED→VERIFIED` raise. Replay asserts `new_rows == 0`.

## DB_MUTATION

DB_MUTATION=staging only

- 070, 071, 072 applied to `stratum_a_p3_staging` (a database created for
  this gate)
- no migration applied to `aii_kg` or any other existing database
- all verification execution is in-memory (`InMemoryAStore`)
- BU2_MUTATION=0, B_MUTATION=0

## CHANGES SINCE THE DRAFT

`5c9a03a` was a draft that could not be executed. The executed version:

- 072 gained `verification_score`, the four `*_check` columns and
  `verified_quote`; dropped `verification_method` and
  `verification_trace`
- `VERIFYING` added to the state machine
- four scores replace the pass/fail rule, combined by minimum
- GATE_1 is now real: applied and queried against a staging database
- the evidence artifact is now generated and drift-tested

STATUS=FROZEN