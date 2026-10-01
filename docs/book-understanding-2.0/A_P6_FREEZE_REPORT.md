# A P6 FREEZE REPORT — Canonical KU Identity

TASK=A_P6_IDENTITY_CANONICALIZATION
BASELINE=A_P5_KU_EVOLUTION
REFREEZE=A_P6_IDENTITY_REFREEZE (see "RE-FREEZE" below)

A仓 now has one identity per knowledge unit. 11 canonical ids, 11 registered
aliases, zero ambiguity — and nothing already written had to move.

## THE_DECISION

`knowledge_unit.id` is the canonical id. P4's freeze id becomes a registered
alias that resolves to it.

```
    canonical_ku_id = ku_<sha256(candidate_id | verification_id | content_hash)[:12]>
    alias_id        = ku_<sha256(statement | evidence_fingerprint)[:12]>
```

The two differed for all 11 units. This is the decision P4.1 said it needed
rather than a workaround, and it is the one that costs nothing already
durable:

- the durable id binds the **verification** that admitted the unit — the
  stronger provenance of the two
- it is already what P4.1 wrote and what P5's revision chain links
- choosing P4's formula instead would mean rewriting 11 persisted
  `knowledge_unit.id` values, which is the mutation this task forbids

**No unit was renumbered. No third id was minted.** P6 names P4.1's formula
rather than restating it, so there is nothing to drift.

## MIGRATION_076

MIGRATION_076=PASS

- applied to `stratum_a_p3_staging`
- ledger verified by query: 070, 071, 072, 073, 074, 075, 076
- additive only: `ALTER` 0, `DROP` 0, `INSERT` 0 (no backfill)
- one new table, three indexes
- only FK `ku_identity.canonical_ku_id → knowledge_unit(id)` `ON DELETE RESTRICT`
- **070–075 byte-unchanged**
- no migration applied to `aii_kg`; no other database touched

## DURABLE_KU

DURABLE_KU=11 canonical ids, 11 alias rows

| table | rows | Δ from P5 |
|---|---|---|
| `knowledge_unit` | 11 | — |
| `ku_freeze_event` | 12 | — |
| `ku_revision` | 1 | — |
| `ku_review_event` | 5 | — |
| `ku_confidence_evolution` | 15 | — |
| `ku_relation` | 2 | — |
| `ku_identity` | **11** | new |

## G1_IDENTITY_UNIQUENESS

G1_IDENTITY_UNIQUENITY=PASS

```
ids_seen 22  →  CANONICAL 11  +  ALIAS 11
ambiguous          []
cross_namespace    []
orphans            []
misbound           []
```

- 11 distinct canonical ids, 11 distinct aliases, 11 rows — one per unit
- `UNIQUE(alias_id)` in the database is the load-bearing constraint; the gate
  reads the same rule from the application side, so a divergence between the
  two fails rather than passing quietly
- **no alias is another unit's canonical id** — the two namespaces share the
  `ku_<12 hex>` shape, so this had to be checked and was empty

Independently refused by the database, each confirmed by query:

| probe | refused by |
|---|---|
| one alias claimed by two units | `ku_identity_alias_uniq` |
| a unit as its own alias | `ku_identity_not_self` |
| an undeclared alias kind | `ku_identity_alias_kind_check` |
| a blank fingerprint | `ku_identity_id_fingerprint_check` |
| an alias for a unit that is not durable | `ku_identity_canonical_ku_id_fkey` |
| deleting the unit an alias names | RESTRICT |

## G2_HISTORICAL_REPLAY

G2_HISTORICAL_REPLAY=PASS

- **all 10 retired ids recorded in the P4 artifact still resolve.** That
  artifact is the honest test: it holds the ids a citation would have been
  made with before P4.1 existed
- all 11 canonical ids resolve to themselves
- an id nothing claims (`ku_000000000000`) comes back **UNRESOLVED**, not
  guessed at
- two independent rebuilds produce identical canonical ids, identical alias
  rows and identical fingerprints
