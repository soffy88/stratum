# A_REPOSITORY_FINAL_ACCEPTANCE_REPORT

```
A_REPOSITORY_FINAL = PASS
```

## 1. Scope

The A仓 repository from raw evidence to a navigable reading projection: ten
layers, thirteen migrations, one book. Every layer that reports gates is
included. Nothing is excluded for being inconvenient, and nothing is counted
that does not run.

```
Raw Evidence -> KU -> Evolution -> Identity -> Mechanism -> Relation
             -> Paper -> Constraint -> Projection -> Final Verification
```

## 2. Architecture

One fact model, one authority, no writes flowing backwards. Each layer reads
rows an earlier layer froze, writes only its own tables, and derives its own
verdict from its own gates by the shared contract in `verdict.py`.

```
                       writes                      reads
P1-P2   book_source, source_version       (source file)
P3      reading_evidence, evidence_quality  book_source
P4/P4.1 ku_candidate, ku_verification      reading_evidence
        knowledge_unit, ku_freeze_event
P5.0    ku_condition_candidate             knowledge_unit
        ku_boundary_candidate
P5.1    mechanism_candidate, mechanism_node
P5.2    relation_candidate, ku_relation
P5.3    paper_source_candidate, paper_evidence
P5.4    constraint_candidate
P5.5    (no table; composite FK)
P5      ku_revision, ku_review_event, ku_confidence_evolution
P6      ku_identity
P7      (no table by design; JSON artifact)
```

Measured on `stratum_a_closure`:

```
tables written by the chain      21, every one an A table
FKs touching P5+ tables          22, all RESTRICT
FKs pointing outside `stratum`    0
FKs with CASCADE delete           7, all in the 070-072 ancestry
```

The CASCADE count is worth stating precisely, because "RESTRICT refuses the
deletes" appears in the P5 freeze report and could be read as covering the whole
chain. It does not. Every foreign key on a P5-or-later table is RESTRICT; the
seven CASCADE keys belong to `book_source`, `source_version`, `reading_run`,
`reading_evidence`, `evidence_quality`, `ku_candidate` and `ku_verification` --
the ancestry from 070-072, where cascading a deleted book is intended. The split
is deliberate: deleting a source should take its evidence with it, while
deleting a knowledge unit must not take its revisions and reviews, because that
would erase history.

## 3. Migration chain

| migration | sha256 (first 16) |
|---|---|
| `070` | `179e9e26c17f13e6` |
| `071` | `6116f929ff5976a5` |
| `072` | `7a210f1130389037` |
| `073` | `4285c1be7a6c4a0c` |
| `074` | `9d3651f35668ddd3` |
| `075` | `b29432e8340faedc` |
| `076` | `2b9de6b42e1c1d87` |
| `077` | `fe4d613f5bb95508` |
| `078` | `ed963f7e82854b04` |
| `079` | `58910b307ea79b1f` |
| `080` | `6215e46078709bc8` |
| `081` | `0e9ebc2ddc443412` |
| `082` | `db3aa8f3f7673c20` |

Files changed since the P5 freeze tag: **0**.

The chain is **not self-sufficient**. Applying 070-082 to an empty database fails
thirteen times with `schema "stratum" does not exist`, because no migration
creates that schema. The real closure is fifteen files -- the two `pg_schema`
bootstraps plus 070-082 -- and it is sufficient: applied to an empty database it
produces all 22 A tables, and the seven emitters then reproduce staging exactly.
Derivation in `A_FINAL_MIGRATION_CLOSURE_SPEC.md`.

One property to know before applying it by hand: 082 is not re-appliable. Its
`ADD CONSTRAINT` has no preceding `DROP CONSTRAINT IF EXISTS`. It is frozen, so
this is recorded rather than repaired.

## 4. Gate matrix

