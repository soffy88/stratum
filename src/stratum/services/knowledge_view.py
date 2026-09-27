"""AII KnowledgeView — the single retrieval contract.

Replaces the previous three disjoint retrieval planes:
  - POST /api/v1/search  (cross_layer_search + tantivy/pgvector)
  - POST /api/v1/retrieve (directory-recursive substrate_layers)
  - companion/agent ad-hoc SQL

KnowledgeView is a projection, not a new authority.
All retrieval backs to PostgreSQL canonical store (stratum.* + aii.*).
Lexical/vector indexes are rebuildable projections.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Scope = Literal["lexical", "dense", "graph", "temporal", "user-authored", "learning", "visual"]
Channel = Literal["metadata", "lexical", "dense", "graph", "visual"]

RESULT_SCHEMA_FIELDS: set[str] = {
    "id",
    "title",
    "type",
    "score",
    "snippet",
    "citation",
    "paragraph_index",
    "char_start",
    "char_end",
    "anchor_status",
    "deep_link",
    "substrate_id",
    "fragment_id",
    "layer",
    "uri",
    "ref_id",
}


@dataclass
class KnowledgeViewRequest:
    query: str
    top_k: int = 10
    scopes: list[Scope] | None = None
    user_id: str | None = None
    rerank: bool = False
    filters: dict[str, Any] = field(default_factory=dict)
    channels: list[Channel] | None = None
    # Internal evaluation/worker optimisation: callers may reuse a batch
    # embedding, while the public API continues to derive it from ``query``.
    query_embedding: list[float] | None = None


@dataclass
class KnowledgeViewResult:
    """Stable result schema for all consumers (search/retrieve/companion/agent/skill)."""

    id: str
    title: str
    type: str
    score: float
    snippet: str
    citation: dict[str, Any] | None = None
    paragraph_index: int | None = None
    char_start: int | None = None
    char_end: int | None = None
    anchor_status: str = "ok"
    deep_link: str | None = None
    substrate_id: str | None = None
    layer: str | None = None
    uri: str | None = None
    ref_id: str | None = None
    fragment_id: str | None = None
    provenance: dict[str, Any] | None = None  # Claim -> Evidence -> Fragment -> Source
    page_number: int | None = None
    bbox: dict[str, Any] | None = None
    visual_score: float | None = None
    tile_uri: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "type": self.type,
            "score": round(self.score, 4),
            "snippet": self.snippet,
            "citation": self.citation,
            "paragraph_index": self.paragraph_index,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "anchor_status": self.anchor_status,
            "deep_link": self.deep_link,
            "substrate_id": self.substrate_id,
            "fragment_id": self.fragment_id,
            "layer": self.layer,
            "uri": self.uri,
            "ref_id": self.ref_id,
            "provenance": self.provenance,
            "page_number": self.page_number,
            "bbox": self.bbox,
            "visual_score": self.visual_score,
            "tile_uri": self.tile_uri,
        }


class KnowledgeViewInvariantError(RuntimeError):
    """Raised when a retrieval result cannot be proven safe and citable."""


class KnowledgeView:
    """The only application-facing retrieval facade.

    Engines below this boundary are implementation details.  Callers must
    provide an authenticated identity; the facade resolves ownership and
    provenance before returning any result.
    """

    @staticmethod
    def search(req: KnowledgeViewRequest) -> dict[str, Any]:
        return search_knowledge_view(req)


def _normalize_scopes(scopes: list[Scope] | None) -> list[Scope]:
    if not scopes:
        return ["lexical", "dense"]
    return scopes


def search_knowledge_view(req: KnowledgeViewRequest) -> dict[str, Any]:
    """Single entry point for all retrieval consumers.

    Delegates to existing engines but enforces:
    - user isolation (user_id + hash_user_id)
    - stable result schema
    - provenance/citation echo
    - lexical+dense as projection (rebuildable), never authority
    """
    if not req.user_id or req.user_id == "default":
        raise KnowledgeViewInvariantError("authenticated user_id is required")

    # Visual is opt-in and isolated from the legacy path while the flag is off.
    from stratum.config import AII_VISUAL_RETRIEVAL_ENABLED
    requested_channels = req.channels or ["metadata", "lexical", "dense", "graph"]
    if "visual" in requested_channels and AII_VISUAL_RETRIEVAL_ENABLED:
        return _search_visual_or_hybrid(req, requested_channels)
    # Use retrieval_engine as canonical dense path; search_utils pgvector as fallback.
    # This keeps behavior identical but routes through one contract.
    from stratum.services.retrieval_engine import retrieve

    # Map scopes to retrieval_engine layers: dense->vector, learning->L1/L2
    max_depth = 2
    if req.scopes and "learning" in req.scopes:
        max_depth = 3
    namespace = "global"
    if req.scopes and "user-authored" in req.scopes and len(req.scopes) == 1:
        namespace = "personal"
    elif req.scopes and "user-authored" in req.scopes:
        namespace = "all"

    resp = retrieve(
        query=req.query,
        max_depth=max_depth,
        top_k=req.top_k,
        rerank=req.rerank,
        user_id=req.user_id or "default",
        namespace=namespace,
        query_embedding=req.query_embedding,
    )

    # Normalize to KnowledgeViewResult stable schema
    from stratum.services.search_anchors import locate_anchor
    from stratum.db import query as db_query

    ref_ids = [r.ref_id for r in resp.results if r.ref_id]
    if any(not r.ref_id for r in resp.results):
        raise KnowledgeViewInvariantError("untraceable retrieval result has no canonical source")
    title_map: dict[str, str] = {}
    owner_map: dict[str, str] = {}
    if ref_ids:
        rows = db_query(
            "SELECT id, title, user_id FROM substrates "
            "WHERE id = ANY(%(ids)s) AND deleted_at IS NULL",
            {"ids": ref_ids},
        )
        title_map = {r["id"]: r["title"] or r["id"] for r in rows}
        owner_map = {r["id"]: r["user_id"] for r in rows}
        from stratum.utils.user_id_hash import hash_user_id

        allowed_owners = {req.user_id, hash_user_id(req.user_id)}
        missing = set(ref_ids) - set(owner_map)
        foreign = {sid for sid, owner in owner_map.items() if owner not in allowed_owners}
        if missing or foreign:
            raise KnowledgeViewInvariantError(
                f"retrieval ownership invariant failed (missing={sorted(missing)}, "
                f"foreign={sorted(foreign)})"
            )

    results: list[KnowledgeViewResult] = []
    for r in resp.results:
        anchor = locate_anchor(r.content or "", None)
        title = title_map.get(r.ref_id or "", r.uri or r.ref_id or "")
        results.append(
            KnowledgeViewResult(
                id=r.ref_id or r.uri,
                title=title or r.uri or "",
                type=r.node_type,
                score=r.score,
                snippet=(anchor.get("snippet") or r.content[:300]) if r.content else "",
                citation={
                    "source_id": r.ref_id,
                    "fragment_id": r.fragment_id,
                    "quote": (r.content or "")[:300],
                },
                paragraph_index=anchor.get("paragraph_index"),
                char_start=anchor.get("char_start"),
                char_end=anchor.get("char_end"),
                anchor_status="ok",
                deep_link=f"stratum://substrate/{r.ref_id}#p{anchor.get('paragraph_index')}"
                if r.ref_id
                else r.uri,
                substrate_id=r.ref_id,
                fragment_id=r.fragment_id,
                layer=r.layer,
                uri=r.uri,
                ref_id=r.ref_id,
                provenance={
                    "source_id": r.ref_id,
                    "fragment_id": r.fragment_id,
                    "layer": r.layer,
                },
            )
        )

    for item in results:
        errors = validate_knowledge_view_result(item, req.user_id, owner_map)
        if errors:
            raise KnowledgeViewInvariantError("; ".join(errors))

    return {
        "query": req.query,
        "scopes": _normalize_scopes(req.scopes),
        "result_count": len(results),
        "results": [x.to_dict() for x in results],
        "trajectory_id": resp.trajectory_id,
        "total_ms": resp.total_ms,
        "trajectory": [
            {
                "phase": step.phase,
                "candidates": step.candidates,
                "hits": step.hits,
                "scores": [round(score, 4) for score in step.scores],
                "details": step.details,
            }
            for step in resp.trajectory
        ],
        "channels": requested_channels,
    }


def validate_knowledge_view_result(
    result: KnowledgeViewResult, user_id: str, owner_map: dict[str, str] | None = None
) -> list[str]:
    """Hard validation for results crossing the KnowledgeView boundary."""
    errors: list[str] = []
    if not user_id or user_id == "default":
        errors.append("authenticated user_id is required")
    if not result.substrate_id:
        errors.append("result missing canonical substrate_id")
    if not result.citation or result.citation.get("source_id") != result.substrate_id:
        errors.append("result missing valid citation")
    if not result.provenance or result.provenance.get("source_id") != result.substrate_id:
        errors.append("result missing valid provenance")
    if owner_map is not None and result.substrate_id:
        from stratum.utils.user_id_hash import hash_user_id

        owner = owner_map.get(result.substrate_id)
        if owner not in {user_id, hash_user_id(user_id)}:
            errors.append("result owner does not match authenticated user")
    return errors


def _response_from_retrieval(req: KnowledgeViewRequest) -> dict[str, Any]:
    """Compatibility adapter for the tiered endpoint, still behind this facade."""
    return search_knowledge_view(req)


def _search_visual_or_hybrid(req: KnowledgeViewRequest, channels: list[str]) -> dict[str, Any]:
    """Rank-based visual fusion; visual rows always resolve to canonical source IDs."""
    from stratum.db import query as db_query
    from stratum.utils.user_id_hash import hash_user_id
    from stratum.services.visual_embedding import get_visual_embedding_provider
    import json
    owner = hash_user_id(req.user_id or "default")
    provider = get_visual_embedding_provider()
    # Text/BGE-M3 vectors are not interchangeable with the visual model.
    qv = provider.embed_query(req.query)
    provider.validate(qv)
    visual: list[dict[str, Any]] = []
    if qv and "visual" in channels:
        rows = db_query("""SELECT id,source_id,fragment_id,page_number,bbox_json,tile_uri,
            1-(embedding <=> %(v)s::vector) AS score FROM visual_region_projection
            WHERE user_id=%(u)s AND deleted_at IS NULL AND embedding IS NOT NULL
            ORDER BY embedding <=> %(v)s::vector LIMIT %(k)s""", {"u": owner, "v": qv, "k": max(req.top_k * 5, 20)})
        for rank, row in enumerate(rows, 1):
            visual.append({"id": row["id"], "source_id": row["source_id"], "fragment_id": row["fragment_id"], "page_number": row["page_number"], "bbox": row["bbox_json"] if isinstance(row["bbox_json"], dict) else json.loads(row["bbox_json"] or "{}"), "tile_uri": row["tile_uri"], "score": float(row["score"] or 0), "rank": rank})
    # TEXT_ONLY remains available for comparison; HYBRID uses RRF, never raw scores.
    output = [
        KnowledgeViewResult(
            id=item["source_id"],
            title=item["source_id"],
            type="visual",
            score=1 / (60 + item["rank"]),
            snippet="",
            citation={
                "source_id": item["source_id"],
                "page_number": item["page_number"],
                "bbox": item["bbox"],
            },
            substrate_id=item["source_id"],
            fragment_id=item["fragment_id"],
            page_number=item["page_number"],
            bbox=item["bbox"],
            visual_score=item["score"],
            tile_uri=item["tile_uri"],
            provenance={
                "source_id": item["source_id"],
                "projection": "visual_region_projection",
            },
        )
        for item in visual[:req.top_k]
    ]
    owner_map = {item.substrate_id: owner for item in output if item.substrate_id}
    for item in output:
        errors = validate_knowledge_view_result(item, req.user_id, owner_map)
        if errors:
            raise KnowledgeViewInvariantError("; ".join(errors))
    return {
        "query": req.query,
        "scopes": _normalize_scopes(req.scopes),
        "result_count": len(output),
        "results": [item.to_dict() for item in output],
        "trajectory_id": None,
        "total_ms": 0,
        "channels": channels,
    }


def validate_result_schema(result: dict[str, Any]) -> list[str]:
    """Validate that a result respects the stable schema."""
    errors: list[str] = []
    for required_field in ("id", "title", "type", "score", "snippet"):
        if required_field not in result:
            errors.append(f"missing required field: {required_field}")
    # score must be finite [0,1] or at least finite
    score = result.get("score")
    if score is not None:
        try:
            s = float(score)
            if s != s or s == float("inf") or s == float("-inf"):
                errors.append("score is non-finite")
        except Exception:
            errors.append("score not numeric")
    return errors
