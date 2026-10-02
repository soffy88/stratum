# B仓 Current State

Audit date: 2026-10-02. Method: read every migration, module and writer in scope; query
the three live Postgres instances read-only for row counts. Live counts are marked
`[live]`. Everything else is read from source.

## 0. The audit target does not exist as specified

The audit brief named these paths:

```
stratum/bu/  understanding/  concept/  ontology/  semantic/  projection/  learning/
aii/knowledge/  kg/
```

**None of them exist.** `find -maxdepth 4 -type d` returns zero hits for all nine.
There is no `stratum/` package root (the Python package is `src/stratum/`), no `bu/`,
no `kg/`. The premise that B仓 has a directory-shaped surface is wrong, and the
design that follows from it would be a fourth implementation rather than a repair
of the first three.

What exists instead is **three unrelated implementations of "semantic layer"**,
in three different databases, with three different object models and no shared
identity space.

| # | Implementation | Database | schema | Migrations | Live rows | Ingesting? |
|---|---|---|---|---|---|---|
| **B-1** | `rf.*` refined repo | `aii_refined` (5436) | `rf` | `aii/migrations/refined/0001-0005` | ~74,700 | **no — stopped 2026-08-13** |
| **B-2** | BU2 book understanding | `aii_kg` (5437) | `stratum` | `pg_migrations/060-066` | **0** | no — no producer wired |
| **B-3** | legacy user concept graph | `aii_kg` (5437) | `stratum` | `pg_schema/001`, `pg_migrations/012/020/029/030` | 549 | yes — LLM, on ingest |

## 1. B-1 — `rf` refined repo (the one with data)

### 1.1 Existing tables

`aii/migrations/refined/0001_refined_repo_schema.sql` declares 13 tables.
`[live]` counts from `aii_refined`.

| table | owner | purpose | authority | live rows | has writer | has reader |
|---|---|---|---|---|---|---|
| `decision_ledger` | B | append-only record of every deepening decision; `llm_raw` retained so replay never re-asks the model | B | 2,403 | `dedup/ledger.py:64`, `normalize_discipline.py:100` | `graph_concepts.py:67,451`, `ku_lint.py:120` |
| `refined_ku` | B | deduplicated knowledge point; `contributions` jsonb is the real body, one fragment per A-side source, original language kept | B | 29,323 | `dedup/integrate.py:133`, `refined_ingest_dryrun.py:395`, **`learning.py:888,948` (live HTTP)** | 8 modules |
| `refined_concept` | B | canonical concept; `discriminative` jsonb, `discipline` for hard isolation, own 1024-d embedding | B | 10,008 | `dedup/integrate.py:170`, `normalize_discipline.py:93` | 9 modules |
| `refined_ku_concept` | B | KU↔concept incidence, the implicit hyperedge used for co-occurrence | B | 24,718 | `dedup/m0.py:197,342`; DELETE `ku_lint.py:201` | 7 modules |
| `refined_directed_edge` | B | concept skeleton: `src_concept`→`dst_concept`, `relation_type` CHECK, `strength`, `evidence` jsonb | B | 1,231 | `dedup/readout.py:324,332`, `edge_backfill.py:97,155`, `edge_match_embed.py:118`, `refined_directed_edge_dryrun.py:161,165,275`; DELETE `ku_lint.py:208` | 8 modules |
| `refined_hyperedge` | B | n-ary mechanism, `mechanism_key` for head-sameness, `nl_description` + embedding | B | 967 | **`edge_backfill.py:182` only** | `ku_lint.py:124` — a row count |
| `refined_theme_kc` | B | spectral community, versioned snapshots, old frozen | B | 79 | `build_theme_kc.py:166,185`, `community_detect.py:100` | 5 modules |
| `refined_kc_member` | B | theme↔KU junction | B | 3,864 | `build_theme_kc.py:197`, `community_detect.py:110` | 4 modules |
| `refined_kc_concept` | B | theme↔concept junction | B | 217 | `build_theme_kc.py:205`, `backfill_kc_concept.py:120` | `graph_concepts.py:386` |
| `refined_invariant` | B | **Nature layer. Reserved, M4. Never written** | B | **0** | **none** | `ku_lint.py:127` — a count |
| `refined_concept_invariant` | B | concept↔nature M:N. Never written | B | **0** | **none** | none |
| `refined_hyperedge_member` | B | polymorphic member of a hyperedge. Never written | B | **0** | **none** | none |
| `refined_cross_domain_relation` | B | SME ⟨M,C,S⟩ cross-domain relation. Reserved, M3 | B | **0** | **none** | none |
| `refined_cdr_member` | B | cross-domain relation↔concept junction | B | **0** | **none** | none |
| `dedup_decision` | B | migration 0002, states in its own comment that no script writes it | B | 0 | none | `refined_ingest_dryrun.py:249` |
| `ku_health_issues` | B | **exists live, in no migration** | B | 10 | `ku_lint.py:167-214`, twice daily via `aii-ku-lint.timer` | `aii_healer.sh:150` |

