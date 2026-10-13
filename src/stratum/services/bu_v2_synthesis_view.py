"""Bounded projections of a P13 book synthesis.

``stratum.book_syntheses`` holds the whole synthesis: for a real textbook the
row is ~1.7 MB, of which ``concept_system`` alone is ~1.3 MB (1067 concepts) and
``evidence_map`` ~240 KB (626 claims, each carrying statement and refs). Serving
that row verbatim on every request made one book's synthesis page transfer more
than the entire rest of the BU2 API combined.

This module answers the same question from the same row without transferring it
all:

* ``summary`` — counts, the core thesis and the top-level shape. A few KB, so a
  page can render its header before anything else arrives.
* ``concepts`` — one page of concepts, defaulting to the 50 core ones.
* ``claims`` — one page of evidence-map claims with statement, support and
  refs, which is what the "章节主张" view actually needs.

Selection is explicit (``?view=…``) and additive: ``view=full`` returns exactly
the row the endpoint returned before this module existed, so no existing caller
changes behaviour unless it opts in. A caller that asks for nothing gets the
summary, which is the new default.
"""

from __future__ import annotations

import json
from typing import Any

# Fields the row carries, in the order the row's ``SELECT *`` produces them.
SYNTHESIS_FIELDS: tuple[str, ...] = (
    "thesis",
    "problem_definition",
    "concept_system",
    "argument_system",
    "mechanism_system",
    "evidence_map",
    "author_model",
    "chapter_roles",
    "unresolved_questions",
    "contradictions",
    "limitations",
    "synthesis_evidence",
)

# Small enough to always be worth sending, and what a page header renders.
SUMMARY_FIELDS: tuple[str, ...] = (
    "problem_definition",
    "author_model",
    "chapter_roles",
    "unresolved_questions",
    "limitations",
    "contradictions",
)

# Concept ordering: the most load-bearing roles first.
_ROLE_ORDER = ("core", "foundational", "terminal", "bridging", "derived", "application")

# Default page sizes. A concept page carries a definition, so 50 is already
# ~50 KB; a page of claims is a third of that. Both stay well under the 200 KB
# default-response target even at the maximum.
DEFAULT_CONCEPT_LIMIT = 50
DEFAULT_CLAIM_LIMIT = 50


def decode(value: Any) -> Any:
    """Decode a jsonb column that may arrive as text (double-encoded)."""
    if not isinstance(value, str):
        return value
    # Two passes, matching the router's ``_j``: psycopg2 hands jsonb back as
    # text and some rows were written double-encoded, so the first pass can
    # still yield a string.
    for _ in range(2):
        try:
            value = json.loads(value)
        except ValueError:
            break
        if not isinstance(value, str):
            break
    return value


def _as_list(value: Any, *keys: str) -> list[Any]:
    """Read a list that may sit under a wrapper key (``{"concepts": [...]}``)."""
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for k in keys:
            inner = value.get(k)
            if isinstance(inner, list):
                return inner
    return []


def _text(value: Any, limit: int = 240) -> str:
    if not isinstance(value, str):
        return ""
    value = value.strip()
    return value if len(value) <= limit else value[: limit - 1] + "…"


def _statement(entry: Any) -> str:
    """A thesis/limitation/question entry rendered as one line."""
    if isinstance(entry, str):
        return entry.strip()
    if isinstance(entry, dict):
        for k in ("statement", "claim_statement", "text", "conclusion", "title"):
            v = entry.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
    return ""


def _concepts_rows(concept_system: Any) -> list[dict]:
    """Flatten the role-grouped concept system into one ordered list."""
    data = decode(concept_system)
    if not isinstance(data, dict):
        return []
    rows: list[dict] = []
    seen: set[str] = set()
    for role in _ROLE_ORDER:
        for entry in _as_list(data.get(role), "concepts"):
            if not isinstance(entry, dict):
                continue
            cid = str(entry.get("concept_id") or entry.get("label") or "")
            if cid and cid in seen:
                continue
            if cid:
                seen.add(cid)
            rows.append(
                {
                    "concept_id": cid,
                    "label": _text(entry.get("label"), 120),
                    "role": role,
                    "final_role": entry.get("final_role"),
                    "confidence": entry.get("confidence"),
                    "definition": _text(entry.get("definition"), 600),
                    "chapter_refs": [str(c) for c in (entry.get("chapter_refs") or [])],
                    "prerequisites": [str(p) for p in (entry.get("prerequisites") or [])],
                    "related_concepts": [str(p) for p in (entry.get("related_concepts") or [])],
                }
            )
    return rows


