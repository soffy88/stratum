# KU Annotation — Where the Calculus Books' KUs Actually Live (Step 1, read-only)

**Date:** 2026-10-12
**Author:** read-only investigation, no code edited, no secrets printed.
**Scope:** find where the KUs of the two calculus books processed 2026-10-10 by
BU2/P13/P14 live, so a real annotator could read them.

---

## 1. TL;DR — stopped after step 1

The two calculus books' **KU content rows do not exist in any database or file.**
What exists is the BU2 / BU13 / BU14 *understanding* layer
(`book_understandings_v2`, `chapter_understandings`, `book_syntheses`,
`crossbook_understandings`), which references KUs only by **two kinds of opaque
handle**:

- **concept-label strings** in `chapter_understandings.major_ku_refs`
  (e.g. `"Limit"`, `"Cauchy's Mean Value Theorem"`, `"Definite Integral"`); and
- **`ev_*` evidence IDs** in `chapter_understandings.supporting_ku_refs` /
  `evidence_program_json` and `book_syntheses.evidence_map.evidence_ids`.

Neither handle resolves to a persisted `knowledge_unit` row, and the verbatim
quote / locator / page that the annotation tables require were computed at BU2
runtime (via `Chapter.locate_term()` over the book markdown) and **discarded** —
they are not stored anywhere. The FK parent tables
(`book_source`, `source_version`, `knowledge_unit`, `reading_evidence`) are all
**empty for these books** in the A-warehouse.

Therefore Step 2 cannot be built to write to prod: every `ku_occurrence` /
`ku_relation_hint` INSERT would fail its foreign-key constraint
(`unit_id → knowledge_unit`, `source_version_id → source_version`,
`evidence_id → reading_evidence`, plus the composite
`(from_unit_id, source_version_id) → knowledge_unit(id, source_version_id)` on
`ku_relation_hint`). There is also no `source_version` to pass as the required
CLI `source_version` argument.

Per the task's instruction ("If Step 1 shows the books' KUs do not exist
anywhere, stop after Step 1 and say 'stopped after step 1' in the report"):

> **stopped after step 1**

A new worktree / real annotator / prod run were **not** created. Details below
so a human can decide whether the ingestion job that should have frozen the KU
rows is expected to run separately.

---

## 2. Collection and the two books

- **Collection** `coll_e902851eac92` (table `stratum.crossbook_collections`, PK
  column is `id`, not `collection_id`) — name
  `微积分：同济高等数学上册 + Thomas Calculus`, description `CLI collection`.
- **Book A** `01KVQ13J49KR54FE8S6PXNWXC3` = 同济高等数学上册 (7 verified chapters).
- **Book B** `01KWRXP646FQEPPRPHS3R617MZ` = Thomas Calculus 14th ed. (bilingual)
  (18 verified chapters in the latest two runs).

Storage: **one Postgres server** reachable at `172.19.0.1:5437` (container
`aii-postgres`, host-published `5437→5432`). Only that port is listening; the
`5435`/`127.0.0.1` default in `stratum.db` is not up. Databases on it:
`aii_kg` (the A / stratum warehouse, schema `stratum`), `stratum_a_p3_fresh`,
`stratum_a_p3_staging`, `postgres`.

---

## 3. What actually exists for these books (tables / files / row counts / fields)

### 3.1 A-warehouse `aii_kg.stratum` — the BU2/BU13/BU14 understanding layer

