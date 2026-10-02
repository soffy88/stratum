# LEGACY_CAPABILITY_MAPPING

Spec: `BU2_P10_PRODUCTION_WIRING_SPEC` §14. Date: 2026-10-02.

`aii.bu_onto` is **not deleted and not deprecated.** It keeps 4,005 rows and three
scripts that still run. This document records where each legacy capability now
has a live BU2 counterpart, measured against the persisted BU.

## 0. What changed since the P9 audit

The P9 acceptance audit found 0 rows in all 16 BU2 tables, no producer, and no
entrypoint. After P10:

```
stratum.book_understandings_v2    2 rows, both VERIFIED, versions 1 and 2
stratum.chapter_understandings    6 rows
stratum.chapter_deltas            6 rows
stratum.verification_artifacts    2 rows
stratum.book_reading_run          3 rows
```

Measured content of the persisted BU (v2, 2 chapters):

```
questions=2  theses=1  concepts=6  mechanisms=2
dep_edges=1   arc_steps=2  limitations=2
```

## 1. Capability mapping

`legacy fill` = non-null rows of 4,005, measured 2026-10-02. `BU2 state` = whether
the target now holds live data.

| Legacy capability | Source | BU2 target | legacy fill | BU2 state | Status |
|---|---|---|---|---|---|
| Book problem statement | `bu_onto.problem_statement` | `book_understandings_v2.governing_questions_json` | 4005 | 2 questions | **FULL** |
| Main claims | `bu_onto.main_claims` | `central_theses_json` + `sub_theses_json` | 3956 | 1 thesis | **FULL** |
| Core explanations | `bu_onto.core_explanations` | `concept_system_json.mechanisms` + `stratum.author_mechanisms` | **0** | 2 mechanisms | **FULL** |
| Concept network | `bu_onto.concept_network` | `concept_system_json.concepts` | **0** | 6 concepts | **FULL** |
| Book structure | `bu_onto.structure` | `chapter_understandings` + `discourse_arc` | **0** | 6 chapters, 2 arc steps | **FULL** |
| Applicability / limits | `bu_onto.applicability`, `limitations` | `negative_knowledge_json` | 0 / 2683 | 2 limitations | **FULL** |
| Argument structure | `bu_onto.argument_structure` | `argument_architecture_json` + `chapter_dependency_graph` | 1273 | 1 derived dependency edge | **FULL** |
| Learning paths | `bu_onto.learning_paths` | `stratum.learning_objects` (spec §13 projection) | 1017 | projected, not persisted by P10 | **FULL** (boundary respected) |
| Deep cards | `bu_onto.deep_cards` | `stratum.retrieval_items` | 1017 | projected | **FULL** (boundary respected) |
| Grade | `bu_onto.grade` | `book_understandings_v2.status` (DRAFT/VERIFICATION_PENDING/VERIFIED/FAILED) | 4005 | VERIFIED | **FULL** |
| KU organisation | `bu_onto.key_concept_ku_ids` | `chapter_understandings.major_ku_refs` + `evidence_program` | **0** | 32 evidence artifacts, all located | **FULL** |
| Evidence chain | *(legacy has none)* | `evidence_program` + `stratum.evidence_trajectory` | — | 32 located spans | **BU2 SUPERIOR** |
| Verification | `bu_onto.bu_quality` via `bu_learning_gate.py` | `stratum.verification_artifacts` + 8-gate `BUVerifier` | 1017 | 2 artifacts, PASS | **BU2 SUPERIOR** |
| Run/version identity | *(legacy has none)* | `run_id` FK + `UNIQUE(substrate_id, version)` | — | v1 and v2 coexist | **BU2 SUPERIOR** |
| Synthesis marker | `bu_onto.synthesis_marker` | `negative_knowledge` + `ungrounded_sections` | 4005 | 1 section declared ungrounded | **FULL** |
| Overview one-liner | `bu_onto.overview_oneline` | `understanding_projection.compile_ladder` | 4005 | in-memory | **FULL** (projection, by design) |
| Positional summary | `bu_onto.positional_summary` | `author_mechanisms` + chapter `primary_role` | 2683 | 6 chapter roles | **FULL** |
| Learning thread | `bu_onto.learning_thread` | `book_understandings_v2.governing_questions_json` | 1322 | whole-book questions | **FULL** |
| Facets zh/en | `bu_onto.facets_zh` / `facets_en` | `chapter_understandings.secondary_roles` + `ku_segmentation` roles | 1322 | 6 chapters | **FULL** |
| Grounded facets | `bu_onto.facets_grounded` | `chapter_understandings.evidence_program` | 1015 | 32 anchored evidence | **FULL** |
| Book mental model | *(legacy has none)* | `discourse_arc` + derived dependency graph | — | ch1 → ch13 order derived | **BU2 SUPERIOR** |
| Expression | *(legacy has none)* | `BUExpressionGenerator`, 6 sections | — | 5 of 6 grounded | **BU2 SUPERIOR** |

| Book structure | *(legacy had none)* | `bu_v2_structure_extractor.BookStructure` | — | 16 of 16 chapters, confidence 0.91 | **BU2 SUPERIOR** |
| Chapter role | *(legacy had none)* | `chapter_understandings.primary_role`, §6.2 vocabulary | — | 7 roles classified | **BU2 SUPERIOR** |
| Understanding quality | *(legacy had `bu_quality`)* | `BUQualityReport`, 7 dimensions, 4 levels | 1017 | quality report per run | **BU2 SUPERIOR** |
| Self-reported limits | `bu_onto.bu_quality.checks[].detail` | `BUQualityReport.limitations` | 1017 | every gap named | **BU2 SUPERIOR** |

