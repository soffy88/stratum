# AII Architecture Contract — Personal Knowledge Infrastructure

> Canonical product: **AII** (`https://aiinote.com`)
> Canonical store: **PostgreSQL + pgvector = aii_kg (stratum + aii schemas)**
> Repo name `stratum` is a historical shell; `src/stratum/` path is kept to avoid rename risk.
> Product/architecture naming MUST be AII.

## 1. Canonical Objects (closed set)

```
Source
  └─ Fragment
      └─ Evidence
          └─ Claim

Concept
Relation

Note          (user authority)
Annotation    (highlight → Evidence)

LearningObject (projection, not authority)
Skill          (projection, never fact source)
```

No new object type without evidence + ADR.

## 2. Six-Item Contract per Object

| Object | owner | authority | lifecycle | version | provenance | projection |
|---|---|---|---|---|---|---|
| Source | user | `stratum.substrates` | acquire → version (new row, never overwrite text/content_hash) | immutable text + content_hash | self | derivative, substrate_chunk (rebuildable) |
| Fragment | system | `stratum.substrate_chunk` | parse → chunk → embed → supersede | `substrate_id#chunk_idx + parser_version + anchor_json` | Fragment → Source | pgvector vector(1024), lexical index |
| Evidence | user | `stratum.evidence` | highlight → evidence → link → supersede | ulid + quote_hash | Evidence → Fragment → Source | claim_evidence |
| Claim | ai (grounded)/user | `stratum.knowledge_claims` | unverified → verified/contradicted/refuted; superseded_by preserves history | ulid + status + updated_at | Claim → Evidence[] → Fragment → Source (no orphan unless hypothesis) | BU, skill, citation |
| Concept | system (ledger+human) | `stratum.concepts` | extract → dedup ledger → human-approved merge | ulid + aliases[] | Concept → Evidence/Claim | graph_entities (legacy RO) |
| Relation | ai (explainable) | `stratum.concept_relations` | create (rationale|evidence required) → update | ulid + unique(user,src,tgt,type) | Relation → Claim/Evidence + rationale | graph_relations |
| Note | user | `stratum.notes_sl` | user-only writes | ulid + updated_at, author=user | optional links | timeline, personal search |
| Annotation | user | `stratum.highlights` | highlight → enrich → supersede | ulid + locator_json | Annotation → Fragment | evidence.source_highlight_id |
| LearningObject | ai (projection) | **NOT authority** (`substrate_layers` L1/L2) | transient JSON → persist with canonical refs → stale on correction | substrate_id + layer | LO → Claim → Evidence → Fragment → Source | substrate_layers |
| Skill | ai (packaging) | **NOT authority** | export with refs → stale detection → regenerate | skill_id + version + generator | Skill → Concept/Claim/Evidence/LO | exported package |

See `src/stratum/knowledge/contract.py:OBJECT_CONTRACTS` for machine-readable source.

## 3. Provenance Graph (unified)

```
Claim  -> Evidence -> Fragment -> Source
Relation -> Claim / Evidence
LearningObject -> Claim / Evidence
Skill -> Claim / Concept / LearningObject
Concept -> Evidence / Claim
```

All AI-generated semantic objects MUST be traceable. See `src/stratum/knowledge/provenance.py`.

Invariants enforced by API + tests:
- Source text never overwritten (`stratum.substrates.text` append-only)
- Evidence always has `substrate_id` + `quote_hash` + `locator_json`
- Claim without evidence must be `status=hypothesis`
- Relation requires `rationale` or `evidence_ids`
- Note `author=user` — AI never masquerades

## 4. KnowledgeView — Single Retrieval Plane

Single contract: `src/stratum/services/knowledge_view.py`

```
KnowledgeViewRequest { query, top_k, scopes, user_id, rerank, filters }
  scopes: lexical | dense | graph | temporal | user-authored | learning
```

Consumers SHARING one plane:
- `POST /api/v1/search` (fused)
- `POST /api/v1/retrieve` (+ /retrieve/search, /retrieve/mix)
- `POST /api/v1/agents/reading_companion/run`
- `agent` / `research` / `skill retrieval`

Guarantees:
- user isolation via `user_id` + `hash_user_id`
- stable result schema: `id,title,type,score,snippet,citation,paragraph_index,char_start,char_end,anchor_status,deep_link,substrate_id,layer,uri,ref_id,provenance`
- citation can resolve to Source anchor
- lexical/vector are projections, DB is authority

See `src/stratum/services/knowledge_view.py:search_knowledge_view`.

## 5. PostgreSQL Canonical Authority

```
DB = authority        (stratum.* + aii.* in aii_kg :5435)
index = rebuildable projection
```

- `substrate_chunk.embedding vector(1024)` is dense authority source
- `tantivy_path` / `lancedb_path` (oskill) are optional projections — never required at runtime
- `DuckDB`, `LanceDB` as canonical paths are removed from runtime (kept only in `docs/history/`)
- Rebuild test: dropping lexical/vector projection → full rebuild from PG succeeds (tested in `tests/architecture/test_aii_closure.py::test_projection_rebuild`)

## 6. AII / Stratum Naming

- Product, UI, docs, API docs, architecture docs: **AII**
- Internal paths `src/stratum/`, `stratum-sl` container: retained (risk avoidance)
- Legacy product naming blocked by CI: `scripts/check_aii_naming.py`
- Allowlist: `src/stratum`, `stratum-sl`, `stratum-api`, `STRATUM_*` env, `docs/history`

## 7. BU Convergence

BU = Understanding / Learning Projection.
- No independent semantic authority
- `learning_paths`, `deep_cards`, `bu_quality` must resolve to canonical `concept_ids` / `claim_refs`
- Stale BU detected via `superseded_by` on canonical claim

## 8. Skill Provenance

Every exported skill persists:
```
skill_id, version, source_refs, concept_refs, claim_refs, evidence_refs,
generated_at, generator_version
```
`status=superseded` on canonical claim → skill marked stale → must regenerate (not silently reuse).

## 9. Authority Uniqueness Test Matrix

See `tests/architecture/test_aii_closure.py` — 18 invariants covering spec §13.

Priority for conflicts: `data integrity > provenance > authority uniqueness > user isolation > backward compatibility > implementation convenience`.
