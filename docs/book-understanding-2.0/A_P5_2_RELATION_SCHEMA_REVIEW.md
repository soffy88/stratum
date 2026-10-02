# A_P5_2_RELATION SCHEMA REVIEW

TASK=A_P5_2_RELATION_IMPLEMENTATION
PHASE=0 (schema review) — **STOPPED BEFORE WRITING 079**
BASELINE=P5.1_MECHANISM=FROZEN (078), 077=FROZEN, 075=FROZEN
STATUS=BLOCKED_PENDING_DECISION

---

## 0. 一句话结论

`079` 还没写。Phase 0 实测发现 **A仓 已经有一张关系表 `ku_relation`（075，已冻结，2 行）**，
而提案要建**第二张**关系表，词表还与 075 的设计理由**互相矛盾**。
这不是实现细节，它决定「079 值不值得建」，所以按 P5.0 §7 的先例停在这里。

其余 6 条是可实现的偏离，逐条给出实测证据与建议。

## 1. F1 — A仓 已经有关系层（BLOCKER）

```
075_a_ku_evolution.sql 建 stratum.ku_relation，已冻结，2 行：
  krl_9ea8c603c443  ku_10fef8f2ffa4 -> ku_59cb9040d0f0  SHARES_EVIDENCE
  krl_f68440daa5c9  ku_10fef8f2ffa4 -> ku_59cb9040d0f0  REVISES
```

它的注释写得很清楚（075:186-193）：

> Factual relations between two units.
> The vocabulary is the whole design. Every value below is a comparison a
> machine can make by reading two rows — same evidence row, same cited span
> under the same source version, one revises the other.

两套表示的实测差异：

```
                     ku_relation (075, 已冻结)      relation_candidate (提案)
relation_type        SHARES_EVIDENCE /               SUPPORTS / CONTRASTS /
                     SAME_SOURCE_SPAN / REVISES      PRECEDES / DEPENDS_ON
有向性               无向（CHECK from < to 定序）    有向（left/right 各带证据）
source_version_id    无此列                          NOT NULL
同书约束             无此约束（见 F4c）              §4 要求
证据链接             0 列                            relation_evidence 双侧
UNIQUE               (from,to,type) + hash           hash only
```

词表**完全不相交**。结果是 A仓 将同时存在两套关系词表，
而没有任何规则说明一个「关系」该写进哪一张。

## 2. F2 — `SUPPORTS` / `CONTRASTS` 与 075 的授权理由冲突（BLOCKER）

075 拒绝这些词，理由写在迁移自己的注释里（075:189-192）：

> There is no value meaning "these say the same thing" or "these are in
> tension', because deciding either is a semantic judgement: it belongs to
> B仓, and A仓 has no authority to make it.

而提案 §7：

- `SUPPORTS` = 「文本明确支持另一事实」
- `CONTRASTS` = 「两个对象存在明确差异/对比」

这正是 075 说「属于 B仓、A仓 无权判断」的那一类判断。
提案 §2 禁止 `CAUSES/PROVES/EXPLAINS/IMPLIES/VALIDATES` 是对的，
但 `CONTRASTS` 与 075 被拒的「in tension」是同一件事，只是换了个词。

四个词里 **`PRECEDES` 最稳**：页序/章节序是机器可读的，
与 075 允许的 SAME_SOURCE_SPAN 同级——这是「读两行就能比」的事实。

## 3. F3 — `status` 与 `side` 可为 NULL，CHECK 被绕过

§3.1 写 `status TEXT`（**没有 NOT NULL**），§5.1 写 `side TEXT`（同样）。
实测（临时表，与 P5.1 的 `array_length` 同一类漏洞）：

```
CREATE TEMP TABLE p_status (id text primary key,
  status text CHECK (status IN ('GENERATED','SUPPORTED','REJECTED')));
INSERT INTO p_status VALUES ('a', NULL);
=> rows inserted with NULL status = 1      -- CHECK 在 NULL 上通过

CREATE TEMP TABLE p_side (id text primary key,
  side text CHECK (side IN ('LEFT','RIGHT')));
INSERT INTO p_side VALUES ('a', NULL);
=> rows inserted with NULL side = 1
```

一个 `status IS NULL` 的关系能进库，且绕开整个词表。
078 的 `mechanism_candidate.status` 是 `NOT NULL`，这里应一致。

**建议**：`status TEXT NOT NULL DEFAULT 'GENERATED'`、
`side TEXT NOT NULL`。

## 4. F4 — §4 同书约束：§10 声称 DB 保证，实测不保证

§10 写「Database guarantees: source_version consistency」，
§4 要求 left/right 同 `source_version_id`。**按 §3.1 的 schema 做不到。**

实测：

```
-- §3.1 原样：两个单列 FK + 一个 source_version FK
两个 unit id 都真实存在，但 source_version_id 谎报另一本书
=> single FK accepted a cross-book pair = 1        -- 跨书关系被接受
```

CHECK 也救不了：

```
CHECK ((SELECT source_version_id FROM knowledge_unit WHERE id = l) = ...)
=> ERROR: cannot use subquery in check constraint
```

两条可行出路，都已实测通过：

**(A) 复合外键**（声明式）
```
CREATE UNIQUE INDEX ... ON knowledge_unit (id, source_version_id);   -- 冻结表上加索引
FOREIGN KEY (left_knowledge_unit_id, source_version_id)
  REFERENCES knowledge_unit (id, source_version_id)
同书对：accepted = 1
跨书对：ERROR violates foreign key constraint (l, source_version_id)
```
代价：给 073 冻结的 `knowledge_unit` 加一个索引。
注：`(id, source_version_id)` 的唯一性本就由 `id` 主键保证，
这个索引纯粹是 FK 的落地目标，不承担唯一性风险，只增加写放大。

