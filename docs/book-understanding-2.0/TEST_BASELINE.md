# TEST BASELINE

## A仓 Baseline (STRATUM_A)

Last updated at commit `6265038`, tag `stratum-a-p5-freeze`.

### Frozen database anchor

All figures are **row counts**. `knowledge_unit` has 10 indexes and 11 rows;
that distinction was once recorded backwards in a freeze record and is called
out here so it is not repeated.

```
migrations                        = 13   (newest 082_a_paper_evidence_composite_fk.sql)
knowledge_unit       ROWS         = 11
ku_freeze_event      ROWS         = 12
ku_revision          ROWS         =  1
ku_identity          ROWS         = 11

BASELINE_ANCHOR                   = 11/12/1/11
```

The anchor has not moved across 075..082. Any stage that changes it is a
regression, not progress.

### Migration chain and fingerprints

The complete A仓 chain, 070–082. 070–074 were committed with P1–P4.1; 075–082
arrived with the P5 extension at `6265038`. First 16 hex characters of each
file's SHA-256:

```
070_a_repository_foundation.sql     179e9e26c17f13e6
071_a_evidence_quality.sql          6116f929ff5976a5
072_a_ku_verification.sql           7a210f1130389037
073_a_knowledge_unit_freeze.sql     4285c1be7a6c4a0c
074_a_ku_freeze_persistence.sql     9d3651f35668ddd3
075_a_ku_evolution.sql              b29432e8340faedc
076_a_ku_identity.sql               2b9de6b42e1c1d87
077_a_condition_boundary.sql        fe4d613f5bb95508
078_a_mechanism_chain.sql           ed963f7e82854b04
079_a_relation_candidate.sql        58910b307ea79b1f
080_a_paper_source.sql              6215e46078709bc8
081_a_constraint_candidate.sql      0e9ebc2ddc443412
082_a_paper_evidence_composite_fk.sql db3aa8f3f7673c20
```

Recompute the whole set with:

```
sha256sum src/stratum/db/pg_migrations/0[78]*.sql
```

### A仓 architecture tests

Working tree, all files green:

```
test_a_repository_p4_1_persistence      55
test_a_repository_p5_evolution         116
test_a_condition_boundary_contract      86
test_a_mechanism_authority              45
test_a_relation_authority               50
test_a_paper_authority                 58
test_a_constraint_authority            52
test_a_paper_evidence_fk_repair        27
test_a_repository_p6_identity          95
test_a_repository_p7_projection        71
```

```
tests/architecture   943 passed, 6 skipped
```

From a **fresh checkout of the tagged commit** — 498 passed, 6 skipped. The gap
is not a discrepancy: the tag carries the P5.1..P5.5 contract files, while the
P4.1/P5.0/P6/P7 files and their artifacts are still uncommitted. Both numbers are
correct for what they contain; the tag is self-consistent but is not yet the
complete A仓 archive.

Reproduce the tag check:

```
git worktree add --detach /tmp/tagcheck stratum-a-p5-freeze
cd /tmp/tagcheck && python3 -m pytest tests/architecture -q
```

### A仓 runners

Each is executable and self-gating. Run with `PYTHONPATH=src`:

```
python3 -m stratum.knowledge.a_repository.mechanism_runner
python3 -m stratum.knowledge.a_repository.relation_runner
python3 -m stratum.knowledge.a_repository.paper_runner
python3 -m stratum.knowledge.a_repository.constraint_runner
python3 -m stratum.knowledge.a_repository.paper_evidence_fk_runner
```

The first four report gates over an in-memory chain. The fifth (`082`) reports
over the **live** staging database, because its question — "does this foreign
key refuse a cross-catalog declaration" — is only the database's to answer.

Its replay gate is read-only unless `A_P5_5_EXECUTE_REPLAY=1` is set. An earlier
version applied the migration from inside the gate, so merely inspecting the
gates migrated the database while the ledger still said `081`. A validation step
that changes the system it validates is a trap; the gate now executes no DDL by
default.

### Authority counters

Zero at every stage from 077 to 082, and asserted by a gate rather than assumed:

```
B_contamination = 0
C_contamination = 0
BU2_dependency  = 0
```

### What this baseline does not cover

- **Extraction quality is unmeasured at every stage.** Recall and precision are
  unknown, which is not the same as "verified empty". No extractor ships in
  075..082; all pilot rows are labelled `pilot-declared` and are never counted
  as extraction evidence.
- **`SOFT` and `SELF_DEFINED` constraints are unexercised** (081). The
  vocabulary is closed in the schema and coverage is reported per run, rather
  than narrowed to what this corpus happened to contain.
- **Declaration-by-text-span is untested** (080). No span in 671 characters of
  corpus declares the author, publisher, ISBN or any year, so source metadata is
  anchored to the `book_source` catalog row and compared against the field it
  names.
- **`ku_boundary_candidate` is empty by design** (077 held back `SCOPE_LIMIT`
  and `EXCEPTION` for want of an extractor).
- **The database has no state-machine guard at any stage.** A raw `UPDATE` can
  still move `SUPPORTED` back to `GENERATED`; terminality is enforced in the
  writers and recorded as a known limitation.

## Architecture Tests
- `tests/architecture/test_aii_closure.py`: MOCK_ONLY. Tests the architecture contract by reading source code files and executing python stubs (`validate_provenance`). Does not test the real DB `aii.ku_onto` pipeline.

## Learning Tests
- `tests/service_layer/test_flashcards.py`: REAL_DB. Tests flashcard creation and spaced repetition.
- `tests/services/test_cx_learning_migration.py`: REAL_DB / MOCK. Tests the C repo mastery mapping.

## Full `tests/` run

```
48 failed, 1307 passed, 25 skipped, 169 errors
```

The 48 failures and 169 errors are **pre-existing and unrelated to A仓** — mostly
missing `aii` / `scripts` packages and a `ulid.ULID` import. They are identical
at `HEAD` and after the P5 chain; verified by diffing the failed/errored set
against a clean worktree at each stage. Treat them as the ambient baseline, not
as A仓 regressions.

## Conclusion
> 当前“BU 已通过”究竟通过了什么？
The BU tests pass mainly via `bu_learning_gate.py` asserting length, format, and structure during ingest. The "Architecture Closure" is largely a doc/schema-level agreement that hasn't fully propagated to the ingest core (`aii.ku_onto`).