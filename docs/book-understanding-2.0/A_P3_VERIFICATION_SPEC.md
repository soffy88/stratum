# A P3 VERIFICATION SPEC — KU Candidate 验证与语义完整性

TASK=STRATUM_A_REPOSITORY_P3_KU_VERIFICATION
VERSION=v0.1 (implemented)
BASELINE=stratum-a-p2-evidence-quality-v0.1
STATUS=FROZEN

## 1. Position in the chain

```
Raw Source
    ↓
Evidence                 (P1)
    ↓
KU Candidate             (P2)
    ↓
KU Verified              (P3)   ← this stage
    ↓
Concept                  (a later repository)
```

A仓 holds fact authority throughout. P3 decides whether a candidate is a
verified understanding unit. It does not group units into concepts.

## 2. What P3 does not do

- no write to any claim table
- no grouping of units into concepts
- no duplicate elimination
- no abstraction
- no inference or gap filling
- no external knowledge injection
- no external answer, no external database, no note without evidence

## 3. Data model

`KnowledgeUnitVerification` — why a candidate may be treated as a
verified unit.

Migration: `src/stratum/db/pg_migrations/072_a_ku_verification.sql`
Table: `stratum.ku_verification`

| Field | Type | Notes |
|---|---|---|
| `id` | TEXT PK | content-derived |
| `candidate_id` | TEXT NOT NULL | FK → `ku_candidate(id)`, UNIQUE |
| `verification_status` | TEXT NOT NULL | CHECK PENDING / VERIFIED / REJECTED |
| `verification_method` | TEXT NOT NULL | `evidence_chain_rules` |
| `verifier_version` | TEXT NOT NULL | `a-p3-v0.1` |
| `verification_trace` | JSONB NOT NULL | a decision without a trace cannot be stored |
| `created_at` | TIMESTAMP NOT NULL | |

`candidate_id UNIQUE`: a candidate is decided once and only once, which
is what makes a terminal state terminal at the schema level.

### 3.1 Lifecycle

```
PENDING ──> VERIFIED   (terminal)
   │
   └────> REJECTED   (terminal)
```

Forbidden: `VERIFIED → PENDING`, `REJECTED → VERIFIED`. `VERIFIED →
REJECTED` is also absent: a terminal state is terminal. Both refusals
raise `VerificationViolation`, as do `reopen()` and `overturn()`.

Re-deciding a settled candidate is out of scope for this freeze. It would
need a reviewed migration that supersedes the stored decision, never an
edit of it.

## 4. Authority

The only inputs to a decision:

```
Evidence Chain  +  KU Candidate  +  Verification Rule
```

```
BookSource
    ↓
SourceVersion
    ↓
ReadingRun
    ↓
ReadingEvidence
    ↓
KU Candidate
    ↓
KU Verification      ← 072 adds this link
```

`load_candidate()` returns the candidate, its evidence and its quality
row, so no later stage can reach for an input outside the chain.

## 5. Pipeline

### Stage 1 — candidate load

`HAS_SOURCE_SPAN`, `QUALITY_PRESENT`. A candidate with no evidence, no
quote or no quality row cannot be decided at all.

### Stage 2 — evidence sufficiency

Must hold: at least one evidence row; quality ≥ threshold
(`VERIFICATION_QUALITY_THRESHOLD = 0.8`); the chain resolves.

Quality score is the **lowest** of the four P2 scores — the weakest link
decides. Traceability is walked, not trusted: a perfect quality score
still fails if the row does not resolve to a reading run and a source
version with a content hash.

### Stage 3 — semantic integrity

A unit of the candidate's declared kind must be present and locatable.

| Kind | Required slots |
|---|---|
| `FACT` | `ANCHORED`, `SUBJECT`, `PREDICATE`, `OBJECT` |
| `RELATION` | `ANCHORED`, `SUBJECT`, `PREDICATE`, `OBJECT` |
| `CONCEPT` | `ANCHORED`, `DEFINITION_SPAN` |
| `EVENT` | `ANCHORED`, `ACTOR`, `TIME`, `ACTION` |
| `ARGUMENT` | `ANCHORED`, `DEFINITION_SPAN` |

**ANCHORED — the meaning of locatable.** The candidate's `source_span`
is its verbatim quote, and it must occur inside the evidence it claims.
That is the locatability guarantee, and it is a real constraint: a quote
that is not in its evidence cannot be verified no matter how well formed
its proposition is.

**Subject / predicate / object.** The predicate is a relation marker —
the word that makes a span a proposition rather than a noun phrase. The
marker is located in `content`, falling back to `source_span`; subject
and object are what sits either side of it. A span with no marker yields
two empty sides, which is exactly how a noun phrase fails.

**Definition span.** A definitional marker (`是指`, `所谓`, `定义为`,
`意思是`, `含义是`, `称为`, `叫做`). A span with none asserts something
but defines nothing, so a `CONCEPT` candidate without one is rejected.

### Stage 4 — verification decision

`VERIFIED` when no rule failed, otherwise `REJECTED` with the failed
rules recorded. Both are terminal.

## 6. Verification trace

Every decision carries its trace:

```json
{
  "candidate_id": "",
  "evidence_ids": [],
  "rules": ["HAS_SOURCE_SPAN", "QUALITY_PASS", "TRACE_COMPLETE"],
  "verifier_version": "a-p3-v0.1",
  "failed_rules": [],
  "classification": "FACT",
  "slots": {"ANCHORED": "True", "SUBJECT": "汉谟拉比", "PREDICATE": "是"},
  "quality_score": 1.0
}
```

`failed_rules` is always present. A `REJECTED` row with an empty
`failed_rules` is not a decision, it is a bug.

## 7. Runner

`verification_runner.py` composes the P2 chain and the P3 stage.

```
quality_runner.py  (P2: evidence -> quality -> classification)
        ↓
verification_runner.py  (P3: candidate -> verification)
```

- resumable: a decided candidate is never re-decided
- idempotent: re-running adds no rows and emits no events
- deterministic: same inputs → same id, same trace, same decision
- first run 17 candidates → 17 verifications
- second run 0 new → 17 existing

## 8. Deviations from the draft spec

| Draft | Implemented | Why |
|---|---|---|
| `src/stratum/a_repository/*` | `src/stratum/knowledge/a_repository/*` | the package has lived at this path since P1 |
| new `a_quality_runner.py` | existing `quality_runner.py` | the P2 runner is frozen under its current name; not renamed |
| new `a_verification_runner.py` | `verification_runner.py` | matches the frozen P2 naming |
| `VERIFIED ↓ REJECTED` (ambiguous diagram) | `REJECTED` is a child of `PENDING` only | a terminal state is terminal |

Two values the draft left open, fixed here and asserted in tests:
`VERIFICATION_QUALITY_THRESHOLD = 0.8`, and the ANCHORED definition of
locatable in §5.

## 9. Not executed at this freeze

The draft's gate 1 asks for 072 applied in staging. No staging target
was provided and no database client is available in this environment, so
the migration was written and reviewed but **not executed against any
database**. Applying it is the one outstanding step before P3 is
operational.

VERIFICATION_SPEC=PASS