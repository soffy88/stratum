# A P4.1 FREEZE REPORT — KU Durable Writer

TASK=A_P4_1_KU_DURABLE_WRITER
BASELINE=A_P4_KNOWLEDGE_UNIT_FREEZE (dfeb54c / c488aff)

A仓's chain is now durable end to end: 10 frozen knowledge units and 10
freeze events exist as rows in a real PostgreSQL database, written in one
transaction, and a replay writes nothing.

## MIGRATION_074

MIGRATION_074=PASS

- applied to `stratum_a_p3_staging`
- ledger verified by query: 070, 071, 072, 073, 074
- additive only: `ALTER` 0, `DROP` 0, `INSERT` 0 (no backfill)
- **073 was not recreated and not altered** — audited first and found
  already complete, so no ALTER was needed
- `ku_freeze_event` FK `ON DELETE RESTRICT`, confirmed by query
- `UNIQUE(knowledge_unit_id, event_type)` + `UNIQUE(event_hash)`
- `aii_kg` untouched — ledger still ends at `066_bu2_p4_p9_repair.sql`

## VERIFIED_INPUT

VERIFIED_INPUT=10 (17 candidates, 10 verified at P3)

## PERSISTED_KU

PERSISTED_KU=10 durable rows, read back by query

| table | rows |
|---|---|
| `book_source` | 1 |
| `source_version` | 1 |
| `reading_run` | 1 |
| `reading_evidence` | 17 |
| `evidence_quality` | 17 |
| `ku_candidate` | 17 |
| `ku_verification` | 17 |
| `knowledge_unit` | **10** |
| `ku_freeze_event` | **10** |

The ancestry rows are not decoration: `knowledge_unit` has three foreign
keys reaching back to the book, and every stage before P4.1 ran in memory.

## FREEZE_EVENTS

FREEZE_EVENTS=10

One `FROZEN` event per unit, `FREEZE_PENDING → FROZEN`, 10 distinct
event hashes. See the spec §2.2 for why `CREATED` is defined but not
emitted.

## TRACEABILITY

TRACEABILITY=PASS

- unit → verification → candidate → evidence → source_version, 10/10
- 100%, 10 unique ids
- a second process built from scratch reproduces the same 10 durable ids
  and the same 10 event ids

## TRANSACTION_ATOMICITY

TRANSACTION_ATOMICITY=PASS

- one `BEGIN`/`COMMIT` per run; 91 statements inside it
- verified against the database, not only in memory: a script that
  inserted a new unit and then violated a unique constraint left 10 units,
  10 events, 0 partial rows

**A real bug was found this way.** The first implementation applied writes
as they arrived, so the unit row landed and the event write then failed —
exactly the half-written state the transaction forbids. Writes are now
staged and merged only after the last succeeds.

## CRASH_RECOVERY

CRASH_RECOVERY=PASS

Two independent checks:

- in memory: fault injection between the unit write and the event write
  leaves zero units and zero events
- in PostgreSQL: a transaction that inserted a genuinely new unit and then
  failed on a constraint rolled back completely — `ku_CRASHNEW` absent,
  counts unchanged at 10/10

## REPLAY

REPLAY=PASS

- the identical script applied twice against staging: still 10 units,
  10 events, 10 distinct event hashes
- every statement carries `ON CONFLICT DO NOTHING`
- `persist()` twice writes 0 units and 0 events
- 0 duplicate units, 0 duplicate events, 0 orphan events

## AUTHORITY_SCAN

AUTHORITY_SCAN=PASS

- the writer reaches nothing outside the A chain; the migration's only FK
  is `knowledge_unit`
- no `UPDATE`, no `DELETE FROM`, no `DROP` in 074
- the writer modifies no candidate, no verification and no evidence row —
  asserted by comparing a full snapshot before and after persistence

## TEST

- tests/architecture/test_a_repository_p4_1_persistence.py: 55 passed
- tests/architecture/test_a_repository_p4_freeze.py: 58 passed
- tests/architecture/test_a_repository_p3_verification.py: 49 passed
- tests/architecture/test_a_repository_p2_quality.py: 33 passed
- tests/architecture/test_a_repository_contract.py: 22 passed
- tests/integration/test_a_authority_freeze.py: 22 passed
- tests/integration/test_a_p1_real_book.py: 11 passed
- A-suite total: 250 passed

Regression: P1, P2, P3 and P4 all still pass. Migrations 070–073
byte-unchanged; the P2 classifier and P3 verifier untouched.

## DB_MUTATION

DB_MUTATION=staging only

- 074 applied to `stratum_a_p3_staging`
- **91 INSERTs executed against that database**: the A chain plus 10 frozen
  units and 10 freeze events
- no migration applied to `aii_kg`; no other database touched
- BU2_MUTATION=0, B_MUTATION=0

## OPEN ITEMS

1. **Two ids per unit.** §5 specifies `sha256(candidate_id | verification_id
   | content_hash)`; P4 froze `sha256(statement | evidence_fingerprint)`. All
   ten differ. This stage implements §5, so a durable row's id is *not* the
   id P4 minted. Anything that already cited a P4 id will not match. Needs a
   decision, not a workaround.
2. **This stage writes tables its spec did not mention.** Persisting a
   knowledge unit requires its ancestry, so the writer now inserts into
   `book_source` through `ku_verification` as well. Unavoidable given the
   foreign keys, but it widens P4.1's blast radius well past §17's list.
3. **Durability is proven against staging only.** Staging is disposable. No
   production database has received any migration from 070 onward.

## A_P4_COMPLETE

```
Frozen KU exists        yes  10 rows in knowledge_unit
Durable                 yes  in PostgreSQL, not memory
Replayable              yes  second run writes nothing
Immutable               yes  RESTRICT FKs, no UPDATE/DELETE path
```

STATUS=FROZEN