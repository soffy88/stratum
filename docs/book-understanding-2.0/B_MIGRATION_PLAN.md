# B_MIGRATION_PLAN

Date: 2026-10-02. Derived from `B_CURRENT_STATE_MAP.md`, `B_AUTHORITY_MAP.md`,
`B_GAP_MAP.md`.

**No code is written by this document.** It sequences work and names the four
decisions that gate it.

## 0. The finding that reorders the brief

The brief's order is:

```
B0 audit -> B1 authority map -> B2 schema spec -> B3 migration
        -> B4 writer -> B5 validator -> B6 freeze -> B7 nature
```

The audit found that **B2 cannot be specified yet**, for two reasons that are not
implementation problems.

**First, B has no A-side.** B-1 reads `aii.ku_onto` — a legacy 44,246-row table in the
old AII_KG warehouse, 299 books, never frozen. A仓's frozen A is
`stratum.knowledge_unit`: 11 rows, one book, in a staging database. Their id spaces
overlap by **zero**. A仓 migrations 070–082 are applied nowhere B can read them
(`aii_kg` stops at 066). So `ConceptEvidence.knowledge_unit_id` and
`evidence_span_id` — the two fields that make the brief's evidence-completeness gate
possible — have nothing to point at.

**Second, there is no B仓 to migrate.** Not one implementation. Three, with no shared
identity:

| | where | rows | discipline |
|---|---|---|---|
| B-1 `rf` | `aii_refined` (5436) | 74,700 | best-in-class components, ingest dead 7 weeks, 0 of 39,331 rows linked to the ledger |
| B-2 BU2 | `aii_kg` (5437) | 0 | complete design, no producer, 85 tests |
| B-3 | `aii_kg` (5437) | 549 | LLM, free-text relations, no evidence requirement |

B-1 is the only one with data and the only one with a ledger discipline worth
inheriting — but its ledger discipline is currently void (0 of 29,323 `refined_ku`
rows carry a `decision_id`), and `contract.py:47-58` names B-3 as the Concept
authority, not B-1.

So the first four P0 rows in `B_GAP_MAP.md` are decisions, not tasks. They need a
person. Everything below is sequenced behind them.

## 1. The four decisions, in the order they block

### DECISION 1 — Does A仓 get promoted, and to where?

Blocks: A2, A3 → every field of `ConceptEvidence`.

A仓's frozen chain is proven against a disposable staging database
(`A_FINAL_KNOWN_LIMITATIONS.md` records this). It has never been applied to the
production `aii_kg`. B cannot read it.

Options, with what each costs:

| option | what it means | cost |
|---|---|---|
| **1a** Apply 070–082 to `aii_kg` | A仓 becomes readable in production; B-1 can point at it | Highest risk. `A_FINAL_MIGRATION_CLOSURE_SPEC.md` derives the 15-file closure (070-082 + the two `pg_schema` bootstraps) and notes 082 is not re-appliable — its `ADD CONSTRAINT` has no preceding `DROP CONSTRAINT IF EXISTS`. Applying to production is a one-way door. |
| **1b** Stand up a dedicated A database | clean separation, matches A's own staging discipline | a third database; B-1's DSN changes; sync problem returns |
| **1c** Keep A in staging, run B against staging only | no production risk | B-1's 74,700 rows stay orphaned from any A-side; B仓 never ships |

**Recommendation: 1a, rehearsed on a copy first.** The closure is already derived and
already audited; 1b re-creates the dual-track problem this project is trying to close.
But this is a person who has to accept 1a's risk. Not an implementer's call.

### DECISION 2 — Which Concept object is canonical?

Blocks: D1, D2, D3, D4 → the entire B3 schema.

Three candidates, and they are not equivalent:

- **`rf.refined_concept`** — 10,008 rows, own 1024-d embedding, `discriminative`
  jsonb, `discipline` for hard isolation, built by a DIFFERENT-biased deterministic
  gate before any LLM sees a pair. Best candidate on every axis except that it has no
  A-side and a void ledger.
