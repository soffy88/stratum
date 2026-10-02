# BU2_QUALITY_MODEL

Spec: `BU2_P11_UNDERSTANDING_QUALITY_UPGRADE_SPEC` §8, §9, §10, §11, §12. Date: 2026-10-02.

## 1. What this model measures, and what it refuses to

§8 is unambiguous:

> 评价不是事实真假, 而是 understanding completeness

So every dimension here asks whether a part of understanding is **present,
traceable and derived**. None of them asks whether a claim is true. That is not
a limitation worked around; it is the design, and it is what makes §10's
separation possible.

Concretely, the model will report that "6 of 32 claims carry a source locator".
It will never report that "the book's claims are 94% accurate", because nothing
in the pipeline could establish that, and a number implying it would be
fabricated precision.

## 2. The separation §10 requires

```
VerificationReport    "did the pipeline do its job"      PASS / FAIL / BLOCKED
BUQualityReport       "how much did it understand"       A / B / C / D
```

These are different objects, computed by different modules, and neither reads the
other's output to decide anything:

| | `bu_v2_verifier.py` | `bu_v2_quality_evaluator.py` |
|---|---|---|
| question | are the required artifacts present and consistent? | how much of the book did we actually understand? |
| outcome | PASS / FAIL / BLOCKED | A / B / C / D |
| can block publication | **yes** | **no** (§11) |
| writes a BU status | **yes** | **no** |
| knows about truth | no | no |

A run is routinely pipeline-PASS at quality-C. Both facts are reported side by
side in every report, in those words, because a green tick next to a quality
score is exactly how "the book was understood" comes to be inferred.

**§11 forbids quality from blocking publication.** This is enforced structurally:
`BUQualityEvaluator.evaluate()` returns a report and has no write path, no status
parameter and no raise. `test_low_quality_still_verifies` asserts that a
deliberately shallow understanding still verifies PASS.

## 3. The seven dimensions

Each score is a weighted sum of sub-measures in `[0,1]`. Sub-measures are stated
so a score can be argued with rather than merely read.

### Q1 Structure — coverage, hierarchy, dependency

```
0.6 × (chapters located ÷ chapters the parser index declares)
+ 0.4 × mean boundary confidence
```

The denominator is what the book declares it has, not what we happened to find —
otherwise the score is 100% whenever the detector and the detector agree.

### Q2 Concept — extraction, relationship, evolution

```
0.40 × min(1, concepts introduced ÷ 20)      extraction happened
+ 0.35 × min(1, book concepts ÷ 10)           concepts persisted to book level
+ 0.25 × min(1, evolution steps ÷ 8)          something was seen again
```

The third term is what distinguishes a concept list from an understanding: a
concept that appears in two chapters becomes two versions of one object.

### Q3 Mechanism — causal explanations and processes

```
0.45 × (chapters recording a mechanism ÷ chapters)    coverage
+ 0.30 × min(1, chapter mechanisms ÷ 15)              volume
+ 0.25 × min(1, book-level mechanisms ÷ 3)            carried upward
```

### Q4 Argument — claims, evidence, reasoning

```
0.30 × central thesis present
+ 0.25 × supporting structure present
+ 0.45 × claims linked to evidence
```

Heaviest on the third term: an argument is claims with support, not claims.

### Q5 Integration — the §10.4 test, made evaluative

```
0.30 × cross-chapter relations ÷ (chapters − 1)
+ 0.20 × discourse arc steps ÷ chapters
+ 0.20 × concept evolution ÷ 8
+ 0.30 × book-level framing present
```

This is the dimension that answers "is this a model of the book or a collection
of chapter summaries". A concatenation scores near zero on the first term
because it never compares chapters, and on the last because it produces
N book-level claims rather than a few.

### Q6 Evidence — traceability, not correctness

```
0.40 × artifacts carrying a locator
+ 0.30 × artifacts carrying a quote
+ 0.30 × min(1, artifacts referenced by an evidence program ÷ artifacts)
```

Zero evidence scores zero, and the report says so in words: *"nothing in this
understanding is traceable to source text."*

### Q7 Boundary — does the understanding know what it does not know

```
0.30 × limitations + open problems stated
+ 0.25 × unresolved questions recorded
+ 0.25 × chapters recording a qualification or assumption
+ 0.20 × honesty about chapters that failed
```

The honesty term rewards recording a chapter that could not be understood. A
system that hides its failures scores lower, deliberately.

## 4. Levels

```
overall = Σ(score × weight) / Σ(weight)      all weights are 1.0

A  ≥ 0.80   comprehensive: structure, concept, mechanism, argument, boundary all present
B  ≥ 0.65   substantial: the book's spine is understood, with identifiable gaps
C  ≥ 0.45   partial: some structure or concept, but the argument is not reconstructed
D  < 0.45   minimal: the book was located but not meaningfully understood
```

Letters rather than numbers because a reader of a report should not have to look
up what "quality 3" means.

## 5. What a level is not

`quality_level: A` means the understanding is *comprehensive in coverage*. It does
not mean the book was understood correctly, and it does not mean the extraction
was faithful to the author's intent. Both would require ground truth this system
does not have.

The wording used everywhere a level is displayed is **understanding confidence**,
never "truth", "accuracy" or "correctness". `test_quality_context_is_confidence_not_truth`
asserts those words are absent.

## 6. Measured on the real book

Thomas Calculus 14th ed, 5,135,239 characters, local `qwen2.5:7b`, 16 chapters.
Full numbers in `BU2_QUALITY_REPORT.md` and `evidence/p10/p11_run.json`.

The dimension that matters most here is Q6, and its limit is worth stating plainly:
**traceability is not faithfulness.** Every one of the 32 evidence artifacts in
the trial points at a real character offset in the book. Whether the claim
attached to that offset is a fair reading of the surrounding text is a different
question, and this model does not answer it. That is the honest boundary of §8.