# BU2_FINAL_ACCEPTANCE_REPORT

Spec: `BU2_FINAL_ACCEPTANCE_SPEC` v1.0. Date: 2026-10-02. Scope: `/data/soffy/projects/stratum`.

Companion: `LEGACY_CAPABILITY_INVENTORY.md`. Trial evidence: `evidence/`.

---

```
LEGACY_CAPABILITY_FUSION:   FAIL
BOOK_UNDERSTANDING_COMPLETENESS: PARTIAL
DOMAIN_MODEL:               PASS (declared) / FAIL (realised)
PIPELINE:                   FAIL
VERIFICATION:               PASS (design) / FAIL (exercised)
EXPRESSION:                 FAIL
B_WAREHOUSE_ISOLATION:      PASS
LEARNING_BOUNDARY:          PASS
RUNTIME_INDEPENDENCE:       FAIL

FINAL_ACCEPTANCE:           NOT ACCEPTED
```

## 1. The one-line reason

BU2 has 16 tables, ~70 models, 14 repositories, a 7-case verification gate and 85
passing tests — and **0 rows in all 16 tables, no producer for any of them, and no
entrypoint that can reach one.**

```
SELECT count(*) FROM stratum.book_understandings_v2;   -- 0
SELECT count(*) FROM stratum.chapter_understandings;  -- 0
   ... all 16 BU2 tables return 0
```

The §15 end-to-end trial was attempted against a real book and is blocked at step 1
of 7. Details in §3.

## 2. What passes, and why it is not the same as being accepted

Four gates pass outright. They are recorded because they are real, and because
together they show the design work was not wasted.

**§12 B-warehouse isolation — PASS.** Zero references to `rf.*`, `aii_refined`,
`refined_ku` or `refined_concept` across all 10 BU2 service modules and
`bu_v2_models.py`. BU2 does not touch the B warehouse.

**§13 learning boundary — PASS.** Zero writes to `cx.learning_progress`. BU2 projects
`LearningObject` and `RetrievalItem` into its own tables and leaves the C authority
alone. Worth recording: that authority does not exist on this host — `cx` has 0 tables
in production and there is no `aii_context` database. The boundary is respected; the
thing on the other side of it is unreachable.

**§8 verification gate (as designed) — PASS.** `_require_verified`
(`bu_v2_pipeline.py:185`) raises `PipelineTransitionError` on 7 distinct cases: missing
BU, BU without book provenance, missing artifact, artifact from another run, artifact
for another book, outcome FAIL, and unresolved gaps. The state machine keeps the
distinction that matters most — a rejected gate raises, while only an *operational*
error reaches `_fail_pipeline` (`:62` vs `:81`), so validation failure never poisons a
run. This is the most complete unwired asset in the repository.

**§4.1 book identity — PASS (as designed).** `book_understandings_v2` carries `book_id`,
`substrate_id` and `run_id`, with FKs to `stratum.substrates` and
`stratum.book_reading_run`, plus `UNIQUE(substrate_id, version)`. The spec's
same-book/multiple-runs requirement is structurally satisfiable.

## 3. §15 end-to-end trial — FAILED, with the trace

Book: **Thomas Calculus 14th ed.**, `substrate_id=01KWRXP646FQEPPRPHS3R617MZ`,
5,135,239 characters of already-extracted `derivative.content`. A real book with real
text, not a fixture.

```
ingestion       OK    derivative content present, 5.1M chars
reading run     FAIL  CheckViolation on the first INSERT
chapter         ---   never reached
integration     ---   never reached
verification    ---   never reached
BookUnderstandingV2  ---   never reached
expression      ---   never reached
```

**The failure.** `scripts/qualify_book_reading_run.py` is the only non-test caller of
any BU2 write path. Run against production with correct credentials:

```
psycopg2.errors.CheckViolation: new row for relation "book_reading_run"
  violates check constraint "book_reading_run_status_check"
DETAIL: Failing row contains (br_2156dbaf..., 'planned', ...)
```

`book_reading.py:82` inserts `status="planned"`. Migration `065` replaced that
constraint with the 10-state pipeline set (`CREATED, PERCEIVED, INSPECTED,
DEEP_READ_COMPLETE, CHAPTER_MODELLED, BOOK_INTEGRATED, VERIFICATION_PENDING, VERIFIED,
COMPRESSION_TESTED, FAILED`). `planned` is not among them. The same file's idempotency
guard at `:68` filters on `'completed'`, which `065` also removed.