- re-registering every retired id appends nothing
- **every alias is exactly the id P4's own formula produces** from its
  recorded inputs, and each recorded statement is the canonical unit's own
  statement, and each recorded evidence fingerprint is the one the
  verification actually computed — three things have to agree, not one
- the emitted script applied **three times** against staging: still 11 rows,
  11 distinct aliases, 11 distinct identity hashes

## G3_REVISION_CHAIN_INTACT

G3_REVISION_CHAIN_INTACT=PASS

- P5's revision links resolve, and resolution agrees with the link
- the superseded unit cited **by its retired id** still reads SUPERSEDED and
  still points at the same successor — otherwise a pre-P4.1 citation would
  resolve to a unit that no longer looks superseded
- the retired id is deliberately *not* in the lifecycle's fold: resolution is
  a lookup layer, and an alias that were also in the fold would be a second
  identity to keep in step
- the chain is still a chain: no unit is both a prior and a successor

## G4_P1_P5_REGRESSION

G4_P1_P5_REGRESSION=PASS

- P4 rebuilt on its own still produces exactly the 10 retired ids its
  artifact records — P4 is frozen and has not moved
- P5 still produces 11 units, 1 revision, 5 reviews, 1 SUPERSEDED, matching
  the committed P5 artifact field for field
- P4.1 still produces the same 10 durable rows
- `a-p4-v0.1` / `a-p4-1-v0.1` / `a-p5-v0.1` all unchanged — checked
  separately from the output check, because a stage that re-labelled itself
  would keep producing identical rows and still be lying
- P6 widened P5's sink seam (`TABLES` / `ROW_TYPES` / `ROW_BUCKETS`), so the
  P5 suite is re-run inside the P6 suite rather than assumed

## G5_AUTHORITY_ISOLATION

G5_AUTHORITY_ISOLATION=PASS

- 076 names only `ku_identity` and `knowledge_unit`; no DML anywhere in it
- `identity.py` imports only the A chain and the standard library, asserted
  against the source's own import statements rather than a forbidden-name
  list
- no B仓 table, `ku_onto` or concept table appears anywhere in the stage
- **no unit row changed.** A full snapshot of all 11 unit rows taken before
  registration and compared field by field after
- `renumber`, `repoint`, `update_identity`, `delete_identity`, `delete_unit`
  and `depend_on("B仓")` all raise

## AUTHORITY_SCAN

AUTHORITY_SCAN=PASS

- BU2_MUTATION=0, B_MUTATION=0
- 060–075 byte-unchanged
- the writable set across the whole replayed chain is the A chain plus
  `ku_identity` — asserted as a set, so no `bu*` table can appear in it

## TEST

- tests/architecture/test_a_repository_p6_identity.py: 95 passed
- tests/architecture/test_a_repository_p5_evolution.py: 116 passed
- tests/architecture/test_a_repository_p4_1_persistence.py: 55 passed
- tests/architecture/test_a_repository_p4_freeze.py: 58 passed
- tests/architecture/test_a_repository_p3_verification.py: 49 passed
- tests/architecture/test_a_repository_p2_quality.py: 33 passed
- tests/architecture/test_a_repository_contract.py: 22 passed
- tests/integration/test_a_authority_freeze.py: 22 passed
- tests/integration/test_a_p1_real_book.py: 11 passed
- A-suite total: 461 passed

Regression: `tests/architecture/ tests/integration/` without P6 gives
1 failed / 493 passed / 7 skipped / 16 errors; with P6 it gives
1 failed / 588 passed / 7 skipped / 16 errors. The delta is exactly the +95
P6 tests. **Zero regressions.** The remaining failure is `ulid.ULID` missing
from the installed `ulid` package, raised in `src/stratum/dao/users.py` —
code this stage does not touch; the 16 errors are the same cause.

