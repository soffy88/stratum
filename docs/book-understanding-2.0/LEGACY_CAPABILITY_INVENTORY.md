# LEGACY_CAPABILITY_INVENTORY

Audit date: 2026-10-02. Acceptance spec: `BU2_FINAL_ACCEPTANCE_SPEC` v1.0 §3.

Method: read `aii.bu_onto`'s live schema and row-level fill rates against all 4,005
rows, read the three generator scripts, and map each legacy capability to whatever
BU2 declares. No capability is marked ABSENT without a row count or a code reference.

## 0. The finding that governs this table

`aii.bu_onto` and `stratum.book_understandings_v2` cannot be compared capability by
capability, because **they do not share a subject**. Measured:

```
aii.bu_onto.substrate_id          advmath_en_0006e343f7, econ_zh_2726f38224, ...
stratum.substrates.id             01KVA1XD27CH2CW7C3BJ7EKC3H, ...
JOIN on substrate_id              0 rows
```

Every legacy BU belongs to a flywheel book that was never ingested as a
`stratum.substrates` row. So "did BU2 absorb capability X" has no measurable answer
against the existing data: there is no book for which both a legacy BU and a BU2
understanding exist. Not one.

The fusion audit therefore has two parts: a capability-by-capability mapping of what
is *declared* (§1), and the live fill rate of what is *real* (§2).

## 1. Capability mapping

`legacy fill` = rows of 4,005 where the field is non-null. `BU2 target` = the table
or column that would carry it.

| Legacy capability | Source | Purpose | BU2 target | legacy fill | Status |
|---|---|---|---|---|---|
| Book problem statement | `bu_onto.problem_statement` | what the book answers | `book_understandings_v2.governing_questions_json` | 4005/4005 | **PARTIAL** — declared; no producer |
| One-line overview | `bu_onto.overview_oneline` | orientation | (none) | 4005/4005 | **OBSOLETE** — BU2 has no equivalent; `understanding_projection.compile_ladder` serves this role in memory |
| KU organisation | `bu_onto.key_concept_ku_ids` | which KUs carry the book | `chapter_understandings` / `book_understandings_v2.concept_system_json` | **0/4005** | **MISSING** — the legacy field is itself empty; BU2 declares the target |
| Main claims | `bu_onto.main_claims` | the book's assertions | `book_understandings_v2.central_theses_json` + `sub_theses_json` | 3956/4005 | **PARTIAL** |
| Argument structure | `bu_onto.argument_structure` | claim → support | `stratum.arguments` + `book_understandings_v2.argument_architecture_json` | 1273/4005 | **PARTIAL** — legacy is jsonb text, not objects |
| Mechanism / explanation | `bu_onto.core_explanations` | why it happens | `stratum.author_mechanisms` | **0/4005** | **MISSING** — legacy empty too |
| Concept network | `bu_onto.concept_network` | concept graph | `stratum.knowledge.concepts` (BU2 has no own) + `concept_system_json` | **0/4005** | **MISSING** |
| Book structure | `bu_onto.structure` | skeleton | `stratum.chapter_understandings` | **0/4005** | **MISSING** |
| Applicability | `bu_onto.applicability` | when it applies | (none) | **0/4005** | **MISSING** |
| Core takeaways | `bu_onto.core_takeaways` | summary bullets | (none) | **0/4005** | **MISSING** |
| Limitations | `bu_onto.limitations` | scope limits | `book_understandings_v2.negative_knowledge_json` | 2683/4005 | **PARTIAL** |
| Positional summary | `bu_onto.positional_summary` | author stance | (none) | 2683/4005 | **MISSING** — no BU2 equivalent |
| Learning thread | `bu_onto.learning_thread` | through-line | (none) | 1322/4005 | **MISSING** |
| Facets (zh/en) | `bu_onto.facets_zh` / `facets_en` | dimension facets | `ku_segmentation` discourse/epistemic roles | 1322/4005 | **PARTIAL** |
| Grounded facets | `bu_onto.facets_grounded` | facets with verbatim source | `stratum.evidence_trajectory` | 1015/4005 | **PARTIAL** — legacy keeps grade + verbatim; BU2 declares a trajectory table with no producer |
| Agent skill | `bu_onto.agent_skill` | machine skill view | (none — C仓 concern) | 2683/4005 | **OUT OF SCOPE** per spec §2.1 |
| Learning paths | `bu_onto.learning_paths` | study order | `stratum.learning_objects` + `learning_graphs` | 1017/4005 | **PARTIAL** — spec §13 permits this projection |
| Deep cards | `bu_onto.deep_cards` | flashcards | `stratum.retrieval_items` | 1017/4005 | **PARTIAL** |
| BU quality gate | `bu_onto.bu_quality` + `bu_learning_gate.py` | evidence floor, per-facet grade checks, drop list | `stratum.verification_artifacts` | 1017/4005 | **PARTIAL** — legacy gate is real and running; BU2's is declared |
| Grade | `bu_onto.grade` | verification state | `book_understandings_v2.status` (DRAFT/VERIFICATION_PENDING/VERIFIED/FAILED) | 4005/4005 | **PARTIAL** |
| Synthesis marker | `bu_onto.synthesis_marker` | "AII综合,非原文断言" | (none) | 4005/4005 (default) | **MISSING** — see §4 |
| Provenance | `bu_onto` has **no** run_id / no source_version / no FK | — | `book_understandings_v2.run_id` + `book_id` + 2 FKs | — | **BU2 SUPERIOR** — BU2 is structurally traceable; legacy is not |
| Comprehension verification | legacy has none | — | `_require_verified` CASE A–G | — | **BU2 SUPERIOR** |
| Multi-version runs | legacy has none (no unique key) | — | `UNIQUE(substrate_id, version)` + `run_id` FK | — | **BU2 SUPERIOR**, but see §4 |
| Immutable understanding | legacy `bu_onto` rows are updated in place | — | BU2 declares status CHECK | — | **BU2 SUPERIOR in design** |