| layer | module | reported | counted | verdict | verdict key |
|---|---|---|---|---|---|
| P5_0_CONDITION_BOUNDARY | `condition_boundary_runner` | 15 | 15 | PASS | `A_P5_0_CONDITION_BOUNDARY` |
| P5_1_MECHANISM | `mechanism_runner` | 13 | 13 | PASS | `A_P5_1_MECHANISM` |
| P5_2_RELATION | `relation_runner` | 21 | 21 | PASS | `A_P5_2_RELATION` |
| P5_3_PAPER | `paper_runner` | 22 | 22 | PASS | `A_P5_3_PAPER` |
| P5_4_CONSTRAINT | `constraint_runner` | 22 | 22 | PASS | `A_P5_4_CONSTRAINT` |
| P5_5_PAPER_EVIDENCE_FK | `paper_evidence_fk_runner` | 12 | 12 | PASS | `A_P5_5_PAPER_EVIDENCE_FK` |
| P5_EVOLUTION | `ku_evolution_runner` | 8 | 8 | PASS | `A_P5_KU_EVOLUTION` |
| P6_IDENTITY | `ku_identity_runner` | 14 | 14 | PASS | `A_P6_IDENTITY` |
| P7_PROJECTION | `projection_builder` | 8 | 8 | PASS | `A_P7_BOOK_UNDERSTANDING_PROJECTION` |

```
FINAL VERDICT   PASS
gate_count      135
not executed    none
failed          none
unknown status  none
```

Every gate, all 135 of them:

