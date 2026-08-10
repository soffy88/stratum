"""decision_intelligence DAO — decision_ledger / kg_reasoning / provenance_w3c 的
PostgreSQL backend (注入 omodul operator 的 backend 协议)。

- DecisionLedgerBackend: put_decision/get_decision/list_decisions/
  put_relation/list_relations (决策 + 因果链持久化)
- list_concept_triples: 概念图 → (predicate, subject, object) 供 kg_reasoning
- list_provenance: 溯源关系供 provenance_w3c
"""

from __future__ import annotations

import json

from stratum.db import get_conn
from stratum.common import generate_ulid


class DecisionLedgerBackend:
    """omodul.decision_ledger 的 backend 注入 (用户隔离)。"""

    def __init__(self, user_id: str) -> None:
        self.user_id = user_id
        try:
            from omodul.decision_ledger import Decision as _D
            from omodul.decision_ledger import DecisionRelation as _R
            self._Decision = _D
            self._Relation = _R
        except ImportError:  # omodul 未装配时退化 dict (仅测试)
            self._Decision = None
            self._Relation = None

    # ── decisions ───────────────────────────────────────────────────
    def put_decision(self, d) -> None:
        with get_conn() as conn:
            conn.execute(
                """INSERT INTO decision_ledger_decisions
                   (decision_id, user_id, category, scenario, reasoning, outcome,
                    confidence, decision_maker, decision_ts, source_refs, metadata)
                   VALUES (%(id)s, %(uid)s, %(cat)s, %(scn)s, %(rea)s, %(out)s,
                           %(conf)s, %(maker)s, %(ts)s, %(src)s::jsonb, %(meta)s::jsonb)
                   ON CONFLICT (decision_id) DO NOTHING""",
                {
                    "id": d.decision_id, "uid": self.user_id,
                    "cat": d.category, "scn": d.scenario, "rea": d.reasoning,
                    "out": d.outcome, "conf": d.confidence, "maker": d.decision_maker,
                    "ts": d.timestamp,
                    "src": json.dumps(d.source_refs, ensure_ascii=False),
                    "meta": json.dumps(d.metadata, ensure_ascii=False),
                },
            )

    def get_decision(self, decision_id: str):
        with get_conn() as conn:
            row = conn.execute(
                "SELECT decision_id, category, scenario, reasoning, outcome, confidence, "
                "decision_maker, decision_ts, source_refs, metadata "
                "FROM decision_ledger_decisions WHERE user_id=%(uid)s AND decision_id=%(id)s",
                {"uid": self.user_id, "id": decision_id},
            ).fetchone()
        if row is None:
            return None
        return self._to_decision(self._row_to_decision(row))

    def list_decisions(self, limit: int = 500):
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT decision_id, category, scenario, reasoning, outcome, confidence, "
                "decision_maker, decision_ts, source_refs, metadata "
                "FROM decision_ledger_decisions WHERE user_id=%(uid)s "
                "ORDER BY decision_ts DESC LIMIT %(lim)s",
                {"uid": self.user_id, "lim": limit},
            ).fetchall()
        return [self._to_decision(self._row_to_decision(r)) for r in rows]

    def _to_decision(self, d: dict):
        if self._Decision is not None:
            return self._Decision.from_dict(d)
        return d

    @staticmethod
    def _row_to_decision(row) -> dict:
        return {
            "decision_id": row[0], "category": row[1], "scenario": row[2],
            "reasoning": row[3], "outcome": row[4], "confidence": row[5],
            "decision_maker": row[6], "timestamp": str(row[7]),
            "source_refs": row[8] if isinstance(row[8], list) else json.loads(row[8] or "[]"),
            "metadata": row[9] if isinstance(row[9], dict) else json.loads(row[9] or "{}"),
        }

    # ── relations (因果链) ──────────────────────────────────────────
    def put_relation(self, r) -> None:
        with get_conn() as conn:
            conn.execute(
                """INSERT INTO decision_ledger_relations
                   (id, user_id, src_id, dst_id, relationship_type, metadata)
                   VALUES (%(id)s, %(uid)s, %(src)s, %(dst)s, %(typ)s, %(meta)s::jsonb)
                   ON CONFLICT DO NOTHING""",
                {
                    "id": generate_ulid(), "uid": self.user_id,
                    "src": r.src_id, "dst": r.dst_id,
                    "typ": r.relationship_type,
                    "meta": json.dumps(r.metadata, ensure_ascii=False),
                },
            )

    def list_relations(self, limit: int = 500):
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT src_id, dst_id, relationship_type, metadata "
                "FROM decision_ledger_relations WHERE user_id=%(uid)s LIMIT %(lim)s",
                {"uid": self.user_id, "lim": limit},
            ).fetchall()
        out = [
            {
                "src_id": r[0], "dst_id": r[1], "relationship_type": r[2],
                "metadata": json.loads(r[3] or "{}"),
            }
            for r in rows
        ]
        if self._Relation is not None:
            return [self._Relation.from_dict(x) for x in out]
        return out


def list_concept_triples(user_id: str, limit: int = 2000) -> list[list[str]]:
    """概念图 → (predicate, subject, object) triples, 供 kg_reasoning 前向推理。

    实体本身 → (entity, "has_type", type); 关系 → (src, relation_type, dst)。
    """
    triples: list[list[str]] = []
    with get_conn() as conn:
        ents = conn.execute(
            "SELECT id, name, entity_type FROM graph_entities WHERE user_id=%(uid)s LIMIT %(lim)s",
            {"uid": user_id, "lim": limit},
        ).fetchall()
        rels = conn.execute(
            "SELECT source_entity_id, relation_type, target_entity_id "
            "FROM graph_relations WHERE user_id=%(uid)s LIMIT %(lim)s",
            {"uid": user_id, "lim": limit},
        ).fetchall()
    for eid, name, etype in ents:
        triples.append(["has_name", eid, name or ""])
        if etype:
            triples.append(["has_type", eid, etype])
    for src, rtype, dst in rels:
        triples.append([rtype or "related_to", src, dst])
    return triples


def list_provenance(user_id: str, limit: int = 500) -> list[dict]:
    """溯源关系供 provenance_w3c (自动聚合)。"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT kind, src, dst, attrs FROM decision_provenance "
            "WHERE user_id=%(uid)s ORDER BY created_at DESC LIMIT %(lim)s",
            {"uid": user_id, "lim": limit},
        ).fetchall()
    return [
        {"kind": r[0], "src": r[1], "dst": r[2],
         "attrs": json.loads(r[3] or "{}")}
        for r in rows
    ]


def put_provenance(user_id: str, kind: str, src: str, dst: str, attrs: dict | None = None) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO decision_provenance (id, user_id, kind, src, dst, attrs)
               VALUES (%(id)s, %(uid)s, %(k)s, %(s)s, %(d)s, %(a)s::jsonb)""",
            {"id": generate_ulid(), "uid": user_id, "k": kind, "s": src, "d": dst,
             "a": json.dumps(attrs or {}, ensure_ascii=False)},
        )
