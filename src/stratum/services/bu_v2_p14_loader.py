"""P14: load the per-book inputs (BU2 + P13 BookSynthesis) from the database.

The cross-book runner needs one ``(BookUnderstandingV2, BookSynthesis)`` pair
per book. BU2 runs persist the BU and its chapter understandings but not the
P13 synthesis, so a synthesis that is missing for the BU's own run is built
here from the persisted rows (and saved when ``persist`` is set). A synthesis
from an older run of the same book is never reused, because its claims and
chapter ids would not match the BU it would be paired with.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from stratum.knowledge.bu_v2_models import (
    BookSynthesis,
    BookUnderstandingV2,
    ChapterUnderstanding,
    CrossBookCollection,
    CrossBookUnderstanding,
)

QueryFn = Callable[..., list[dict]]


def _jload(value: Any, default: Any):
    if value is None:
        return default
    if isinstance(value, (bytes, bytearray)):
        value = value.decode()
    if isinstance(value, str):
        if not value:
            return default
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return value


def _query() -> QueryFn:
    from stratum.db import query

    return query


_BU_JSON = {
    "governing_questions_json": ("governing_questions", []),
    "central_theses_json": ("central_theses", []),
    "sub_theses_json": ("sub_theses", []),
    "concept_system_json": ("concept_system", {}),
    "argument_architecture_json": ("argument_architecture", {}),
    "negative_knowledge_json": ("negative_knowledge", {}),
    "concept_evolution_json": ("concept_evolution", []),
    "claim_evolution_json": ("claim_evolution", []),
    "resolved_questions_json": ("resolved_questions", []),
    "unresolved_questions_json": ("unresolved_questions", []),
}
_BU_PLAIN_JSON = {"chapter_dependency_graph": {}, "discourse_arc": {}}


def bu_from_row(row: dict) -> BookUnderstandingV2:
    data: dict[str, Any] = {}
    fields = BookUnderstandingV2.model_fields
    for key, value in row.items():
        if key in _BU_JSON:
            name, default = _BU_JSON[key]
            data[name] = _jload(value, default)
        elif key in _BU_PLAIN_JSON:
            data[key] = _jload(value, _BU_PLAIN_JSON[key])
        elif key in fields and value is not None:
            data[key] = value
    if not data.get("book_id"):
        data["book_id"] = row.get("substrate_id", "")
    return BookUnderstandingV2(**data)


_CU_JSON = {
    "secondary_roles_json": "secondary_roles",
    "evidence_program_json": "evidence_program",
    "assumptions_json": "assumptions",
    "qualifications_json": "qualifications",
}


def chapter_from_row(row: dict) -> ChapterUnderstanding:
    data: dict[str, Any] = {}
    fields = ChapterUnderstanding.model_fields
    for key, value in row.items():
        if key in _CU_JSON:
            data[_CU_JSON[key]] = _jload(value, [])
        elif key in ("dependencies_on_prior", "promises_to_future"):
            data[key] = _jload(value, [])
        elif key == "evidence_strengths":
            data[key] = _jload(value, {})
        elif key in fields and value is not None:
            data[key] = value
    return ChapterUnderstanding(**data)


_SYNTH_JSON = (
    "thesis", "concept_system", "argument_system", "mechanism_system",
    "evidence_map", "author_model", "chapter_roles", "contradictions",
    "synthesis_evidence",
)


def synthesis_from_row(row: dict) -> BookSynthesis:
    data = dict(row)
    for key in _SYNTH_JSON:
        if key in data:
            data[key] = _jload(data[key], {})
    for key in ("unresolved_questions", "limitations"):
        value = data.get(key)
        if isinstance(value, str):
            parsed = _jload(value, None)
            if parsed is None:
                try:
                    import ast

                    parsed = ast.literal_eval(value)
                except (ValueError, SyntaxError):
                    parsed = [value] if value else []
            data[key] = parsed
        elif value is None:
            data[key] = []
    if data.get("created_at") is not None and not isinstance(data["created_at"], str):
        data["created_at"] = data["created_at"].isoformat()
    return BookSynthesis(**{k: v for k, v in data.items() if k in BookSynthesis.model_fields})


def latest_verified_bu(book_id: str, query: QueryFn | None = None) -> BookUnderstandingV2 | None:
    q = query or _query()
    rows = q(
        "SELECT * FROM book_understandings_v2 "
        "WHERE (substrate_id = %(b)s OR book_id = %(b)s) AND status = 'VERIFIED' "
        "ORDER BY version DESC, created_at DESC LIMIT 1",
        {"b": book_id},
    )
    return bu_from_row(rows[0]) if rows else None


def chapters_for_run(run_id: str, query: QueryFn | None = None) -> list[ChapterUnderstanding]:
    q = query or _query()
    rows = q(
        "SELECT * FROM chapter_understandings WHERE run_id = %(r)s ORDER BY created_at, chapter_id",
        {"r": run_id},
        limit=10000,
    )
    return [chapter_from_row(r) for r in rows]


def synthesis_for_run(run_id: str, query: QueryFn | None = None) -> BookSynthesis | None:
    q = query or _query()
    rows = q(
        "SELECT * FROM book_syntheses WHERE run_id = %(r)s ORDER BY created_at DESC LIMIT 1",
        {"r": run_id},
    )
    return synthesis_from_row(rows[0]) if rows else None


def load_book_pair(
    book_id: str,
    *,
    persist: bool = False,
    query: QueryFn | None = None,
) -> tuple[BookUnderstandingV2 | None, BookSynthesis | None, str]:
    """Return ``(bu, synthesis, note)`` for the latest VERIFIED BU of a book."""
    bu = latest_verified_bu(book_id, query)
    if bu is None:
        return None, None, f"Book {book_id}: no VERIFIED BookUnderstandingV2"
    synth = synthesis_for_run(bu.run_id, query)
    if synth is not None:
        return bu, synth, f"Book {book_id}: synthesis loaded for {bu.run_id}"
    chapters = chapters_for_run(bu.run_id, query)
    if not chapters:
        return bu, None, f"Book {book_id}: run {bu.run_id} has no chapter understandings"
    from stratum.services.bu_v2_book_synthesis import BookSynthesisBuilder

    synth = BookSynthesisBuilder().build(bu, chapters)
    note = f"Book {book_id}: synthesis built for {bu.run_id} ({len(chapters)} chapters)"
    if persist:
        from stratum.services.bu_v2_repositories import BookSynthesisRepository

        BookSynthesisRepository.save(synth)
        note += ", persisted"
    return bu, synth, note


def collection_from_row(row: dict) -> CrossBookCollection:
    data = {
        "collection_id": row.get("collection_id") or row.get("id") or "",
        "name": row.get("name", ""),
        "description": row.get("description") or "",
        "book_ids": list(row.get("book_ids") or []),
        "version": row.get("version") or 1,
    }
    created = row.get("created_at")
    if created is not None:
        data["created_at"] = created if isinstance(created, str) else created.isoformat()
    return CrossBookCollection(**data)


_CBU_LISTS = (
    "shared_problems", "concept_system", "concept_relations", "thesis_system",
    "thesis_relations", "argument_system", "argument_relations", "mechanism_system",
    "mechanism_relations", "evidence_system", "evidence_relations", "contradictions",
    "comparisons", "knowledge_gaps",
)


def save_understanding(cbu: CrossBookUnderstanding, *, execute=None) -> None:
    """Upsert the cross-book understanding, one row per collection."""
    if execute is None:
        from stratum.db import execute
    dump = cbu.model_dump(mode="json")
    row: dict[str, Any] = {
        "collection_id": cbu.collection.collection_id,
        "understanding_id": cbu.understanding_id,
    }
    for name in _CBU_LISTS:
        row[f"{name}_json"] = json.dumps(dump.get(name, []), ensure_ascii=False)
    row["synthesis_json"] = json.dumps(dump.get("synthesis", {}), ensure_ascii=False)
    row["quality_json"] = json.dumps(dump.get("quality", {}), ensure_ascii=False)
    row["traceability_json"] = json.dumps(dump.get("traceability", {}), ensure_ascii=False)
    cols = list(row)
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c != "collection_id")
    sql = (
        f"INSERT INTO crossbook_understandings ({', '.join(cols)}, created_at, updated_at) "
        f"VALUES ({', '.join('%(' + c + ')s' for c in cols)}, now(), now()) "
        f"ON CONFLICT (collection_id) DO UPDATE SET {updates}, updated_at = now()"
    )
    execute(sql, row)


def save_collection(collection: CrossBookCollection, user_id: str, *, execute=None) -> None:
    if execute is None:
        from stratum.db import execute
    execute(
        "INSERT INTO crossbook_collections (id, user_id, name, description, book_ids, version, created_at, updated_at) "
        "VALUES (%(id)s, %(u)s, %(n)s, %(d)s, %(b)s, %(v)s, now(), now()) "
        "ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, "
        "book_ids = EXCLUDED.book_ids, updated_at = now()",
        {"id": collection.collection_id, "u": user_id, "n": collection.name,
         "d": collection.description, "b": collection.book_ids, "v": collection.version},
    )


def understanding_row_view(row: dict | None) -> dict | None:
    """Expose a crossbook_understandings row under the model's field names."""
    if not row:
        return row
    view = dict(row)
    for name in _CBU_LISTS:
        view[name] = _jload(row.get(f"{name}_json"), [])
    view["synthesis"] = _jload(row.get("synthesis_json"), {})
    view["quality"] = _jload(row.get("quality_json"), {})
    view["traceability"] = _jload(row.get("traceability_json"), {})
    return view