- **`stratum.concepts`** — 4 rows, user-authored, and named the Concept authority by
  `contract.py:53`. Correct for personal notes, wrong as a warehouse.
- **`stratum.graph_entities`** — 185 rows, free-text relations with 12 unconstrained
  live values, name-equality merge that splits 中/英 aliases, no evidence check.
  Not a candidate.

**Recommendation: `rf.refined_concept`, and amend `contract.py` to say so.** B-3
becomes a projection or gets deprecated; `stratum.concepts` stays as the user's own
object, which is a different thing with a different owner. This is the row that most
changes the meaning of every downstream decision, so it goes first among the D rows.

### DECISION 3 — One relation vocabulary, or three?

Blocks: D4, D5 → `ConceptRelation`.

`rf` CHECK: `[derives, subsumes, prerequisite, explains, contrasts, example_of]`.
B-3: free text, 12 live values. The brief: `[IS_A, PART_OF, CAUSES, DEPENDS_ON,
INSTANCE_OF]`.

The brief's list is better than `rf`'s for a concept skeleton — `IS_A` and `PART_OF`
are the two the existing data most obviously needs, and it excludes
value-judgement types by construction. But it drops `prerequisite`, and `rf` has 174
rows of it, and `explains` has 295.

Note the live CHECK was **widened by hand** from 3 to 6 values, and
`edge_backfill.py:155` still inserts a value migration 0001 rejects. Any decision here
must be paired with F3 (reconcile live schema with migrations), or the next rebuild
loses 295 rows.

### DECISION 4 — Does BU2 continue?

Blocks: G1–G7 → roughly a third of the planned B work.

BU2 is a complete design with no implementation: 16 tables, ~60 models, 14
repositories, a 7-case verification gate, 85 tests, zero LLM calls, zero producers,
zero routes, zero CLI commands. Its only reachable writer
(`book_reading.py:82`) writes a status that migration 065 made illegal.

| option | cost |
|---|---|
| **4a** Write the extractor and finish it | real work, and it duplicates B-1's job with a second object model |
| **4b** Stop; delete 060–066 and the six unwired modules | loses the verification gate (`bu_v2_pipeline.py:185`) and 6 well-tested pure modules — **unless those are salvaged first** |
| **4c** Leave it | a third implementation nobody chose, which is where B-3 came from |

**Recommendation: 4a or 4b, never 4c.** If 4b, salvage first: `bu_v2_pipeline.py`'s
verification gate is the most valuable unwired asset in the repository and is exactly
what the brief's B5 asks for. `working_bu.py`'s
`TypeError("SUMMARY_OF_SUMMARIES=0")` (`:42-45`) and `ku_segmentation.py`'s
`ValueError("STANCE_ERROR")` (`:138`) are the same class of structural guard and are
worth keeping whatever happens.

## 2. Sequence, given the four decisions

```
D0 ── the four decisions above ──────────────────────────────┐
                                                            ▼
M1  ledger integrity          B1 B2 B3
M2  gate harness              B4 B5 C4
M3  lifecycle + supersession  C1 C2 C3
M4  schema reconciliation     F3 F6 D4
M5  B writer                  D1 D2
M6  B validator               brief B5/B7
M7  B freeze                  brief B6
M8  nature                    E2 E4  (deferred, correctly)
```

Each step lists its own gates. None of them is "the feature works."

### M1 — Ledger integrity

Fixes `B = f(A仓, 台账)`, which is currently false: 0 of 29,323 `refined_ku` and 0 of
10,008 `refined_concept` rows carry a `decision_id`, while 2,403 ledger rows link to
nothing.

The bug is narrow: `integrate.py:114-149,153-182` already accept a `decision_id`
kwarg. Neither caller passes it (`orchestrate.py:414-423`, `m0.py:310-319`). So this
is a wiring fix, not a redesign.