Five of thirteen tables are pure schema reservation. The 第③层 cross-domain pair and
the entire 第④层 Nature pair have no code and no data.

### 1.2 Existing models

`rf` has no ORM, no model classes, no dataclasses. Every writer hand-writes SQL with
`asyncpg`. Consequence: the DDL is not the only definition, and they disagree
(§ 5).

### 1.3 Existing pipelines

**P1 — KU dedup (the real B仓 ingest).** `aii/scripts/dedup/`

```
aii.ku_onto  ──candidates.py:23──▶  vector neighbours (cos ≥ --sim 0.90)
                ──gates.py:80──▶     deterministic gates 0/1/2, run BEFORE the model
                ──judge.py:141──▶   LLM pass, only for a proposed merge
                ──ledger.py:64──▶   decision_ledger row, llm_raw retained
                ──integrate.py:133─▶ rf.refined_ku UPSERT (default dry-run; --apply commits)
```

`gates.py` is the part worth keeping: it is deterministic, closed-dictionary, and
DIFFERENT-biased — "宁碎片不错合". A merge verdict can only be `same` if the
deterministic gates did not already object. That is the shape the brief's
"LLM proposal → Validator → Evidence check → commit" wants, and it already exists.

**P2 — concept merge.** `aii/scripts/dedup/m0.py` — `rf.refined_ku.contributions.raw_ku_id`
→ `aii.ku_concept_onto` → `aii.concept_onto` → LLM concept-sameness → `rf.refined_concept`
+ `rf.refined_ku_concept`. Also dry-run by default.

**P3 — relation readout.** `aii/scripts/dedup/readout.py` — LLM, NIM pool, per-pair
judgment into `rf.refined_directed_edge`, **with** a `decision_ledger` row
(`decision_type='readout'`, `actor='llm'`, `llm_raw` saved). This is the only B
pipeline that honours the ledger discipline end to end.

**P4 — orchestration.** `aii/scripts/b_repo_sync.sh` → orchestrate → m0 → readout.
Default `--singletons-only`, i.e. no auto-merge without passing the gold set.

### 1.4 Existing tests

**There are none for B仓 logic.** Specifically:

- No `aii/tests/` directory exists.
- `dedup/gates.py` is pure and would be trivially testable, but has only a
  `__main__` print block, not pytest.
- `dedup/run_gold.py` is the adversarial gold harness and is **not runnable in CI**:
  it needs two live databases and `DEEPSEEK_API_KEY` (`run_gold.py:35-36,104`).
- The one test that touches B仓 code, `tests/services/test_slo_and_contracts.py:80-90`,
  tests `BGraph.ppr()` on a hand-built in-memory graph. It never opens a connection.
- `tests/architecture/test_*.py` (998 tests) contains **negative** assertions only:
  A仓 must not reference B tables. Those are freeze guards for A, not B coverage.

So the "判同逻辑先过金集才准碰真数据" rule from `STATUS.md:65` is a convention in a
shell comment. Nothing enforces it.

### 1.5 Existing artifacts

- `aii/refined_graph/graph.json`, `graph.html` — output of `community_detect.py:31`.
  No code in that directory.
- `aii/scripts/gold/preds_judge.jsonl` — 926 bytes, last touched 2026-07-17.
- Live DB is 724 MB `[live]`, backed up daily (`aii-pg-backup.timer`, enabled, ran
  2026-10-01 03:15). Backup size byte-identical for Sep 29/30/Oct 1 — independent
  confirmation that nothing has been written in three days.

