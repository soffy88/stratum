# A SOURCE LOCATOR SPEC — 证据定位规范

TASK=STRATUM_A_REPOSITORY_P2_EVIDENCE_QUALITY_AND_KU_CLASSIFICATION
STATUS=DEFINED
SCOPE=A仓 only (no B仓 / C仓 / BU2 dependency)

## 1. Canonical Locator

Every `reading_evidence` row carries a canonical `EvidenceLocator`.
The locator is the address of a span inside one specific source version.

### EvidenceLocator — required fields

| Field | Type | Required | Meaning |
|-------|------|----------|---------|
| `source_type` | str | yes | `PDF` / `EPUB` / `HTML` / `MARKDOWN` / `OCR_TEXT` |
| `source_id` | str | yes | `source_version.id` the span was read from |
| `content_hash` | str | yes | sha256 of the exact source file bytes |
| `logical_locator` | str | yes | Semantic address in the document tree (see §3) |
| `physical_locator` | str \| None | no | Physical address in the file (page, sheet, block) |
| `line_range` | tuple[int,int] \| None | no | 1-based inclusive line span for text sources |
| `page_number` | int \| None | no | Declared page in the source edition |

## 2. Rules

### Rule 1 — physical page != logical page

A **physical locator** addresses a position in a concrete file
representation (PDF page 12, EPUB spine item 3, HTML node id).

A **logical locator** addresses a position in the work's own structure
(chapter 1 § "汉谟拉比法典", section index 2).

These are different coordinate systems and are **never interchangeable**.
A re-typeset edition changes physical locators while the logical locator
stays valid. An OCR correction changes physical locators and the logical
locator with it. A仓 therefore treats `logical_locator` as the durable
address and `physical_locator` as a convenience pointer valid only for
the exact `content_hash` it was recorded against.

### Rule 2 — at least one of physical or logical is required

Every evidence row MUST resolve. The enforced rule is:

```
logical_locator  is required (always present, non-empty)
physical_locator optional, but when the source is paginated
                  (PDF / OCR_TEXT) it MUST also be present
```

An evidence row with neither an addressable logical position nor a
physical position is rejected at write time. The P1 pilot corpus uses
`logical_locator` of the form `第一章/1.2` and carries `physical_locator`
as `p.4` for every paginated row.

### Rule 3 — original source position is immutable

Once an evidence row is written, its locator is frozen.
Re-anchoring an evidence to a different position is a **new evidence row**,
never an update of the existing one. `EvidenceLocator` has no mutator; the
ingestion layer raises `AuthorityViolation` on any attempt to change
`source_id`, `content_hash`, `logical_locator`, `physical_locator`,
`line_range`, or `page_number` of a persisted evidence row.

This is what makes replay verification meaningful: if the locator cannot
move, then a replay that produces the same locator is provably reading
the same text.

## 3. logical_locator format

```
<chapter>/<section>[/<subsection>]
```

Examples from the frozen P1 baseline:

| evidence key | logical_locator | physical_locator |
|---|---|---|
| ev_hammurabi_grain_rate | `第一章 古代时期的信贷/1.2` | `p.4` |
| ev_solon_no_interest_limit | `第一章 古代时期的信贷/1.3` | `p.7` |
| ev_prehistory_conclusion | `第一章 古代时期的信贷/1.5` | `p.10` |

For sources without chapter structure (single-file HTML), the first
segment is the document itself:

```
/body/div[@id='content']
```

## 4. Line range semantics

For text sources (`MARKDOWN` / `HTML` / `OCR_TEXT`) `line_range` is
1-based and inclusive on both ends: `(104, 108)` covers lines 104..108.
Line numbers refer to the **content_hash-identified file**, so a
`line_range` is only meaningful together with its `content_hash`.

## 5. Relationship to quality scoring

`locator_score` in `evidence_quality` (migration 071) measures whether the
locator satisfies this spec:

| Condition | locator_score |
|-----------|---------------|
| `logical_locator` non-empty and `physical_locator` present for a paginated source | 1.0 |
| `logical_locator` non-empty, source not paginated | 0.9 |
| `logical_locator` empty but `physical_locator` present | 0.5 |
| neither present (rejected at write time) | 0.0 |

SOURCE_LOCATOR_SPEC=PASS

## 6. Accepted locator policy (P2 record)

Recorded at the P2 freeze. **No schema change** — this section states
policy over the fields already defined in §1.

### 6.1 A logical locator is always accepted

`logical_locator` alone is a sufficient address. An evidence row whose
logical address resolves is valid regardless of whether a physical
address was recorded. The logical address is the durable one: a
re-typeset edition keeps it while `physical_locator` goes stale.

### 6.2 A physical page is optional

`physical_locator` and `page_number` are optional. They are convenience
pointers valid only against the exact `content_hash` they were recorded
with. Absence degrades `locator_score` (§5) but does not reject the row,
except for a paginated source, where a missing physical address scores
`0.6` instead of `1.0`.

### 6.3 For a markdown source, `line_range` outranks `physical_page`

For `MARKDOWN` (and any text source), a `line_range` is a stronger
address than a declared page number:

- `line_range` is 1-based inclusive and is tied to the
  `content_hash`-identified file, so it is checkable.
- `page_number` for a text source is a claim inherited from the printed
  edition; nothing in the file verifies it.

Where both exist, `line_range` is the authority for resolving a span and
`page_number` is retained only as an edition-level cross-reference.

### 6.4 Frozen P2 baseline conformance

The frozen baseline is a `PDF` source with `logical_locator` and
`physical_locator` on all 17 evidence rows, so all 17 score
`locator_score = 1.0` and `source_trace_score = 1.0`.

LOCATOR_POLICY=PASS