Also close `learning.py:888,948` — the only live B-1 writer, over HTTP, no ledger row.

```
GATE  every refined_ku/refined_concept has a non-null decision_id
GATE  every decision_id resolves to a ledger row
GATE  no B write path exists that does not create a ledger row   (grep gate)
GATE  replay: A + ledger reproduces B's row set
```

The replay gate is the one that matters. Everything else is bookkeeping.

### M2 — Gate harness

Gives B a verdict, by adopting A's rather than inventing one.
`src/stratum/knowledge/a_repository/verdict.py` derives a verdict from whatever gates
a layer reports, holds no hardcoded list, and is mutation-checked by 11 tests
(`test_a_final_verdict.py`). Reuse it as-is.

Put pytest on `dedup/gates.py` first — it is pure, deterministic, and currently has
only a `__main__` print block. It is the component that makes merging safe
("宁碎片不错合") and the only B component with no test.

Then make `run_gold.py` runnable without live databases, so the "no auto-merge before
the gold set" rule in `STATUS.md:65` becomes enforceable rather than a comment. It
currently needs two live DBs and an LLM key.

```
GATE  gates.py covered; each gate has a positive and a negative case
GATE  gold harness runs with no DB and no key
GATE  verdict derives from reported gates, no hardcoded list
GATE  injected FAIL -> FAIL; injected NOT_EXECUTED -> BLOCKED
```

### M3 — Lifecycle and supersession

The brief's `PROPOSED → EVIDENCE_ATTACHED → VALIDATED → ACTIVE → SUPERSEDED`. Today
every row is `unverified` and no code path sets anything else; `refined_ku` has no
`status` column at all, and `refined_invariant.status` is a 2-value
`candidate`/`confirmed`, which is not a lifecycle.

Add a `status` column. Add supersession — A仓 has `ku_identity` + `superseded_by` and
B-1 has neither, so today a corrected merge leaves the old row live and
indistinguishable. The brief's `ACTIVE -> GENERATED` prohibition matches A's, and
should be enforced the same way: A enforces it in the service, and records in
`A_FINAL_KNOWN_LIMITATIONS.md` that the schema does not. B can do better at no cost
by adding the CHECK.

```
GATE  every B row has a status
GATE  SUPERSEDED -> ACTIVE refused
GATE  a superseded row keeps its history (no UPDATE in place)
GATE  the transition table is the one the code uses — not a second list
```

### M4 — Schema reconciliation

Live schema ≠ migrations, with no tracking. `rf.ku_health_issues` (10 rows, written
twice daily by a live timer) and `refined_directed_edge.{edge_source, raw_substrate}`
exist live, in no migration. The `relation_type` CHECK was widened by hand. A rebuild
from `migrations/refined/` would reject 295 existing `explains` rows.

A-2 solved this for `stratum` with `public._pg_migrations`. Copy that.

Also fold in DECISION 3: one vocabulary, migration file and live CHECK agreeing.

```
GATE  every rf table and column is described by a migration file
GATE  migrations applied to a fresh DB reproduce live schema exactly
GATE  applying to a DB that already has the data is lossless
GATE  one relation vocabulary, CHECK and prompt agree
```

### M5 — B writer

Only after M1 (so decisions are recorded), M3 (so status exists), M4 (so the schema
is trustworthy), and DECISION 1 (so there is an A-side to cite).

The brief wants `Extractor → Candidate Concept → Evidence Validation → Concept Merge
→ B commit`. Two of those exist and are good:

- **Deterministic gate before the LLM** — `dedup/gates.py`. Closed dictionary,
  DIFFERENT-biased, model never sees a pair the gates already object to. This is the
  shape the brief's B5 wants and it predates the brief.
- **Ledger-carrying commit** — `dedup/readout.py`. The only path that honours the
  discipline end to end: per-edge judgment, `decision_type='readout'`, `actor='llm'`,
  `llm_raw` retained, `evidence` written. 1,654 such rows exist.