Ruff (`E4,E7,E9,F`, the project's effective rule set) is clean on
`identity.py`, `ku_identity_runner.py`, `evolution.py`,
`ku_evolution_runner.py` and the P6 test file.

## TWO REAL BUGS, BOTH FOUND BY EXECUTING

076 first shipped **without an `id` column**, then **without an
`identity_hash` column**. The sink and the emitter both key rows by `id` and
both write `identity_hash`, so every insert failed against a real database —
`column "id" of relation "ku_identity" does not exist`, then the same for
`identity_hash`.

Neither is visible by reading the migration or the dataclass. Only the
disagreement between them is. So there is now a standing test: the columns the
emitter writes, the columns 076 declares, and the fields `IdentityAlias`
carries must all agree. The staging table was dropped and 076 re-applied
cleanly; nothing depended on it and it held no rows.

## DB_MUTATION

DB_MUTATION=staging only

- 076 applied to `stratum_a_p3_staging` (re-applied twice while fixing the two
  missing columns, on an empty table)
- the P6 script executed against that database three times; the first wrote
  the 11 identity rows, the second and third wrote nothing
- no migration applied to `aii_kg`; no other database touched
- BU2_MUTATION=0, B_MUTATION=0

## OPEN_ITEMS

1. **"An alias is never another unit's canonical id" is an application
   invariant, and it is now *proven* not to be declaratively expressible.**
   The original note said this would need a composite foreign key onto
   `knowledge_unit(id, id)` and therefore an `ALTER`. That reading was wrong,
   and the re-freeze tested it rather than repeating it:

   ```sql
   CREATE UNIQUE INDEX tmp_ku_id_id_uniq ON stratum.knowledge_unit (id, id);
   ALTER TABLE stratum.ku_identity ADD CONSTRAINT tmp_alias_not_a_unit_fk
     FOREIGN KEY (alias_id, alias_id)
     REFERENCES stratum.knowledge_unit (id, id);
   -- ERROR:  foreign key referenced-columns list must not contain duplicates
   ```

   So the 082 composite-key technique does not apply. The invariant is a
   **non-membership** claim; a foreign key asserts **membership**, and repeated
   referenced columns are refused outright. A CHECK cannot read another table
   and A仓 introduces no trigger or function.

   Frozen as `ALIAS_NAMESPACE_INVARIANT = SERVICE_ENFORCED_ONLY`, read by
   `cross_namespace_collisions()`, which is empty today. This is no longer an
   open question awaiting a decision; it is a settled limit.
2. **Both namespaces are `ku_<12 hex>`.** A reader cannot tell a canonical id
   from a retired one by shape alone. That is exactly why the alias table
   exists, and it is why open item 1 matters.
3. **`resolve()` scans the alias rows.** The row id binds the canonical id
   too, so a caller holding only an alias cannot compute it. Negligible at a
   unit's own alias count; `UNIQUE(alias_id)` provides the index at
   catalogue scale.
4. **Durability is proven against staging only.** No production database has
   received any migration from 070 onward.

## A_P6_COMPLETE

```
One identity          yes  11 canonical + 11 aliases, zero ambiguity
Nothing renumbered    yes  canonical IS knowledge_unit.id; renumber raises
No third id           yes  canonical delegates to P4.1's formula, never restates it
Old citations live    yes  all 10 P4-recorded ids resolve; unknown ids are UNRESOLVED
Aliases auditable     yes  every alias rebuilds from P4's own formula
Revision chain intact yes  both namespaces walk to the same successor
No frozen KU mutated  yes  11/11 unit rows byte-identical before and after
Authority isolated    yes  076 references knowledge_unit and nothing else
```

A_P6_IDENTITY=PASS
A_REPOSITORY_STATUS=FROZEN

STATUS=FROZEN

---

## RE-FREEZE — verdict gate repair

`A_P6_IDENTITY_REFREEZE_SPEC` audited this freeze and found the verdict did not
read the gates it reported.

```
gate_results()  reported   14
GATE_ORDER      counted     5
outside verdict           9
```

The nine: `G1_canonical_id`, `G2_citations_resolve`,
`G2_retired_id_recomputes`, `G3_successor_walk`, `G4_stage_versions`,
`G5_no_external_dependency`, `G5_no_mutation`, `idempotency`, `schema`.

Measured consequence, before the repair:

```
no A_P6_LEDGER_FILE  ->  schema = NOT_EXECUTED  ->  A_P6_IDENTITY = PASS
with ledger          ->  schema = PASS          ->  A_P6_IDENTITY = PASS
```

A gate that never executed produced a PASS. `gate_results`' own docstring said
"A gate that cannot be evidenced is NOT_EXECUTED" — true, and not honoured
downstream. Every P5.0–P5.5 layer blocks in this situation; P6 was the only one
that passed.

Repaired: `GATE_ORDER` is gone. `verdict()` derives from `gate_results` itself,
so there is exactly one place that decides and no parallel list to drift.

```
no A_P6_LEDGER_FILE  ->  schema = NOT_EXECUTED  ->  A_P6_IDENTITY = BLOCKED
with ledger          ->  schema = PASS          ->  A_P6_IDENTITY = PASS
```

Three verdict states rather than two — `PASS` / `FAIL` / `BLOCKED`. `FAIL`
outranks `BLOCKED` (positive evidence of breakage outranks missing evidence),
an empty gate set is `BLOCKED` rather than a vacuous pass, and an unrecognised
status is `BLOCKED` so a new gate cannot pass by default.

076 and 077–082 are untouched. No migration, schema or semantics changed: the
repair is to how the verdict is computed, not to what the layer records.

Open item 5 (from the re-freeze audit): `UNRESOLVED` stays an ephemeral
in-process return value. No table — a resolution record would be a resolution
authority, and that is a B/C semantic risk, not A仓 knowledge authority.

### RE-FREEZE 验收（冻结时核对）

```
P6 tests                          98 passed
tests/architecture  工作树         946 passed, 6 skipped
tests/architecture  干净检出       712 passed, 6 skipped
full tests/                       与 tagged baseline 逐项相同，无新增失败

076 2b9de6b42e1c1d87  077 fe4d613f5bb95508  078 ed963f7e82854b04
079 58910b307ea79b1f  080 6215e46078709bc8  081 0e9ebc2ddc443412
082 db3aa8f3f7673c20                        全部逐字节未动

migrations = 13    anchor = 11/12/1/11    ku_identity = 11
```

`712` 与 `946` 的差不是不一致，是范围不同：干净检出只含本层契约测试，
工作树另含尚未归档的 P5.0 / P5-evolution / P7 测试。

verdict 三态逐一构造验证：

```
{PASS, PASS}               -> PASS
{PASS, FAIL}               -> FAIL
{PASS, NOT_EXECUTED}       -> BLOCKED
{FAIL, NOT_EXECUTED}       -> FAIL      证据确凿的破坏优先于证据缺失
{}                         -> BLOCKED   空集合不是 vacuous pass
{PASS, SOMETHING_NEW}      -> BLOCKED   未识别状态不得默认通过
```

### P6_REFREEZE_READY

```
R-1  reported_set == verdict_set          PASS  14/14，verdict() 由 gate_results 派生
R-2  NOT_EXECUTED 不得产出 PASS            PASS  抽掉 ledger -> BLOCKED
R-3  裁定内全 PASS                        PASS  14/14 with ledger
R-4  schema 带 ledger 时 PASS              PASS
R-5  076 sha256 未变                       PASS  2b9de6b42e1c1d87
R-6  ku_identity 11 行 / anchor 11/12/1/11 PASS
R-7  open item 1 已改为「已证明不可声明式」 PASS
R-8  report 与 artifact 按新口径重出        PASS
R-9  98 个 P6 测试 + P5 契约全绿            PASS
R-10 干净 worktree 可复现                  PASS  712 passed, 6 skipped
```

### 后续顺序（已锁定）

```
P6 freeze commit + tag
  -> P5_EVOLUTION_REFREEZE_SPEC   （同类 verdict 缺陷：reported 8 / counted 6）
  -> P7 依赖闭包审计 + SPEC
```

P5-evolution 的缺陷**不在 P6 修**（`ORDER_LOCKED`）。
P7 之前必须先做依赖闭包审计：P6 已经暴露过一次文件级隐藏依赖，
P7 若不做审计，会在 freeze 时才发现，而不是在 spec 时。
