"""Concept CRUD + knowledge graph."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from stratum.changefeed import emit_event
from stratum.common import generate_ulid, jwt_auth, now_utc
from stratum.db import insert, query, read, soft_delete, update

router = APIRouter(prefix="/api/v1/concepts", tags=["concepts"])


class ConceptCreate(BaseModel):
    name: str
    aliases: list[str] = []
    type: str = "concept_idea"
    wikilink: str | None = None
    substrate_refs: list[str] = []


class ConceptUpdate(BaseModel):
    name: str | None = None
    aliases: list[str] | None = None
    substrate_refs: list[str] | None = None


@router.post("")
async def create_concept(body: ConceptCreate, user_id: str = Depends(jwt_auth)):
    cid = generate_ulid()
    insert(
        "concepts",
        {
            "id": cid,
            "user_id": user_id,
            "name": body.name,
            "aliases": body.aliases,
            "wikilink": body.wikilink,
            "type": body.type,
            "substrate_refs": body.substrate_refs,
            "created_at": now_utc(),
        },
    )
    await emit_event(user_id, "concept_create", {"concept_id": cid, "name": body.name})
    return {"concept_id": cid}


@router.get("")
async def list_concepts(user_id: str = Depends(jwt_auth)):
    return query(
        "SELECT * FROM concepts WHERE user_id = %(uid)s AND deleted_at IS NULL ORDER BY name",
        {"uid": user_id},
    )


@router.get("/{concept_id}")
async def concept_detail(concept_id: str, user_id: str = Depends(jwt_auth)):
    concept = read("concepts", concept_id)
    if not concept or concept.get("user_id") != user_id or concept.get("deleted_at"):
        raise HTTPException(404, "Concept not found")

    related_subs = query(
        "SELECT id, title FROM substrates "
        "WHERE $cid = ANY(concept_refs) AND user_id = $uid LIMIT 20",
        {"cid": concept_id, "uid": user_id},
    )
    platform = read("platform_concepts", concept_id)

    return {
        "id": concept["id"],
        "name": concept["name"],
        "type": concept.get("type"),
        "aliases": concept.get("aliases") or [],
        "wikilink": concept.get("wikilink"),
        "platform_view": platform,
        "related_substrates": related_subs,
    }


@router.get("/graph/{concept_id}")
async def concept_graph(concept_id: str, depth: int = 2, user_id: str = Depends(jwt_auth)):
    concept = read("concepts", concept_id)
    if not concept or concept.get("user_id") != user_id or concept.get("deleted_at"):
        raise HTTPException(404, "Concept not found")

    nodes = [{"id": concept_id, "type": "concept", "label": concept["name"]}]
    edges: list[dict] = []

    for rel_id in (concept.get("related_concept_ids") or [])[: depth * 5]:
        rel = read("concepts", rel_id)
        # Only include related concepts owned by the same user
        if rel and rel.get("user_id") == user_id and not rel.get("deleted_at"):
            nodes.append({"id": rel_id, "type": "concept", "label": rel["name"]})
            edges.append({"from": concept_id, "to": rel_id, "type": "related_concept"})

    subs = query(
        "SELECT id, title FROM substrates "
        "WHERE $cid = ANY(concept_refs) AND user_id = $uid LIMIT 20",
        {"cid": concept_id, "uid": user_id},
    )
    for s in subs:
        nodes.append({"id": s["id"], "type": "substrate", "title": s["title"]})
        edges.append({"from": concept_id, "to": s["id"], "type": "references"})

    return {"nodes": nodes, "edges": edges}


@router.put("/{concept_id}")
async def update_concept(concept_id: str, body: ConceptUpdate, user_id: str = Depends(jwt_auth)):
    existing = read("concepts", concept_id)
    if not existing or existing.get("user_id") != user_id or existing.get("deleted_at"):
        raise HTTPException(404, "Concept not found")
    changes = {k: v for k, v in body.model_dump().items() if v is not None}
    if changes:
        update("concepts", concept_id, changes)
    await emit_event(user_id, "concept_update", {"concept_id": concept_id})
    return {"concept_id": concept_id, "status": "updated"}


@router.delete("/{concept_id}")
async def delete_concept(concept_id: str, user_id: str = Depends(jwt_auth)):
    existing = read("concepts", concept_id)
    if not existing or existing.get("user_id") != user_id or existing.get("deleted_at"):
        raise HTTPException(404, "Concept not found")
    soft_delete("concepts", concept_id)
    await emit_event(user_id, "concept_delete", {"concept_id": concept_id})
    return {"concept_id": concept_id, "status": "deleted"}
