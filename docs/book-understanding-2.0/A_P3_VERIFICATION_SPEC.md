# A P3 VERIFICATION SPEC — KU Verification 执行版

TASK=STRATUM_A_REPOSITORY_P3_KNOWLEDGE_UNIT_VERIFICATION
AUTHORITY=A_REPOSITORY_ONLY
BASELINE=stratum-a-p2-evidence-quality-v0.1 (5fd748e)
STATUS=FROZEN

## 1. Position

```
Raw Source → Evidence → KU Candidate → KU Verification → Verified KU
                          (P1)         (P2)          (P3)
```

A candidate never flows straight to another repository's claim table. P3
sits between them and produces no data outside A仓.

## 2. Authority boundary

A仓 owns: `book_source`, `source_version`, `reading_run`,
`reading_evidence`, `ku_candidate`, `ku_verification`.

A仓 depends on nothing else. No claim table, no other repository, no
learning object, no graph.

```
Evidence > Candidate > Verification
```

A verdict never outranks its evidence. A human never overrides evidence.
Nothing automatically combines candidates. The decision is the product of
the candidate, its evidence chain and the four recorded checks.

## 3. Migration

`072_a_ku_verification.sql` — **CREATED and APPLIED to staging.**

| Column | Type |
|---|---|
| `id` | TEXT PK |
| `candidate_id` | TEXT NOT NULL → `ku_candidate(id)` ON DELETE CASCADE |
| `verification_status` | TEXT NOT NULL CHECK 4 states |
| `verification_score` | FLOAT NOT NULL CHECK 0.0–1.0 |
| `definition_check` | BOOLEAN NOT NULL |
| `trace_check` | BOOLEAN NOT NULL |
| `source_check` | BOOLEAN NOT NULL |
| `quality_check` | BOOLEAN NOT NULL |
| `verified_quote` | TEXT |
| `verifier_version` | TEXT NOT NULL |
| `created_at` | TIMESTAMP NOT NULL |

`candidate_id UNIQUE`: a candidate is decided once, which is what makes a
terminal state terminal.

Indexes: `candidate_id`, `verification_status`, `created_at`.

### 3.1 GATE_1 — the database gate

Applied to a dedicated staging database `stratum_a_p3_staging` on the
`aii-postgres` instance, using the repository's own ledger:

```
docker exec aii-postgres psql -U aii -d stratum_a_p3_staging -Atc \
  "SELECT filename FROM public._pg_migrations ORDER BY filename"
```

```
070_a_repository_foundation.sql
071_a_evidence_quality.sql
072_a_ku_verification.sql
```

The staging database holds the A仓 schema only. The shared
`aii_kg` database was **not** touched: its ledger still ends at
`066_bu2_p4_p9_repair.sql`.

The runner reads that ledger from the file named by `A_P3_LEDGER_FILE`
so no credential ever reaches the verification process. Without the file
GATE_1 reports `NOT_EXECUTED` rather than `PASS`.

## 4. State machine

```
PENDING ──> VERIFYING ──> VERIFIED   (terminal)
               └───────> REJECTED   (terminal)
```

Refused: `VERIFIED → REJECTED`, `VERIFIED → PENDING`,
`REJECTED → VERIFIED`. All three raise `VerificationViolation`.
`transition()` is the only thing that changes a state; `reject_verified()`,
`reopen()` and `overturn()` exist to refuse the illegal moves explicitly.

`verify()` walks the two legal transitions in order and emits an event at
each, so the path is observable rather than implied.

## 5. Gates

### GATE_2 — candidate integrity

Every candidate must have an `evidence_id` that resolves, a
`source_span`, and a content hash reachable through its evidence.
Measured on the pilot: 17/17 traceable, 0 duplicates, 100%.

### GATE_3 — verification quality

Four scores, each the ratio of satisfied checks to required checks:

| Score | Measures |
|---|---|
| `definition_score` | satisfied required slots / required slots for the candidate's kind |
| `trace_score` | candidate → evidence → reading run |
| `source_score` | evidence → source version → addressable position |
| `quality_score` | the weakest of the four P2 scores |

```
verification_score = min(definition_score,
                         trace_score,
                         source_score,
                         quality_score)
```

`VERIFIED` requires `verification_score >= 0.8`. Each `*_check` column is
true exactly when its own score reached the threshold, so the four
booleans plus the score state the whole reason for a verdict.

Required slots per kind:

| Kind | Slots |
|---|---|
| `FACT` | ANCHORED, SUBJECT, PREDICATE, OBJECT |
| `RELATION` | ANCHORED, SUBJECT, PREDICATE, OBJECT |
| `CONCEPT` | ANCHORED, DEFINITION_SPAN |
| `EVENT` | ANCHORED, ACTOR, TIME, ACTION |
| `ARGUMENT` | ANCHORED, DEFINITION_SPAN |

**correctness outranks pass count.** A false positive is a hard failure
and is counted separately (`false_positives`).

### GATE_4 — anchor verification

`ANCHORED` means the candidate's quote occurs inside
`reading_evidence.content`. That is the whole anchoring guarantee.

A generated quote, a summary standing in for the original text, or a
paraphrase that is not a substring all fail. `verified_quote` is written
only when the quote was actually found, so an empty value is evidence that
nothing was anchored rather than an omission.

### GATE_5 — replay safety

The candidate fingerprint is a hash over source version, reading run,
evidence id, quote, content, classification and content hash. A replay over
the same inputs produces:

- 0 new candidates
- 0 new verification rows
- 0 duplicates (17 candidates, 17 unique fingerprints)
- an identical report
- 0 new events

## 6. Classification dependency

P2's classifier splits the frozen pilot 11 `FACT` / 6 `CONCEPT`, and its
marker ordering means `EVENT`, `RELATION` and `ARGUMENT` never fire. Six
of those `CONCEPT` candidates contain no definitional marker, so they score
`definition_score = 0.5` and are rejected.

**P3 does not repair this.** P3 verifies; P2 extracts. P3 does not touch
`candidate_type`, the classifier, or the lexicon — asserted by
`test_p2_classifier_and_lexicon_are_untouched`. The defect belongs to P2
and is recorded, not patched.

## 7. Artifact

`artifacts/a_repository/p3_ku_verification.json`, written by
`verification_runner.main()` — the runner's own output, not a
transcription. `test_committed_artifact_matches_the_runner` fails if the
committed file drifts from a fresh run.

## 8. Known limits of this stage

- `PREDICATE_MARKERS` / `DEFINITION_MARKERS` are a fixed vocabulary this
  stage owns; the specification supplied none. `kc_babylon_grain_rate_cap`
  is rejected because its quote `谷物贷款每年33.333%` contains no relation
  word, while `kc_babylon_silver_rate_cap` passes only because its quote
  contains `计算`. Widening the vocabulary to raise the pass count would
  make GATE_3 meaningless, so it was left as written.
- `definition_score` is a slot ratio, not a semantic judgement. It proves a
  unit is well-formed and anchored, not that it is true.
- A rejected row still stores `verified_quote` when its quote was anchored.
  Rejection and anchoring are independent: a candidate can be correctly
  quoted and still fail its definition check.

VERIFICATION_SPEC=PASS