# A P5 FREEZE REPORT — KU Lifecycle Evolution

TASK=A_P5_KNOWLEDGE_UNIT_EVOLUTION
BASELINE=A_P4_1_KU_DURABLE_WRITER (79dce2d)

A仓's knowledge units now have a history. 11 durable units, 1 revision,
5 review events, 15 confidence observations and 2 relations exist as rows
in a real PostgreSQL database, written in one transaction, and a replay
writes nothing.

## MIGRATION_075

MIGRATION_075=PASS

- applied to `stratum_a_p3_staging`
- ledger verified by query: 070, 071, 072, 073, 074, 075
- additive only: `ALTER` 0, `DROP` 0, `INSERT` 0 (no backfill)
- four new tables, nine indexes
- **070–074 byte-unchanged** — `git status` on the migration directory shows
  only the new file
- every foreign key `ON DELETE RESTRICT`, confirmed by query
- `aii_kg` untouched — no migration applied outside the A staging database

## DURABLE_KU

DURABLE_KU=11 rows, read back by query

| table | rows | Δ from P4.1 |
|---|---|---|
| `book_source` | 1 | — |
| `source_version` | 1 | — |
| `reading_run` | 1 | — |
| `reading_evidence` | 17 | — |
| `evidence_quality` | 17 | — |
| `ku_candidate` | 18 | **+1** (the revision's candidate) |
| `ku_verification` | 18 | **+1** (the revision's verification) |
| `knowledge_unit` | **11** | **+1** (the successor) |
| `ku_freeze_event` | **12** | **+2** (successor's FROZEN, prior's SUPERSEDED) |
| `ku_revision` | **1** | new |
| `ku_review_event` | **5** | new |
| `ku_confidence_evolution` | **15** | new |
| `ku_relation` | **2** | new |

Nothing was overwritten. Every delta is an addition.

## LIFECYCLE

```
    ACTIVE ──> QUARANTINED ──> ACTIVE
       │             │
       └─────────────┴──────> SUPERSEDED   (terminal)
```

STATUS_BREAKDOWN={"ACTIVE": 10, "QUARANTINED": 0, "SUPERSEDED": 1}

- 074's `SUPERSEDED` — defined by P4.1 and emitted by nothing — is now
  emitted once, on the unit the revision replaced
- `kc_athens_debt_crisis` carries `QUARANTINED → RELEASED`; both steps stay
  on the record, the release does not erase the quarantine
- `kc_solon_abolished_rate_cap` carries a `CHALLENGED` signal and stays
  ACTIVE: a signal is recorded, the status is not moved

## G1_TRACEABILITY

G1_TRACEABILITY=PASS

- unit → verification → candidate → evidence → source_version, 11/11, 100%
- **5/5 review events** cite real evidence from their own unit's book
- 0 orphan revisions, reviews, observations or relations

## G2_IMMUTABILITY

G2_IMMUTABILITY=PASS

- a full row snapshot of all 10 prior units taken before the lifecycle and
  compared field by field after: identical
- the superseded unit still carries its own original text, verified by query
  against the database:

| | prior `ku_59cb9040d0f0` | successor `ku_10fef8f2ffa4` |
|---|---|---|
| statement | 《汉谟拉比法典》（约前1800年）是最早的成文信贷法典之一 | 《汉谟拉比法典》（约公元前1800年）是最早的成文信贷法典之一 |
| cited span | 第一部已知最早的正式法典 | 在大约公元前1800年，……制订了第一部已知最早的正式法典。 |
| freeze_status | FROZEN | FROZEN |

- `update_unit`, `set_status`, `delete_*`, `supersede`, `merge_units` and
  `dedupe_units` all raise
- **the database refuses the deletes too**: `DELETE` on either endpoint of a
  revision is rejected by RESTRICT

## G3_REVISION

G3_REVISION=PASS

- a revision appends a successor that is a distinct unit behind its own
  candidate and its own verification
- `UNIQUE(prior_unit_id)` holds at the database — a second successor is
  rejected — so a history is a chain and never a tree
- a revision may not cross source versions: a successor from another book is
  refused, because calling that a revision would silently re-source a
  citation
- a revision without a basis is refused

## G4_REPLAY

G4_REPLAY=PASS

- two independent builds produce identical fingerprints for all 36 rows
- the identical SQL script applied **three times** against staging: still
  11 / 12 / 1 / 5 / 15 / 2 rows, and 12 / 1 / 5 / 15 / 2 distinct hashes
- re-running the review ledger, the revisions, the baseline confidence sweep
  and the derived-relation sweep each append nothing
- every statement in the emitted script carries `ON CONFLICT DO NOTHING`
- 0 duplicate revisions, 0 duplicate reviews, 0 duplicate relations

**A real bug was found by this gate.** The first implementation allocated the
next `sequence` *before* checking whether an equivalent row already existed,
so a replay saw sequence 1 taken, minted sequence 2, and appended a second
CHALLENGED event — turning a replay into a write. Identity is now
content-addressed: a review's identity is what it says and what it read, not
its position in a list.

## G5_AUTHORITY

G5_AUTHORITY=PASS

- 075 declares four tables and nothing else; no DML anywhere in it
- every `stratum.X` the migration names is one of the four tables it creates
  or one of the two permitted reference targets, so the migration is
  structurally unable to reach another repository
- no unit exists without its evidence chain; no review exists without
  evidence; a review citing another book's evidence is refused in the service
- the schema refuses the same things independently, each confirmed by query:

| probe | refused by |
|---|---|
| a review with `evidence_id` NULL | `ku_review_event_evidence_id` NOT NULL |
| a review with a blank rationale | `ku_review_event_rationale_check` |
| a second successor for one unit | `ku_revision_prior_uniq` |
| a unit revising itself | `ku_revision_not_self` |
| a relation not canonically ordered | `ku_relation_ordered` |
| confidence 4.0 | `ku_confidence_evolution_measured_confidence_check` |
| a second SUPERSEDED event per unit | `ku_freeze_event_uniq` (074) |
| `relation_type = 'EQUIVALENT_TO'` | `ku_relation_relation_type_check` |
| deleting either endpoint of a revision | RESTRICT |

## G6_DURABILITY

G6_DURABILITY=PASS

- a second process rebuilt from scratch produces identical ids and
  fingerprints for every row
- all five write positions of a revision are exercised with injected
  failures — the revision row, the review row, the SUPERSEDED event, the
  observations and the relations. At every position: status FAILED, zero
  rows in the four lifecycle tables, rollback counted, and the unit that
  would have been retired still reads ACTIVE
- in PostgreSQL: a transaction that inserted a revision row and then rolled
  back left the table unchanged (1 row visible inside, 0 after), with all
  counts unmoved at 11 / 1 / 5 / 15 / 2

## AUTHORITY_SCAN

AUTHORITY_SCAN=PASS

- the writer reaches nothing outside the A chain
- no B仓 table, no `ku_onto`, no concept table is named anywhere in 075
- `merge_units` and `dedupe_units` exist only to raise
- the relation vocabulary has no value meaning "these say the same thing";
  a test asserts it contains no `EQUIVALENT`, `SAME_CONCEPT`, `DUPLICATE`,
  `MERGED`, `CONTRADICTS` or `CONFLICTS`
- BU2_MUTATION=0, B_MUTATION=0

## TEST

- tests/architecture/test_a_repository_p5_evolution.py: 116 passed
- tests/architecture/test_a_repository_p4_1_persistence.py: 55 passed
- tests/architecture/test_a_repository_p4_freeze.py: 58 passed
- tests/architecture/test_a_repository_p3_verification.py: 49 passed
- tests/architecture/test_a_repository_p2_quality.py: 33 passed
- tests/architecture/test_a_repository_contract.py: 22 passed
- tests/integration/test_a_authority_freeze.py: 22 passed
- tests/integration/test_a_p1_real_book.py: 11 passed
- A-suite total: 366 passed

Regression: `tests/architecture/ tests/integration/` with P5 fully removed
gives 2 failed / 375 passed / 16 errors; with P5 it gives 2 failed / 491
passed / 16 errors. The delta is exactly the +116 P5 tests. **Zero
regressions.** The 2 failures and 16 errors are pre-existing and unrelated —
one needs a live production HTTP endpoint, the rest are
`ulid.ULID` missing from the installed `ulid` package.

Ruff (`E4,E7,E9,F`, the project's effective rule set) is clean on
`evolution.py`, `ku_evolution_runner.py`, `pilot_corpus.py` and the P5 test
file.

Migrations 070–074 byte-unchanged. P4 and P4.1 logic untouched, and both of
their versions still read `a-p4-v0.1` / `a-p4-1-v0.1`.

## DB_MUTATION

DB_MUTATION=staging only

- 075 applied to `stratum_a_p3_staging`
- the P5 script executed against that database three times; the first wrote
  the 36 rows, the second and third wrote nothing
- no migration applied to `aii_kg`; no other database touched
- BU2_MUTATION=0, B_MUTATION=0

## OPEN_ITEMS

1. **Two ids per unit, still open.** Unchanged by P5 and deliberately so.
   The durable id follows P4.1 §5; P4's in-memory id still differs. P5's
   revision chain runs on the durable id. This needs a decision, not a
   workaround.
2. **P5 writes tables its own spec did not mention.** A revision must
   persist a new unit, and that unit's foreign keys reach `ku_candidate` and
   `ku_verification`, so the ancestry is written too — the same discovery
   P4.1 made and documented. It widens P5's blast radius.
3. **The fold is a read, not a materialised column.** `status_of()` costs a
   scan of a unit's review events. At the pilot's scale that is irrelevant;
   at catalogue scale a reader would want a projection, and a projection is
   a cache, not authority.
4. **A revision's `_require_traceable` is used by gates through a
   private-name method.** A deliberate trade-off, not a design.
5. **Durability is proven against staging only.** No production database has
   received any migration from 070 onward.

## A_P5_COMPLETE

```
Lifecycle                yes  ACTIVE / QUARANTINED / SUPERSEDED, folded from an append-only log
Immutable                yes  no unit row changed; RESTRICT refuses the deletes in the database too
Revision                 yes  successor appended, prior row intact, chain never forks
Review evidence-bound    yes  5/5 reviews cite their own book's evidence; schema refuses NULL
Confidence               yes  append-only series, bounded in [0,1], never moves a unit on its own
Relations factual        yes  closed vocabulary with no equivalence or merge value
Replayable               yes  three applications against staging, zero rows written twice
```

A_P5_KU_EVOLUTION=PASS
A_REPOSITORY_STATUS=FROZEN

STATUS=FROZEN

---

# RE-FREEZE (2026-10-01)

The original freeze is not withdrawn. Its migration, its lifecycle logic and its
36 rows are unchanged and still verified. What follows records why the verdict
itself was wrong the first time, and what had to be re-measured.

## DEFECT_VERDICT_INCOMPLETE

`A_P5_KU_EVOLUTION` reported 8 gates and counted 6.

```
reported  = G1..G6, idempotency, schema     (8)
into verdict                              (6)  <- idempotency, schema dropped
```

Both dropped gates are capable of changing the outcome. `idempotency` FAILs
when a second application writes rows. `schema` is `NOT_EXECUTED` whenever no
ledger is supplied. A run with no ledger therefore reported `PASS` while the one
gate that was waiting on evidence had never run.

P6 had the identical defect, and comparing the two is how it was found: a
contract that is copied into each layer drifts in each layer.

## FIX_SHARED_VERDICT

`verdict.py` extracted to `src/stratum/knowledge/a_repository/verdict.py`,
imported by both layers.

```
FAIL > BLOCKED > PASS
  PASS     every reported gate ran and passed
  BLOCKED  evidence was unavailable; never reported as merit
  FAIL     a gate ran and failed; outranks missing evidence
```

- no hardcoded gate list — the verdict is computed from whatever `gate_results`
  returned, so a gate added later cannot escape it
- an unrecognised status is `BLOCKED`, not `PASS`, so a new status fails closed
- an empty gate set is `BLOCKED`
- imports nothing, because a shared rule placed in either runner cannot be
  imported by the other: the two runners call each other

Both layers assert they call the *same function object*, so a future copy cannot
quietly replace the contract.

## RE_FREEZE_EVIDENCE

```
DEPENDENCY_CLOSURE    PASS   13 tracked dependencies, runnable clean, exit 0
CLEAN_CHECKOUT        PASS   131 P5-evolution tests
REGRESSION            PASS   961 architecture passed, 6 skipped
MIGRATIONS            13     070..082, no gaps, no duplicates
DESTRUCTIVE_STMT      0      measured over the chain, not asserted
REPLAY_x3             PASS   45-part content fingerprint identical
EMITTED_SQL           PASS   byte-identical across runs
NEGATIVE_PROBES       12/12   refused by the intended constraint
DB_BASELINE           PASS   11/12/1/11 anchor unmoved
```

`DESTRUCTIVE_STMT=0` is worth being precise about. Scanning all 54 migrations
in the repository finds 5 files with `DROP`/`TRUNCATE`, and they belong to BU2
and to migrations earlier than 070 — outside the A仓 chain and outside this
authority. Within 070–082 the only `ALTER`s are 071's two `ADD COLUMN IF NOT
EXISTS` and 082's `ADD CONSTRAINT`, neither of which drops a row.

The scan that produced zero is itself tested: `test_the_destructive_scan_would_
still_notice_one` feeds it three destructive statements and asserts it finds all
three, and separately asserts it does not flag an additive `ADD COLUMN`. A scan
that has quietly stopped detecting anything would otherwise also report zero.

### Probes

| probe | refused by |
|---|---|
| duplicate observation_hash | `ku_confidence_hash_uniq` |
| confidence 1.7 | `ku_confidence_evolution_measured_confidence_check` |
| sequence 0 | `ku_confidence_evolution_sequence_check` |
| revision to a missing unit | `ku_revision_prior_unit_id_fkey` |
| revision into itself | `ku_revision_not_self` |
| undeclared relation_type | `ku_relation_relation_type_check` |
| unordered relation pair | `ku_relation_ordered` |
| alias is its own canonical id | `ku_identity_not_self` |
| alias reused | `ku_identity_alias_uniq` |
| undeclared review_type | `ku_review_event_review_type_check` |
| undeclared to_status | `ku_review_event_to_status_check` |

Eleven of the twelve were refused by the constraint named above. The twelfth —
deleting a unit referenced by a relation — was refused first by
`ku_freeze_event_knowledge_unit_id_fkey` from 073, which fires ahead of
`ku_relation`'s own. `ku_relation`'s two foreign keys were confirmed `RESTRICT`
separately rather than being credited with a refusal that did not reach them.

Four of these probes were rewritten before they were counted. The first attempt
was refused, but for the wrong reason: `'PROBE'` was not in the basis
vocabulary, so `basis_check` fired and the probe proved nothing about the hash
or the range it was written to test. An early fingerprint query also "passed"
its own comparison while comparing two identical *error strings*. A refused
probe and a passing assertion are both easy to misread as evidence; neither was
accepted until it refused for the stated reason.

## FREEZE_GATE

Writing the freeze artifact needs both the gates and the recorded evidence.

`freeze_blockers()` refuses when any evidence is unrecorded **or** the layer
verdict is not `PASS`. Only checking the first was the second version of the
same defect: with all three evidence fields set to `PASS` and no ledger, the
artifact was written and the process exited 0 while `schema` had never run.

That bug was caught by mutation, not by reading. The tests written for it passed
with the fix reverted, because they called `freeze_artifact()` and never
`main()`. They now drive `main()` end to end and assert no file appears. Reverting
the fix fails 2 of them.

## OUTCOME

```
A_P5_EVOLUTION_FREEZE = PASS
BASE_SHA              = 70d70f239ca10d5ab04e13fac2401e81f0af7d28
TAG                   = stratum-a-p5-evolution-freeze
```

`base_sha` is the parent commit: the tree the evidence above was measured
against. An artifact cannot name the commit that contains it.

The five OPEN_ITEMS above are unchanged by this re-freeze and remain open.
