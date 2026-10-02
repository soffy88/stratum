# B_AUTHORITY_MAP

Date: 2026-10-02. Companion to `B_CURRENT_STATE_MAP.md`.

Purpose: fix who owns which object, so that B仓 work cannot redefine A仓. A仓 P0–P8 is
frozen and this document treats it as a given. Where the existing code already
violates the map, the violation is named rather than quietly accepted.

## 1. The map

| object | authority | concrete table | notes |
|---|---|---|---|
| raw text | **A** | `stratum.book_source` / `source_version` | A-1. Immutable by FK design (RESTRICT downstream). |
| section structure | **A** | `stratum.reading_evidence` | A-3. The span A read. |
| evidence span | **A** | `stratum.reading_evidence` + `evidence_quality` | A-3/A-4.1. |
| candidate KU | **A** | `stratum.ku_candidate` | A-4. Not citable. |
| KU verification | **A** | `stratum.ku_verification` | A-4.2. |
| **KU statement** | **A** | `stratum.knowledge_unit` | A-4.1 FROZEN. `statement` = the candidate's wording; `canonical_text` = the verbatim span. B may cite; B may not restate. |
| KU identity / supersession | **A** | `stratum.ku_identity`, `ku_revision`, `ku_review_event` | A-5/A-6. |
| condition / boundary | **A** | `stratum.ku_condition_candidate`, `ku_boundary_candidate` | A-5.0. |
| mechanism chain | **A** | `stratum.mechanism_candidate`, `mechanism_node` | A-5.1. Per-KU mechanism, not cross-KU abstraction. |
| KU-level relation | **A** | `stratum.ku_relation` | A-5. Relation **between statements**. |
| relation **candidate** | **A** | `stratum.relation_candidate` | A-5.2. |
| paper source / evidence | **A** | `stratum.paper_source_candidate`, `paper_evidence` | A-5.3/A-5.5. |
| constraint candidate | **A** | `stratum.constraint_candidate` | A-5.4. |
| reading projection | **A** | no table, JSON artifact | A-7. Read-only by design. |
| **concept induction** | **B** | `rf.refined_concept` | Grouping KUs into concepts. `073:11` already says so: *"Grouping these units into concepts is another repository's work."* |
| **concept relation** | **B** | `rf.refined_directed_edge` | Between **concepts**, not between statements. Distinct object from `ku_relation`. |
| dedup / merge decision | **B** | `rf.decision_ledger` | The B仓 equivalent of A's review ledger. |
| **Nature / 本性** | **B** | `rf.refined_invariant` | Reserved, empty. See §4 on naming. |
| cross-domain relation | **B** | `rf.refined_cross_domain_relation` | Reserved, empty. |
| theme / community | **B** | `rf.refined_theme_kc`, `refined_kc_member` | Spectral, versioned. |
| personal concept | **C/user** | `stratum.concepts` | User-authored. Not B. See §3. |
| **learning path** | **C** | `cx.learning_progress` (unreachable), `stratum.learning_objects` (0 rows) | |
| **user mastery** | **C** | `cx.learning_progress` | Sole authority per `mastery_authority.py:3-6`. Unverifiable — §6. |
| flashcard scheduling | **C** | `stratum.flashcards` | Card state, not mastery. |
| cornell note telemetry | **C** | `stratum.cornell_notes`, `cornell_progress` | Not mastery. |

## 2. The one boundary that is already drawn, in A's own words

A仓's KU freeze migration states the division of labour at `073_a_knowledge_unit_freeze.sql:11`:

> Grouping these units into concepts is another repository's work.

A-2's final acceptance report lists `inference or judgement — none` and
`semantic similarity — none` among its non-goals
(`A_REPOSITORY_FINAL_ACCEPTANCE_REPORT.md` §8). So the A→B seam is not something this
project needs to invent. A has already declared where it stops.

Consequence for the brief's rule *"B 不得直接生成未经 A仓锚定的知识事实"*: it is
already structurally enforced for the frozen chain. A frozen `knowledge_unit` is
`ON DELETE RESTRICT` from its verification and candidate, and B cannot produce a
`knowledge_unit` row. Verified: no B-side code writes any A-frozen table.

## 3. Three violations of this map that exist today

### V1 — B-1's A-side is not A仓

This is the most consequential finding, and it is not a code defect.

B-1 reads `aii.ku_onto` (`candidates.py:23`, `m0.py:107-128`), which lives in the
**legacy AII_KG A仓**: 44,246 rows, written by flywheel scripts, never frozen,
`grade`-carried but unverified, no `knowledge_unit` equivalent. A仓's frozen A is a
**different database and a different object**:

```
A仓 frozen   stratum_a_p3_staging / _fresh   stratum.knowledge_unit   11 rows
             book: 《利率史（第四版）》 one book, 11 units, ULID ids ku_*
B-1's A      aii_kg (5437)                   aii.ku_onto             44,246 rows
             299 distinct books, compound ids book::chN_kuM
```