### Totals

```
FULLY_FUSED   0
PARTIAL      10   (declared in BU2, no producer)
MISSING      10   (no BU2 equivalent; 6 of these are empty in legacy too)
OBSOLETE      1
OUT OF SCOPE  1
BU2-SUPERIOR  4   (traceability, verification, versioning, immutability)
```

**Zero capabilities are fully fused.** Every "PARTIAL" is the same failure: the
target is declared in a table, model or repository, and nothing constructs it.

## 2. What the legacy system actually has, and BU2 does not

Worth stating plainly, because the spec's framing ("升级") invites the opposite
assumption. The legacy path is a working system with 4,005 populated rows and three
scripts that run in production:

```
generate_bu.py       LLM generation, 1 prompt, per-substrate
persist_bu.py        writes aii.bu_onto
bu_learning_gate.py  real quality gate: evidence floor, per-facet grade checks, drop list
```

`bu_learning_gate.py` is the one thing BU2 has no equivalent of *in operation*: it
runs, it has a real checklist, and it drops bad facets
(`:378` `bad_grade_ku_removed`, `:404` per-facet checks). BU2's
`verification_artifacts` is the same idea, declared and unpopulated.

So the fusion is not "BU2 replaced a working system." It is "a working system
coexists with a complete design that has no implementation," and the working system's
output cannot be compared to it because the two never touch the same book.

## 3. Isolation checks — these PASS

Verified, and worth recording as PASS rather than assumed:

| spec § | check | result |
|---|---|---|
| 12 | BU2 references `rf.*` / `aii_refined` / `refined_ku` / `refined_concept` | **0 hits** across all 10 BU2 service modules and `bu_v2_models.py` |
| 13 | BU2 writes `cx.learning_progress` | **0 hits** — no INSERT, no reference |
| 14 | BU2 references `aii.bu_onto` | **0 hits** — no dependency in either direction |
| 8 | Verification gate is enforced, not advisory | `_require_verified` raises on 7 distinct cases; `VALID_TRANSITIONS` is one-way; rejected gates raise while only operational errors call `_fail_pipeline` |

§14 deserves a caveat. BU2 is independent of `aii.bu_onto` trivially — it has no
connection to it at all, in either direction. The spec's test is "disable the legacy
runtime and BU2 still works." That test would pass today, and it would prove nothing,
because BU2 cannot run at all with the legacy runtime fully up. The honest statement
is that §14 is untestable as specified, not that it passes.

## 4. Two gaps in BU2 that no legacy comparison would surface

**§11's expression layer has no schema.** The spec requires six outputs. Grepped
`book_understandings_v2` for all six: `essence`, `world_model`, `mechanism`,
`logical_architecture`, `boundaries`, `contribution` — **0 columns each**. The ten
`*_json` fields cover questions, theses, concepts, arguments, dependency graph,
discourse arc, negative knowledge, two evolutions, and two question sets. The
expression layer is a rendering concern in `understanding_projection.py`, and
`ExpressionProfile` (`bu_v2_models.py:530`) is an audience/duration/modality profile,
not a book-essence artifact.

**13 of 70 model classes have no consumer at all** — no repository, no service:

```
DiscourseRole  EpistemicRole  KU20Extensions  EvidenceProgramItem
ArgumentArchitecture  ChapterDependency  ChapterDependencyGraph
DiscourseArcStep  DiscourseArc  NegativeKnowledge
ConceptEvolutionStep  ClaimEvolutionStep  FrontierResolution
```

None is even covered by a test. These are exactly the classes §6 (cross-chapter
dependency graph), §7.4 (discourse structure) and §7.5 (evolution model) require.
The spec's domain model is declared in types and never built.

## 5. Verdict

```
LEGACY_CAPABILITY_FUSION: FAIL
```

Not PARTIAL. The mapping cannot be completed as specified, because for the 4,005
legacy BUs there is no corresponding `stratum.substrates` row to re-read and no BU2
table to compare against. Fusion would have to mean re-running extraction against
`substrates`, which is new implementation, not an audit finding.

What is genuinely true: **BU2's design is stronger than the legacy system on
traceability, verification, versioning and immutability, and weaker on everything
that requires running something.**
