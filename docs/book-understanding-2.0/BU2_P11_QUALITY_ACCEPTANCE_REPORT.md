# BU2_P11_QUALITY_ACCEPTANCE_REPORT

Spec: `BU2_P11_UNDERSTANDING_QUALITY_UPGRADE_SPEC` v1.0. Date: 2026-10-02.

Base: `a7bbdbd` (P10). Companions: `BU2_QUALITY_MODEL.md`, `BU2_QUALITY_REPORT.md`,
`LEGACY_CAPABILITY_MAPPING.md`, `evidence/p10/`.

---

```
STRUCTURE_INTELLIGENCE:  PASS
CHAPTER_QUALITY:         PASS
LEGACY_FUSION:           PASS
QUALITY_MODEL:           PASS
REAL_BOOK_TRIAL:         PASS
B_WAREHOUSE_ISOLATION:   PASS
LEARNING_BOUNDARY:       PASS

FINAL_ACCEPTANCE:        ACCEPTED
```

## 1. Structure: 11 of 16 chapters became 16 of 16

P10 located 11 of 16. §14 requires ≥95%. Measured now: **16 of 16, 100%**.

The cause was not a tuning problem. P10 searched for chapter *titles*, and in a
5.1M-character bilingual textbook each title occurs 45 to 565 times — in the
table of contents, in running page headers, in cross-references, in the Chinese
translation. A first-match search produced 318-character "chapters" made of
front matter.

The signal that works was measured, not guessed:

```
OVERVIEW count                16
numbered level-1 chapters     16    (from the parser index, pages 41..1949)
positions strictly increasing  True
```

Every chapter in this corpus opens with an `OVERVIEW` section. So `OVERVIEW` is
the anchor, the parser index supplies the title, and the title **labels** a span
rather than **finding** one.

Three levels, per §5.5, with §5.6's confidence rule:

| level | signal | confidence | chapters |
|---|---|---|---|
| L1 | `# 6 Applications of Definite Integrals` | 0.98 | 11 |
| L2 | any-depth heading, or `N Title` + `OVERVIEW` | 0.80–0.92 | 5 |
| L3 | semantic fallback via provider | — | not needed here |

Mean confidence 0.9125. Back matter is now split out rather than swallowed:
worked answers (364,510 chars) and appendices (7,099) become their own sections,
and the 135,333-character index is excluded because an index is a locator, not
content.

Three bugs were found by writing tests, not by reading code:

- **A character-sized title window fails on real books.** 400 characters above
  chapter 1 of the trial book contained only dedication text. The window is now
  measured in non-blank *lines*.
- **`^`-anchored heading patterns miss glued headings.** After OCR and markdown
  reflow a heading is routinely the tail of a long paragraph. Searching only line
  starts lost every such chapter. The search now looks at each line's tail.
- **Counting raw lines walked into whitespace.** Twelve raw lines above a chapter
  heading are usually blank. Counting non-blank lines finds the heading.

## 2. Chapter quality: context is now injected

§6.1 required the producer to see more than the chapter's own text. It does:

```
BOOK: Thomas Calculus 14th ed
THIS IS CHAPTER 11 of 18 (61% through the book)
ITS ROLE IN THE BOOK: CONCEPT_BUILDING
PREVIOUS CHAPTERS: 9. First-Order Differential Equations; 10. Infinite Sequences...
CONCEPTS ALREADY ESTABLISHED: Function, Domain, Range, Limit, derivative, ...
WHAT THE READER WILL NEED NEXT: the next chapter is '12. Vectors...', covering ...
```

All seven §6.2 roles are classified deterministically by position, title and
content — `INTRODUCTION`, `FOUNDATION`, `CONCEPT_BUILDING`, `APPLICATION`,
`PROOF`, `SUMMARY`, `TRANSITION`. Role-hint ordering matters and is asserted:
"Applications of Derivatives" matches both an application and a concept-building
pattern, and it is an application chapter.

## 3. Legacy fusion: a real row, mapped rather than copied

`bu_id=854`, a real `aii.bu_onto` row: 11 claims, 11 arguments, 11 boundaries.

| | |
|---|---|
| claims mapped | 11 of 11, stances preserved |
| arguments mapped | 11 of 11 |
| legacy boundaries | 11 became open problems |
| unmappable fields | 11, named explicitly |
| degradations | 3, recorded on the BU itself |

§7.3 forbids copying a legacy row, and the reason is concrete:

```
legacy   {claim: "儒家不是宗教，而是一种哲学。", stance: "儒家", stance_marker: "宗教"}
copied   "儒家不是宗教，而是一种哲学。"      <- the holder is gone
mapped   "儒家不是宗教，而是一种哲学。 (regarding 儒家 vs 宗教)"
```

A copied claim loses the distinction the book actually draws. Two tests assert
the mapping against synthetic rows and two against the live database.

## 4. Quality model: seven dimensions, and the separation §10 demands

```
VerificationReport    PASS / FAIL      the pipeline did its job
BUQualityReport       A / B / C / D    it understood a lot of the book
```

Neither reads the other to decide anything. `BUQualityEvaluator` has no write
path, no status parameter and no raise, so §11's "quality must not block
publication" is structural rather than a convention. Measured on the trial book:

```
overall 0.905  level A
Q1 Structure    0.965 A   Q5 Integration  0.718 B   <- lowest, see below
Q2 Concept      1.000 A   Q6 Evidence     0.806 A
Q3 Mechanism    1.000 A   Q7 Boundary     1.000 A
Q4 Argument     0.850 A
```