### 1.6 Operational state

```
max(rf.refined_ku.updated_at)   2026-08-13 01:11:44 UTC   [live]
aii-b-repo-sync.timer           disabled / inactive, never executed, no log file
aii-pg-backup.timer             enabled / active
aii-ku-lint.timer               enabled — the only B仓 write still running
```

B-1 has had **no ingestion for seven weeks**. And it cannot simply be restarted:

- `aii/deploy/systemd/aii-b-repo-sync.service:10` sets `AII_KG_URL=…:5435/aii_kg`;
  the live `aii-postgres` container publishes **5437**.
- `b_repo_sync.sh:60-68` hard-returns 1 when the embed endpoint is unreachable, under
  `set -euo pipefail` (`:17`). `STATUS.md:58` and `aii/PIPELINE_STATUS.md:155` both
  record that endpoint as already migrated to the laptop. **The documented fix is not
  in the code.** The doc and the script disagree.

## 2. B-2 — BU2 (schema-complete, producer-empty)

### 2.1 Existing tables

16 tables from `pg_migrations/060-066`, all present in `stratum_a_p3_fresh` `[live]`,
**all 0 rows** `[live]`.

| table | model | repository `save()` | producer in production code? |
|---|---|---|---|
| `book_reading_run` | plain class, `book_reading.py:7` | none (read+update only) | `create_reading_run` — **broken, see §5** |
| `reading_ledger` | plain class, `book_reading.py:40` | none | yes (accounting only) |
| `visual_semantic_unit` | `bu_v2_models.py:149` | `repos:86` | no |
| `evidence_trajectory` | `:138` | `repos:686` | no |
| `arguments` | `:163` | `repos:493` | no |
| `author_mechanisms` | `:176` | `repos:546` | no |
| `situation_models` | `:190` | `repos:603` | no |
| `understanding_frontiers` | `:411` | `repos:648` | no |
| `chapter_understandings` | `:251` | `repos:146` | no |
| `chapter_deltas` | `:272` | `repos:180` | no |
| `book_understandings_v2` | `:287` | `repos:208` | no |
| `understanding_gaps` | `:313` | `repos:305` | no |
| `learning_objects` | `:326` | `repos:428` | only from the state machine |
| `learning_graphs` | `:349` | `repos:737` | no |
| `retrieval_items` | `:361` | `repos:462` | only from the state machine |
| `verification_artifacts` | `:374` | `repos:381` | no |

Proof of producer-emptiness: every `Repository.save()` / `.transition()` call site in
`src/` and `scripts/` is

```
bu_v2_pipeline.py:291   LearningObjectRepository.save(...)
bu_v2_pipeline.py:308   RetrievalItemRepository.save(...)
```

and `BU2PipelineStateMachine(` has **zero** instantiations outside
`tests/architecture/test_bu_v2_foundation.py`. There is no CLI command, no API route,
no scheduler job. `src/stratum/cli/main.py` has 0 hits for any BU2 name.

`BU2_FINAL_FREEZE_REPORT.md:108` states the same: *"No INSERT / UPDATE / DELETE /
migration upgrade executed."*

### 2.2 Existing models

`bu_v2_models.py` — ~60 pydantic models, 17 enums, purely declarative. Seventeen of
them (`LearningPath`, `TutorSession`, `MasteryDimensions`, `BUStatement`,
`WorkingBU`, the four gold classes…) have **no persistence consumer at all**.

### 2.3 Existing pipelines

`bu_v2_pipeline.py` — 7 ordered transitions, 8 one-way edges, `FAILED` absorbing.
Design invariant worth keeping: `_assert_and_transition:62` turns a validation
rejection into an exception while `_fail_pipeline:81` is reserved for operational
errors, so a rejected gate never poisons the run.

**Zero LLM calls anywhere in BU2.** Every gate is `check_exists` / `SELECT 1`. The one
producing function, `_project_learning:259`, emits LearningObjects whose
`target_refs`, `prerequisites_refs` are `[]` and `expected_answer` is `""` —
structurally thin placeholders.

Six service modules are pure functions with **no caller in `src/`** and no
persistence: `bu_provenance.py`, `working_bu.py`, `understanding_projection.py`,
`learning_compiler.py`, `tutor_engine.py`, and `ku_segmentation.py`'s analyzer
(`DeterministicAnalyzer` is the only implementation of the `PropositionAnalyzer`
protocol; no LLM implementation exists). They are well-specified and unwired.

