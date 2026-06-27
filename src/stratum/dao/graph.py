import json
from stratum.db import get_conn
from stratum.common import generate_ulid


def upsert_entity(user_id: str, name: str, entity_type: str,
                  description: str | None, substrate_id: str) -> str:
    """Insert or merge entity. Returns entity id.

    Matching is case- and whitespace-insensitive so "Deep Learning",
    "deep learning" and " deep learning " collapse onto one node. Cross-lingual
    aliases (中/英) still split — that needs embedding-based merge (follow-up).
    """
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id, mention_count, source_substrate_ids FROM graph_entities "
            "WHERE user_id=? AND LOWER(TRIM(name))=LOWER(TRIM(?))",
            (user_id, name)
        ).fetchone()
        if existing:
            eid, count, sids = existing
            sids_list = json.loads(sids) if sids else []
            if substrate_id not in sids_list:
                sids_list.append(substrate_id)
            conn.execute(
                "UPDATE graph_entities SET mention_count=?, source_substrate_ids=?, "
                "updated_at=NOW() WHERE id=?",
                (count + 1, json.dumps(sids_list), eid)
            )
            return eid
        else:
            eid = generate_ulid()
            conn.execute(
                "INSERT INTO graph_entities "
                "(id, user_id, name, entity_type, description, source_substrate_ids) "
                "VALUES (?,?,?,?,?,?)",
                (eid, user_id, name, entity_type, description,
                 json.dumps([substrate_id]))
            )
            return eid


def upsert_relation(user_id: str, source_id: str, target_id: str,
                    relation_type: str, description: str | None,
                    substrate_id: str, confidence: float = 0.5) -> str:
    """Insert or merge relation."""
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id, source_substrate_ids FROM graph_relations "
            "WHERE user_id=? AND source_entity_id=? AND target_entity_id=? AND relation_type=?",
            (user_id, source_id, target_id, relation_type)
        ).fetchone()
        if existing:
            rid, sids = existing
            sids_list = json.loads(sids) if sids else []
            if substrate_id not in sids_list:
                sids_list.append(substrate_id)
            conn.execute(
                "UPDATE graph_relations SET source_substrate_ids=? WHERE id=?",
                (json.dumps(sids_list), rid)
            )
            return rid
        else:
            rid = generate_ulid()
            conn.execute(
                "INSERT INTO graph_relations "
                "(id, user_id, source_entity_id, target_entity_id, relation_type, "
                "description, source_substrate_ids, confidence) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (rid, user_id, source_id, target_id, relation_type,
                 description, json.dumps([substrate_id]), confidence)
            )
            return rid


def get_entity_neighbors(user_id: str, entity_ids: list[str]) -> list[dict]:
    """Return adjacency list for graph_traversal injection."""
    if not entity_ids:
        return []
    placeholders = ",".join("?" * len(entity_ids))
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT source_entity_id, target_entity_id, relation_type, weight "
            f"FROM graph_relations "
            f"WHERE user_id=? AND source_entity_id IN ({placeholders})",
            (user_id, *entity_ids)
        ).fetchall()
    return [{"source": r[0], "target": r[1], "type": r[2], "weight": r[3]}
            for r in rows]


def query_entities_by_ids(user_id: str, entity_ids: list[str]) -> list[dict]:
    """Fetch entity details by ids."""
    if not entity_ids:
        return []
    placeholders = ",".join("?" * len(entity_ids))
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT id, name, entity_type, description, source_substrate_ids "
            f"FROM graph_entities WHERE user_id=? AND id IN ({placeholders})",
            (user_id, *entity_ids)
        ).fetchall()
    return [{"id": r[0], "name": r[1], "type": r[2],
             "description": r[3], "substrate_ids": json.loads(r[4] or "[]")}
            for r in rows]
