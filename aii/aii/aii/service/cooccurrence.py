"""跨块共现强度 — 纯计算 (0 次 LLM), 独立于边.

★术语表 (AII): 共现 ≠ 边, 正交, 不冒充.
  - 边 (edge_onto): 抽取时 LLM 在块内识别的【真实关系】(explains/causes/...). 有方向, 有语义.
  - 共现 (ku_cooccurrence): 两 KU【共含概念】的联系, 跨块, 纯由"共享几个概念 + 语义多近"算出.
    无方向, 不断言关系, 只表"它们谈同一些概念". 单独存表, 绝不写 edge_onto.

强度分层 (纯计算, 不调 LLM):
  共享 1 个概念              → weak
  共享 ≥2 个概念             → medium
  共享 ≥2 个概念 + 语义近     → strong   (semantic_sim >= sim_threshold)

为什么砍掉 LLM 判: 共享概念对 O(热概念²) 爆炸(整本微观 22.7 万对), 每对一次 LLM 判=不可行;
而"共现"本就不需要 LLM 判真关系 —— 它不是边, 只是共含概念的可计算联系. 几秒算完全量.
"""
from __future__ import annotations

_DDL = """
CREATE TABLE IF NOT EXISTS aii.ku_cooccurrence (
    substrate_id          text NOT NULL,
    ku_a                  text NOT NULL,
    ku_b                  text NOT NULL,
    shared_concept_count  int  NOT NULL,
    semantic_sim          real,
    strength              text NOT NULL,
    PRIMARY KEY (substrate_id, ku_a, ku_b)
);
CREATE INDEX IF NOT EXISTS idx_cooc_sub_strength ON aii.ku_cooccurrence(substrate_id, strength);
"""

# 共享概念跨块对 → 纯计算 shared_count(数) + semantic_sim(pgvector 余弦) + strength(分层).
# 0 次 LLM. ku_a<ku_b 去重, 只跨块(chunk idx 不同).
_COMPUTE = """
WITH pairs AS (
    SELECT a.ku_id AS k1, b.ku_id AS k2, count(*) AS shared
    FROM aii.ku_concept_onto a
    JOIN aii.ku_concept_onto b ON a.concept_id = b.concept_id AND a.ku_id < b.ku_id
    JOIN aii.ku_onto ka ON a.ku_id = ka.ku_id AND ka.substrate_id = $1
    JOIN aii.ku_onto kb ON b.ku_id = kb.ku_id AND kb.substrate_id = $1
    WHERE substring(ka.ku_id from 'ku_c([0-9]+)_') <> substring(kb.ku_id from 'ku_c([0-9]+)_')
    GROUP BY a.ku_id, b.ku_id
)
INSERT INTO aii.ku_cooccurrence (substrate_id, ku_a, ku_b, shared_concept_count, semantic_sim, strength)
SELECT $1, p.k1, p.k2, p.shared, sim,
       CASE WHEN p.shared >= 2 AND sim >= $2 THEN 'strong'
            WHEN p.shared >= 2                THEN 'medium'
            ELSE                                   'weak' END
FROM pairs p
JOIN aii.ku_onto ka ON p.k1 = ka.ku_id
JOIN aii.ku_onto kb ON p.k2 = kb.ku_id
CROSS JOIN LATERAL (SELECT (1 - (ka.embedding <=> kb.embedding))::real AS sim) s
ON CONFLICT (substrate_id, ku_a, ku_b) DO UPDATE SET
    shared_concept_count = EXCLUDED.shared_concept_count,
    semantic_sim = EXCLUDED.semantic_sim,
    strength = EXCLUDED.strength
"""


async def compute_cooccurrence(conn, *, substrate_id: str, sim_threshold: float = 0.80) -> dict:
    """纯计算跨块共现强度并入 ku_cooccurrence (0 LLM). 幂等: 先清本 substrate 再重算."""
    await conn.execute(_DDL)
    await conn.execute("DELETE FROM aii.ku_cooccurrence WHERE substrate_id = $1", substrate_id)
    await conn.execute(_COMPUTE, substrate_id, sim_threshold)
    dist = await conn.fetch(
        "SELECT strength, count(*) n FROM aii.ku_cooccurrence WHERE substrate_id=$1 GROUP BY 1",
        substrate_id)
    total = await conn.fetchval(
        "SELECT count(*) FROM aii.ku_cooccurrence WHERE substrate_id=$1", substrate_id)
    return {"total": total, "by_strength": {r["strength"]: r["n"] for r in dist}}
