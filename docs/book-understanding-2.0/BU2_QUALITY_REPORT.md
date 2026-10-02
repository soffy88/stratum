# BU2_QUALITY_REPORT

Spec: `BU2_P11_UNDERSTANDING_QUAL_UPGRADE_SPEC` §9. Date: 2026-10-02.

Machine-readable source: `evidence/p10/p11_run.json`.
Method: `BU2_QUALITY_MODEL.md`.

## The two numbers, kept apart

```
pipeline_status      VERIFIED     the run did what it was asked to do
quality_level        A (0.905)    it understood a lot of the book
```

These are independent and the report prints them that way. §10 forbids treating
`verification PASS` as knowledge truth, and §11 forbids quality from blocking
publication, so neither is derived from the other.

## Run

```
book        Thomas Calculus 14th ed (托马斯微积分第十四版)
substrate   01KWRXP646FQEPPRPHS3R617MZ
text        5,135,239 characters of derivative.content
provider    local ollama, qwen2.5:7b
run_id      br_01M3YE3PA9D8ZKQ9H9W95S36RK
chapters    18 located (16 numbered + worked answers + appendices)
evidence    54 artifacts, 100% carrying a locator
failures    none
```

## Dimension scores

| dim | name | score | level | detail |
|---|---|---|---|---|
| Q1 | Structure | 0.965 | **A** | 16 of 16 chapters located, mean confidence 0.91 |
| Q2 | Concept | 1.000 | **A** | 42 book concepts, 45 introduced, 45 evolution steps |
| Q3 | Mechanism | 1.000 | **A** | 20 chapter mechanisms, 20 carried to book level |
| Q4 | Argument | 0.850 | **A** | 1 root argument, 5 supporting, 19 evidenced claims |
| Q5 | Integration | 0.718 | **B** | 1 cross-chapter edge, 18 arc steps, 1 book thesis |
| Q6 | Evidence | 0.806 | **A** | 54 artifacts, 100% with a locator |
| Q7 | Boundary | 1.000 | **A** | 24 limitations, 24 open problems, 24 unresolved questions |
| | **overall** | **0.905** | **A** | comprehensive, with identifiable gaps |

## Reading the scores honestly

**Q5 is the interesting one, and it is the lowest.** It measures the thing §10.4
forbids — whether the result is a model of the book or a collection of chapter
summaries — and a single cross-chapter dependency edge out of 16 chapters is thin.
The arc has 18 steps and there are 45 concept-evolution steps, so the book was not
read as sixteen independent texts. But one prerequisite relation is close to a
collection that happens to have been ordered.

The cause is measurable rather than mysterious: a 7B local model rarely reports a
chapter's dependency on a *specific named concept from a specific earlier
chapter*. It reports dependencies generically ("requires calculus"), which do not
resolve to an earlier chapter and therefore form no edge. The integrator's loose
matching recovers some of them; a stronger model would recover more. This is
recorded as a B rather than smoothed into the average.

**Q6 at 0.806, not 1.0.** Every artifact carries a locator, but not every one is
referenced by a chapter's evidence program, so the third sub-measure is
unsaturated. That is a bookkeeping gap in the producer, not a traceability
failure.

**Q1 at 0.965, not 1.0.** All 16 chapters were located, but five of them fell back
to the parser index for their title (confidence 0.80) because their heading number
survives only inside OCR picture-text blocks. Mean confidence 0.91.

## Legacy fusion on the same run

```
legacy_id    854  (aii.bu_onto, substrate misc_zh_a98b36503c)
claims       11 of 11 mapped, stances preserved
arguments    11 of 11 mapped, 11 boundaries became open problems
unmappable   11 legacy fields named explicitly
degradations 3 recorded on the BU itself
```

The mapping is not a copy. The decisive case:

```
legacy   {claim: "儒家不是宗教，而是一种哲学。", stance: "儒家", stance_marker: "宗教"}
BU2      "儒家不是宗教，而是一种哲学。 (regarding 儒家 vs 宗教)"
```

A copy would drop the holder and turn a distinction the book draws into an
unattributed sentence. See `LEGACY_CAPABILITY_MAPPING.md` §1a.

The mapped BU carries `coverage_score = 0.0`, `verification_score = 0.0`,
`status = DRAFT`. It has read no text, so it claims no understanding, and its
quality report scores Q6 at zero.

## What this report does not say

- **Not that the book was understood correctly.** 54 artifacts point at real
  character offsets. Whether each claim is a fair reading of the text around its
  offset is a different question, and §8's model does not answer it. Traceability
  is not faithfulness.
- **Not that structure detection is proven.** 16 of 16 on one book, one
  discipline, one parser. `test_structure_extractor.py` pins the detector against
  synthetic normal, bilingual, repeated-title and missing-heading books; that is
  four shapes, not fifteen.
- **Not that quality is calibrated.** The bands A/B/C/D are chosen, not fitted to
  a labelled corpus. They are internally consistent and externally unvalidated.
- **Not that the run is reproducible bit-for-bit.** A local 7B model at
  temperature 0 still varies with host load; one chapter timed out at a 300s
  timeout in an earlier run and passed at 900s. The structure measurements are
  deterministic; the model-derived content is not.