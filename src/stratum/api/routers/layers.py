"""L0/L1/L2 内容分层 + viking:// 虚拟文件系统 API.

对标 OpenViking Context Layers + Viking URI protocol.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel


from stratum.common import jwt_auth
from stratum.utils.ownership import fetch_owned_substrate, owner_ids

router = APIRouter(prefix="/api/v1", tags=["layers"])


def _assert_owns_substrate(substrate_id: str, user_id: str) -> dict:
    """404 if substrate missing or not owned by user."""
    row = fetch_owned_substrate(substrate_id, user_id, columns="id, title, source_path, user_id")
    if not row:
        raise HTTPException(404, "Substrate not found")
    return row


def _safe_read_source(source_path: str | None, max_chars: int = 10000) -> str | None:
    """Read local source only if under allowed vault/watch roots."""
    if not source_path:
        return None
    from pathlib import Path as P
    p = P(source_path)
    if not p.exists() or p.suffix.lower() not in (".md", ".txt", ".tex", ".html"):
        return None
    try:
        from stratum.services.vault_sync_service import assert_safe_vault_path
        assert_safe_vault_path(str(p))
    except Exception:
        return None
    try:
        return p.read_text(encoding="utf-8", errors="replace")[:max_chars]
    except Exception:
        return None



# ── Layer generation ─────────────────────────────────────────────────────────

class LayerGenerateRequest(BaseModel):
    substrate_id: str | None = None
    ku_id: str | None = None
    force: bool = False  # regenerate even if layers exist


@router.post("/layers/generate")
async def generate_layers(req: LayerGenerateRequest,
                          user_id: str = Depends(jwt_auth)):
    """Generate L0/L1/L2 layers for a substrate or KU."""
    from stratum.services.layer_generator import (
        generate_substrate_layers_async,
        generate_ku_layers,
        get_substrate_layers,
        get_ku_layers,
    )

    if req.substrate_id:
        owned = _assert_owns_substrate(req.substrate_id, user_id)
        # Check if layers already exist
        if not req.force:
            existing = get_substrate_layers(req.substrate_id)
            if existing.get("L0") and existing.get("L1"):
                return {"status": "exists", "layers": existing}

        title, source_path = owned.get("title"), owned.get("source_path")

        # Read content: prefer exported MD, fall back to safe source_path
        content = None
        from pathlib import Path
        # Check exported MD directory first (shared export pipe)
        _export_dir = Path("/data/shared/stratum-to-aii")
        if _export_dir.exists():
            for md_file in _export_dir.glob(f"*{req.substrate_id}*"):
                if md_file.suffix == ".md":
                    try:
                        content = md_file.read_text(encoding="utf-8", errors="replace")[:10000]
                    except Exception:
                        pass
                    break
        if not content:
            content = _safe_read_source(source_path)

        try:
            layers = await generate_substrate_layers_async(
                req.substrate_id, title=title, content=content,
            )
            return {"status": "generated", "substrate_id": req.substrate_id,
                    "layers": {k: {"length": len(v)} for k, v in layers.items()}}
        except Exception as exc:
            import logging
            logging.getLogger(__name__).exception("Layer generation failed for %s", req.substrate_id)
            raise HTTPException(500, f"Layer generation failed: {exc}")

    elif req.ku_id:
        if not req.force:
            existing = get_ku_layers(req.ku_id)
            if existing.get("L0") and existing.get("L1"):
                return {"status": "exists", "layers": existing}

        # Get KU content from AII backend
        from stratum.db import get_conn
        with get_conn() as conn:
            row = conn.execute(
                "SELECT natural_text, natural_text_zh FROM aii.ku_onto WHERE id = ?",
                (req.ku_id,),
            ).fetchone()
        if not row:
            raise HTTPException(404, "KU not found")

        layers = await asyncio.to_thread(
            generate_ku_layers, req.ku_id, row[0], row[1],
        )
        return {"status": "generated", "ku_id": req.ku_id,
                "layers": {k: {"length": len(v)} for k, v in layers.items()}}

    else:
        raise HTTPException(400, "Must provide substrate_id or ku_id")


@router.get("/layers/substrate/{substrate_id}")
async def get_substrate_layer(substrate_id: str,
                              layer: str = Query("L0", regex="^L[012]$"),
                              user_id: str = Depends(jwt_auth)):
    """Get a specific layer for a substrate (owner only)."""
    from stratum.services.layer_generator import get_substrate_layers
    _assert_owns_substrate(substrate_id, user_id)
    layers = get_substrate_layers(substrate_id)
    if layer not in layers:
        raise HTTPException(404, f"Layer {layer} not found for substrate {substrate_id}")
    return {"substrate_id": substrate_id, "layer": layer, **layers[layer]}


@router.get("/layers/ku/{ku_id}")
async def get_ku_layer(ku_id: str,
                       layer: str = Query("L0", regex="^L[012]$"),
                       user_id: str = Depends(jwt_auth)):
    """Get a specific layer for a KU."""
    from stratum.services.layer_generator import get_ku_layers
    layers = get_ku_layers(ku_id)
    if layer not in layers:
        raise HTTPException(404, f"Layer {layer} not found for KU {ku_id}")
    return {"ku_id": ku_id, "layer": layer, **layers[layer]}


@router.get("/layers/stats")
async def layer_stats(user_id: str = Depends(jwt_auth)):
    """Get layer generation statistics."""
    from stratum.services.layer_generator import get_layer_stats
    return get_layer_stats()


# ── Viking filesystem ────────────────────────────────────────────────────────

@router.get("/fs/ls")
async def fs_ls(uri: str = Query("viking://resources/"),
                depth: int = Query(1, ge=1, le=3),
                user_id: str = Depends(jwt_auth)):
    """List directory contents in the viking:// filesystem."""
    from stratum.services.directory_builder import ls
    children = ls(uri, depth=depth)
    return {"uri": uri, "children": children, "count": len(children)}