| layer | gate | status |
|---|---|---|
| `P5_0_CONDITION_BOUNDARY` | GATE_A_frozen_ku_immutable | PASS |
| `P5_0_CONDITION_BOUNDARY` | GATE_A_upstream_untouched | PASS |
| `P5_0_CONDITION_BOUNDARY` | GATE_A_verification_logic | PASS |
| `P5_0_CONDITION_BOUNDARY` | GATE_B_evidence_trace | PASS |
| `P5_0_CONDITION_BOUNDARY` | GATE_B_traceability_percent | PASS |
| `P5_0_CONDITION_BOUNDARY` | GATE_C_B_REFERENCE | PASS |
| `P5_0_CONDITION_BOUNDARY` | GATE_C_C_REFERENCE | PASS |
| `P5_0_CONDITION_BOUNDARY` | GATE_C_isolation | PASS |
| `P5_0_CONDITION_BOUNDARY` | GATE_D_baseline_invariance | PASS |
| `P5_0_CONDITION_BOUNDARY` | GATE_D_extraction_purity | PASS |
| `P5_0_CONDITION_BOUNDARY` | GATE_E_idempotency | PASS |
| `P5_0_CONDITION_BOUNDARY` | GATE_E_replay | PASS |
| `P5_0_CONDITION_BOUNDARY` | GATE_F_anchoring | PASS |
| `P5_0_CONDITION_BOUNDARY` | schema_column_parity | PASS |
| `P5_0_CONDITION_BOUNDARY` | schema_vocabulary | PASS |
| `P5_1_MECHANISM` | GATE_1_banned_fields | PASS |
| `P5_1_MECHANISM` | GATE_1_column_parity | PASS |
| `P5_1_MECHANISM` | GATE_1_constraints | PASS |
| `P5_1_MECHANISM` | GATE_1_fk_verb | PASS |
| `P5_1_MECHANISM` | GATE_1_schema | PASS |
| `P5_1_MECHANISM` | GATE_2_completeness | PASS |
| `P5_1_MECHANISM` | GATE_2_trace | PASS |
| `P5_1_MECHANISM` | GATE_2_traceability_percent | PASS |
| `P5_1_MECHANISM` | GATE_3_idempotency | PASS |
| `P5_1_MECHANISM` | GATE_3_replay | PASS |
| `P5_1_MECHANISM` | GATE_4_authority | PASS |
| `P5_1_MECHANISM` | GATE_4_baseline_unchanged | PASS |
| `P5_1_MECHANISM` | GATE_5_negative | PASS |
| `P5_2_RELATION` | GATE_1_banned_fields | PASS |
| `P5_2_RELATION` | GATE_1_column_parity | PASS |
| `P5_2_RELATION` | GATE_1_constraints | PASS |
| `P5_2_RELATION` | GATE_1_fk_verb | PASS |
| `P5_2_RELATION` | GATE_1_frozen_index | PASS |
| `P5_2_RELATION` | GATE_1_isolation_schema | PASS |
| `P5_2_RELATION` | GATE_1_not_null | PASS |
| `P5_2_RELATION` | GATE_1_schema | PASS |
| `P5_2_RELATION` | GATE_1_vocabulary | PASS |
| `P5_2_RELATION` | GATE_2_authority | PASS |
| `P5_2_RELATION` | GATE_2_baseline_unchanged | PASS |
| `P5_2_RELATION` | GATE_2_ku_relation_untouched | PASS |
| `P5_2_RELATION` | GATE_3_double_side | PASS |
| `P5_2_RELATION` | GATE_3_trace | PASS |
| `P5_2_RELATION` | GATE_3_traceability_percent | PASS |
| `P5_2_RELATION` | GATE_4_hash_stability | PASS |
| `P5_2_RELATION` | GATE_4_idempotency | PASS |
| `P5_2_RELATION` | GATE_4_replay | PASS |
| `P5_2_RELATION` | GATE_5_isolation | PASS |
| `P5_2_RELATION` | GATE_5_order | PASS |
| `P5_2_RELATION` | GATE_6_negative | PASS |
| `P5_3_PAPER` | GATE_1_banned_fields | PASS |
| `P5_3_PAPER` | GATE_1_column_parity | PASS |
| `P5_3_PAPER` | GATE_1_constraints | PASS |
| `P5_3_PAPER` | GATE_1_fk_verb | PASS |
| `P5_3_PAPER` | GATE_1_frozen_index | PASS |
| `P5_3_PAPER` | GATE_1_hash_formula | PASS |
| `P5_3_PAPER` | GATE_1_isolation_schema | PASS |
| `P5_3_PAPER` | GATE_1_not_null | PASS |
| `P5_3_PAPER` | GATE_1_schema | PASS |
| `P5_3_PAPER` | GATE_1_vocabulary | PASS |
| `P5_3_PAPER` | GATE_2_authority | PASS |
| `P5_3_PAPER` | GATE_2_baseline_unchanged | PASS |
| `P5_3_PAPER` | GATE_2_catalog_untouched | PASS |
| `P5_3_PAPER` | GATE_2_frozen_layers | PASS |
| `P5_3_PAPER` | GATE_3_declaration_fidelity | PASS |
| `P5_3_PAPER` | GATE_3_trace | PASS |
| `P5_3_PAPER` | GATE_3_traceability_percent | PASS |
| `P5_3_PAPER` | GATE_4_hash_stability | PASS |
| `P5_3_PAPER` | GATE_4_idempotency | PASS |
| `P5_3_PAPER` | GATE_4_replay | PASS |
| `P5_3_PAPER` | GATE_5_isolation | PASS |
| `P5_3_PAPER` | GATE_6_negative | PASS |
| `P5_4_CONSTRAINT` | GATE_1_banned_fields | PASS |
| `P5_4_CONSTRAINT` | GATE_1_column_parity | PASS |
| `P5_4_CONSTRAINT` | GATE_1_constraints | PASS |
| `P5_4_CONSTRAINT` | GATE_1_fk_verb | PASS |
| `P5_4_CONSTRAINT` | GATE_1_hash_ordering | PASS |
| `P5_4_CONSTRAINT` | GATE_1_index_reuse | PASS |
| `P5_4_CONSTRAINT` | GATE_1_isolation_schema | PASS |
| `P5_4_CONSTRAINT` | GATE_1_schema | PASS |
| `P5_4_CONSTRAINT` | GATE_1_vocabulary | PASS |
| `P5_4_CONSTRAINT` | GATE_2_authority | PASS |
| `P5_4_CONSTRAINT` | GATE_2_baseline_unchanged | PASS |
| `P5_4_CONSTRAINT` | GATE_2_frozen_layers | PASS |
| `P5_4_CONSTRAINT` | GATE_3_ku_statement_not_evidence | PASS |
| `P5_4_CONSTRAINT` | GATE_3_quote_authority | PASS |
| `P5_4_CONSTRAINT` | GATE_4_coverage | PASS |
| `P5_4_CONSTRAINT` | GATE_4_trace | PASS |
| `P5_4_CONSTRAINT` | GATE_4_traceability_percent | PASS |
| `P5_4_CONSTRAINT` | GATE_5_hash_stability | PASS |
| `P5_4_CONSTRAINT` | GATE_5_idempotency | PASS |
| `P5_4_CONSTRAINT` | GATE_5_replay | PASS |
| `P5_4_CONSTRAINT` | GATE_6_isolation | PASS |
| `P5_4_CONSTRAINT` | GATE_7_negative | PASS |
| `P5_5_PAPER_EVIDENCE_FK` | GATE_1_constraint_present | PASS |
| `P5_5_PAPER_EVIDENCE_FK` | GATE_1_index_present | PASS |
| `P5_5_PAPER_EVIDENCE_FK` | GATE_1_index_target | PASS |
| `P5_5_PAPER_EVIDENCE_FK` | GATE_1_no_new_lifecycle | PASS |
| `P5_5_PAPER_EVIDENCE_FK` | GATE_1_rows_unmutated | PASS |
| `P5_5_PAPER_EVIDENCE_FK` | GATE_1_schema | PASS |
| `P5_5_PAPER_EVIDENCE_FK` | GATE_1_two_objects | PASS |
| `P5_5_PAPER_EVIDENCE_FK` | GATE_2_baseline | PASS |
| `P5_5_PAPER_EVIDENCE_FK` | GATE_2_existing_data | PASS |
| `P5_5_PAPER_EVIDENCE_FK` | GATE_3_negative | PASS |
| `P5_5_PAPER_EVIDENCE_FK` | GATE_4_replay | PASS |
| `P5_5_PAPER_EVIDENCE_FK` | GATE_5_authority | PASS |
| `P5_EVOLUTION` | G1_traceability | PASS |
| `P5_EVOLUTION` | G2_immutability | PASS |
| `P5_EVOLUTION` | G3_revision | PASS |
| `P5_EVOLUTION` | G4_replay | PASS |
| `P5_EVOLUTION` | G5_authority | PASS |
| `P5_EVOLUTION` | G6_durability | PASS |
| `P5_EVOLUTION` | idempotency | PASS |
| `P5_EVOLUTION` | schema | PASS |
| `P6_IDENTITY` | G1_canonical_id | PASS |
| `P6_IDENTITY` | G1_identity_uniqueness | PASS |
| `P6_IDENTITY` | G2_citations_resolve | PASS |
| `P6_IDENTITY` | G2_historical_replay | PASS |
| `P6_IDENTITY` | G2_retired_id_recomputes | PASS |
| `P6_IDENTITY` | G3_revision_chain | PASS |
| `P6_IDENTITY` | G3_successor_walk | PASS |
| `P6_IDENTITY` | G4_regression | PASS |
| `P6_IDENTITY` | G4_stage_versions | PASS |
| `P6_IDENTITY` | G5_authority | PASS |
| `P6_IDENTITY` | G5_no_external_dependency | PASS |
| `P6_IDENTITY` | G5_no_mutation | PASS |
| `P6_IDENTITY` | idempotency | PASS |
| `P6_IDENTITY` | schema | PASS |
| `P7_PROJECTION` | G1_authority | PASS |
| `P7_PROJECTION` | G1_no_new_id | PASS |
| `P7_PROJECTION` | G1_read_only | PASS |
| `P7_PROJECTION` | G2_traceability | PASS |
| `P7_PROJECTION` | G3_determinism | PASS |
| `P7_PROJECTION` | G4_replay | PASS |
| `P7_PROJECTION` | G5_isolation | PASS |
| `P7_PROJECTION` | G5_schema_closure | PASS |

