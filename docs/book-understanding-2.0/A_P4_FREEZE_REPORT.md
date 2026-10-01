# A P4 FREEZE REPORT — Frozen Knowledge Unit

TASK=STRATUM_A_P4_KNOWLEDGE_UNIT_FREEZE
BASELINE=stratum-a-p3-ku-verification-v0.1 (d67a0a5)

```
SourceVersion → ReadingEvidence → KU Candidate → KU Verification → Frozen KU
```

A仓's final knowledge object: a stable, citable projection of a verified
candidate. Not a truth judgement, not a concept.

## MIGRATION_073

MIGRATION_073=PASS

- applied to `stratum_a_p3_staging`
- ledger verified by query: 070, 071, 072, 073
- one new table, `ALTER TABLE` count 0, **no `INSERT` — no data backfill**
- three FKs, all `ON DELETE RESTRICT` (confirmed by query)
- three unique constraints + four check constraints + three indexes
- confirmed live: 10 rows exist in `stratum.knowledge_unit` after the run
- `aii_kg` untouched — its ledger still ends at `066_bu2_p4_p9_repair.sql`

RESTRICT rather than CASCADE is the load-bearing choice: a frozen unit
must outlive attempts to delete its chain.

## VERIFIED_INPUT

VERIFIED_INPUT=17 presented, 10 passed, 7 rejected at P3

## FROZEN_KU

FROZEN_KU=10

| frozen unit | canonical_text | score |
|---|---|---|
| `ku_786628598c94` | 雅典出现了一次经济危机 | 1.0 |
| `ku_d3f2fe6c4a16` | 银子贷款按重量计算每年20% | 1.0 |
| `ku_a44f563cfe25` | 信贷在古代和中世纪时期就得到了普遍应用 | 1.0 |
| `ku_5598d00f0c90` | 第一部已知最早的正式法典 | 1.0 |
| `ku_1f5ed939b386` | 将被处以4倍损害赔偿 | 1.0 |
| `ku_35059d773f8d` | 贷款的利息被限制为不得超过每年8.333% | 1.0 |
| `ku_740f36615879` | 索伦的法典取消了对利率的所有限制 | 1.0 |
| `ku_413413c3af3d` | 古希腊的法律史始于索伦（Solon）的法典 | 1.0 |
| `ku_a66d80954630` | 更多的是模仿《汉谟拉比法典》 | 1.0 |
| `ku_e0dcd52d6f6b` | 债务的本金就会被免除 | 1.0 |

10, not 17. A rejected candidate never enters the frozen set — the
rejected set and the frozen set are disjoint, asserted directly.

## TRACEABILITY

TRACEABILITY=PASS

- unit → verification → candidate → evidence → source_version, 10/10
- 100%
- 10 unique ids, 10 unique content hashes, 0 orphans, 0 unanchored
- every `canonical_text` is a substring of its evidence content
- every `statement` equals the candidate's own content — the freeze stage
  writes no wording of its own

## AUTHORITY_SCAN

AUTHORITY_SCAN=PASS

- `freeze.py` and `ku_freeze_runner.py` contain no foreign table, no
  foreign repository, no claim store
- 073 references exactly `{ku_verification, ku_candidate, source_version}`
- GATE_3 is structural: allowed FK targets, no `ALTER TABLE`, no `INSERT`
- AST-level scan confirms no grouping vocabulary in code identifiers or
  non-docstring strings. Prose is exempt, so a docstring saying "this is
  not a concept" does not fail the gate while a `cluster_concepts()`
  function would

## REPLAY

REPLAY=PASS

- `freeze()` twice: 0 new rows, 0 duplicates
- second pass produces an identical report
- ids are content-derived, so a replay resolves the same units

## IMMUTABILITY

IMMUTABILITY=PASS

- `VERIFIED → FREEZE_PENDING → FROZEN` legal
- `FREEZE_PENDING → REJECTED` legal
- `FROZEN → VERIFIED` refused
- statement update, canonical_text update, evidence replacement,
  verification replacement, delete — all refused
- refused for a `FREEZE_PENDING` row too: immutability is the rule, not a
  `FROZEN` special case

## TEST

- tests/architecture/test_a_repository_p4_freeze.py: 58 passed
- tests/architecture/test_a_repository_p3_verification.py: 49 passed
- tests/architecture/test_a_repository_p2_quality.py: 33 passed
- tests/architecture/test_a_repository_contract.py: 22 passed
- tests/integration/test_a_authority_freeze.py: 22 passed
- tests/integration/test_a_p1_real_book.py: 11 passed
- A-suite total: 195 passed

## DB_MUTATION

DB_MUTATION=staging only

- 073 applied to `stratum_a_p3_staging`, a database created for the A
  staging gates
- no migration applied to `aii_kg` or any other existing database
- all freeze execution is in-memory (`InMemoryAStore`)
- BU2_MUTATION=0, B_MUTATION=0

## COMMIT BOUNDARY

Untouched, asserted by tests: migrations 060–072, the P2 classifier, P3's
verification logic.

**One incident during this stage.** An earlier draft of the freeze runner
was written to `freeze_runner.py`, overwriting P1's baseline runner —
whose name the package already owned. It was caught immediately by a
circular import, reverted with `git checkout`, and the P4 runner was
written to `ku_freeze_runner.py` instead. P1's file is byte-identical to
its committed version and the P1 suite passes. Recorded here because the
P1 baseline is a frozen artifact and it was briefly clobbered.

## KNOWN LIMITS

Carried forward and unchanged by this stage: the 10 frozen units are
verified as *sourced and anchored*, not as correct. Six of the 17
candidates remain rejected on P2's `CONCEPT` mislabelling, and
`kc_babylon_grain_rate_cap` on a P3 lexicon gap. See
`A_P4_KNOWLEDGE_UNIT_FREEZE_SPEC.md` §9.

STATUS=FROZEN