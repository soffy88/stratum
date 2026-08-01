"""Directory Builder — viking:// 虚拟文件系统目录树构建.

从现有 Stratum 数据结构构建统一目录树:
  viking://
  ├── resources/          # 文档资源 (substrates)
  │   ├── 数学/
  │   ├── 经济学/
  │   └── ...
  ├── memories/           # 用户长期记忆 (Phase 4)
  │   └── {user_id}/
  ├── sessions/           # 会话 (Phase 4)
  └── skills/             # Agent 技能 (Phase 5)

目录节点携带 L0/L1 摘要, 支持按需加载.
"""

from __future__ import annotations

import logging
from typing import Any

from stratum.db import get_conn

logger = logging.getLogger(__name__)

_URILIB_PREFIX = "viking://"

# ── 学科分类映射 (从现有 discipline_rules.py 和 concept_onto 提取) ────────────

_DISCIPLINE_DIRS: dict[str, str] = {
    "数学": "数学",
    "linear_algebra": "数学/线性代数",
    "calculus": "数学/微积分",
    "probability": "数学/概率统计",
    "optimization": "数学/最优化",
    "differential_equations": "数学/微分方程",
    "topology": "数学/拓扑学",
    "number_theory": "数学/数论",
    "经济学": "经济学",
    "microeconomics": "经济学/微观经济学",
    "macroeconomics": "经济学/宏观经济学",
    "econometrics": "经济学/计量经济学",
    "finance": "经济学/金融学",
    "game_theory": "经济学/博弈论",
    "计算机科学": "计算机科学",
    "machine_learning": "计算机科学/机器学习",
    "algorithms": "计算机科学/算法",
    "data_structures": "计算机科学/数据结构",
    "databases": "计算机科学/数据库",
    "physics": "物理学",
    "philosophy": "哲学",
    "engineering": "工程学",
    "other": "其他",
}


def _gen_id(prefix: str = "dir") -> str:
    import hashlib
    import time
    import random
    raw = f"{prefix}-{time.time()}-{random.randint(0, 999999)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def _slugify(name: str) -> str:
    """Create a URI-safe slug from a name."""
    import re
    # Keep CJK characters, alphanumerics, underscores
    safe = re.sub(r"[^\w\u4e00-\u9fff_]", "_", name)
    return safe.strip("_") or "untitled"


# ── Core operations ──────────────────────────────────────────────────────────

def ensure_directory(parent_uri: str | None, name: str,
                     l0: str | None = None, l1: str | None = None) -> str:
    """Ensure a directory node exists, return its URI.

    Args:
        parent_uri: Parent directory URI (None for root)
        name: Directory name
        l0: One-line abstract
        l1: Structured overview

    Returns:
        The URI of the directory node
    """
    if parent_uri:
        # Strip trailing slash
        parent = parent_uri.rstrip("/")
        uri = f"{parent}/{_slugify(name)}"
    else:
        uri = f"{_URILIB_PREFIX}{_slugify(name)}"

    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id, depth FROM context_directory WHERE uri = ?", (uri,)
        ).fetchone()

        if existing:
            # Update L0/L1 if provided
            if l0 or l1:
                conn.execute(
                    """UPDATE context_directory
                       SET l0_content = COALESCE(?, l0_content),
                           l1_content = COALESCE(?, l1_content),
                           updated_at = NOW()
                       WHERE uri = ?""",
                    (l0, l1, uri),
                )
            return uri

        # Calculate depth
        depth = uri.count("/") - 1 if _URILIB_PREFIX in uri else 0

        # Get parent_id
        parent_id = None
        if parent_uri:
            row = conn.execute(
                "SELECT id FROM context_directory WHERE uri = ?", (parent_uri,)
            ).fetchone()
            parent_id = row[0] if row else None

        node_id = _gen_id("dir")
        conn.execute(
            """INSERT INTO context_directory
               (id, parent_id, uri, node_type, l0_content, l1_content, depth)
               VALUES (?, ?, ?, 'directory', ?, ?, ?)
               ON CONFLICT (uri) DO NOTHING""",
            (node_id, parent_id, uri, l0, l1, depth),
        )

    return uri