Measured overlap: **zero**. None of the 11 frozen `knowledge_unit` ids exist in
`aii.ku_onto`. None of B-1's 29,323 KUs are `ku_*` shaped. B-1's `contributions[].raw_ku_id`
values (`econ_zh_2726f38224::ch22_ku0`, `advmath_zh_c110afbec7::ch12_ku10`) resolve in
`aii.ku_onto` and nowhere else.

So B-1 is not currently derived from A仓. It is derived from a legacy table that
predates it and shares no identity space. Any B design that says "B = f(A仓)" is
describing an intended relationship, not the existing one.

Note also that 070–082 are **not applied to `aii_kg` at all** — the live
`_pg_migrations` in `aii_kg` stops at `066_bu2_p4_p9_repair.sql` `[live]`. A仓's frozen
chain exists only in the two staging databases. B-1 cannot point at it until it is
applied somewhere it can read.

### V2 — B-3 is B仓 by name only

`stratum.graph_entities` (185) and `stratum.graph_relations` (163) are concept nodes
and concept relations, produced by an LLM with a free-text `relation_type`
(12 distinct values live, unconstrained) and no evidence requirement
(`source_substrate_ids` is a bare id list, never checked to have been read).

Under this map those are B-owned objects with no B discipline. Under
`contract.py:53-54` they are the declared authority for `Concept` and `Relation`. Both
cannot stand. This is a decision, not a bug — see `B_GAP_MAP.md` §D1.

### V3 — `contract.py` does not mention B-1 or B-2

`src/stratum/knowledge/contract.py:47-58` maps `Concept → stratum.concepts` and
`Relation → stratum.concept_relations`. Neither `rf.*` nor any of the 16 BU2 tables
appears. `knowledge/__init__.py` does not export `bu_v2_models`, so BU2 is outside the
constitutional package's public surface entirely.

Consequence: the repository's own constitution names B-3 as the Concept authority.
B-1 and B-2 have no constitutional standing at all. Whatever this project decides,
`contract.py` has to be amended, or the next reader will take B-3 as settled.

## 4. Naming: 本性 is `invariant`, not `nature`

The brief's B4 proposes a `Nature` object. `rf.refined_invariant` already exists and
`aii/migrations/refined/0001_refined_repo_schema.sql:11-12` locks the terminology:

```
术语锁定: 本性=invariant（非 nature）; 本性概念=is_invariant_concept 字段（不独立建表）;
         本性同一=invariant-identity。
```

That is a deliberate decision already taken, with a reason the brief re-derives
independently: 本性 is an invariant, not a nature. `nature` invites description;
`invariant` demands a property that survives across instances. The schema also
records that a 本性 that has been promoted to a concept is a **field on the concept**,
not a separate table.

Recommendation: adopt `invariant`, do not re-litigate. The columns the brief wants
already exist — `statement`, `invariant_vector`, `is_invariant_concept`,
`status IN ('candidate','confirmed')`, `decision_id` — except `supporting_evidence`
and `emergence_count`, which are the two that would make emergence auditable (§G4).

## 5. What B is permitted to do

Derived from A-frozen objects, with a ledger row per decision:

| permitted | mechanism that must exist | exists today |
|---|---|---|
| group KUs into a concept | deterministic gates → LLM → `decision_ledger` → commit | yes, `dedup/` — but the commit drops `decision_id` |
| assert a relation between two concepts | per-edge LLM judgment + `evidence` + ledger | yes, `dedup/readout.py` — the only complete path |
| record that a merge was decided | `decision_ledger`, append-only, `llm_raw` retained | table yes, linkage **no** (0 of 39,331) |
| induce a community | deterministic louvain, versioned snapshot | yes, `community_detect.py` |
| promote a repeated property to 本性 | needs `supporting_evidence` + `emergence_count` | no — table empty, no writer |

## 6. What B is not permitted to do

```
B -> A mutation                no code path exists; keep the grep as a gate
B -> A overwrite               same
B -> A correction              same
B restating a KU statement     A holds `statement` and `canonical_text` separately
                               on purpose (073:26-29) so no downstream copy is needed
B asserting truth of a concept every rf row is grade='unverified' [live]; nothing in
                               the code can set any other value
B owning a learning path       C owns it; bu_v2_models.py:607 and tutor_engine.py:14
                               both say so, and neither reads cx
B owning user mastery          C owns it, sole authority, unverifiable from this host
```

## 7. C仓 authority cannot be verified from this host

`cx.learning_progress` is named the sole canonical mastery authority by
`mastery_authority.py:3-6,95`, and by `AUTHORITY_MAP.md`. Measured: the `cx` schema has
**0 tables** in `aii_kg`, and no `aii_context` database or container exists on this
host. The only `cx` references in `src/` are docstrings and one unexercised query path.

This is C仓's problem, not B仓's, and it does not block B work. It is recorded because
a B design that plans to hand learning paths to "the C authority" is handing them to
something that cannot be reached. Whoever picks up C needs to know that first.