### 2.4 Existing tests

85 test functions across 6 files, all in `tests/architecture/`:

| file | tests |
|---|---|
| `test_bu_v2_foundation.py` | 38 |
| `test_bu_p2_segmentation.py` | 10 |
| `test_bu_p4_working_bu.py` | 8 |
| `test_challenge_suite.py` | 8 |
| `test_bu_p8p9_benchmark.py` | 9 |
| `test_bu_p3_structure.py` | 6 |
| `test_understanding_projection.py` | 5 |
| `tests/services/test_book_reading.py` | 1 |

**No test touches a real database.** `tests/conftest.py` builds a fake whose only BU2
tables are `book_reading_run` and `reading_ledger`; the other 14 are absent, so no
integration test could exercise them even if a producer were wired.

### 2.5 The one thing BU2 has that B-1 lacks

A verification gate that refuses to proceed. `bu_v2_pipeline.py:185` `_require_verified`
implements seven hard cases (missing BU, missing artifact, FAIL, BLOCKED, wrong run,
wrong book, self-reported gaps, live blocking gaps). And `repos:264` defines a gap
lifecycle with explicit blocking statuses. This is the "validator before commit"
discipline the brief asks for, already written and already unit-tested — it just has
nothing upstream of it.

## 3. B-3 — legacy user concept graph

Not part of any warehouse design. Per-user, LLM-extracted, ungoverned.

| table | owner | purpose | authority | live rows | writer |
|---|---|---|---|---|---|
| `stratum.concepts` | user | personal concept, `substrate_refs text[]`, `related_concept_ids text[]` | user, not B | 4 | `api/routers/concepts.py:52` only — API POST |
| `stratum.concept_relations` | user | concept→concept, `relation_type TEXT NOT NULL` | user, not B | 1 | `api/routers/knowledge.py:341` only — API POST |
| `stratum.graph_entities` | system | LLM-extracted entity from raw markdown | system, not B | 185 | `dao/graph.py:35` via `graph_builder_service.py`, `extract_merge_service.py` |
| `stratum.graph_relations` | system | LLM-extracted relation | system, not B | 163 | `dao/graph.py:72`, same path |
| `stratum.knowledge_claims` | — | statement + status, KU2.0-shaped | stub per `CURRENT_STATE_MAP.md` | 102 | none in production |
| `stratum.evidence` | — | portable quote object | — | 8 | highlights backfill + API |
| `stratum.claim_evidence` | — | claim↔evidence | — | 144 | none |

This is B-3 in production and it is the weakest of the three:

- **No authority.** `graph_builder_service.py:29` prompts the LLM for
  `relation_type(affects/defines/part_of/supports/contradicts/uses)` and
  `dao/graph.py:72` inserts it. `[live]` distinct values in `graph_relations`:
  `affects, defines, uses, triggers, contradicts, related, part_of, supports,
  contains, related_to, is_a, redefines` — twelve, none constrained. The brief's
  prohibition on value judgement (`SIMILAR` / `IMPORTANT` / `BETTER` / `WORSE`) is
  enforced nowhere, and the prompt actively invites judgement words.
- **No evidence requirement.** `graph_entities.source_substrate_ids` is a bare id
  list. Nothing checks the substrate was read.
- **Merge is name equality.** `dao/graph.py:16-24` matches on
  `LOWER(TRIM(name))`, and its own docstring admits cross-lingual aliases split. So
  「价格弹性」 and "price elasticity" are two nodes.
- `stratum.concept_relations.relation_type` has **no CHECK constraint at all**
  `[live: only a confidence CHECK and the unique key]`.

## 4. Existing contradictions

1. **Three concept objects, no shared identity.** `rf.refined_concept` (10,008),
   `stratum.concepts` (4), `stratum.graph_entities` (185). `cornell_generator.py:114`
   reads the first; `api/routers/concepts.py` serves the second; `graph_query.py:34`
   reads the first and the third. Nothing reconciles them.