| Table | Rows for the 2 books | What it carries |
|---|---|---|
| `book_understandings_v2` | A: 5 runs (2 VERIFIED); B: 8 runs (6 VERIFIED) | canonical BU per run: `governing_questions_json`, `central_theses_json`, `concept_system_json`, `chapter_dependency_graph`, `discourse_arc`, `negative_knowledge_json`, `coverage_score`, `verification_score`, `book_id`, `status`. **No KU text.** |
| `chapter_understandings` | A: 14 chapters across verified runs; B: 46 | the only place KUs are *referenced*: `primary_role`, `secondary_roles_json`, `concepts_introduced_refs`, **`major_ku_refs`** (concept labels), **`supporting_ku_refs`** (`ev_*` IDs), `evidence_program_json` (`claim_ref` + `evidence_refs`), `evidence_strengths` (`ev_* → DIRECT/DERIVED/DEFINITION`), `chapter_question/goal/thesis`, `dependencies_on_prior`. |
| `book_syntheses` | A: 2; B: 1 (for the 2 latest verified runs) | `evidence_map.entries[]` each = `{claim_id, claim_statement, evidence_ids[ev_*], chapter_ids, is_supported, evidence_strengths}` — claim prose + `ev_*` ref, **still no verbatim quote or locator**. |
| `crossbook_understandings` | 1 (the collection) | carries the same `ev_*` IDs mirrored into `evidence_system_json` / `evidence_relations_json` / `comparisons_json`. |
| **`knowledge_unit`** | **0** | **FK target for `ku_occurrence.unit_id` and `ku_relation_hint.(from/to)_unit_id` — EMPTY.** |
| **`source_version`** | **0** | **FK target for `ku_occurrence.source_version_id` and `ku_relation_hint.source_version_id` — EMPTY.** No `source_version` id exists to pass as the CLI argument. |
| **`book_source`** | **0** | **FK target for `source_version.book_source_id` — EMPTY.** |
| **`reading_evidence`** | **0** | **FK target for `ku_relation_hint.evidence_id` — EMPTY.** |
| `ku_occurrence` / `ku_relation_hint` | **0 / 0** | the annotation target tables (migration `080_a_ku_inbook_annotations.sql` applied) — empty, no rows. |
| `evidence`, `claim_evidence`, `ku_relation`, `ku_layers`, `ku_candidate`, … | unrelated / empty | `evidence` = 8 hand-test rows; `ku_layers` = a different `math_prog_*` pipeline; `ku_relation` = 0. |

**KU-reference counts** (distinct) on the **latest VERIFIED** runs of each book:
- Book A (同济): 51 distinct concept-label `major_ku_refs` + 32 distinct
  `ev_*` supporting refs (33 total supporting refs, all `ev_*`).
- Book B (Thomas): 97 distinct concept-label `major_ku_refs` + 129 distinct
  `ev_*` supporting refs (187 total supporting refs, all `ev_*`).

The 51 + 97 concept labels and the `ev_*` IDs are the only "KU" handles. The
`ev_*` IDs were confirmed **not** to appear in any `knowledge_unit` /
`reading_evidence` / `evidence` table on the whole server (full value scan across
all schemas). They are dangling references created by BU2's runtime
`EvidenceArtifact.make(...)` and never stored.

### 3.2 Other DBs on the same server (checked, not relevant)

- `stratum_a_p3_fresh.stratum`: has 11 `knowledge_unit` + 17 `reading_evidence`,
  but **all belong to the 利率史（第四版） pilot corpus** (`source_version_id =
  sv_f548f51a5df5`, `book_source` = 利率史). Zero rows for the calculus books.
  (This is the frozen pilot data, not calculus.)
- `stratum_a_p3_staging.stratum`: 1 `book_source`, 1 `source_version`, 11
  `knowledge_unit`, 17 `reading_evidence` — also 利率史 only. No `chapter_understandings`.
- `postgres`: template/empty.

### 3.3 Files under `aii/` (checked)

- **Thomas Calculus markdown IS present:**
  `aii/books/MD/中文数学/托马斯微积分第十四版Thomas Calculus英文中文双语AI翻译 (Joel R. Hass, Christopher D. Heil etc.) (z-library.sk, 1lib.sk, z-lib.sk).md`
  (~6.2 MB). A corrupted copy also sits in `aii/quarantine_corrupted_md/`.
- **同济高等数学上册 markdown is NOT currently on disk** under `aii/books/MD/`
  or anywhere reachable by name/id grep — only the BU rows reference it by
  `substrate_id = 01KVQ13J49KR54FE8S6PXNWXC3`. (It was apparently ingested then
  removed/relocated; the BU layer was still produced from it on 2026-10-10.)
- The `ev_*` IDs and concept labels are **not** present as values in any
  `.json` / `.md` / `.csv` / `.txt` under the repo (filesystem grep returned
  nothing for a sampled `ev_*` id).

---

## 4. How BU2 produces the missing KU content (why it's absent)

`src/stratum/services/bu_v2_producer.py`:
- `EvidenceArtifact.make(run_id, chapter, kind, locator, snippet)` (line 65) and
  `Chapter.locate_term(term, window=320)` (line 202) locate a verbatim snippet
  from the in-memory book markdown **at pipeline runtime**.
