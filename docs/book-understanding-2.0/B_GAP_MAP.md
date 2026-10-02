# B_GAP_MAP

Date: 2026-10-02. Every row is a measured difference between what the B仓 brief
specifies and what the repository contains. Priority is mine, argued below; rows
marked **DECISION** are not gaps but choices only a person can make.

Measured baselines used throughout `[live]`: `rf.refined_ku` 29,323 rows,
`rf.refined_concept` 10,008, `rf.decision_ledger` 2,403, `rf.refined_directed_edge`
1,231, 5 of 13 `rf` tables empty, BU2 16 tables all 0 rows, A仓 frozen
`knowledge_unit` 11 rows in staging only.

## A. Blocking — B仓 has no verified A-side

| id | gap | evidence | priority |
|---|---|---|---|
| **A1** | B-1 derives from `aii.ku_onto` (legacy, 44,246 rows, 299 books), not from A仓's frozen `knowledge_unit` (11 rows, 1 book). Overlap between the two id spaces: **0**. | `candidates.py:23`, `m0.py:107-128`; id comparison against both databases | **P0** |
| **A2** | A仓 migrations 070–082 are applied nowhere B can read them. `aii_kg`'s `_pg_migrations` stops at `066`. A仓 exists only in `stratum_a_p3_staging` and `stratum_a_p3_fresh`. | `SELECT max(filename) FROM _pg_migrations` | **P0** |
| **A3** | Consequently "B = f(A仓)" is an intention, not a fact. The seam the whole B design rests on does not exist yet. | A1 + A2 | **P0** |

This is the one that should stop the project. Everything in the brief's B3–B6 —
`evidence_refs[]`, `derived_from[]`, the extractor flow, the state machine — presumes
a resolvable A-side pointer. There is none. `ConceptEvidence.knowledge_unit_id` and
`evidence_span_id` have nothing to point at.

A3 is a sequencing fact, not a defect: A仓 was frozen against staging on purpose
(`A_FINAL_KNOWN_LIMITATIONS.md` records "durability is proven against staging only"),
and promoting it is a decision with its own risk. But B cannot be designed as if the
promotion already happened.

## B. Blocking — the ledger discipline does not hold

| id | gap | evidence | priority |
|---|---|---|---|
| **B1** | `refined_ku.decision_id` non-null on **0 of 29,323** rows. `refined_concept.decision_id` non-null on **0 of 10,008**. The ledger's 2,403 rows link to nothing materialised. | live count; `integrate.py:114-149,153-182` accept a `decision_id` kwarg that neither caller passes (`orchestrate.py:414-423`, `m0.py:310-319`) | **P0** |
| **B2** | So `B = f(A仓, 台账)` — the invariant stated at `0001:10-11`, the reason the ledger exists — is false. B cannot be replayed from A + ledger. | B1 | **P0** |
| **B3** | `aii/aii/aii/api/routes/learning.py:888` writes `rf.refined_ku` over HTTP on read, no ledger row. `:948` writes on human correction, no ledger row. This is the only *live* B-1 writer. | source; `[live]` 5 rows `zh_grade='unverified'`, 0 `'verified'` | **P1** |
| **B4** | `dedup/gates.py` — the deterministic pre-LLM gate set — has no pytest. Only a `__main__` print block (`:93-101`). The one component that makes merging safe is the one component with no test. | source | **P1** |
| **B5** | `run_gold.py`, the adversarial gold harness the "no auto-merge before the gold set" rule depends on, needs two live databases plus `DEEPSEEK_API_KEY` (`:35-36,104`). It cannot run in CI, so the rule is a shell comment. | source | **P1** |

## C. Blocking — B仓 has no state machine and no verdict