The gap is the evidence link, and it is blocked on DECISION 1. Until A仓 is readable,
`contributions[].raw_ku_id` can only point at `aii.ku_onto`, which is what it does now.

```
GATE  every B row has >=1 A-side reference
GATE  no B row references an A object that does not exist
GATE  deterministic gates run before any LLM call, and can veto
GATE  every commit creates a ledger row
GATE  re-running on unchanged A changes nothing
```

### M6 — B validator

The brief's four gates: evidence completeness, no orphan concept, no authority
inversion, replay. The last two are nearly free and should be built first.

- **No authority inversion** is a grep. It already passes: no B code writes an
  A-frozen table; no A code writes `rf.*`. Make it a test so it cannot regress.
- **Replay** needs M1.
- **Evidence completeness** needs M5.

`bu_v2_pipeline.py:185` is the reference implementation if DECISION 4 goes 4a — seven
hard cases, already tested, refusing to proceed on missing BU, missing artifact, FAIL,
BLOCKED, wrong run, wrong book, self-reported gaps, live blocking gaps. And it draws
the line the brief wants: `_assert_and_transition:62` raises on a validation rejection
while `_fail_pipeline:81` is reserved for operational errors, so a rejected gate never
poisons a run.

### M7 — B freeze

Same discipline as A: derived verdict, no hardcoded gate list, mutation-checked. The
`verdict.py` reuse from M2 is the whole mechanism.

Do not repeat A's one recorded weakness: the lifecycle state machine is
service-enforced, not schema-enforced (`A_FINAL_KNOWN_LIMITATIONS.md`). Add the CHECK.

### M8 — Nature

Deferred, and the brief's reasoning is right: Nature must sit on stable concepts, and
concepts are not stable yet (M3 incomplete, 0 verified rows).

Two things must be designed when this starts, both additions to the existing
`rf.refined_invariant` rather than new tables:

- `supporting_evidence[]` — otherwise emergence is an assertion.
- `emergence_count` — otherwise there is no way to distinguish a stable property from
  a coincidence.

And an emergence *mechanism*, which does not exist anywhere. The brief's chain is
`多来源 evidence → 重复模式 → 稳定属性 → Nature`; nothing computes repetition, and
nothing distinguishes stability from coincidence.

Settle the name now: `0001:11-12` locks 本性 = `invariant` (非 nature) and records
that a promoted 本性 is a field on the concept, not a table. Adopting `nature` means
a later rename of two tables and a column.

## 3. What this plan does not do

```
promote A仓 to production        DECISION 1, a person's risk call
write a B schema spec            blocked on DECISIONS 1 and 2
delete B-3 or B-2                DECISIONS 2 and 4
re-enable b_repo_sync            F1/F2: the restart path is broken in two places
                                  (wrong port, embed endpoint) and the documented
                                  fix is not in the code
change any A仓 migration         070-082 are frozen, 0 files changed since the P5 tag
write any code                   this document is a plan
```

## 4. If the four decisions are made today

Realistic sequencing, with the constraint that M5–M7 need DECISION 1 first:

```
week 1   DECISION 1 rehearsal on a DB copy; M4 schema reconciliation
week 2   M1 ledger wiring; M2 gates.py pytest + gold harness offline
week 3   M3 status + supersession + CHECK
week 4   DECISION 1 applied; M5 writer with real A-side references
week 5   M6 validator (inversion gate first, it is free); M7 freeze
later    M8 nature
```

If DECISION 1 is 1c (A仓 stays in staging), then M5–M7 do not start, and the honest
outcome is: B-1 keeps its 74,700 rows with no A-side, the ledger stays void, and the
only B仓 work worth doing is M1–M4. That is a coherent stopping point. It is not a
warehouse, and it would be better to say so than to keep three half-built ones.