The verdict is computed, not written down. `scripts/a_final_verdict.py` runs each
layer, collects the gates it reports, and applies the same `verdict()` to the
union. It holds no list of gate names, because a list is the mechanism by which a
reported gate falls outside the outcome.

`reported == counted` for all nine layers is the property this project exists to
protect. Three layers shipped a verdict reading a subset of the gates they
printed -- P5 Evolution 8/6, P6 14/12, P7 7 gates beside a list of 5 -- and P5.0
read 9 of 15. A gate that is displayed and excluded can print PASS and change
nothing, which is not a verdict.

### The derivation responds

```
all gates PASS                    -> PASS
one gate injected FAIL            -> FAIL
one gate NOT_EXECUTED             -> BLOCKED
one unrecognised status           -> BLOCKED
a measurement left inside gates   -> BLOCKED, not coerced to PASS
a layer that fails to execute     -> BLOCKED, not skipped
```

The last two are mutation-checked against the suite that must catch them.

## 5. Test matrix

```
tests/architecture                 992 passed, 6 skipped
  A仓 contract tests               9 layers
  final-verdict contract           11 tests, mutation-checked
CURRENT_FAILURES - BASELINE_FAILURES = EMPTY
```

The ambient baseline of 48 failures and 169 errors in the full `tests/` run is
unchanged and unrelated to A仓, verified by diffing failure ids against a clean
worktree rather than by comparing counts.