| id | gap | evidence | priority |
|---|---|---|---|
| **C1** | Every B-1 row is `unverified`: 29,323 `refined_ku`, 1,231 `refined_directed_edge`. No code path sets any other value. | live `GROUP BY grade` | **P0** |
| **C2** | The brief's `PROPOSED → EVIDENCE_ATTACHED → VALIDATED → ACTIVE → SUPERSEDED` has no home. `refined_ku` has `grade` (8 values, a confidence vocabulary, not a lifecycle) and no `status`. `refined_invariant` has `status IN ('candidate','confirmed')` — 2 values, also not a lifecycle. | `0001:59-88`, `0001:45-56` | **P0** |
| **C3** | No `SUPERSEDED` anywhere in B-1. A仓 has `ku_identity` + `ku_revision` + `superseded_by` for exactly this; B-1 has none of it, so a corrected merge leaves the old row live and indistinguishable. | `0001` column list; A side `076`, `075` | **P1** |
| **C4** | No verdict mechanism. A-2's `verdict.py` derives a verdict from whatever gates a layer reports, with no hardcoded gate list, mutation-checked by 11 tests. B has no equivalent and no gates at all. | `src/stratum/knowledge/a_repository/verdict.py`; `tests/architecture/test_a_final_verdict.py` | **P1** |

The brief's B6 assumed B would mirror A's freeze thinking. It has to be built, not
inherited — but `verdict.py` is directly reusable and needs no adaptation.

## D. Design decisions — three concept objects, no shared identity

| id | decision | evidence | priority |
|---|---|---|---|
| **D1** | **DECISION.** Three Concept objects exist: `rf.refined_concept` (10,008), `stratum.concepts` (4), `stratum.graph_entities` (185). No shared id space. `cornell_generator.py:114` reads the first, `api/routers/concepts.py` serves the second, `graph_query.py:34` reads the first and third. | source; live counts | **P0** |
| **D2** | **DECISION.** B-3 (`graph_entities`/`graph_relations`) has no B discipline: free-text `relation_type` with 12 live unconstrained values, no evidence requirement, name-equality merge that splits 中/英 aliases. | `graph_builder_service.py:29`, `dao/graph.py:16-24,72`; live `pg_constraint` shows no CHECK on `concept_relations.relation_type` | **P0** |
| **D3** | **DECISION.** `contract.py:47-58` names `stratum.concepts` / `stratum.concept_relations` as the Concept/Relation authority — i.e. B-3. Neither `rf.*` nor any BU2 table appears. B-1 and B-2 have no constitutional standing. | `contract.py`; `knowledge/__init__.py` does not export `bu_v2_models` | **P0** |
| **D4** | **DECISION.** Three relation vocabularies, no two agreeing: `rf` CHECK `[derives, subsumes, prerequisite, explains, contrasts, example_of]`; B-3 free text with 12 live values; the brief proposes `[IS_A, PART_OF, CAUSES, DEPENDS_ON, INSTANCE_OF]`. | `0001:150` vs live `pg_get_constraintdef` vs the brief | **P0** |
| **D5** | The brief's ban on value-judgement relation types (`SIMILAR` / `IMPORTANT` / `BETTER` / `WORSE`) is enforced nowhere, and `graph_builder_service.py:29` actively invites judgement words in its prompt. | source | **P1** |

D1–D4 are not gaps a schema spec can close. Each needs one sentence from a person:
which of the three Concept objects is canonical, and what happens to the other two.

## E. Blocking — the Nature layer is specified and empty

| id | gap | evidence | priority |
|---|---|---|---|
| **E1** | `rf.refined_invariant` and `rf.refined_concept_invariant` exist with no writer and no reader. `refined_hyperedge_member` likewise: no writer, no reader. | live 0 rows; zero references outside DDL | **P2** — correct to defer |
| **E2** | The brief's Nature model wants `supporting_evidence[]` and `emergence_count`. Neither column exists. Without them emergence is an assertion; with them it is a count someone can check. | `0001:45-56` column list | **P1** |
| **E3** | **Naming.** The brief says `Nature`. `0001:11-12` locks 本性 = `invariant` (非 nature), and records that a promoted 本性 is a field on the concept, not a table. Recommendation: adopt `invariant`; do not re-litigate. | `0001:11-12` | **P2** — settle now, cheap later |
| **E4** | There is no emergence *mechanism* anywhere. The brief's chain is `多来源 evidence → 重复模式 → 稳定属性 → Nature`. Nothing computes repetition, and nothing distinguishes a stable property from a coincidence. | absence across `dedup/`, `m0.py`, `readout.py` | **P2** — defer with Nature |

