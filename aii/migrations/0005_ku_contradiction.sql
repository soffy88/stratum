-- AII 矛盾检测: 记录语义相近但断言冲突的 KU 对.
-- 动机: 规划中的 P0矛盾检测 未实现; 跨书/跨章同主题 KU 若结论相悖应被发现并标记.
-- 候选来自向量近邻(同 P2⑨ 去重的配对), LLM 判定 CONTRADICT 入此表.
-- ku_id 用 TEXT(与 ku_onto 一致, 不用 ku_defeater 的 UUID 旧设计). 幂等.

CREATE TABLE IF NOT EXISTS aii.ku_contradiction (
    id          BIGSERIAL PRIMARY KEY,
    ku_a        TEXT NOT NULL,
    ku_b        TEXT NOT NULL,
    similarity  DOUBLE PRECISION,
    verdict     TEXT NOT NULL,              -- contradict | (judge 其它值不入表)
    rationale   TEXT,
    confidence  DOUBLE PRECISION,
    judged_by   TEXT,                       -- 模型标识
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (ku_a, ku_b)
);

CREATE INDEX IF NOT EXISTS idx_ku_contradiction_a ON aii.ku_contradiction (ku_a);
CREATE INDEX IF NOT EXISTS idx_ku_contradiction_b ON aii.ku_contradiction (ku_b);