**(B) 触发器**（只在**新表**上）
```
knowledge_unit 新增索引 = 0            -- 冻结表完全不动
同书对：accepted = 1
跨书对：ERROR cross-book relation: unit ku_15a527238f5c is not of source_version sv_probe2
```
代价：A仓 至今**没有任何 trigger 或 function**：
```
grep -c "CREATE TRIGGER|CREATE FUNCTION" 07*.sql  =>  全部 0
```
079 会是 A仓 第一个触发器，且 PL/pgSQL 函数是会漂移的代码。

**(C) 只做服务层门**，与 P5.1 的 `KNOWN_LIMITATION 5` 同级。
诚实，但等于承认 §10 那行字是错的。

**顺带一个实测发现（关于已冻结的 075）**：
`ku_relation` 既没有 `source_version_id` 列，也没有同书约束，实测能写入跨书对。
也就是说 **079 会给新表补上 075 缺的那道约束**——这是 079 的真实价值之一，
但也意味着两表的严格程度从此不同。

## 5. F5 — §6 双侧证据无法由 DB 保证

实测：`UNIQUE(relation_id, side)` 能挡住「两个 LEFT」，但挡不住「只有 LEFT」。

```
两个 LEFT 行：accepted = 1  ->  再插一个 LEFT 被 ev_side_uniq 拒绝
只有 LEFT 的关系：accepted（有 RIGHT 的行数 = 0）
```

**建议**：加 `UNIQUE(relation_id, side)`（DB 保住「至多一侧」，
排除双 LEFT 这种畸形态），「恰好两侧」仍由服务层保证，
与 §11 的写入事务一起冻结为已知限制。

## 6. F6 — 没有状态机守卫（与 P5.1 同级）

P5.1 实测过 `UPDATE ... SET status` 可以绕过 writer。
079 同理：`GENERATED → SUPPORTED → GENERATED` 直连 SQL 可写。
§9 的终态 `SUPPORTED` 是**约定**，不是约束。建议照 P5.1 的写法冻结为已知限制。

## 7. F7 — 重放需要决定有向性

§12「Existing hash: NOOP」成立与否，取决于方向算不算同一件事：

- `ku_relation` 用 `CHECK (from < to)` 把无向对定序，重放不会写出镜像。
- P5.2 的 left/right **各自带证据**，`SUPPORTS(A,B)` 与 `SUPPORTS(B,A)`
  证据不同、hash 不同，是两个不同的关系——这是对的。

但 `UNIQUE(relation_hash)` **挡不住** A→B 与 B→A 同时存在。
需要你决定是否接受，还是加一条方向互斥的约束。

## 8. F8 — `created_at` 缺 DEFAULT（housekeeping）

实测 17 张 A 表：`DEFAULT now()` 13 张，`NO DEFAULT` 4 张——
恰好是 P5.0 与 P5.1 建的 4 张（077 两张、078 两张）。
没有 DEFAULT 意味着漏写该列的 INSERT 直接失败（077 上线时踩过这个坑）。

**建议 079 用 `DEFAULT NOW()`**，与多数一致，也让人工执行的 SQL 不易踩坑。

## 9. 建议的 079 骨架（在 F1/F2 决定之前不写）

```
relation_candidate
  id                     TEXT PK
  source_version_id      TEXT NOT NULL  FK -> source_version       RESTRICT
  left_knowledge_unit_id TEXT NOT NULL  FK -> knowledge_unit       RESTRICT
  right_knowledge_unit_id TEXT NOT NULL FK -> knowledge_unit       RESTRICT
  relation_type          TEXT NOT NULL  CHECK IN (4 词)
  status                 TEXT NOT NULL DEFAULT 'GENERATED'
                                   CHECK IN (GENERATED/SUPPORTED/REJECTED)
  relation_hash          TEXT NOT NULL  UNIQUE
  extractor_version      TEXT NOT NULL
  created_at             TIMESTAMP NOT NULL DEFAULT NOW()
  CHECK (left_knowledge_unit_id <> right_knowledge_unit_id)     -- 可 DB 保证
  (+ F4 的 (A) 或 (B)，待你选)

relation_evidence
  id            TEXT PK
  relation_id   TEXT NOT NULL FK -> relation_candidate          RESTRICT
  side          TEXT NOT NULL CHECK IN (LEFT/RIGHT)
  knowledge_unit_id TEXT NOT NULL FK -> knowledge_unit          RESTRICT
  evidence_ids  TEXT[] NOT NULL CHECK (cardinality(evidence_ids) >= 1)
  created_at    TIMESTAMP NOT NULL DEFAULT NOW()
  UNIQUE (relation_id, side)                                   -- F5 部分保证
```

自反关系实测可保证：`CHECK (l <> r)` 拒绝了 `('a','ku_x','ku_x')`。

## 10. 需要你决定的四件事

1. **F1/F2**：`relation_candidate` 与已冻结的 `ku_relation` 是什么关系？
   并行第二套词表 / 收窄 079 只做 `PRECEDES` / 停 P5.2 回头修 075 /
   其它。
2. **F4**：同书约束走 (A) 复合外键（动冻结表一个索引）、(B) 触发器（A仓 首个）、
   还是 (C) 服务层门 + 如实改掉 §10 那行字。
3. **F7**：`SUPPORTS(A,B)` 与 `SUPPORTS(B,A)` 并存是否可接受。
4. **F3/F5/F8** 是否照建议改（都是把提案收紧，不放宽）。