def register_substrate(substrate_id: str, title: str,
                       discipline: str | None = None,
                       l0: str | None = None) -> str:
    """Register a substrate in the directory tree.

    Args:
        substrate_id: The substrate ID
        title: Substrate title
        discipline: Auto-detected discipline (from discipline_rules)
        l0: L0 abstract for the substrate node

    Returns:
        The URI of the registered node
    """
    # Determine directory path
    dir_name = _DISCIPLINE_DIRS.get(discipline or "", "其他")
    dir_uri = ensure_directory(f"{_URILIB_PREFIX}resources", dir_name)

    # Create substrate node
    slug = _slugify(title)[:80]
    uri = f"{dir_uri}/{slug}"

    with get_conn() as conn:
        parent_row = conn.execute(
            "SELECT id FROM context_directory WHERE uri = ?", (dir_uri,)
        ).fetchone()
        parent_id = parent_row[0] if parent_row else None

        node_id = _gen_id("sub")
        depth = uri.count("/") - 1

        conn.execute(
            """INSERT INTO context_directory
               (id, parent_id, uri, node_type, ref_id, l0_content, depth)
               VALUES (?, ?, ?, 'substrate', ?, ?, ?)
               ON CONFLICT (uri) DO UPDATE
               SET ref_id = EXCLUDED.ref_id,
                   l0_content = COALESCE(EXCLUDED.l0_content, context_directory.l0_content),
                   updated_at = NOW()""",
            (node_id, parent_id, uri, substrate_id, l0, depth),
        )

    logger.info("directory_builder: registered substrate %s → %s", substrate_id, uri)
    return uri


def register_ku(ku_id: str, title: str, parent_uri: str | None = None,
                l0: str | None = None) -> str:
    """Register a KU in the directory tree."""
    if not parent_uri:
        parent_uri = f"{_URILIB_PREFIX}resources/其他"
        ensure_directory(f"{_URILIB_PREFIX}resources", "其他")

    slug = _slugify(title)[:80]
    uri = f"{parent_uri.rstrip('/')}/{slug}"

    with get_conn() as conn:
        parent_row = conn.execute(
            "SELECT id FROM context_directory WHERE uri = ?", (parent_uri,)
        ).fetchone()
        parent_id = parent_row[0] if parent_row else None

        node_id = _gen_id("ku")
        depth = uri.count("/") - 1

        conn.execute(
            """INSERT INTO context_directory
               (id, parent_id, uri, node_type, ref_id, l0_content, depth)
               VALUES (?, ?, ?, 'ku', ?, ?, ?)
               ON CONFLICT (uri) DO UPDATE
               SET ref_id = EXCLUDED.ref_id,
                   l0_content = COALESCE(EXCLUDED.l0_content, context_directory.l0_content),
                   updated_at = NOW()""",
            (node_id, parent_id, uri, ku_id, l0, depth),
        )

    return uri


# ── Build full tree from existing data ────────────────────────────────────────

def build_initial_tree() -> dict[str, int]:
    """Build the initial directory tree from existing substrates and KUs.

    Returns:
        dict with counts: {directories: N, substrates: N, kus: N}
    """
    counts = {"directories": 0, "substrates": 0, "kus": 0}

    # Create root directories
    for root in ["resources", "memories", "sessions", "skills"]:
        ensure_directory(None, root)
        counts["directories"] += 1

    # Create discipline directories
    seen_dirs: set[str] = set()
    for discipline, path in _DISCIPLINE_DIRS.items():
        parts = path.split("/")
        parent = f"{_URILIB_PREFIX}resources"
        for part in parts:
            uri = ensure_directory(parent, part)
            if uri not in seen_dirs:
                seen_dirs.add(uri)
                counts["directories"] += 1
            parent = uri

    # Register existing substrates — single query with L0 LEFT JOIN (no N+1)
    with get_conn() as conn:
        substrates = conn.execute(
            """SELECT s.id, s.title, COALESCE(s.meta_json->>'discipline', ''),
                      sl.content as l0_content
               FROM substrates s
               LEFT JOIN substrate_layers sl ON s.id = sl.substrate_id AND sl.layer = 'L0'
               WHERE s.title IS NOT NULL
               ORDER BY s.created_at"""
        ).fetchall()

    for sid, title, discipline, l0 in substrates:
        if not title:
            continue
        register_substrate(sid, title, discipline or None, l0)
        counts["substrates"] += 1

    logger.info("directory_builder: built initial tree: %s", counts)
    return counts


