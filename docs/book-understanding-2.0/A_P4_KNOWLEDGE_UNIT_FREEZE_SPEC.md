# A P4 KNOWLEDGE UNIT FREEZE SPEC — Frozen KU

TASK=STRATUM_A_P4_KNOWLEDGE_UNIT_FREEZE
AUTHORITY=A_REPOSITORY_ONLY
BASELINE=stratum-a-p3-ku-verification-v0.1 (d67a0a5)
STATUS=FROZEN

## 1. Position

```
SourceVersion → ReadingEvidence → KU Candidate → KU Verification → Frozen KU
                    (P1)            (P2)           (P3)            (P4)
```

A frozen knowledge unit is A仓's final knowledge object: a stable
projection of a verified candidate that can be cited by id. It is not a
judgement that the world is true, and it is not a concept. Grouping units
into concepts belongs to a later repository.

Authority priority:

```
Evidence > Verification > Frozen KU
```

A frozen unit never outranks the evidence it came from, nor the
verification that admitted it.

## 2. Migration

`073_a_knowledge_unit_freeze.sql` — **CREATED and APPLIED to staging.**

One new table. No existing table altered. **No data backfill**: the
migration contains no `INSERT`, so rows arrive only through the freeze
service.

`ON DELETE RESTRICT`, not CASCADE, on all three foreign keys. A frozen
unit is meant to outlast attempts to delete its chain; cascading would let
a deleted evidence row take a frozen unit with it, which is precisely the
rewrite this table exists to prevent.

### 2.1 Fields

| Column | Type | Note |
|---|---|---|
| `id` | TEXT PK | `ku_<sha256 prefix>` |
| `verification_id` | TEXT NOT NULL | FK → `ku_verification(id)` RESTRICT |
| `candidate_id` | TEXT NOT NULL | FK → `ku_candidate(id)` RESTRICT |
| `source_version_id` | TEXT NOT NULL | FK → `source_version(id)` RESTRICT |
| `title` | TEXT NOT NULL | derived from the statement |
| `statement` | TEXT NOT NULL | the candidate's proposition, copied |
| `canonical_text` | TEXT NOT NULL | the anchored span, copied |
| `evidence_count` | INTEGER NOT NULL | CHECK >= 1 |
| `verification_score` | FLOAT NOT NULL | CHECK 0.0–1.0 |
| `content_hash` | TEXT NOT NULL | UNIQUE |
| `freeze_status` | TEXT NOT NULL | CHECK 4 states |
| `freeze_version` | TEXT NOT NULL | `a-p4-v0.1` |
| `created_at` | TIMESTAMP NOT NULL | DEFAULT NOW() |
| `frozen_at` | TIMESTAMP | set when FROZEN |

`statement` and `canonical_text` are separate on purpose: the first is the
extracted proposition as the candidate worded it, the second is the
verbatim span the verification anchored it to. Both are copied, never
generated, so a frozen unit cannot say anything its evidence does not
already say.

### 2.2 Deviations from the draft field list

- **`content_hash` added.** §3's field list omits it, but §6 mandates
  `UNIQUE(content_hash)`, and the constraint needs a column to attach to.
  The identity rule in §4 is the same digest.
- **`frozen_at` is nullable.** §3 lists it, but the lifecycle
  `VERIFIED → FREEZE_PENDING → FROZEN` means the row exists before it is
  frozen. A `CHECK (freeze_status <> 'FROZEN' OR frozen_at IS NOT NULL)`
  constraint makes the pairing mandatory rather than leaving it to
  convention.

## 3. Identity

```
content_hash = sha256(statement + "|" + evidence_fingerprint)
id           = "ku_" + content_hash[:12]
```

Content-derived. Never a random UUID, never a sequence, never a
timestamp: the same evidence plus the same candidate must always produce
the same unit id.

The evidence fingerprint is part of the hash deliberately. The same
proposition drawn from two different spans is two units, because a reader
must be able to tell which span was actually read.

## 4. Uniqueness

Three constraints, each asserted in the tests:

- `UNIQUE(verification_id)` — a verification freezes at most once
- `UNIQUE(candidate_id)` — a candidate freezes at most once
- `UNIQUE(content_hash)` — one unit per evidence-plus-candidate pair

Together these are what make a replay a no-op rather than a second copy.

## 5. Freeze lifecycle

```
VERIFIED ──> FREEZE_PENDING ──> FROZEN   (terminal)
                  └──────────> REJECTED  (terminal)
```

Refused: `FROZEN → VERIFIED`, `FROZEN → MODIFY`, `FROZEN → DELETE`.
`update_unit`, `replace_evidence`, `replace_verification` and `delete_unit`
all raise `FreezeViolation`.

Immutability is the rule, not a special case for `FROZEN`: `update_unit`
is refused for a `FREEZE_PENDING` row too. Asserted by
`test_update_is_refused_even_before_freezing`.

A revision is never an update. A corrected unit is a new row under a new
`freeze_version`, leaving the frozen row intact and still citable.

## 6. Content rules

A frozen unit carries a `statement`, at least one `evidence_id`, an
evidence row that exists with a span, an existing `source_version`, and a
verification that is `VERIFIED` with `score >= 0.8`.

`title` is derived, never written: the statement's own opening clause,
cut at the first clause-ending punctuation. A title that said something
the evidence did not would be a second, unsourced claim.

## 7. Gates

| Gate | Check | Pilot |
|---|---|---|
| GATE_1 | 073 plus its whole chain in the ledger; tables, FKs, indexes | PASS |
| GATE_2 | only `VERIFIED` verifications became units, all ≥ 0.8 | PASS |
| GATE_3 | authority, structural | PASS |
| GATE_4 | full chain traceable; every unit anchored | PASS |
| GATE_5 | replay freezes nothing twice | PASS |

GATE_3 is structural rather than a name scan: it checks that every
`REFERENCES` target lands in `{ku_verification, ku_candidate,
source_version}`, that there is no `ALTER TABLE`, and that there is no
`INSERT INTO`. A name list inside the gate would itself contain the names
it forbids — the same trap P2's authority scan fell into.

## 8. Runner

`ku_freeze_runner.py`, not `freeze_runner.py`: the P1 baseline runner
already owns that name inside the package, and P1's runner is the one
that imports the P2 runner, so taking the name would close an import
cycle. An earlier attempt at `freeze_runner.py` overwrote P1's file and was
reverted.

GATE_1 reads the ledger from `A_P4_LEDGER_FILE`, so no credential reaches
the freeze process. Without it, GATE_1 reports `NOT_EXECUTED`.

## 9. Known limits of this stage

- `statement` is the P2 candidate's wording, so a frozen unit inherits
  P2's compression quality. The freeze stage checks that the wording is
  sourced and anchored; it cannot check that it is well chosen.
- `evidence_count` is always 1 on this pilot: A仓 attaches exactly one
  evidence row per candidate. The column and its `>= 1` check anticipate
  multi-evidence units; nothing produces them yet.
- `knowledge_unit_revision` (§8 of the draft) is **not** created. The
  policy it implies — revise by adding, never by updating — is enforced
  by the four refusing methods, and no revision has been needed. Creating
  an empty table now would be schema for a case that has not occurred.
- A rejected verification produces no unit at all, so `REJECTED` in the
  freeze state machine currently has no producer. It exists for a
  verification that passed but whose content could not be frozen.

FREEZE_SPEC=PASS