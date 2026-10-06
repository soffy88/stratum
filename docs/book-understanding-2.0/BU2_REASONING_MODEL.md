# BU2_REASONING_MODEL

Spec: `STRATUM BU2 P12 — DEEP UNDERSTANDING & SELF-IMPROVEMENT` §1, §5–§8. Date: 2026-10-02.

## 1. The gap, measured

P11 could run a book and said how much it understood. Its lowest quality
dimension was the informative one:

```
Q5 Integration   0.72 (B)   1 cross-chapter edge, across 16 chapters
```

One edge across sixteen chapters is a collection with one tie in it. P11's
approach was to ask a 7B local model what depends on what, and that is what one
edge looks like.

## 2. The signal that was already in the book

P12 does not ask the model. The author's own cross-references are written in the
text:

```
"Here we state the general version of the rule, but postpone its proof
 until Chapter 7."                                       ch3 -> ch7
"We encountered another type of vector field in Chapter 13."   ch16 -> ch13
```

Measured on the trial text: **66 distinct explicit cross-chapter references**,
each a verbatim string at a known character offset. That is a stronger
foundation than an inference, and it is what §6 asks for — an edge with a reason
and evidence, where the author's own sentence is both.

The difference in results:

| | P11 | P12 |
|---|---|---|
| source of the relation | model inference | the author's text |
| cross-chapter edges | 1 | 29 (14 author-stated) |
| every edge has a reason | no | yes, enforced by NOT NULL |
| uncertain relations | not recorded | recorded, 36 of them |

## 3. Three layers of evidence, never conflated

| layer | what it is | strength | confidence |
|---|---|---|---|
| explicit reference | the text says "Chapter N" in a clause that states a dependence | `DIRECT` | 0.92 |
| concept recurrence | an earlier chapter's concept recurs later | `DERIVED` | 0.55 |
| document order | a chapter follows another, nothing else found | `DERIVED` | **0.21, `uncertain`** |

The third exists only so a book with no explicit cross-references still yields a
graph. It is deliberately weak and marked `uncertain`, and it is counted
separately, so it cannot be presented as an author-stated relation or quietly
used to clear §13's threshold.

## 4. §15: nothing is dropped, and nothing is invented

Both halves of the prohibition are implemented:

```
66 references found
  30 with a stated dependence or support  -> asserted as edges
  36 with the reference but no stated why -> UnresolvedRelation, status uncertain
```

An `UnresolvedRelation` carries `kind`, `subject`, `reason`, `source`,
`confidence` and `fallback`. The fallback defaults to
*"recorded as absent; no relation asserted"* — a record that says what failed
but not what happened instead is half a record.

## 5. Concept evolution is a life, not a count

P11 recorded "45 evolution steps" as a number. P12 records, per concept:

```
limit        introduced ch1 -> refined ch5 -> connected ch8, ch11, ch15
integral     introduced ch5 -> refined ch14 -> expanded, applied ch15, ch16
```

Four event kinds per §7.3 — `INTRODUCTION`, `REFINEMENT`, `EXPANSION`,
`CONNECTION` — in document order, each with a chapter and evidence where a
location exists. A concept that is introduced and never refined is reported as
static rather than counted as evolution.

## 6. Argument chains: asserted is not argued

```
CLAIM --SUPPORTS--> EVIDENCE --DERIVES--> REASONING --DERIVES--> CONCLUSION
CONCLUSION --SUMMARIZES--> CLAIM
```

A chain is emitted only with a claim, evidence and a conclusion. Two of three is
recorded as a partial chain and counted separately — "the author asserted X" is
not the same claim as "the author argued X from Y to Z".

## 7. §10/§11: still never truth, still never gating

Q8–Q11 join Q1–Q7 with the same discipline: they measure completeness, not
correctness. `DeepQualityEvaluator` has no write path and no status parameter, so
§11's "quality must not block publication" survives the addition of four more
dimensions.

The deepest limit is unchanged from P11 and worth restating: an edge pointing at
character 431,193 is traceability. Whether the claim attached to it fairly reads
the surrounding text is not measured, and §2.3 is explicit that evidence grounds a
claim rather than certifying it.

## 8. What "understanding a book's organisation" means here

Q11 asks why the book is ordered as it is, and answers from one measurable
signal: the direction of the author's references.

```
forward references   the author points ahead  -> the text was planned
backward references  the author points behind  -> the text accumulates
```

A book with 24 backward and 2 forward references reads as cumulative, and the
score says so rather than rewarding sheer edge count.
