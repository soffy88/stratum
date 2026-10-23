# KU Annotation Pilot — 2026-10-12

## ⛔ Task could not be executed as specified — root cause

The task asks to run `src/stratum/knowledge/a_repository/ku_annotation_runner.py`
"for real on two already-VERIFIED calculus books in the A warehouse (verified
2026-10-10)". After reading the runner and its dependencies and inspecting the
production A-warehouse directly, **the runner cannot be pointed at any book,
and the A-warehouse contains no frozen book content at all.** The task's
premises do not match the actual state of the code or the database. Details
below.

## 1. The runner is hardcoded to ONE book, built entirely in memory

- `ku_annotation_runner.py` / `pilot_corpus.py` are the **A-P8 feature branch
  merge** (`891b04f`, in `c010635`). The runner's `PILOT_OCCURRENCES` and
  `PILOT_HINTS` are **literal Python constants** keyed to a single book:
  - Book: **利率史（第四版）** (History of Interest Rates, 4th ed.), Chapter 1
    「古代时期的信贷」, pages 1–10.
  - Unit IDs are hardcoded: `ku_6460a6062a10`, `ku_59cb9040d0f0`,
    `ku_10fef8f2ffa4`, `ku_639e79172556`.
  - Source version is content-derived and fixed: `sv_f548f51a5df5`.
- There is **no CLI flag, no `book_id`/`source_version_id` argument, no env
  var, and no DB read** that selects a target book. `grep` for
  `argparse|add_argument|sys.argv|book_id|getenv|psycopg|connect(` across
  `a_repository/*.py` finds nothing — the only `sys.argv` handling is
  `--sql` (emit SQL to a file). `main()` calls `build_annotation()` →
  `build_identity()` → the in-memory `pipeline`, with no external input.
- The runner therefore **cannot be retargeted at calculus books or any other
  book without editing the source.** (Editing repo code is explicitly
  out of scope for this task.)

## 2. There is no "calculus books verified 2026-10-10" anywhere

- No "calculus" / "微积分" / "导数" / "积分" book is referenced anywhere in
  `src/stratum/knowledge/` or in the A-warehouse.
- No record of a "verified 2026-10-10" book exists. The 6 `VERIFIED`
  `book_reading_run` rows in prod are all `source_version = v1` for just **two**
  `source_id` values (`01KWRXP646FQEPPRPHS3R617MZ`,
  `01KVQ13J49KR54FE8S6PXNWXC3`); their `book_source` rows have **no title** and
  no frozen units. None is a calculus book.

## 3. The production A-warehouse has ZERO frozen book content

Queried `aii_kg` (Postgres `172.19.0.1:5437`, schema `stratum`, via the
`aii-postgres` container — same DSN stratum-sl uses, `STRATUM_PG_*`) on
2026-10-12:

| Table | Rows |
|---|---|
| `book_source` | 0 |
| `source_version` | 0 |
| `knowledge_unit` | 0 |
| `reading_evidence` | 0 |
| `ku_candidate` | 0 |
| `ku_occurrence` | 0 |
| `ku_relation_hint` | 0 |

(Other DBs `stratum_a_p3_staging` / `stratum_a_p3_fresh` do **not** have
`ku_occurrence` at all — the migration only exists in `aii_kg`.)

- Migration **080_a_ku_inbook_annotations.sql IS applied** in prod — the
  `ku_occurrence` / `ku_relation_hint` tables exist and are empty. That part of
  the task statement is correct.
- But because `knowledge_unit` / `source_version` are empty, **no occurrence
  or hint row the runner emits can be inserted into prod** — every
  `ku_occurrence` row carries `unit_id` FKs to `knowledge_unit(id)` and
  `source_version(id, source_version_id)` composite FKs, and every hint
  references two units + a `source_version` + a `reading_evidence` row. All of
  those parents are absent. The runner's own `ON CONFLICT DO NOTHING` INSERT
  also **does not exist in practice** unless `emit_annotation_sql` output is
  executed by hand — the runner itself writes only to an in-memory `sink` and
  never issues a DB statement.

## 4. The runner does not write to any database

- `FreezeTransaction` / `InMemorySink` in `persistence.py` are pure in-memory
  transactional structures. `AnnotationService.annotate_occurrence` writes
  only `self.sink.ku_occurrences[...]` — nothing is committed to Postgres.
- The ONLY DB-bound path is `emit_annotation_sql()` → `--sql annotation.sql`,
  which **emits a `.sql` file for a DBA to execute manually** (the module
  docstring even says "Emit both annotation tables for a DBA to execute").
  It is not invoked by `main()` unless `--sql` is passed, and even then it
  only writes a file — it does not connect.
- So "run it for real on the book" with rows landing in prod is **not what this
  code does.** The author-facing design (see module docstring) is: build the
  pilot off the frozen 利率史 chapter in memory, exercise the gates, and hand a
  DBA the SQL. Running `--sql` against prod would fail on FK — all parent rows
  are missing.

## 5. The LLM precondition does not arise

The runner declares **"The pilot annotations are declared, not extracted. No
role classifier and no hint extractor ship in this stage"** — it uses no LLM.
The `local-veya-fllm` profile was therefore not needed and not contacted.

## What I actually did (read-only verification, no code edited, no secrets printed)

1. Read `ku_annotation_runner.py`, `ku_annotation.py`, `pilot_corpus.py`,
   `ku_identity_runner.py`, `persistence.py`.