def _claims_rows(evidence_map: Any) -> list[dict]:
    """Flatten the evidence map into claim rows, supported ones first."""
    data = decode(evidence_map)
    if not isinstance(data, dict):
        return []
    entries = [e for e in _as_list(data.get("entries"), "entries") if isinstance(e, dict)]
    rows = [
        {
            "claim_id": str(e.get("claim_id") or ""),
            "claim": _text(e.get("claim_statement"), 400),
            "is_supported": e.get("is_supported")
            if isinstance(e.get("is_supported"), bool)
            else None,
            "provenance": e.get("provenance"),
            "chapter_ids": [str(c) for c in (e.get("chapter_ids") or [])],
            "evidence_ids": [str(x) for x in (e.get("evidence_ids") or [])],
            "evidence_strengths": e.get("evidence_strengths") or {},
        }
        for e in entries
    ]
    # Supported first, then document order inside each group: the page's first
    # entries should be the claims the book actually stands behind.
    rows.sort(key=lambda r: r["is_supported"] is False)
    return rows


def _in_chapter(refs: Any, chapter: str) -> bool:
    return chapter in {str(c) for c in (refs or [])}


def _thesis_facts(thesis: Any) -> dict:
    data = decode(thesis) or {}
    core = data.get("core_thesis") if isinstance(data, dict) else None
    if not isinstance(core, dict):
        core = {}
    return {
        "core_thesis": _text(core.get("statement"), 1200),
        "core_thesis_provenance": core.get("provenance"),
        "counts": {
            k: len(_as_list(data.get(k), k))
            for k in (
                "conclusions",
                "supporting_theses",
                "key_assumptions",
                "central_questions",
                "problem_statements",
                "limitations",
            )
        }
        if isinstance(data, dict)
        else {},
    }


def _mechanism_facts(mechanism_system: Any) -> dict:
    data = decode(mechanism_system) or {}
    items = _as_list(data.get("mechanisms"), "mechanisms")
    return {"count": len(items) if isinstance(items, list) else 0}


def _argument_facts(argument_system: Any) -> dict:
    data = decode(argument_system) or {}
    out: dict[str, int] = {}
    for k, v in data.items() if isinstance(data, dict) else []:
        if isinstance(v, list):
            out[k] = len(v)
    return out


def _evidence_facts(evidence_map: Any) -> dict:
    data = decode(evidence_map) or {}
    if not isinstance(data, dict):
        return {}
    return {
        "claim_count": len(_as_list(data.get("entries"), "entries")),
        "evidence_coverage": data.get("evidence_coverage"),
        "contradiction_count": data.get("contradiction_count"),
        "model_inference_ratio": data.get("model_inference_ratio"),
        "unsupported_claim_count": data.get("unsupported_claim_count"),
    }


def _chapter_facts(chapter_roles: Any) -> dict:
    data = decode(chapter_roles) or {}
    assignments = _as_list(data.get("assignments"), "assignments")
    per_chapter = []
    for a in assignments:
        if not isinstance(a, dict):
            continue
        per_chapter.append(
            {
                "chapter_id": a.get("chapter_id"),
                "roles": a.get("roles") or [],
                "confidence": a.get("confidence"),
            }
        )
    return {"chapter_count": len(per_chapter), "assignments": per_chapter}


def _list_facts(value: Any) -> dict:
    items = _as_list(decode(value))
    return {"count": len(items), "items": [_text(s, 200) for s in items[:20]]}


def _page(rows: list, limit: int, offset: int) -> tuple[list, int, bool]:
    window = rows[offset : offset + limit] if offset else rows[:limit]
    return window, len(rows), offset + len(window) < len(rows)


def _as_int(value: Any, default: int) -> int:
    """Coerce a parameter to int, falling back when it is not one.

    A handler called directly (tests, another route) receives FastAPI's ``Query``
    default object rather than the parsed value, so ``limit``/``offset`` can
    arrive as something that is not an int. Falling back keeps the default page
    rather than raising a TypeError on the way out.
    """
    return value if isinstance(value, int) and not isinstance(value, bool) else default