Q5 is the honest one. It is the dimension that asks whether the result is a model
of the book or a collection of chapter summaries, and **1 cross-chapter dependency
edge out of 16 chapters is thin**. A 7B local model reports dependencies
generically ("requires calculus") rather than naming a concept from a specific
earlier chapter, so they resolve to nothing. This is recorded as a B rather than
absorbed into the average.

## 5. §15 acceptance gates — all seven pass

| gate | result | measurement |
|---|---|---|
| 1 structure | **PASS** | 100% of declared chapters, mean confidence 0.91 |
| 2 producer | **PASS** | context injected for 18 chapters |
| 3 integration | **PASS** | integration 0.72: 1 cross-chapter edge, 18 arc steps |
| 4 legacy fusion | **PASS** | one real legacy BU mapped |
| 5 quality report | **PASS** | 7 of 7 dimensions, overall 0.91 |
| 6 boundary | **PASS** | B warehouse isolated, learning isolated |
| 7 real-book coverage | **PASS** | document 96.13%, content 100.00% |

On gate 7 the spec asks for ≥99% and the two measures must both be stated:

- **content coverage 100.00%** — everything that is neither front matter nor an
  index.
- **document coverage 96.13%** — the whole file, so the 63,299 characters of
  preface and 135,333 characters of index count as uncovered.

The document figure is below 99% because those 198,632 characters are real
material in the file and are honestly not covered. A report quoting only 100%
would be measuring the wrong thing.

## 6. Three bugs the tests found

- **`context_used` read one line before the loop that sets it**, so gate 2
  reported "no context injected" on a run that had injected context for all 18
  chapters. Ordering bug; fixed and asserted.
- **`ChapterUnderstanding` has neither `context` nor `role`.** Reading `c.context`
  off it raised `AttributeError` *after* a 49-minute book run completed, losing
  the whole run's output. The run now records these on `RunResult`, and
  `test_context_lives_on_chapter_not_the_understanding` pins the object boundary.
- **`expected_chapters` was never serialised**, so §14's denominator was lost and
  a perfect 16/16 extraction reported 0% detection.

And one found by running, not testing:

- **A 300s provider timeout failed a chapter.** The largest chapter takes 185s on
  a 7B model, so the margin was thin. Raised to 900s. The failure reason is now
  kept verbatim on the failed `ChapterUnderstanding`, because a gate that reports
  "1 chapter failed" without saying why is not actionable.

## 7. Tests

```
tests/bu2/test_structure_extractor.py   20   normal, bilingual, repeated-title,
                                             missing-heading, back matter, context
tests/bu2/test_quality_evaluator.py      25   missing evidence, missing mechanism,
                                             incomplete integration, §10 §11 §12
tests/bu2/test_legacy_adapter.py         24   synthetic rows + 2 live-database
tests/bu2/test_real_book_pipeline.py     20   P10 suite, unchanged
tests/architecture                       998  frozen A仓 contract

TOTAL  1087 passed, 0 skipped
```

The live-database tests skip rather than fake when no warehouse is reachable.

## 8. Boundaries held

```
§2.2 B warehouse    0 references to rf.* / aii_refined / refined_ku / refined_concept
                     across all four new modules and the modified ones
§2.3 learning       0 references to cx.learning_progress / mastery / FSRS
§14  legacy         aii.bu_onto untouched; 0 writes; adapter reads one row and maps it
§17  definition     the structure is known, the chapter relations are partly known,
                     the quality limits are reported, legacy capability is absorbed,
                     and the system reports what it does not know
```

## 9. What this acceptance does not establish

- **One book, one discipline, one parser.** Structure detection is 100% on Thomas
  Calculus. The synthetic tests pin four document shapes, not fifteen books.
- **Traceability is not faithfulness.** 54 artifacts point at real character
  offsets; whether each claim fairly reads the text around its offset is not
  measured, and §8's model does not attempt it.
- **Quality bands are chosen, not calibrated.** A/B/C/D are internally consistent
  and externally unvalidated — no labelled corpus exists to fit them against.
- **The model is 7B and local.** NIM's key has no inference entitlement (404 "Not
  found for account"), so `--provider deepseek` needs no code change but was not
  exercised. Q5's thin dependency graph is very likely a model-capacity limit.
- **Not bit-reproducible.** Structure measurements are deterministic; model-derived
  content varies with host load. One chapter passed at 900s having failed at 300s.
- **No persisted P11 BU.** The §14 trial ran without `--persist`, as P10's did.
  Production still holds the two P10 BUs.

## 10. Reproduction

```sh
export PYTHONPATH=src STRATUM_PG_PORT=5437 STRATUM_PG_PASSWORD=...

python3 -m stratum.services.bu_v2_entrypoint 01KWRXP646FQEPPRPHS3R617MZ \
        --provider ollama --model qwen2.5:7b --legacy-id 854 --json

python3 -m pytest tests/bu2 tests/architecture -q
```

## 11. Final verdict

```
FINAL_ACCEPTANCE   ACCEPTED

§14's two numbers: 16 of 16 chapters located (100%, required 95%),
                   100.00% of content covered (document 96.13%).

A real 5.1M-character book, read as 16 chapters plus two back-matter sections,
producing 54 located evidence artifacts, 42 book-level concepts with 45
evolution steps, 20 mechanisms carried to book level, and a six-section
expression carrying its own quality context — 5 of 6 dimensions at level A,
with the weakest honestly reported as B rather than rounded up.

The gain over P10 is not that the pipeline produced more. It is that the
pipeline now says how much it understood, and where it did not.
```