# ── Query operations ─────────────────────────────────────────────────────────

def ls(uri: str, depth: int = 1) -> list[dict[str, Any]]:
    """List children of a directory node."""
    with get_conn() as conn:
        # Find the node
        node = conn.execute(
            "SELECT id, node_type, l0_content FROM context_directory WHERE uri = ?",
            (uri.rstrip("/") + "/" if not uri.endswith("/") else uri,)
        ).fetchone()

        if not node:
            # Try exact match
            node = conn.execute(
                "SELECT id, node_type, l0_content FROM context_directory WHERE uri = ?",
                (uri.rstrip("/"),),
            ).fetchone()
        if not node:
            return []

        node_id = node[0]

        if depth == 1:
            children = conn.execute(
                """SELECT uri, node_type, ref_id, l0_content, depth
                   FROM context_directory
                   WHERE parent_id = ?
                   ORDER BY node_type, uri""",
                (node_id,),
            ).fetchall()
        else:
            children = conn.execute(
                """SELECT uri, node_type, ref_id, l0_content, depth
                   FROM context_directory
                   WHERE uri LIKE ? AND depth <= ?
                   ORDER BY depth, uri""",
                (f"{uri.rstrip('/')}%", node[3] if len(node) > 3 else 0 + depth),
            ).fetchall()

    return [
        {
            "uri": c[0],
            "type": c[1],
            "ref_id": c[2],
            "l0": c[3],
            "depth": c[4],
        }
        for c in children
    ]


def tree(uri: str, max_depth: int = 2) -> list[dict[str, Any]]:
    """Get hierarchical tree structure."""
    return ls(uri, depth=max_depth)


def find_node(uri: str) -> dict[str, Any] | None:
    """Find a single node by URI."""
    with get_conn() as conn:
        row = conn.execute(
            """SELECT id, parent_id, uri, node_type, ref_id, l0_content, l1_content, depth
               FROM context_directory WHERE uri = ?""",
            (uri,),
        ).fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "parent_id": row[1],
        "uri": row[2],
        "type": row[3],
        "ref_id": row[4],
        "l0": row[5],
        "l1": row[6],
        "depth": row[7],
    }


def get_stats() -> dict[str, Any]:
    """Get directory tree statistics."""
    with get_conn() as conn:
        total = conn.execute("SELECT count(*) FROM context_directory").fetchone()[0]
        by_type = conn.execute(
            "SELECT node_type, count(*) FROM context_directory GROUP BY node_type"
        ).fetchall()
        max_depth = conn.execute(
            "SELECT COALESCE(MAX(depth), 0) FROM context_directory"
        ).fetchone()[0]
    return {
        "total_nodes": total,
        "by_type": {r[0]: r[1] for r in by_type},
        "max_depth": max_depth,
    }


# ── Grep / Find operations ───────────────────────────────────────────────────

def grep(pattern: str, scope_uri: str = "viking://", layer: str = "L2",
         case_sensitive: bool = False, limit: int = 50) -> list[dict[str, Any]]:
    """Regex search within layer content under a URI scope.

    Args:
        pattern: Regex pattern to match
        scope_uri: Only search under this URI prefix
        layer: Which layer to search (L0, L1, L2)
        case_sensitive: Case-sensitive matching
        limit: Max results

    Returns:
        List of {uri, node_type, ref_id, layer, match, line_number, context}
    """
    import re

    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        regex = re.compile(pattern, flags)
    except re.error as exc:
        logger.warning("grep: invalid regex: %s", exc)
        return []

    scope = scope_uri.rstrip("/")

    with get_conn() as conn:
        # Get all nodes under scope
        nodes = conn.execute(
            """SELECT cd.uri, cd.node_type, cd.ref_id
               FROM context_directory cd
               WHERE cd.uri LIKE ? AND cd.ref_id IS NOT NULL""",
            (f"{scope}%",),
        ).fetchall()

    results = []
    for uri, node_type, ref_id in nodes:
        if not ref_id:
            continue

        # Get layer content
        table = "substrate_layers" if node_type == "substrate" else "ku_layers"
        id_col = "substrate_id" if node_type == "substrate" else "ku_id"

        with get_conn() as conn:
            row = conn.execute(
                f"SELECT content FROM {table} WHERE {id_col} = ? AND layer = ?",
                (ref_id, layer),
            ).fetchone()

        if not row:
            continue

        content = row[0]
        lines = content.split("\n")
        for line_no, line in enumerate(lines, 1):
            if regex.search(line):
                # Get context (2 lines before/after)
                start = max(0, line_no - 3)
                end = min(len(lines), line_no + 2)
                context = "\n".join(lines[start:end])

                results.append({
                    "uri": uri,
                    "node_type": node_type,
                    "ref_id": ref_id,
                    "layer": layer,
                    "match": line.strip()[:200],
                    "line_number": line_no,
                    "context": context[:500],
                })

                if len(results) >= limit:
                    return results

    return results