## 6. Dependency closure

Every layer resolves from a clean checkout, with no missing dependency and no
untracked file.

| layer | modules | missing | untracked | clean-checkout verify |
|---|---|---|---|---|
| P5_0_CONDITION | 20 | 0 | 0 | yes |
| P5_1_MECHANISM | 20 | 0 | 0 | yes |
| P5_2_RELATION | 20 | 0 | 0 | yes |
| P5_3_PAPER | 20 | 0 | 0 | yes |
| P5_4_CONSTRAINT | 20 | 0 | 0 | yes |
| P5_5_PAPER_EVIDENCE_FK | 19 | 0 | 0 | yes |
| P5_EVOLUTION | 13 | 0 | 0 | yes |
| P6_IDENTITY | 16 | 0 | 0 | yes |
| P7_PROJECTION | 18 | 0 | 0 | yes |

P5.1-P5.5 had no entry in this audit until the final acceptance needed a figure
for every layer that reports gates. A layer absent from the table is a layer
whose closure nobody had checked, which is the same shape as a gate absent from
a verdict.

`P5_0_CONDITION` could not be verified from a clean checkout at all before
`2254f9a`: its implementation, contract test, artifact and freeze report were all
untracked. That was the one layer in the chain whose gates could not be
reproduced from a tag.

## 7. Known limitations

Eighteen items in five classes, in `A_FINAL_KNOWN_LIMITATIONS.md`. Four need a
person's decision rather than code. The sharpest:

- **The lifecycle state machine is service-enforced, not schema-enforced.** Both
  status columns are constrained to ACTIVE / QUARANTINED / SUPERSEDED, but no
  constraint forbids SUPERSEDED -> ACTIVE. A writer bypassing the service can
  produce a state the service would refuse.
- **Extractor recall is unmeasured.** The gates check that what was produced is
  well-formed and traceable. None check that what was present was found.
- **One book, one chapter, five sections.** Every count in every artifact is a
  fact about that chapter.
- **Durability is proven against staging only.** No production database has
  received a migration from 070 onward.

## 8. Non-goals

```
inference or judgement     none; the review ledger records what a reviewer said
semantic similarity        none; the traversal tiebreak is not a reading order
compression or summary     none; P7 arranges frozen rows and adds no knowledge
cross-repository writes    none; 0 FKs leave `stratum`, 0 BU2 dependencies
destructive migration      none; 0 DROP/TRUNCATE/DELETE/UPDATE in 070-082
a projection database      P7 v0.1 stores JSON, to avoid a second authority
production promotion       not attempted
```

## 9. Reproduction

```sh
# the chain verdict; needs a ledger and P7's catalog
A_P5_LEDGER_FILE=<13 A-chain filenames> \
A_P7_DB_TABLES=<stratum table names from information_schema> \
  python scripts/a_final_verdict.py

# one layer
PYTHONPATH=src python -m stratum.knowledge.a_repository.ku_evolution_runner

# the chain onto an empty database: see A_FINAL_MIGRATION_CLOSURE_SPEC.md
# the suite
python -m pytest tests/architecture -q
```

`A_P7_DB_TABLES` is not optional. Without it `G5_schema_closure` is
`NOT_EXECUTED` and the chain blocks -- deliberately, since the check it replaced
passed on staging for the wrong reason.

## 10. Final verdict

```
FINAL VERDICT   PASS
gate_count      135
contract        FAIL > BLOCKED > PASS; derived from gate_results,
                no hardcoded gate list
```

Not a stated result: the output of applying one function to the union of every
gate nine layers report, which is the same function each applies to itself.

Two things this verdict does not cover, recorded so PASS is not read wider than
it is. Migration 082 is not re-appliable, and durability is proven against a
disposable staging database only. Both are in `A_FINAL_KNOWN_LIMITATIONS.md`.