The brief's own B8 reasoning is right: Nature must sit on stable concepts. E2 and E4
are the parts that must be designed when that time comes, and both are additions to
an existing table rather than a new one.

## F. Non-blocking — operational and schema-hygiene

| id | gap | evidence | priority |
|---|---|---|---|
| **F1** | B-1 ingest has been down 7 weeks. `max(refined_ku.updated_at)` = 2026-08-13. `aii-b-repo-sync.timer` is `disabled`/`inactive`, has never executed, and has no log file. Backup size byte-identical for 3 days confirms it independently. | live; `systemctl --user` | **P1** |
| **F2** | Re-enabling F1 will not work. The unit's `AII_KG_URL` points at 5435; the container publishes 5437. And `b_repo_sync.sh:60-68` hard-returns 1 on embed unreachability under `set -euo pipefail`. `STATUS.md:58` and `PIPELINE_STATUS.md:155` both record that endpoint as already migrated — **the documented fix is not in the code.** | `aii-b-repo-sync.service:10`, `b_repo_sync.sh:17,32,60-68` vs `STATUS.md:58` | **P1** |
| **F3** | Live schema ≠ migration. `rf.ku_health_issues` (10 rows, written twice daily by a live timer) and `refined_directed_edge.{edge_source, raw_substrate}` exist live, in no migration. The `relation_type` CHECK was widened by hand from 3 to 6 values. A rebuild from `migrations/refined/` rejects 295 existing `explains` rows. No `schema_migrations` table in `rf`. | live `information_schema` + `pg_get_constraintdef` vs `0001` | **P1** |
| **F4** | Three writers would crash on `--commit`: `refined_concept_commit.py:154` (non-existent `rf.refined_ku.sources`), `:175,186` (non-existent `rf.concept_decision`), `edge_backfill.py:155` (CHECK rejects `explains`). All superseded by `dedup/` but still on disk and still look runnable. | source vs live schema | **P2** |
| **F5** | `refined_hyperedge`: 967 rows, one writer (`edge_backfill.py:182`), one reader — a row count in `ku_lint.py:124`. Write-only. | live; source | **P2** |
| **F6** | No migration tracking in `rf`; migrations applied by hand. A-2 solved the equivalent problem for `stratum` with `public._pg_migrations`. | no `schema_migrations` in `rf` | **P1** |

## G. BU2-specific — schema-complete, producer-empty

| id | gap | evidence | priority |
|---|---|---|---|
| **G1** | 14 of 14 `Repository.save()` methods have no production caller. The only two call sites in the whole repo are `bu_v2_pipeline.py:291,308`, and `BU2PipelineStateMachine(` is instantiated **only** in tests. | source-wide grep | **P0 if BU2 continues; P2 if it does not** |
| **G2** | Zero LLM calls in BU2. All 16 tables are gated on `check_exists` / `SELECT 1`. The one producer, `_project_learning:259`, emits LearningObjects with `target_refs=[]`, `prerequisites_refs=[]`, `expected_answer=""` — placeholders. | source | same as G1 |
| **G3** | No CLI command, no API route, no scheduler job reaches BU2. `src/stratum/cli/main.py` has 0 hits for any BU2 name. | source | same as G1 |
| **G4** | `book_reading.py:82` writes `status="planned"`, which migration 065 made illegal. The only reachable BU2 writer is broken against current schema. `:68` also filters on `'completed'`, removed by the same migration. | `065:6-19` vs `book_reading.py:68,82` | same as G1 |
| **G5** | Six service modules are pure, tested, and have no caller in `src/`: `bu_provenance.py`, `working_bu.py`, `understanding_projection.py`, `learning_compiler.py`, `tutor_engine.py`, `ku_segmentation.py`. | source | same as G1 |
| **G6** | `tests/conftest.py` builds a fake DB with only `book_reading_run` and `reading_ledger`. The other 14 BU2 tables are absent, so no integration test could exercise them even with a producer wired. | `tests/conftest.py` | same as G1 |
| **G7** | `check_fidelity` hardcodes `STANCE_PRESERVED: True` and `BOUNDARY_PRESERVED: True` (`understanding_projection.py:83-84`). Two of seven fidelity checks are unconditional no-ops that print PASS. | source | P1 |