- `major_ku_refs = concepts_introduced` (line 456) — i.e. the *names* of
  concepts, not frozen units.
- `supporting_ku_refs = [e.evidence_id for e in evidence]` (line 457) — the
  runtime-generated `ev_*` IDs, which are never written to `reading_evidence` /
  `knowledge_unit`.
- The verbatim `snippet` / `locator` is used to build `chapter_understandings`
  and `book_syntheses` and then dropped; nothing persists it to the A-warehouse
  KU tables.

So the A-warehouse holds the *understanding*, not the *frozen KUs*. The
annotation target tables (`ku_occurrence`/`ku_relation_hint`) sit one layer
below and have no rows to point at.

---

## 5. Why Step 2 is blocked (concrete FK evidence)

From `aii_kg.stratum` constraints:

- `ku_occurrence`: `FOREIGN KEY (source_version_id) REFERENCES source_version(id)`,
  `FOREIGN KEY (unit_id) REFERENCES knowledge_unit(id)`, plus CHECKs
  `length(locator)>0`, `length(quote_span)>0`, `quote_status IN
  ('LOCATED','UNLOCATED')`, `role IN
  ('DEFINITION','THEOREM','EXAMPLE','EXERCISE','SUMMARY','ASIDE','OTHER')`,
  and `review_required` must equal `(quote_status='UNLOCATED')`. Idempotency keys:
  `UNIQUE(source_version_id, unit_id, locator, role)` and `UNIQUE(occurrence_hash)`.
- `ku_relation_hint`: `FOREIGN KEY (source_version_id) REFERENCES source_version(id)`,
  `FOREIGN KEY (evidence_id) REFERENCES reading_evidence(id)`,
  `FOREIGN KEY (from_unit_id, source_version_id) REFERENCES knowledge_unit(id, source_version_id)`
  (composite), `FOREIGN KEY (to_unit_id, source_version_id) REFERENCES
  knowledge_unit(id, source_version_id)` (composite), plus `kind IN
  ('RESTATES','SUMMARIZES','APPLIES')`, `from_unit_id <> to_unit_id`,
  `confidence IN [0,1]`, `UNIQUE(kind, from_unit_id, to_unit_id)`,
  `UNIQUE(hint_hash)`.
- `knowledge_unit` itself requires `evidence_count >= 1`, a `candidate_id →
  ku_candidate`, a `verification_id → ku_verification`, and `freeze_status IN
  ('VERIFIED','FREEZE_PENDING','FROZEN','REJECTED')` with `frozen_at` set when
  `FROZEN`.

Every one of these parents (`source_version`, `knowledge_unit`, `reading_evidence`)
is empty for the calculus books, so no occurrence/hint row can be inserted, and
there is no `source_version` id to pass as the CLI argument. The migration
`080` is applied but its tables are empty.

---

## 6. What would have to exist for Step 2 to run

One of:
1. A separate ingestion/freeze job populates `book_source`, `source_version`,
   `knowledge_unit` (with `evidence_count>=1`, frozen, and `source_version_id`),
   and `reading_evidence` for both calculus books — turning the BU2 reference
   labels/`ev_*` IDs into real, resolvable rows. Then a real annotator could read
   those and write `ku_occurrence`/`ku_relation_hint`.
2. Or the annotator is retargeted at the **understanding layer** it can actually
   read (`chapter_understandings` / `book_syntheses`) and at the Thomas markdown
   on disk — but that output would not fit `ku_occurrence`/`ku_relation_hint`
   without first creating the FK parents (a schema/ingestion decision, out of
   scope for this read-only step and likely a design change the user must approve).

## 7. Verification notes

- DB reachability and every `count(*)` / `information_schema` lookup were run
  read-only via `psycopg2` against `172.19.0.1:5437` using the existing
  `***REMOVED***` (read from `aii/.env`, **never printed**).
- The `ev_*` ID scan covered all schemas on the server (`stratum`, `aii`,
  `public`, `toolkit_experimental`) across text/varchar/jsonb columns — nothing
  matched outside `chapter_understandings`/`book_syntheses`/`crossbook_understandings`.
- No repo code was edited. No rows were written. OCR / docs_service /
  `quark_catalog.json` / `arxiv_math_state.json` were not touched.

> **stopped after step 1**