2. Ran the runner (`PYTHONPATH=src .venv/bin/python -m …ku_annotation_runner`)
   — it executes in-memory in ~3 ms and passes all of its own acceptance
   gates for the **利率史** pilot (4 occurrences, 2 hints, no review queue,
   replay idempotent, 26/26 negative refusals).
3. Confirmed DB reachability from the prod container and inventoried every
   relevant A-chain table (all empty). DB password was read only from
   in-container env, never printed.

---

## What a correct pilot run WOULD produce (observed from the in-memory pilot)

Since the only runnable book is 利率史 Ch.1, here is the real output the runner
produces today. It is **not** a calculus book, and **not** written to prod.

### Per-book: 利率史（第四版） — 第一章 古代时期的信贷 (`sv_f548f51a5df5`)

- **KU occurrence count:** 4
- **Count per role:**
  - DEFINITION: 2
  - THEOREM: 1
  - SUMMARY: 1
  - EXAMPLE: 0, EXERCISE: 0, ASIDE: 0, OTHER: 0
- **Relation hints per type:**
  - RESTATES: 1 (confidence 0.95)
  - APPLIES: 1 (confidence 0.75)
  - SUMMARIZES: 0
  - confidence distribution: {0.95: 1, 0.75: 1}
- **Review-queue count (quote_span not verbatim / UNLOCATED):** 0 — all 4
  quotes located verbatim in their evidence rows.
- **Runtime:** ~0.003 s (build + intra-process rerun; in-memory only).
- **Rerun duplicate count:** 0 (idempotent; `replay_gate` →
  `identical_keys=1, rewrite_is_noop=1, duplicate_occurrences=0,
  duplicate_hints=0`).
- **Authority / isolation:** B_CONTAMINATION=0, C_CONTAMINATION=0,
  BU2_DEPENDENCY=0, cross_source_hints=0, 26/26 forbidden mutations refused.

### 5 sample annotations (the only 4 occurrences; full set shown)

1. **id `kao_6051357dcce2`** — unit `ku_6460a6062a10`, p.1, **DEFINITION**,
   LOCATED.
   Quote: 「信贷在古代和中世纪时期就得到了普遍应用。信贷的历史远远早于工业、银行业，甚至早于铸币业；它可能比最原始的货币形式还要早。」
   **Judgement: role CORRECT.** The passage states a general fact about the
   antiquity of credit — a definition/statement of what is, not a theorem or
   example. Matches the declared role.

2. **id `kao_db3e3c68b412`** — unit `ku_59cb9040d0f0`, p.3, **DEFINITION**,
   LOCATED.
   Quote: 「在大约公元前1800年，古代巴比伦王朝的第一个国王汉谟拉比（Hammurabi）给他的臣民制订了第一部已知最早的正式法典。」
   **Judgement: role CORRECT.** Identifies/defines the earliest formal code.

3. **id `kao_58b40839fe34`** — unit `ku_10fef8f2ffa4`, p.3, **THEOREM**, LOCATED.
   Quote (same span as #2): 「在大约公元前1800年…制订了第一部已知最早的正式法典。」
   **Judgement: role QUESTIONABLE.** This is the *revised* unit over the same
   evidence as #2, deliberately labelled THEOREM so the pilot can exercise the
   same-span-twice / no-merge path. As a reading of the book it is a stretch —
   the passage is an historical fact, not a theorem — but the mislabel is the
   *point of the test*: it proves the occurrence key keeps the two rows
   distinct (role is part of the key) instead of merging them. For a real
   corpus this would be DEFINITION.

4. **id `kao_0a2606d98b80`** — unit `ku_639e79172556`, p.4, **SUMMARY**, LOCATED.
   Quote: 「银子贷款按重量计算每年20%」
   **Judgement: role CORRECT.** A concise restatement of the Babylonian silver
   rate cap — reads as a summary of the surrounding legal detail.

### 2 relation hints

- `kai_145e01da9619` **RESTATES** 0.95: `ku_59cb9040d0f0` → `ku_10fef8f2ffa4`.
  **Judgement: CORRECT** — these are the same proposition frozen twice (the
  prior unit and its revision), so "restates" is exactly right, and the hint
  correctly does NOT merge them.
- `kai_e12bca7c1d39` **APPLIES** 0.75: `ku_6460a6062a10` → `ku_639e79172556`.
  **Judgement: CORRECT but low-confidence is apt** — "credit predates coinage"
  (p.1) and "silver loans 20%/year by weight" (p.4) are both about ancient
  credit practice rather than one applying the other; 0.75 acknowledges the
  loose link. Marked `applied: false` (handed to B仓 as a dedup candidate,
  never asserted).

---

## Recommendation / blocker

To run this "for real on two VERIFIED calculus books," the following must hold,
none of which are true today:

1. **Retarget the runner** — `PILOT_OCCURRENCES` / `PILOT_HINTS` /
   `pilot_corpus.py` must be generalized to accept a `source_version_id` (or a
   book) and read its frozen units + evidence from the DB. This requires
   editing repo code (out of scope here) and a code review.
2. **Populate the A-warehouse** — at minimum `book_source`, `source_version`,
   `knowledge_unit`, `reading_evidence` rows for the target books must exist
   (currently all empty), or the FK-bearing INSERTs will fail.
3. **Confirm the two calculus books actually exist and were VERIFIED
   2026-10-10** — no such books were found.

Please confirm the intended target (a) and whether the A-warehouse content is
expected to be populated by a separate ingestion job that hasn't run yet. I did
not write any rows to prod, did not edit any repo code, and did not touch
OCR / docs_service / quark_catalog.json / arxiv_math_state.json.