def build_synthesis_view(
    row: dict,
    *,
    view: str = "summary",
    limit: int = 50,
    offset: int = 0,
    chapter: str | None = None,
) -> dict:
    """Project ``book_syntheses`` row ``row`` into a bounded response.

    ``row`` is the raw DB row (jsonb values may be text). The returned dict always
    carries ``view`` and ``available_views`` so a client can discover the rest.
    """
    # Normalise every parameter first: a handler may be called directly rather
    # than through FastAPI, in which case `view` is a ``Query`` object and
    # `limit`/`offset` are ``QueryInfo`` rather than ints.
    requested = view if isinstance(view, str) else "summary"
    limit = max(1, _as_int(limit, DEFAULT_CONCEPT_LIMIT))
    offset = max(0, _as_int(offset, 0))
    chapter = chapter if isinstance(chapter, str) and chapter else None
    view = requested.lower()
    known = ("full", "summary", "concepts", "claims")
    if view not in known:
        view = "summary"
    base: dict[str, Any] = {
        "run_id": str(row.get("run_id") or ""),
        "book_id": str(row.get("book_id") or ""),
        "view": view,
        "available_views": list(known),
    }

    if view == "full":
        out = dict(base)
        for f in SYNTHESIS_FIELDS:
            if f in row:
                out[f] = row[f]
        if "created_at" in row:
            out["created_at"] = str(row["created_at"])
        return out

    thesis = decode(row.get("thesis"))
    concepts = _concepts_rows(row.get("concept_system"))
    claims = _claims_rows(row.get("evidence_map"))
    if chapter:
        concepts = [c for c in concepts if _in_chapter(c.get("chapter_refs"), chapter)]
        claims = [c for c in claims if _in_chapter(c.get("chapter_ids"), chapter)]

    if view == "concepts":
        window, total, has_more = _page(concepts, limit, offset)
        base.update(
            {
                "concepts": window,
                "total": total,
                "offset": offset,
                "limit": limit,
                "has_more": has_more,
                "thesis": _thesis_facts(row.get("thesis")),
            }
        )
        return base

    if view == "claims":
        window, total, has_more = _page(claims, limit, offset)
        base.update(
            {
                "claims": window,
                "total": total,
                "offset": offset,
                "limit": limit,
                "has_more": has_more,
            }
        )
        return base

    # summary: the default. Counts and the core thesis, no per-item payloads.
    top = _concepts_rows(row.get("concept_system"))[: limit * 5]
    base.update(
        {
            "thesis": _thesis_facts(row.get("thesis")),
            "problem_definition": _text(decode(row.get("problem_definition")), 2000),
            "counts": {
                "concepts": len(concepts),
                "claims": len(claims),
                "arithmetic_arguments": _argument_facts(row.get("argument_system")),
                "mechanisms": _mechanism_facts(row.get("mechanism_system"))["count"],
            },
            # Not called "evidence_map": that name is the raw 240 KB row field,
            # and a client checking for its absence must be able to tell that
            # the payload was trimmed.
            "claims_summary": _evidence_facts(row.get("evidence_map")),
            "chapters": _chapter_facts(row.get("chapter_roles")),
            "concept_roles": _role_counts(concepts),
            "unresolved_questions": _list_facts(row.get("unresolved_questions")),
            "limitations": _list_facts(row.get("limitations")),
            "author_model": decode(row.get("author_model")),
            "contradictions": decode(row.get("contradictions")),
            # The core concepts in full: a few KB, and the ones a page shows
            # first without a second round trip.
            "core_concepts": [
                {
                    "concept_id": c["concept_id"],
                    "label": c["label"],
                    "role": c["role"],
                    "chapter_refs": c["chapter_refs"],
                }
                for c in top
                if c["role"] in ("core", "foundational")
            ][:limit],
            "_thesis_raw_available": thesis is not None,
        }
    )
    return base


def _role_counts(concepts: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for c in concepts:
        role = c.get("role") or "unknown"
        out[role] = out.get(role, 0) + 1
    return out
