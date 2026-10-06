# BU2_GRAPH_SCHEMA

Spec: P12 §4, §5.2, §6, §7.2, §8, §9, §11. Date: 2026-10-02.

Migration: `src/stratum/db/pg_migrations/068_bu2_p12_reasoning_graph.sql` — additive only, applied to production, verified.

## 1. Why tables and not JSON

P7 of A仓 stored a projection as JSON deliberately, to avoid a second authority.
The P12 graphs are different in kind: §13 counts relations, §15 records
uncertainty, and Q10 asks how many chapters take part. Those need to be queryable
and countable. Node and edge rows it is; the expression stays a rendering.

## 2. Reasoning graph (§5.2)

```
book_reasoning_graph     id, run_id→book_reading_run, book_id, counts, mean_confidence
reasoning_node          id, graph_id, node_type, label, chapter_id, source_ref, confidence, metadata
reasoning_edge          id, graph_id, source/target→reasoning_node, relation_type,
                        reason NOT NULL, evidence_refs, evidence_type, confidence, status
reasoning_unresolved    id, graph_id, kind, subject, reason, source, confidence, fallback
```

### Node types — CHECK-constrained

```
CHAPTER  CONCEPT  CLAIM  MECHANISM  QUESTION  EXAMPLE  CONCLUSION
```

Constrained so a typo fails the insert instead of creating a seventh kind that
no query can find.

### Edge types — CHECK-constrained

```
DEPENDS_ON  EXTENDS  REFINES  CONTRADICTS  APPLIES_TO  EXPLAINS  SUPPORTS
```

### The two constraints that carry §6 and §15

```sql
reason         TEXT NOT NULL          -- §6: an edge without a reason cannot be written
reason_type    CHECK (status IN ('asserted','uncertain','refuted'))
```

Verified against production rather than assumed:

```
INSERT ... relation_type='DEPENDS_ON'  (no reason)
ERROR: null value in column "reason" ... violates not-null constraint
```

`reasoning_unresolved` is what makes §15 auditable: a proposed relation that
evidence did not support is a row, not a gap in the data.

## 3. Concept evolution (§7.2, §7.3)

```
concept_trajectory        id, run_id, book_id, concept_label, introduced_at, final_state,
                          definition_count, change_count, application_count, confidence
                          UNIQUE(run_id, concept_label)
concept_trajectory_event  id, trajectory_id, event_type, chapter_id, detail,
                          evidence_refs, confidence, sequence
```

`event_type` is CHECK-constrained to §7.3's four kinds. `sequence` preserves
document order so a trajectory reads as a narrative rather than a set.

**`UNIQUE(run_id, concept_label)` is the §2.1 guarantee.** A concept label is
scoped to one run and one book. There is no canonical concept id and no
cross-book key, so this cannot drift into the B warehouse's `refined_concept`.

## 4. Argument graph (§8)

```
argument_graph    id, run_id, book_id, chain_count
argument_node     id, graph_id, node_type, label, chapter_id, confidence
                  CHECK node_type IN (CLAIM, EVIDENCE, REASONING, CONCLUSION)
argument_edge     id, graph_id, source/target→argument_node, relation_type, reason NOT NULL,
                  evidence_refs, confidence, chain_id
                  CHECK relation_type IN (SUPPORTS, DERIVES, CHALLENGES, SUMMARIZES)
```

Separate from the reasoning graph because a reasoning chain answers a different
question from a structural relation: "how does the author advance a thought" is
not "what needs what".

## 5. The three ids on the BU (§9)

```sql
ALTER TABLE stratum.book_understandings_v2
  ADD COLUMN reasoning_graph_id      TEXT,
  ADD COLUMN concept_evolution_id   TEXT,
  ADD COLUMN argument_graph_id      TEXT;
```

Nullable on purpose. A BU produced before P12 has NULL, which reads as "produced
before P12" rather than as corruption. Verified in production:

```
v1 reasoning=NULL evolution=NULL argument=NULL      <- P10 run
v2 ... v3 ...                                        <- P11 runs
v4 reasoning=graph_3e84d93c evolution=traj_65c8f4657 argument=agraph_7fbb3bc
```

## 6. Evidence strength (§11)

```sql
ALTER TABLE stratum.chapter_understandings
  ADD COLUMN evidence_strengths JSONB NOT NULL DEFAULT '{}'::jsonb;
```

```json
{"ev_6c7f95accf9f9ec5": "DIRECT", "ev_a1b2...": "DEFINITION"}
```

Five strengths, ranked, and bound per claim at the moment evidence is created —
not inferred later by whichever consumer happens to need it:

```
DIRECT            the model's own verbatim quote verified at a location
DEFINITION        the concept's first locatable mention
EXAMPLE           located in worked examples
DERIVED           located via a term anchor, the model having paraphrased
MODEL_INFERENCE   the weakest; explicit rather than implied
```

`chapter_understandings` gained a column; no row was rewritten.

## 7. Deletion and lifecycle

Every FK to `book_reading_run` is `ON DELETE CASCADE`: a reading run's graphs
belong to that run and go with it. Nothing cascades upward — deleting a
`reasoning_node` does not delete a BU.

## 8. What is deliberately absent

- **No global or canonical concept identity.** §2.1.
- **No edge without a reason.** §6, by NOT NULL.
- **No table for the expression.** §2 of P10: an expression is a rendering of a
  verified BU, and storing it would create a second authority.
- **No learning or mastery column.** §2.2 and §2.3.
- **No A仓 or B仓 table referenced.** 0 foreign keys leave `stratum`.