G1–G7 share one priority because they share one decision. BU2 is a **complete design
with no implementation**: 85 tests, 16 tables, ~60 models, a verification gate that
refuses to proceed — and no producer. That is a legitimate state for a design
document. It is not a warehouse. Continuing it means writing the extractor; stopping
it means deleting 060–066 and the six modules. Half-measures leave a third
implementation nobody chose.

The verification gate at `bu_v2_pipeline.py:185` is the most valuable unwired asset in
the repository: seven hard cases, already unit-tested, doing exactly what the brief's
B5 "LLM proposal → validator → evidence check → commit" asks for.

## H. Verified clean — do not disturb

| id | fact | evidence |
|---|---|---|
| **H1** | **No authority inversion, either direction.** No B-side code writes any A-frozen table. No A code writes `rf.*` or `aii.bu_onto`. The brief's central prohibition already holds. | grep across `aii/`, `src/stratum/services/`, `src/stratum/api/`, `src/stratum/knowledge/a_repository/` — zero hits both ways |
| **H2** | `dedup/gates.py` is the right shape already: deterministic, closed-dictionary, DIFFERENT-biased ("宁碎片不错合"). A merge can only be `same` if the gates did not object. This is the brief's B5, built. | `gates.py:1-10,80` |
| **H3** | `dedup/readout.py` is the only B pipeline that honours the ledger end to end: per-edge LLM judgment, `decision_type='readout'`, `actor='llm'`, `llm_raw` saved, `evidence` written. 1,654 such rows `[live]`. | source + live |
| **H4** | A-2's `verdict.py` is directly reusable: derives a verdict from reported gates, no hardcoded list, mutation-checked by 11 tests. B needs gates, not a new verdict mechanism. | `a_repository/verdict.py`, `test_a_final_verdict.py` |
| **H5** | A-2's own final report lists `inference or judgement: none` and `semantic similarity: none` as non-goals, and `073:11` says *"Grouping these units into concepts is another repository's work."* The A→B seam is already declared by A. | `A_REPOSITORY_FINAL_ACCEPTANCE_REPORT.md` §8; `073:11` |
| **H6** | `a[li]-ku-lint.timer` and `aii-pg-backup.timer` are enabled and running. B-1 is backed up daily and health-checked twice a day. 724 MB, retained 7 days. | `systemctl --user`; `deploy/pg_backup.sh:62,69` |

## Priority summary

```
P0  A1 A2 A3   B has no A-side to derive from
P0  B1 B2      ledger discipline is void; B is not replayable
P0  C1 C2      no lifecycle state, everything unverified
P0  D1 D2 D3 D4   three Concept objects, no authority, no shared vocabulary
P0/G1          BU2: continue or delete, do not leave half-built
P1  B3 B4 B5   live writer bypasses ledger; gates untested; gold set unrunnable in CI
P1  C3 C4      no supersession in B; no verdict mechanism
P1  E2         Nature needs supporting_evidence + emergence_count to be auditable
P1  F1 F2 F3 F6   ingest down 7wk; restart is broken; live schema ≠ migration; no migration tracking
P1  G7         two fidelity checks are hardcoded True
P2  E1 E3 E4   Nature reserved and correctly empty; naming settled now
P2  F4 F5      dead writers; write-only hyperedge
```

Four of the five P0 rows are not implementation work. They are A2–A3 (does A仓 get
promoted, and where), and D1–D4 (which Concept object is canonical). Both need a
person's decision before a schema spec is worth writing.
