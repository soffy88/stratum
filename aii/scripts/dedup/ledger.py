"""决策台账 rf.decision_ledger 读写 — B=f(A仓,台账) 可重放的骨架。

纪律:
  · append-only: 只 INSERT, 从不 UPDATE/DELETE 历史行。
  · 修订: 追加一条 supersedes 指向被改的旧决策(不改旧行)。
  · 重放: replay_lookup 命中即返回既有 verdict + llm_raw(不重问模型)。

pair 决策(判同/去重)的 inputs 规约: {"kind":..., "a": <id>, "b": <id>}(a,b 已排序去向)。
"""

from __future__ import annotations
import json


def _pair_inputs(kind: str, a, b) -> dict:
    a, b = sorted((str(a), str(b)))  # 排序 → (a,b) 与 (b,a) 同一决策
    return {"kind": kind, "a": a, "b": b}


class DecisionLedger:
    def __init__(self, conn):
        self.conn = conn

    async def replay_lookup(self, decision_type: str, kind: str, a, b) -> dict | None:
        """查这对是否已有未被取代的决策; 命中返回 {decision_id, verdict, llm_raw, model}(重放, 不重问)。"""
        inp = _pair_inputs(kind, a, b)
        row = await self.conn.fetchrow(
            """
            SELECT decision_id, verdict, llm_raw, model FROM rf.decision_ledger d
            WHERE decision_type=$1 AND inputs->>'a'=$2 AND inputs->>'b'=$3
              AND NOT EXISTS (SELECT 1 FROM rf.decision_ledger s WHERE s.supersedes=d.decision_id)
            ORDER BY decision_id DESC LIMIT 1
            """,
            decision_type,
            inp["a"],
            inp["b"],
        )
        if not row:
            return None
        return {
            "decision_id": row["decision_id"],
            "verdict": json.loads(row["verdict"])
            if isinstance(row["verdict"], str)
            else row["verdict"],
            "llm_raw": row["llm_raw"],
            "model": row["model"],
        }

    async def record(
        self,
        decision_type,
        inputs: dict,
        verdict: dict,
        *,
        evidence=None,
        model=None,
        llm_raw=None,
        actor="llm",
        supersedes=None,
    ) -> int:
        """追加一条决策, 返回 decision_id。verdict/inputs 为 dict(存 jsonb)。"""
        return await self.conn.fetchval(
            """
            INSERT INTO rf.decision_ledger
              (decision_type, inputs, evidence, model, llm_raw, verdict, actor, supersedes)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING decision_id
            """,
            decision_type,
            json.dumps(inputs, ensure_ascii=False),
            json.dumps(evidence, ensure_ascii=False) if evidence is not None else None,
            model,
            json.dumps(llm_raw, ensure_ascii=False) if llm_raw is not None else None,
            json.dumps(verdict, ensure_ascii=False),
            actor,
            supersedes,
        )

    async def record_pair(self, decision_type, kind, a, b, verdict: dict, **kw) -> int:
        return await self.record(decision_type, _pair_inputs(kind, a, b), verdict, **kw)