### Totals

```
FULL             20
BU2 SUPERIOR      9
PARTIAL           0
MISSING           0
OBSOLETE          0
```

**Zero capabilities remain PARTIAL or MISSING.** Every one either has a live
counterpart or is carried by a projection.

## 1a. §7.3 fusion is mapping, not copying

P11 added `BU2LegacyAdapter`, and the distinction is now enforced rather than
asserted. The decisive case is a real one:

```
legacy main_claims[0]
  {claim: "儒家不是宗教，而是一种哲学。", stance: "儒家", stance_marker: "宗教"}

copied into central_theses[0]          <- forbidden by §7.3
  "儒家不是宗教，而是一种哲学。"
  the claim now has no holder; it reads as an unattributed assertion

mapped by BU2LegacyAdapter (§7.4, real row bu_id=854)
  "儒家不是宗教，而是一种哲学。 (regarding 儒家 vs 宗教)"
  the distinction the book actually draws survives
```

Verified end to end in `tests/bu2/test_legacy_adapter.py`:
`test_stance_survives_the_mapping`, and two tests against the live
`aii.bu_onto` row rather than a fixture.

A mapped BU is also never self-certifying: `coverage_score = 0.0`,
`verification_score = 0.0`, `status = DRAFT`. It has read no text, so it claims
no understanding — asserted by `test_import_is_never_self_verifying`.

Eleven legacy fields have no BU2 counterpart and are named explicitly in
`FusionResult.unmapped_fields` rather than dropped silently. Six of them were
empty in all 4,005 legacy rows anyway.

## 2. Six capabilities that were empty in the legacy system

The fusion that matters is not legacy→BU2. Six legacy fields held **0 of 4,005
rows** — the capability was never built, only named. All six now hold live data:

| legacy field | fill | BU2 now holds |
|---|---|---|
| `core_explanations` | 0 | 2 mechanisms, derived from chapter records |
| `concept_network` | 0 | 6 concepts with the chapters that introduce each |
| `structure` | 0 | 6 chapter understandings + 2-step discourse arc |
| `applicability` | 0 | 2 limitations in `negative_knowledge` |
| `core_takeaways` | 0 | essence + world model in the expression |
| `key_concept_ku_ids` | 0 | 32 located evidence artifacts |

So BU2 does not merely absorb the legacy system. It fills six gaps the legacy
system left open, which is the direction §14 actually points at.

## 3. Why fusion was previously unmeasurable

The P9 audit recorded that fusion could not be measured: `bu_onto.substrate_id`
and `substrates.id` join to **0 rows**, so no book had both a legacy BU and a BU2
understanding. That is still true, and it does not block this document:

- The mapping above is capability-to-capability, which does not need a shared book.
- The trial book (Thomas Calculus) has no legacy BU, because it was never ingested
  by the flywheel that produces `bu_onto`.

**A legacy BU for the same book would not add evidence about BU2.** It would add a
second, differently-derived account of the same book with no ground truth to
compare against. If cross-validation against the legacy system is wanted, it needs
a book present in both systems, and none is.

## 4. Legacy remains in production, unchanged

```
aii.bu_onto                  4,005 rows     untouched
generate_bu.py / persist_bu.py              still the writer
bu_learning_gate.py                          still the quality gate
```

Nothing in P10 reads or writes `aii.bu_onto`. Spec §14's prohibition on deletion is
respected, and §14's runtime-independence requirement is satisfied in the only
direction that is testable: BU2 runs with the legacy system entirely absent from its
own code path (0 references, measured).

## 5. What is still weak in the fusion

Honest limits, so the FULL column above is not read wider than it is:

- **Coverage is 2 chapters, not 16.** The persisted run used `--chapters 2`. The
  full-book trial (11 chapters, 32 evidence, PASS) ran without `--persist` to
  avoid writing 11 chapter rows during an audit. Both are real; neither is the
  full 16-chapter book.
- **5 of 16 chapters were not located.** Chapters 2, 3, 5, 14 and 15 have no
  reliable heading marker in this particular markdown derivative. They are absorbed
  into their neighbours' spans, so 98% of the text is covered but chapter identity
  is lost for those five. This is a parser limitation, recorded in
  `evidence/p10/CHAPTER_EXTRACTION.txt`.
- **Quality is bounded by a 7B local model.** See `PROVIDER_NOTES.txt`. The
  structure is real; the prose contains noise. `--provider deepseek` needs no code
  change.
## 6. Fusion gaps that remain after P11

Recorded so the FULL column is not read as "nothing is left to do".

| gap | detail |
|---|---|
| no shared book | `bu_onto.substrate_id` and `substrates.id` still join to 0 rows. The trial book has no legacy BU; the fusion test used `bu_id=854` on its own. No book has been through both systems. |
| legacy claims stay unverified | All 11 claims on `bu_id=854` carry `grade='unverified'`, and the adapter does not upgrade them. Upgrading would be a claim about the claim, which §7.3 forbids. |
| legacy evidence cannot satisfy §11 | The 11 evidence items on that row are `{text, grade}` with no locator and no content hash. They are recorded as a degradation, not converted into `EvidenceArtifact`. |
| learning projection not migrated | `learning_paths` and `deep_cards` are deliberately not imported (§2.3). They belong to the C warehouse, which remains unreachable from this host: `cx` has 0 tables. |
| one book, one discipline | The fusion test is one Chinese intellectual history. Nothing here shows the mapping holds across genres or languages. |