@router.get("/fs/tree")
async def fs_tree(uri: str = Query("viking://resources/"),
                  depth: int = Query(2, ge=1, le=4),
                  user_id: str = Depends(jwt_auth)):
    """Get hierarchical tree view."""
    from stratum.services.directory_builder import tree
    nodes = tree(uri, max_depth=depth)
    return {"uri": uri, "nodes": nodes, "count": len(nodes)}


@router.get("/fs/read")
async def fs_read(uri: str,
                  layer: str = Query("L2", regex="^L[012]$"),
                  user_id: str = Depends(jwt_auth)):
    """Read content from a node at a specific layer."""
    from stratum.services.directory_builder import find_node
    from stratum.services.layer_generator import get_substrate_layers, get_ku_layers

    node = find_node(uri)
    if not node:
        raise HTTPException(404, f"Node not found: {uri}")

    if node["type"] in ("substrate", "ku") and node["ref_id"]:
        if node["type"] == "substrate":
            _assert_owns_substrate(node["ref_id"], user_id)
            layers = get_substrate_layers(node["ref_id"])
        else:
            layers = get_ku_layers(node["ref_id"])

        if layer in layers:
            return {"uri": uri, "layer": layer, "node_type": node["type"],
                    "content": layers[layer]["content"],
                    "token_count": layers[layer].get("token_count", 0)}
        else:
            raise HTTPException(404, f"Layer {layer} not available for {uri}")

    # Directory node — return L0/L1 from context_directory
    if layer == "L0" and node.get("l0"):
        return {"uri": uri, "layer": "L0", "node_type": node["type"],
                "content": node["l0"]}
    elif layer == "L1" and node.get("l1"):
        return {"uri": uri, "layer": "L1", "node_type": node["type"],
                "content": node["l1"]}
    else:
        return {"uri": uri, "layer": layer, "node_type": node["type"],
                "content": node.get("l0") or node.get("l1") or ""}


@router.get("/fs/stat")
async def fs_stat(uri: str, user_id: str = Depends(jwt_auth)):
    """Get metadata for a node."""
    from stratum.services.directory_builder import find_node
    node = find_node(uri)
    if not node:
        raise HTTPException(404, f"Node not found: {uri}")
    return node


@router.get("/fs/stats")
async def fs_stats(user_id: str = Depends(jwt_auth)):
    """Get directory tree statistics."""
    from stratum.services.directory_builder import get_stats
    return get_stats()


@router.post("/fs/build")
async def fs_build_tree(user_id: str = Depends(jwt_auth)):
    """Build/rebuild the directory tree from existing data."""
    from stratum.services.directory_builder import build_initial_tree
    counts = await asyncio.to_thread(build_initial_tree)
    return {"status": "built", "counts": counts}


@router.get("/fs/grep")
async def fs_grep(
    pattern: str = Query(..., description="Regex pattern"),
    scope: str = Query("viking://", description="URI scope prefix"),
    layer: str = Query("L2", regex="^L[012]$"),
    case_sensitive: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    user_id: str = Depends(jwt_auth),
):
    """正则搜索 — 在 URI 范围内匹配 layer 内容."""
    from stratum.services.directory_builder import grep
    import re
    if not case_sensitive:
        pattern_ci = pattern  # regex handles IGNORECASE
    results = await asyncio.to_thread(grep, pattern, scope, layer, case_sensitive, limit)
    return {"pattern": pattern, "scope": scope, "layer": layer,
            "matches": results, "count": len(results)}


@router.get("/fs/find")
async def fs_find(
    q: str = Query(..., description="Search query"),
    mode: str = Query("name", regex="^(name|content|semantic)$"),
    node_type: str | None = Query(None),
    layer: str = Query("L0", regex="^L[012]$"),
    limit: int = Query(20, ge=1, le=100),
    user_id: str = Depends(jwt_auth),
):
    """查找节点 — by name (URI), content (text), or semantic (vector)."""
    from stratum.services.directory_builder import find_by_name, find_by_content

    if mode == "name":
        results = await asyncio.to_thread(find_by_name, q, node_type, limit)
    elif mode in ("content", "semantic"):
        results = await asyncio.to_thread(find_by_content, q, layer, limit, user_id)
    else:
        results = []

    return {"query": q, "mode": mode, "results": results, "count": len(results)}


@router.get("/fs/cat")
async def fs_cat(
    uri: str = Query(..., description="viking:// URI"),
    layer: str = Query("L2", regex="^L[012]$"),
    user_id: str = Depends(jwt_auth),
):
    """读取完整内容 (cat file)."""
    from stratum.services.directory_builder import cat
    result = await asyncio.to_thread(cat, uri, layer)
    if not result:
        raise HTTPException(404, f"Content not found: {uri}")
    return result
