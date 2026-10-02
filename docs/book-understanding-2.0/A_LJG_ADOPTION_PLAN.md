# A_LJG ADOPTION PLAN v1.0

TASK=STRATUM_A_LJG_SKILLS_ALIGNMENT_AUDIT
TYPE=PLAN — 未执行
A_BASELINE=P7 / migrations 070..076
上游目标=`lijigang/ljg-skills` @ `d4d39115c8fc7a6baac9f8841f1a6b343e153f07`

---

## 1. 优先级矩阵（审计修正后）

SPEC Phase 7 的矩阵方向正确，但基于「A 在 P4.1、目标只有 5 个技能」两个已失效
的前提。本节按实测修正。

### 1.1 P0 — 必吸收

| 能力 | SPEC 给的理由 | 审计修正 |
|---|---|---|
| ljg-read | 提升 KU 理解质量 | **成立，但要收窄**：`object`/`action` 已在 P3 槽位里，只需 `condition` + `boundary` |
| ljg-book | 提升全书理解 | **降级为 P1**：A 的 `assumption` 需要先给出可判定判据（§1.4） |
| ljg-qa | 验证理解 | **成立，且成本比 SPEC 想的低**：四段与 P3 四项检查同形，是接口改造不是新层 |
| **ljg-paper** | *SPEC 未提及* | **新增 P0**：「证据边界」+「贡献声明核验」是 A仓 目前没有的第五项检查 |
| **ljg-constraint** | *SPEC 未提及* | **新增 P0**：给 `boundary` 一个三层判别（硬/软/自设） |

### 1.2 P1 — 吸收（须先满足约束）

| 能力 | 理由 | 前置条件 |
|---|---|---|
| ljg-is | 机制抽取 | `MECHANISM` 类型已声明，**但必须先有 077 关系层** |
| relation / ljg-map | 图增强 | **双端证据 + 同 source_version + 无 VERIFIED** |
| ljg-structure | 结构发现 | **待语料 ≥2 章**，当前 DEFER |
| **ljg-book (ASSUMPTION)** | 全书前提 | **待可判定判据** |

### 1.3 P2 — 暂缓

ljg-learn（概念解剖/顿悟） · ljg-rank（领域降维） · ljg-think（追本本质） ·
ljg-teach · ljg-relationship · ljg-invest · ljg-word —— 均为 `RESERVE`，属 B/C 域。

### 1.4 不进 A 核心

ljg-card · ljg-plain · ljg-writes · ljg-present · ljg-classic ·
ljg-roundtable · ljg-blind · ljg-push —— `NOT_IN_A`。

其中 **ljg-plain 值得写进记录**：它最像「理解」，但白话改写产出的句子在原书里
不存在，`ANCHORABLE` 恒为 false。它只能是 A仓 冻结 KU 的**下游消费者**，永远
不能回流 A仓。

### 1.5 审计新增的否决项

| 能力 | 理由 |
|---|---|
| `book_question_candidate` | 一本书的「核心问题」是读者的框定，不是书里的一句话 → 解释污染 |
| `a_question_candidate` | 核验输入存成事实行会**反转权威顺序** |

---

## 2. 分阶段计划

每一阶段都是独立可交付的，前一阶段不完成不进入下一阶段。

### Stage 0 — 本次已完成（audit + docs）

```
四道验收门实测通过
24 个技能全部分类
4 张提议表裁定完毕（2 ADOPT / 1 DEFER / 1 REJECT）
DB_MUTATION=0  SCHEMA_CHANGE=0
```

### Stage 1 — `a_insight_candidate`（A P5，无依赖，可立即开始）

吸收 `condition` + `boundary`。**无新关系层，无新依赖。**

```
落点      : ku_candidate 并列的新候选层
来源      : ljg-read 的「有条件的关系」+ ljg-qa 的「边界」+ ljg-constraint 的三层
不新增    : object / action（已在 P3 SemanticIntegrity）
门        : ORPHAN=0 / REPLAY / EXPLAIN / DETERMINISM / NO_MERGE / CONTAMINATION
风险      : 低。唯一新增概念是 condition/boundary，且都可锚定到跨度
```

### Stage 2 — 核验接口改造（ljg-qa + ljg-paper）

不加表。改 P3 的**输出形态**，并新增第五项检查。

```
新增检查  : contribution_check —— 作者声称的贡献 vs 跨度是否支持
来源      : ljg-paper 的「证据边界」与「作者贡献」
输出形态  : 向 ljg-qa 的四段靠拢（结论/形式化/步骤/边界）
风险      : 中。改的是冻结阶段的输出，不改其判定逻辑
前置      : Stage 1 的 boundary 可用（边界需要能被表达）
```

### Stage 3 — `a_relation_candidate`（077）

**必须先实现 R1 双端证据检查，否则不得落表。**

```
R1 双端证据      : from 与 to 各自的证据都必须列出
R2 同 source_version
R3 无 VERIFIED    : 最高状态是 ACCEPTED
R4 追加禁止项     : EQUIVALENT_TO / SAME_AS / 跨版本 CONTRADICTS
风险      : 高。P5 明确排除过这一类关系；本阶段是受约束的逆转，不是扩展
门        : R1 必须有反例测试 —— 见 §3
```

### Stage 4 — `a_mechanism_candidate`（077，与 Stage 3 同迁移）

依赖 Stage 3（`relation_candidate_ids` 指向关系层）。

