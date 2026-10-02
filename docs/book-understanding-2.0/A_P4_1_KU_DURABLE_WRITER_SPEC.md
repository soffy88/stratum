# A P4.1 KU DURABLE WRITER SPEC — Frozen KU 持久化

TASK=A_P4_1_KU_DURABLE_WRITER
AUTHORITY=A_REPOSITORY_ONLY
BASELINE=A_P4_KNOWLEDGE_UNIT_FREEZE (dfeb54c / c488aff)
STATUS=FROZEN

## 1. Objective

Turn a frozen knowledge unit held in memory into a durable A仓 asset:
written in one transaction, recoverable by a later process, unaltered by a
replay.

```
KUVerification(VERIFIED)
        |
        v
    Freeze Service
        |
        v
    knowledge_unit  +  ku_freeze_event
```

## 2. Migration

`074_a_ku_freeze_persistence.sql` — **CREATED and APPLIED to staging.**

Audited before writing: 073 already satisfies §4's canonical schema in
full, so **no ALTER of `knowledge_unit` was needed and none was written**.
073 additionally carries `title` and `evidence_count`, which are kept.
074 adds one table and five indexes.

- additive only, no `DROP`, no `ALTER`, no backfill (`INSERT` count 0)
- the only foreign key is `ku_freeze_event.knowledge_unit_id →
  knowledge_unit(id)` `ON DELETE RESTRICT`

### 2.1 `ku_freeze_event`

| Column | Type |
|---|---|
| `id` | TEXT PK |
| `knowledge_unit_id` | TEXT NOT NULL → `knowledge_unit(id)` RESTRICT |
| `event_type` | TEXT NOT NULL CHECK `CREATED`/`FROZEN`/`SUPERSEDED` |
| `from_status` | TEXT |
| `to_status` | TEXT NOT NULL CHECK `FREEZE_PENDING`/`FROZEN`/`FAILED` |
| `event_hash` | TEXT NOT NULL |
| `created_at` | TIMESTAMP NOT NULL |

`UNIQUE(knowledge_unit_id, event_type)` and `UNIQUE(event_hash)` are what
turn a replay into a no-op rather than a second copy.

### 2.2 Deviations from the draft

- **The durable writer persists the whole ancestry, not just the unit.**
  073 gives `knowledge_unit` three foreign keys reaching back through the
  verification, the candidate, the evidence, the reading run and the
  source version. Every stage before P4.1 ran in memory, so staging held
  the schema and none of the rows. Writing only the unit fails on its
  first foreign key — this was found by executing against a real database,
  not by reading. The writer therefore emits its ancestry, parents before
  children, inside the same transaction.
- **One event per unit, `FROZEN`.** §7 says "create freeze_event"
  (singular), §13 says `"events": 10` and §15 says `ku_freeze_event=10`
  for 10 units. §10 admits `CREATED` and `FROZEN` as types. Emitting both
  would give 20 and contradict the acceptance counts three times over. The
  unit row is its own record of existence, so the single event records the
  one state change that matters: `FREEZE_PENDING → FROZEN`.
  `CREATED` and `SUPERSEDED` stay defined in the schema and unemitted.
- **`knowledge_unit.id` uses §5's formula, which differs from P4's.**
  P4 froze `ku_<sha256(statement | evidence_fingerprint)[:12]>`; §5
  specifies `ku_<sha256(candidate_id | verification_id | content_hash)[:12]>`.
  All ten ids differ. §5 is implemented for the durable row because it is
  the explicit instruction for the asset everything downstream will cite,
  and binding the id to the verification is strictly better provenance. P4
  is frozen and was not rewritten. **This leaves two ids for one unit** —
  see the open items.

## 3. Persistence lifecycle

```
FREEZE_PENDING ──> FROZEN
       └───────> FAILED
```

`FAILED` is deliberately **not** a value of `knowledge_unit.freeze_status`,
whose CHECK admits only `VERIFIED`, `FREEZE_PENDING`, `FROZEN`,
`REJECTED`. A failed freeze leaves no unit row at all, so there is nothing
for `FAILED` to describe: it is the terminal outcome of an *attempt*, not
a state a unit is left in.

`FROZEN → MODIFY` and `FROZEN → DELETE` are refused by `update_unit`,
`delete_unit` and `delete_event`, and by the RESTRICT foreign keys.

## 4. The transaction

One `BEGIN` / `COMMIT` around every unit and every event. A failure
anywhere leaves the database exactly as it was.

Proven against staging, not just in memory: a script that inserted a
genuinely new unit and then violated a unique constraint left
`knowledge_unit` at 10 rows, `ku_freeze_event` at 10, and zero partial
rows.

**A real bug was caught by that test.** The first implementation applied
writes as they were handed to it, so the unit row landed and then the
event write failed — leaving exactly the half-written state the
transaction exists to prevent. Writes are now staged and merged only after
the last one succeeds.

## 5. Preconditions

Checked before the transaction opens, so a refusal writes nothing at all
rather than opening and rolling back: verification is `VERIFIED`, score
≥ 0.8, the candidate exists, the evidence chain resolves to an existing
source version, and the unit is anchored.

A failed precondition raises `PersistencePrecondition`; a failed
transaction returns `PersistenceResult(status=FAILED)` rather than
raising, because the caller still has nine units left to process.

## 6. Identity

```
ku_id      = "ku_"  + sha256(candidate_id|verification_id|content_hash)[:12]
event_id   = "kfe_" + sha256(ku_id|event_type|version)[:12]
event_hash = "keh_" + sha256(ku_id|event_type|from|to|version)[:16]
```

All content-derived — never `uuid4()`, never a sequence, never a
timestamp. `event_hash` is content-derived rather than bucketed by time on
purpose: that is precisely what lets `UNIQUE(event_hash)` make a replay a
no-op. `frozen_at` is the one non-deterministic value written, because
073 requires it on a `FROZEN` row; nothing depends on it.

## 7. Idempotency

Same `(candidate_id, verification_id, content_hash)` → first run inserts,
second run is a NOOP. Enforced twice over: the writer checks for an
existing row, and every emitted SQL statement carries
`ON CONFLICT DO NOTHING`. Verified against staging — the script was
applied twice and the counts stayed at 10 units, 10 events, 10 distinct
event hashes.

## 8. The runner

`ku_persistence_runner.py`. A reader for everything upstream: it never
modifies a candidate, a verification or an evidence row, asserted by
comparing a full snapshot before and after.

- `--sql PATH` emits the durable script for a DBA to execute
- `A_P4_1_LEDGER_FILE` supplies the migration ledger for the schema gate
- `A_P4_1_DB_COUNTS` supplies row counts read back from the database

No credential reaches the writer; both inputs are files a DBA-side query
produced.

## 9. Known limits

- **Two ids per unit.** See §2.2. The persisted id follows §5; the P4
  in-memory id is unchanged and still differs. Anything that cited a P4
  id will not match the durable row. This needs a decision, not a
  workaround.
- The ancestry write is the one thing this stage does that its own spec
  did not ask for. It is unavoidable — the foreign keys forbid anything
  else — but it means P4.1 now writes to `book_source` through
  `ku_verification` as well as to `knowledge_unit`.
- `SUPERSEDED` and `CREATED` are schema-only. Nothing emits them.
- Durability is proven against staging, not production. The staging
  database is disposable; no production database has ever received any of
  these migrations.
- No retry or resume policy. A failed attempt is reported per unit and the
  caller re-runs; the writer does not keep a queue.

PERSISTENCE_SPEC=PASS