def find_by_name(name_pattern: str, node_type: str | None = None,
                 limit: int = 50) -> list[dict[str, Any]]:
    """Find nodes by URI name pattern (glob-like).

    Args:
        name_pattern: Substring or glob pattern to match in URI
        node_type: Filter by node type (directory, substrate, ku, etc.)
        limit: Max results

    Returns:
        List of matching nodes with L0 preview
    """
    with get_conn() as conn:
        sql = """SELECT uri, node_type, ref_id, l0_content, depth
                 FROM context_directory
                 WHERE uri ILIKE ?"""
        params: list = [f"%{name_pattern}%"]

        if node_type:
            sql += " AND node_type = ?"
            params.append(node_type)

        sql += " ORDER BY depth, uri LIMIT ?"
        params.append(limit)

        rows = conn.execute(sql, tuple(params)).fetchall()

    return [
        {
            "uri": r[0],
            "type": r[1],
            "ref_id": r[2],
            "l0": r[3],
            "depth": r[4],
        }
        for r in rows
    ]


def find_by_content(query: str, layer: str = "L0", top_k: int = 20,
                    user_id: str = "default") -> list[dict[str, Any]]:
    """Semantic + text search for content. Wraps retrieval_engine with directory context.

    Args:
        query: Natural language query
        layer: Which layer to search
        top_k: Number of results
        user_id: For trajectory logging

    Returns:
        List of results with URI, content preview, score
    """
    from stratum.services.retrieval_engine import retrieve

    # Use retrieval engine which handles vector + text search
    layers_list = [layer]
    response = retrieve(query=query, max_depth=1, top_k=top_k,
                        layers=layers_list, user_id=user_id)

    return [
        {
            "uri": r.uri,
            "node_type": r.node_type,
            "ref_id": r.ref_id,
            "layer": r.layer,
            "score": round(r.score, 4),
            "content_preview": r.content[:300],
        }
        for r in response.results
    ]


def cat(uri: str, layer: str = "L2") -> dict[str, Any] | None:
    """Read full content of a node (alias for fs/read with full content).

    Args:
        uri: viking:// URI
        layer: Layer to read

    Returns:
        {uri, node_type, layer, content, token_count} or None
    """
    node = find_node(uri)
    if not node:
        return None

    ref_id = node.get("ref_id")
    node_type = node.get("type")

    if ref_id and node_type in ("substrate", "ku"):
        table = "substrate_layers" if node_type == "substrate" else "ku_layers"
        id_col = "substrate_id" if node_type == "substrate" else "ku_id"

        with get_conn() as conn:
            row = conn.execute(
                f"SELECT content, token_count FROM {table} WHERE {id_col} = ? AND layer = ?",
                (ref_id, layer),
            ).fetchone()

        if row:
            return {
                "uri": uri,
                "node_type": node_type,
                "ref_id": ref_id,
                "layer": layer,
                "content": row[0],
                "token_count": row[1],
            }

    # Directory node
    content = node.get("l1") or node.get("l0") or ""
    return {
        "uri": uri,
        "node_type": node_type,
        "layer": "L1" if node.get("l1") else "L0",
        "content": content,
        "token_count": len(content) // 4,
    }