```
复用      : CandidateType.MECHANISM（已声明）、SemanticIntegrity.anchored
加严      : transition 三槽位必须各自可回指跨度，任一不可锚定则 REJECTED
禁止      : 空字符串通过 NOT NULL
风险      : 中。类型已在 A仓 枚举里，不需新分类学
```

### Stage 5 — `a_assumption_candidate`（078）

前置：给出「前提」的可判定判据（跨度原文含前提 + 前提标记词）。

```
禁止      : book_summary / book_answer / book_truth 直接落库
风险      : 中。前提是原文可陈述的，但判据未定就会产生不可复现的行
```

### Stage 6 — `a_structure_candidate`（待定编号）

前置：**语料扩到第 2 章及以后**。

```
当前      : DEFER。冻结试读语料 1 章 5 节，跨章模式无法验证
禁止      : VERIFIED_PATTERN 进入 A（理由：模式是关于书的结论，不是记录）
风险      : 高
```

---

## 3. Stage 3 必须先有的反例测试

R1 不是承诺，是一个布尔检查。在落表之前，以下探针必须**被拒绝**，且每条都由
真实数据库确认：

| 探针 | 必须被谁拒绝 |
|---|---|
| `SUPPORTS` 只带单端 evidence | `CHECK (jsonb_array_length(evidence_ids) >= 2)` + 服务端双端校验 |
| 跨 source_version 的 `CONTRADICTS` | 服务端同版本校验（schema 无法表达） |
| `relation_type = 'SIMILAR_TO'` | `CHECK` 词表 |
| `relation_type = 'EQUIVALENT_TO'` | `CHECK` 词表（SPEC 原有 3 个 + 追加） |
| `candidate_status = 'VERIFIED'` | `CHECK` 词表 |
| 重放同一关系 | `UNIQUE (relation_hash)` → `ON CONFLICT DO NOTHING` |

其中「跨 source_version 的 `CONTRADICTS`」与「双端证据」**无法由 schema 表达**，
必须在服务层判定并由 gate 读取。这与 A仓 现有的处理方式一致（P6 的
`cross_namespace_collisions()` 同理）。

---

## 4. 每阶段通用门

```
ORPHAN          = 0    每行 evidence 可解析（P7 trace_complete 已实测 11/11）
REPLAY          PASS   NEW_EVIDENCE=0 NEW_KU=0（内容派生 id + ON CONFLICT）
EXPLAIN         100%   source → page → span → extractor_version
DETERMINISM     PASS   同输入同字节
NO_MERGE        PASS   无 dedup / merge / 自动并入
CONTAMINATION   0      导入图 + 产物 + FK 目标（**不扫源码字面量**）
```

**CONTAMINATION 门的实施警告**：按 SPEC 字面扫描 A仓 源码会得到 **24 处假阳性**，
全部是 A仓 自己的守卫清单（`projection.FORBIDDEN_AUTHORITY`、
`projection_builder.ISOLATED_TABLES`）。看到这个数字时的正确动作是**改门**，
不是删守卫。这个陷阱本仓库已记录两次（P4、P6）。

---

## 5. 何时可以说 IMPLEMENTATION_READY=YES

当前是 **NO**。逐阶段就绪度：

| 阶段 | 就绪 | 阻塞项 |
|---|---|---|
| Stage 1 condition/boundary | **YES** | 无 |
| Stage 2 核验接口 + contribution | **YES** | 无 |
| Stage 3 关系层 | **YES** | 无，但 R1 必须先实现 |
| Stage 4 机制 | **YES** | 依赖 Stage 3 |
| Stage 5 前提 | PARTIAL | 需可判定判据 |
| Stage 6 结构 | **NO** | 语料只有 1 章 |

**转 YES 的条件**：Stage 1 与 Stage 2 落地并通过全部门。Stage 3 在 R1 有反例测试
之后可就绪。Stage 5、6 不阻塞 A v0.2。

---

## 6. 明确的执行禁令

> **不要直接把 ljg skills 接入 pipeline。**

理由：A仓 已建立的权威链是
`SourceVersion > Evidence > Verification > Frozen KU`，其中每一步都可反查到
原文跨度与抽取器版本。ljg 的多数技能产出的是**关于书的结论**（顿悟、本质、
白话改写、母题、约束墙），不是**关于书的记录**。把它们直接接入，会让
`ANCHORABLE` 恒为 false 的行进入事实链，而 A仓 的核验只检查锚定与打分，不会
拦住一条锚定良好但语义是重构的行。

**允许的接入形态**：ljg 的**结构方法**作为一个候选生成器，接在
`Evidence → Quality → Verification` 之间，其产出是候选，必须过 P3。

---

## 7. 上游漂移的处理

`ljg-skills` 是一个活跃仓库（227 commits，7.4k stars）。本计划钉在
`d4d39115c8fc7a6baac9f8841f1a6b343e153f07`。

**上游更新时必须重跑本审计的四件事**：

1. 重数技能个数（本次 24）
2. 重读每个技能的**定义原文**（本次以 README 作者原话为准）
3. 重测与 A仓 已存在结构的重叠（本次发现 object/action 已存在、MECHANISM 已声明）
4. 重跑四道验收门

**不要**在没有重跑的情况下沿用本矩阵。矩阵的价值在于它对着一个具体 commit
测过，不在于它写下来了。

A_LJG_ADOPTION_PLAN=PASS