2. **Three relation vocabularies.** `rf.refined_directed_edge` CHECK
   `[derives, subsumes, prerequisite, explains, contrasts, example_of]`; B-3 free
   text; the brief proposes `[IS_A, PART_OF, CAUSES, DEPENDS_ON, INSTANCE_OF]`. No
   two agree.
3. **The Nature layer is already specified and empty.** `rf.refined_invariant`
   exists with `statement`, `invariant_vector`, `is_invariant_concept`, `status
   IN ('candidate','confirmed')`, and a `decision_id` FK. The brief's B4 Nature
   proposal and this table are the same object under two names — the schema's own
   header comment (`0001:11-12`) locks the term as **invariant (本性), not
   "nature"**, deliberately. Picking one name now avoids a rename later.
4. **`refined_hyperedge` is write-only.** 967 rows from one script, read by a row
   count in a lint.
5. **`B = f(A仓, 台账)` does not hold.** The invariant is stated at
   `0001:10-11`. Measured: `refined_ku` rows with `decision_id IS NOT NULL` = **0 of
   29,323**; `refined_concept` = **0 of 10,008** `[live]`. The ledger holds 2,403
   rows that link to nothing. B cannot be replayed from A + ledger, which was the
   design's whole justification for the ledger.
6. **Every B object is `unverified`.** `rf.refined_ku.grade` = `unverified` for all
   29,323; `rf.refined_directed_edge.grade` = `unverified` for all 1,231 `[live]`.
   There is no path in the code that sets any other value.
7. **Live schema ≠ migration.** `rf.ku_health_issues` and
   `refined_directed_edge.{edge_source, raw_substrate}` exist live, in no migration.
   The `relation_type` CHECK was widened by hand from 3 values to 6. A rebuild from
   `migrations/refined/` would reject 295 existing `explains` rows. There is no
   `schema_migrations` table in `rf` — migrations are applied by hand.
8. **Three writers would crash on `--commit`.** `refined_concept_commit.py:154`
   inserts into a non-existent `rf.refined_ku.sources`; `:175,186` write a
   non-existent table `rf.concept_decision`; `edge_backfill.py:155` inserts
   `relation_type='explains'`, which migration 0001's CHECK rejects. All three are
   superseded by `dedup/` but are still on disk and still look runnable.
9. **`learning.py` writes B-1 over HTTP.** `aii/aii/aii/api/routes/learning.py:888`
   updates `natural_text_zh` and `zh_grade` on read, `:948` on human correction.
   Neither writes a ledger row. `[live]` 5 rows have `zh_grade='unverified'`, 0
   `'verified'`. So the only live B-1 writer bypasses the decision ledger.
10. **The constitutional package does not know B exists.**
    `src/stratum/knowledge/__init__.py` re-exports `contract` and `provenance` only —
    not `bu_v2_models`. `contract.py:47-58` assigns `Concept` to
    `stratum.concepts` and `Relation` to `stratum.concept_relations`, i.e. to B-3.
    No BU2 table and no `rf` table appears in `contract.py`.

## 5. Verified clean

Two things are already correct and must not be disturbed.

- **No authority inversion, in either direction.** Grep for B writing A-frozen tables
  (`stratum.knowledge_unit`, `ku_candidate`, `reading_evidence`, `book_source`)
  across `aii/`, `src/stratum/services/`, `src/stratum/api/`: zero hits. Grep for A
  code writing `rf.*` or `aii.bu_onto`: zero hits. The prohibition holds today.
- **A-2's gate machinery is reusable as-is.** `verdict.py` derives a verdict from
  whatever gates a layer reports, with no hardcoded gate list, and is
  mutation-checked (`test_a_final_verdict.py`, 11 tests). B's gate set can adopt it
  without inheriting A's object model.

## 6. What could not be verified

- Whether B-1's 2,403 ledger rows would replay to the current 29,323 KUs. That
  requires running the pipeline, which needs the embed service and an LLM key.
- `tests/architecture` was collected (998 tests) but **not run**; the A仓 baseline of
  48 failures / 169 errors in the full suite was not re-measured here.
- C-warehouse `cx.learning_progress`, named the sole mastery authority by
  `mastery_authority.py:95`, is **not reachable from this host** — no `aii_context`
  database or container exists in the `aii-postgres` instance, and `cx` has 0 tables
  in `aii_kg`. C仓 authority is asserted in code and unverifiable in fact.
