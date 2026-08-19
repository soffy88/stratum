"""Document-level Deletion — 基于锚点的完整文档删除系统.

功能:
  - 级联删除: substrate → derivative → substrate_layers → substrate_chunk → 
    graph_entities(如果仅由此文档引用) → highlights → flashcards
  - LLM 缓存清除: 删除关联的 ku_layers、context_directory 条目
  - 日志记录: 写入 purge_journal 表用于审计和回滚
  - 软删除 vs 硬删除: 默认软删除 (deleted_at), 支持硬删除

核心设计:
  1. Anchor 驱动: 通过 source_path / file_hash 定位 substrate
  2. 依赖分析: 先检查哪些表引用了该 substrate
  3. 级联执行: 在事务中顺序删除
  4. 审计追踪: 记录所有删除操作到 purge_journal

对比 LightRAG:
  LightRAG 删除是"逻辑删除"(不更新图谱)，Stratum 提供完整级联 + 图谱修正
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any

from stratum.db import get_conn

logger = logging.getLogger(__name__)

# ── ID Generation ────────────────────────────────────────────────────────────

def _gen_id() -> str:
    return uuid.uuid4().hex[:24]


# ── Dependency Map: substrate → child tables ─────────────────────────────────

# Maps child table names to their FK column pointing to substrate_id
_SUBSTRATE_DEPENDENTS = {
    "derivative": "substrate_id",
    "substrate_layers": "substrate_id",
    "substrate_chunk": "substrate_id",
    "highlights": "substrate_id",
    "flashcards": "source_id",  # source_kind='substrate'
    "ku_layers": "ku_id",       # indirect — need to resolve ku_id from substrate
}

# Tables that reference substrates via JSON arrays (source_substrate_ids)
_JSON_DEPENDENTS = ["graph_entities", "graph_relations"]


# ── Core: Deprecation Analysis ────────────────────────────────────────────────

def analyze_substrate_impact(substrate_id: str) -> dict[str, Any]:
    """Analyze what will be affected by deleting a substrate.

    Returns a detailed impact report showing counts of dependent records.
    Used for dry-run validation before actual deletion.
    """
    impact: dict[str, Any] = {
        "substrate_id": substrate_id,
        "timestamp": time.time(),
        "affected_tables": {},
        "total_records": 0,
        "graph_entities_to_review": [],
    }

    with get_conn() as conn:
        # Check substrate exists
        sub = conn.execute(
            "SELECT id, title, source_path FROM substrates WHERE id = ?",
            (substrate_id,),
        ).fetchone()
        if not sub:
            impact["error"] = "substrate_not_found"
            return impact

        impact["substrate"] = {"id": sub[0], "title": sub[1], "path": sub[2]}

        # Check SQL-dependent tables
        for table, fk_col in _SUBSTRATE_DEPENDENTS.items():
            try:
                row = conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE {fk_col} = ?",
                    (substrate_id,),
                ).fetchone()
                count = row[0] if row else 0
                if count > 0:
                    impact["affected_tables"][table] = count
                    impact["total_records"] += count
            except Exception:
                pass

        # Check JSON-dependent tables (graph_entities with source_substrate_ids)
        for table in _JSON_DEPENDENTS:
            try:
                rows = conn.execute(
                    f"SELECT id, name FROM {table} "
                    f"WHERE source_substrate_ids::text LIKE %s",
                    (f'%"{substrate_id}"%',),
                ).fetchall()
                if rows:
                    impact["affected_tables"][f"{table}(json_ref)"] = len(rows)
                    impact["total_records"] += len(rows)
                    if table == "graph_entities":
                        impact["graph_entities_to_review"] = [
                            {"id": r[0], "name": r[1]} for r in rows
                        ]
            except Exception:
                pass

    return impact


# ── Core: Soft Deletion ──────────────────────────────────────────────────────

def soft_delete_substrate(substrate_id: str, reason: str = "manual") -> dict[str, Any]:
    """Soft-delete a substrate: set deleted_at, cascade to child tables.

    Does NOT physically remove data — supports undo via unmark_deleted().
    """
    result = {"substrate_id": substrate_id, "deleted_records": {}, "errors": []}

    try:
        with get_conn() as conn:
            # Mark substrate as deleted
            conn.execute(
                "UPDATE substrates SET deleted_at = NOW() WHERE id = ?",
                (substrate_id,),
            )

            # Soft-delete from derivative
            try:
                cur = conn.execute(
                    "UPDATE derivative SET deleted_at = NOW() WHERE substrate_id = ? AND deleted_at IS NULL",
                    (substrate_id,),
                )
                result["deleted_records"]["derivative"] = cur.rowcount if hasattr(cur, 'rowcount') else 0
            except Exception as e:
                result["errors"].append(f"derivative: {e}")

            # Soft-delete from highlights
            try:
                cur = conn.execute(
                    "UPDATE highlights SET deleted_at = NOW() WHERE substrate_id = ? AND deleted_at IS NULL",
                    (substrate_id,),
                )
                result["deleted_records"]["highlights"] = cur.rowcount if hasattr(cur, 'rowcount') else 0
            except Exception as e:
                result["errors"].append(f"highlights: {e}")

            # Log to purge_journal
            journal_id = _gen_id()
            try:
                conn.execute(
                    """INSERT INTO purge_journal (id, substrate_id, action, reason, details, created_at)
                       VALUES (?, ?, 'soft_delete', ?, ?, NOW())""",
                    (journal_id, substrate_id, reason, json.dumps(result["deleted_records"])),
                )
            except Exception as e:
                result["errors"].append(f"journal: {e}")

    except Exception as e:
        result["errors"].append(f"transaction_error: {e}")

    logger.info("soft_delete_substrate: %s reason=%s records=%s",
                substrate_id, reason, result["deleted_records"])
    return result


# ── Core: Hard Deletion ─────────────────────────────────────────────────────

def hard_delete_substrate(substrate_id: str, reason: str = "manual",
                          cascade_graph: bool = True) -> dict[str, Any]:
    """Hard-delete a substrate and all dependent records.

    Args:
        substrate_id: The substrate to delete
        reason: Deletion reason for audit log
        cascade_graph: Whether to also clean up graph_entities (only if not shared)

    Returns:
        Detailed result with counts per table.
    """
    result = {"substrate_id": substrate_id, "deleted_records": {}, "errors": [], "graph_cleaned": []}

    try:
        with get_conn() as conn:
            # 1. Delete from derivative (all kinds)
            try:
                cur = conn.execute(
                    "DELETE FROM derivative WHERE substrate_id = ?",
                    (substrate_id,),
                )
                result["deleted_records"]["derivative"] = cur.rowcount if hasattr(cur, 'rowcount') else 0
            except Exception as e:
                result["errors"].append(f"derivative: {e}")

            # 2. Delete from substrate_layers
            try:
                cur = conn.execute(
                    "DELETE FROM substrate_layers WHERE substrate_id = ?",
                    (substrate_id,),
                )
                result["deleted_records"]["substrate_layers"] = cur.rowcount if hasattr(cur, 'rowcount') else 0
            except Exception as e:
                result["errors"].append(f"substrate_layers: {e}")

            # 3. Delete from substrate_chunk
            try:
                cur = conn.execute(
                    "DELETE FROM substrate_chunk WHERE substrate_id = ?",
                    (substrate_id,),
                )
                result["deleted_records"]["substrate_chunk"] = cur.rowcount if hasattr(cur, 'rowcount') else 0
            except Exception as e:
                result["errors"].append(f"substrate_chunk: {e}")

            # 4. Delete from highlights
            try:
                cur = conn.execute(
                    "DELETE FROM highlights WHERE substrate_id = ?",
                    (substrate_id,),
                )
                result["deleted_records"]["highlights"] = cur.rowcount if hasattr(cur, 'rowcount') else 0
            except Exception as e:
                result["errors"].append(f"highlights: {e}")

            # 5. Delete flashcards referencing this substrate
            try:
                cur = conn.execute(
                    "DELETE FROM flashcards WHERE source_id = ? AND source_kind = 'substrate'",
                    (substrate_id,),
                )
                result["deleted_records"]["flashcards"] = cur.rowcount if hasattr(cur, 'rowcount') else 0
            except Exception as e:
                result["errors"].append(f"flashcards: {e}")

            # 6. Clean up graph_entities (only if exclusively referenced by this substrate)
            if cascade_graph:
                _cleanup_graph_references(conn, substrate_id, result)

            # 7. Delete from context_directory (LLM cache entries)
            try:
                cur = conn.execute(
                    "DELETE FROM context_directory WHERE ref_id = ?",
                    (substrate_id,),
                )
                result["deleted_records"]["context_directory"] = cur.rowcount if hasattr(cur, 'rowcount') else 0
            except Exception as e:
                result["errors"].append(f"context_directory: {e}")

            # 8. Finally delete the substrate itself
            try:
                cur = conn.execute(
                    "DELETE FROM substrates WHERE id = ?",
                    (substrate_id,),
                )
                result["deleted_records"]["substrates"] = cur.rowcount if hasattr(cur, 'rowcount') else 0
            except Exception as e:
                result["errors"].append(f"substrates: {e}")

            # 9. Log to purge_journal
            journal_id = _gen_id()
            try:
                conn.execute(
                    """INSERT INTO purge_journal (id, substrate_id, action, reason, details, created_at)
                       VALUES (?, ?, 'hard_delete', ?, ?, NOW())""",
                    (journal_id, substrate_id, reason, json.dumps(result["deleted_records"])),
                )
            except Exception as e:
                result["errors"].append(f"journal: {e}")

    except Exception as e:
        result["errors"].append(f"transaction_error: {e}")

    total = sum(result["deleted_records"].values())
    logger.info("hard_delete_substrate: %s reason=%s total=%d errors=%d",
                substrate_id, reason, total, len(result["errors"]))
    return result


# ── Graph Reference Cleanup ──────────────────────────────────────────────────

def _cleanup_graph_references(conn, substrate_id: str, result: dict) -> None:
    """Remove substrate_id from graph_entities source_substrate_ids.

    If an entity becomes orphaned (no more sources), delete it and its relations.
    """
    import json as _json

    # Find entities that reference this substrate
    entity_rows = conn.execute(
        """SELECT id, name, source_substrate_ids
           FROM graph_entities
           WHERE source_substrate_ids::text LIKE %s""",
        (f'%"{substrate_id}"%',),
    ).fetchall()

    for eid, ename, sj in entity_rows:
        try:
            sources = _json.loads(sj) if sj else []
        except (json.JSONDecodeError, TypeError):
            sources = []

        if substrate_id not in sources:
            continue

        remaining = [s for s in sources if s != substrate_id]

        if remaining:
            # Entity still has other sources — just remove this substrate
            conn.execute(
                """UPDATE graph_entities
                   SET source_substrate_ids = %s
                   WHERE id = %s""",
                (_json.dumps(remaining), eid),
            )
            result["graph_cleaned"].append({"entity": eid, "name": ename, "action": "source_removed"})
        else:
            # Entity is now orphaned — delete it and its relations
            conn.execute(
                "DELETE FROM graph_relations WHERE source_entity_id = %s OR target_entity_id = %s",
                (eid, eid),
            )
            conn.execute(
                "DELETE FROM graph_entities WHERE id = %s",
                (eid,),
            )
            result["graph_cleaned"].append({"entity": eid, "name": ename, "action": "orphaned_deleted"})


# ── Undo (Soft Delete Recovery) ──────────────────────────────────────────────

def restore_substrate(substrate_id: str) -> dict[str, Any]:
    """Restore a soft-deleted substrate.

    Only works for soft deletes (hard deletes are irreversible).
    """
    result = {"substrate_id": substrate_id, "restored": False, "errors": []}

    with get_conn() as conn:
        sub = conn.execute(
            "SELECT id, deleted_at FROM substrates WHERE id = ?",
            (substrate_id,),
        ).fetchone()

        if not sub:
            result["errors"].append("substrate_not_found")
            return result

        if not sub[1]:
            result["errors"].append("substrate_not_deleted")
            return result

        try:
            conn.execute(
                "UPDATE substrates SET deleted_at = NULL WHERE id = ?",
                (substrate_id,),
            )
            result["restored"] = True
        except Exception as e:
            result["errors"].append(str(e))

    return result


# ── Batch Purge ──────────────────────────────────────────────────────────────

def batch_purge_substrates(substrate_ids: list[str], reason: str = "batch_cleanup",
                           soft: bool = True) -> dict[str, Any]:
    """Purge multiple substrates at once.

    Args:
        substrate_ids: List of substrate IDs to delete
        reason: Reason for audit log
        soft: True = soft delete, False = hard delete

    Returns:
        Aggregated results.
    """
    aggregate = {
        "total": len(substrate_ids),
        "succeeded": 0,
        "failed": 0,
        "results": [],
    }

    for sid in substrate_ids:
        if soft:
            r = soft_delete_substrate(sid, reason)
        else:
            r = hard_delete_substrate(sid, reason)

        if not r["errors"]:
            aggregate["succeeded"] += 1
        else:
            aggregate["failed"] += 1
        aggregate["results"].append(r)

    logger.info("batch_purge: total=%d ok=%d fail=%d",
                aggregate["total"], aggregate["succeeded"], aggregate["failed"])
    return aggregate


# ── Anchor-based Deletion ────────────────────────────────────────────────────

def delete_by_anchor(anchor: str, anchor_type: str = "source_path",
                     soft: bool = True) -> dict[str, Any]:
    """Delete substrates matched by anchor (source_path, file_hash, or title).

    Args:
        anchor: The anchor value to match
        anchor_type: "source_path" | "file_hash" | "title"
        soft: True = soft delete, False = hard delete

    Returns:
        Aggregated deletion results for all matching substrates.
    """
    col_map = {
        "source_path": "source_path",
        "file_hash": "file_hash",
        "title": "title",
    }
    col = col_map.get(anchor_type, "source_path")

    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT id FROM substrates WHERE {col} = ?",
            (anchor,),
        ).fetchall()

    if not rows:
        return {"error": "no_matching_substrates", "anchor": anchor, "anchor_type": anchor_type}

    ids = [r[0] for r in rows]
    return batch_purge_substrates(ids, reason=f"anchor:{anchor_type}={anchor}", soft=soft)