I isolated whether this is the only blocker by replaying the insert on staging inside a
rolled-back transaction with a real substrate: with `status='CREATED'` it succeeds. So
the status literal is a one-line fix — and it changes nothing about the verdict, because:

**Fixing it advances the trial zero steps.** With a run created, step 2 needs something
to produce a `ChapterUnderstanding`. Nothing does. Every reference to
`ChapterUnderstandingRepository`, `ChapterDeltaRepository` and
`BookUnderstandingRepository` outside `bu_v2_repositories.py` is inside
`bu_v2_pipeline.py` — and there they are only **read**, as `check_exists` gates
(`:131,133,141,143,145`). The pipeline verifies that upstream stages produced artifacts.
It never produces them.

Concretely: of 14 `Repository.save()` methods, the only two call sites in the entire
repository are `bu_v2_pipeline.py:291` and `:308`, inside `_project_learning` — and
`BU2PipelineStateMachine(` is instantiated **only** in
`tests/architecture/test_bu_v2_foundation.py`. There is no CLI command, no API route, no
scheduler job. Confirmed by grep across `cli/main.py`, `api/`, `http_api/`,
`scheduler/`: zero hits.

**Root cause, one line.** BU2 contains **no LLM capability at all.** Grep for
`llm|oprim|llm_call|deepseek|nim_|openai|anthropic` across the pipeline, repositories
and `book_reading.py`: zero hits. `ku_segmentation.py:3` says so in its own docstring —
*"Deterministic baseline (no LLM)"* — and its `PropositionAnalyzer` protocol has exactly
one implementation, `DeterministicAnalyzer`. Every gate in the 7-pass pipeline is
`check_exists` or `SELECT 1`. The extraction step the architecture assumes does not
exist in any form.

The one function that does produce anything, `_project_learning:259`, emits
`LearningObject`s with `target_refs=[]`, `prerequisites_refs=[]` and
`expected_answer=""` — structurally empty placeholders, and it is unreachable anyway.

## 4. Per-section verdicts

| § | Requirement | Verdict | Evidence |
|---|---|---|---|
| 3 | Legacy capability fusion | **FAIL** | 0 fully fused. Also unmeasurable as specified: `bu_onto.substrate_id` and `substrates.id` share **0 rows**, so no book has both a legacy BU and a BU2 understanding. See `LEGACY_CAPABILITY_INVENTORY.md`. |
| 4.1 | Book identity | PASS (design) | `book_id`/`substrate_id`/`run_id` + 2 FKs + `UNIQUE(substrate_id,version)`. 0 rows. |
| 4.2 | Reading foundation | PARTIAL | `visual_semantic_unit` + `reading_ledger` declared; 0 rows; the only writer crashes (§3). |
| 5 | Chapter understanding layer | **FAIL** | `chapter_understandings` 0 rows, no producer. 13 of 70 models have no consumer at all. |
| 6 | Whole-book integration | **FAIL** | `ChapterDependencyGraph`, `DiscourseArc`, `ConceptEvolutionStep`, `ClaimEvolutionStep` — declared, zero consumers, not even tested. The spec's prohibition on summary-concatenation is currently satisfied vacuously: there is no integration either. |
| 7.1 | Argument architecture | PARTIAL | `stratum.arguments` + `argument_architecture_json`; `ArgumentArchitecture` model has no consumer. `Argument.confidence` is unreachable: the column is `NOT NULL DEFAULT 0.5`, the model has no such field, so every row would be permanently 0.5. |
| 7.2 | Mechanism understanding | **FAIL** | `author_mechanisms` 0 rows. `MechanismRepository.save:562-563` hardcodes `"ku_refs": []` and `"evidence_refs": []` — mechanisms would be permanently ungrounded even if written. |
| 7.3 | Situation model | **FAIL** | `situation_models` 0 rows, no producer. |
| 7.4 | Discourse structure | **FAIL** | `DiscourseArc`/`DiscourseArcStep`/`DiscourseRole` have no consumer and no test. |
| 7.5 | Evolution model | **FAIL** | `concept_evolution_json`/`claim_evolution_json` columns exist; `ConceptEvolutionStep`/`ClaimEvolutionStep` classes are unreferenced. |
| 8 | Evidence + verification | PASS (design) / FAIL (exercised) | Gate is real and well-built; 0 verification artifacts, so it has never fired against data. `EvidenceTrajectory` also has a dead read path: `TrajectoryRepository.list_for_run:724` always returns `[]` because nothing writes `knowledge_claims.extraction_run_id`. |
| 9 | Negative knowledge | **FAIL** | `negative_knowledge_json` column exists; `NegativeKnowledge` model has no consumer. |
| 10 | Frontier layer | PARTIAL | `understanding_frontiers` 0 rows; `FrontierResolution` unreferenced. |
| 11 | Final expression layer | **FAIL** | All six required outputs absent from the schema: `essence`, `world_model`, `mechanism`, `logical_architecture`, `boundaries`, `contribution` — 0 columns each. `ExpressionProfile` is a rendering profile (audience/duration/modality), not a book-essence artifact. |
| 12 | B-warehouse isolation | **PASS** | 0 references to `rf.*`/`aii_refined` across 10 modules. |
| 13 | Learning projection boundary | **PASS** | 0 writes to `cx.learning_progress`. Note: `cx` has 0 tables in production; no `aii_context` database exists on this host. |
| 14 | Runtime independence | **FAIL** | Untestable as specified. BU2 has no dependency on `aii.bu_onto` in either direction, so "disable the legacy runtime" would pass trivially while BU2 cannot run at all with it fully up. |
| 15 | End-to-end book trial | **FAIL** | Attempted on a real 5.1M-char book; blocked at step 1. Trace in `evidence/`. |
| 16 | This report | — | — |

## 5. Why PASS is not available, stated as the spec defines it

§17 requires all eight conditions. Measured:

```
Legacy capability absorbed              NO   0 of 20 capabilities fused
BU2 owns complete book understanding    NO   0 rows across all 16 tables
Evidence traceable                      NO   no BU2 object exists to trace
Verification enforced                   NO   gate exists, has never executed on data
Expression complete                     NO   no schema for the six outputs
B warehouse isolated                    YES
Learning isolated                       YES
Real book end-to-end proven             NO   blocked at step 1 of 7
```

Two of eight. The spec's own rule: **NOT ACCEPTED**.

## 6. What is worth keeping, and the one thing that would change the verdict

This is not a design failure. The parts that exist are better than the legacy system
they would replace, on the four axes the legacy system is weakest:

```
traceability   BU2 has run_id + 2 FKs;  bu_onto has no run_id and no FK
verification   7-case hard gate;        bu_onto.bu_quality runs but only on legacy
versioning     UNIQUE(substrate,version) + run_id;  legacy has no unique key
immutability   status CHECK;            legacy rows are updated in place
```

And the verification gate, the delta-fold guard (`TypeError("SUMMARY_OF_SUMMARIES=0")`),
the stance guard (`ValueError("STANCE_ERROR")`) and the `check_fidelity` refusal to
accept ref-less claims are all real, tested, and worth preserving verbatim.

**The single change that would move this from FAIL to a real trial:** an extractor that
turns `derivative.content` into `ChapterUnderstanding` and `ChapterDelta` rows. That is
one missing component. It is also the entire remaining project — 14 of 16 tables exist
to hold its output, and the gate that would judge its output is already written and
tested.

Ordering note, because the dependency is easy to get backwards: fixing the `status`
literal is necessary and is genuinely one line, but it is not the blocker. Writing the
extractor is the blocker, and the status fix is invisible until it exists.

## 7. Evidence index

`evidence/` holds the trial:

| file | what it shows |
|---|---|
| `TRIAL_BOOK.txt` | the book, its id, and the 5,135,239-char derivative that made it a real trial rather than a fixture |
| `BU2_TABLE_COUNTS.txt` | all 16 tables at 0 rows |
| `TRIAL_FAILURE.txt` | the CheckViolation, verbatim, with the failing row |
| `TRIAL_ISOLATION.txt` | the rolled-back staging insert proving `status='CREATED'` succeeds — i.e. the status literal is the only thing between the current code and a created run, and the next step still has no producer |
| `PRODUCER_SEARCH.txt` | the greps proving no producer, no entrypoint, and no LLM capability |
| `ISOLATION_CHECKS.txt` | §12 and §13 greps, both clean |
