# AII 知识本体落地 · 主库元素 SPEC（Owner SPEC）

> **Doc ID:** AII-ONTOLOGY-MAINLIB-SPEC-001
> **面向:** Owner → 主库 CC（3O 主库 ~/projects/platform/3O，§20：项目 CC 不碰主库）
> **依据:** AII-KNOWLEDGE-ONTOLOGY-002（六分类本体）+ AII-DATA-MODEL-001（数据设计）+ AII-BU-UPGRADE-001（BU 全字段）
> **目的:** 把知识本体落地为主库元素，使六分类抽取 / KU 写入 / 聚类成为主库能力，供 AII（及未来其他项目）消费。
>
> **★ 关键边界（默认，待 Owner 确认）:**
> - **新增不改旧**：主库**新增**六分类元素，**旧元素（`_two_step_ingest` / `register_ku` / `community_cluster`）原样保留**。Helios 等现有消费者零影响。验证成立后其他项目可自行切换。
> - 若 Owner 要"原地改造旧元素让所有项目升级"，结构不变，仅去掉旧接口保留——另行指示。

---

## 〇、本 SPEC 的三部分

1. **数据层**：新表 DDL 规范（六分类 KU / edge / concept / KC / BU），含 enum 全集与约束。
2. **主库元素**：新增的抽取 / 写入 / 聚类元素（oprim/oskill/omodul 层）。
3. **验证**：AII 侧消费新元素，跑一本微观，质量核对。

---

# 第一部分 · 数据层（新表 DDL 规范）

> 列类型、约束、enum 全集已给全，主库 CC 据此写 CREATE TABLE（SQL 由 CC 写，本文是规范）。

## 1.1 enum 全集（受控，不可自由扩展）

```
knowledge_type:   factual | conceptual | positional | procedural | rationale | metacognitive
sub_type:         (conceptual)    classification | principle | theory
                  (procedural)    skill | technique | conditional
                  (metacognitive) strategic | task_knowledge | self_knowledge
                  (其余类型 sub_type 为 NULL)
grade:            unverified | verified | refuted | high | moderate | low | contradicted | pending
grounded_method:  default | formal_proof | source_crosscheck | stance_internal
relation_type:    explains | causes | subsumes | special_case_of | prerequisite_of
                  | contrasts_with | opposes | contradicts | supported_by | same_as
extraction_method: rule | llm | textbook_order
doc_type:         textbook | monograph | popular | paper | lecture
source_credibility: high | medium | low
```

## 1.2 ku 表（六分类，正交轴列化）

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | uuid | PK, default uuidv7() | |
| name | text | NOT NULL | 简短标题 |
| natural_text | text | NOT NULL | 完整陈述 |
| natural_text_zh | text | | 中文译文 |
| symbolic_form | jsonb | | 公式/步骤/命题形式 |
| knowledge_type | text | NOT NULL, CHECK in enum | 六分类 |
| sub_type | text | CHECK in enum or NULL | 细分 |
| is_positional | bool | NOT NULL default false | |
| stance_holder | text | CHECK (is_positional → NOT NULL) | 立场必填 |
| opposing_stance | text | | 对立立场 |
| grade | text | NOT NULL default 'unverified', CHECK in enum | |
| grounded_by | jsonb | NOT NULL default '{"method":"default"}' | 可信度来源链 |
| valid_from | timestamptz | default now() | |
| valid_until | timestamptz | NULL = 当前有效 | |
| superseded_by | uuid | FK ku(id) | 被取代 |
| intuition | text | | 直观/为什么重要 |
| insight | text | | 深层洞察 |
| example | jsonb | | 应用实例（论据降级到此） |
| source | text | | 出处 |
| substrate_id | uuid | | 来源文档 |
| sources | jsonb | default '[]' | 多来源多表述 |
| merge_count | int | default 1 | |
| provenance | jsonb | | chunk_id/抽取方法/全书纲要版本 |
| embedding | vector | | BGE-M3，英文原文算 |
| fingerprint | text | | 去重 |
| created_at / updated_at | timestamptz | default now() | |

**约束要点：**
- `CHECK (NOT is_positional OR stance_holder IS NOT NULL)` —— 立场性必有持有者
- `CHECK (grade <> 'verified' OR grounded_by->>'method' <> 'default')` —— 默认态不得为 verified（grade 铁律）
- 索引：knowledge_type、substrate_id、is_positional、grade、embedding(向量索引)

## 1.3 edge 表（含 explains）

| 列 | 类型 | 约束 |
|---|---|---|
| id | uuid | PK |
| src_id / dst_id | uuid | NOT NULL, FK ku(id) |
| relation_type | text | NOT NULL, CHECK in enum |
| grade | text | default 'unverified', CHECK in enum |
| extraction_method | text | CHECK in enum |
| evidence | jsonb | |
| created_at | timestamptz | default now() |

- `relation_type` 必在受控词表内（治长尾噪声：旧库 22 种自由值的教训）
- `same_as` 不入 edge（触发合并，见 ku.sources）—— 应用层保证
- 索引：(src_id, relation_type)、(dst_id, relation_type)、relation_type

## 1.4 concept + ku_concept（概念复用）

```
concept:    id uuid PK / name text NOT NULL / name_zh text / aliases text[] / created_at
            UNIQUE(name)  —— 同名概念唯一（entity resolution）
ku_concept: ku_id uuid FK / concept_id uuid FK / PRIMARY KEY(ku_id, concept_id)
```

## 1.5 kc 表（知识簇，独立表）

| 列 | 类型 | 约束 |
|---|---|---|
| id | uuid | PK |
| level | int | NOT NULL default 0 |
| community_label | text | |
| summary | text | |
| summary_zh | text | |
| member_ku_ids | jsonb | NOT NULL（KU id 数组） |
| core_concept_id | uuid | FK concept(id) |
| grade | text | CHECK in enum，≤ 成员 KU，**永不最高确证级** |
| synthesis_marker | text | NOT NULL default 'AII综合，非原文断言' |
| parent_kc_id | uuid | FK kc(id) |
| substrate_id | uuid | 所属书（验证期按书聚） |
| created_at / updated_at | timestamptz | |

## 1.6 bu 表（书级理解，独立表，不缩水）

| 列 | 类型 | 来源 |
|---|---|---|
| id | uuid PK | |
| substrate_id | uuid NOT NULL | |
| doc_type | text CHECK in enum | |
| source_credibility | text CHECK in enum | BU-UPGRADE ① |
| problem_statement | text | ② |
| overview_oneline | text | ③ |
| learning_thread | text | ④ |
| applicability | text | ⑤ |
| core_takeaways | jsonb | ⑥ |
| main_claims | jsonb | ⑦ `[{claim,stance_marker,claim_grade,key_ku_ids}]` |
| argument_structure | jsonb | ⑧ `[{point,evidence,evidence_grade,boundary}]` |
| core_explanations | jsonb | ★新增 `[{question,explanation,ku_ids}]`（全书 why） |
| concept_network | jsonb | `{concepts,key_relations}` |
| structure | jsonb | ⑨ 章节骨架(list) |
| key_concept_ku_ids | jsonb | ⑩ |
| positional_summary | jsonb | `{stance,holder,opposing}` |
| grade | text | ≤ 成员 KU，永不最高级 |
| synthesis_marker | text | NOT NULL default 'AII综合，非原文断言' |
| member_kc_ids | jsonb | |
| created_at / updated_at | timestamptz | |

> **BU 全字段对照见 AII-DATA-MODEL-001 §4.3：旧 10 字段 + concept_network + positional_summary 全留，新增 core_explanations。一个不减。**

---

# 第二部分 · 主库新增元素

> 全部**新增**，旧元素保留。命名加 `_v2` 或 `ontology_` 前缀区分（具体命名主库 CC 定）。

## 2.1 oskill：六分类抽取元素（新增 `ontology_extract`）

替代旧 `_two_step_ingest` 的"挑重点"逻辑。**两遍法**（因 deepseek 64K 窗口 < 书 8-10 倍，整本通读不可能）：

**遍 1 · 全书理解纲要（map→汇总）**
```
对每块(~2000字) deepseek 过一遍 → 产出：核心概念候选 / 主题 / 章节归属
汇总 → 全书纲要(轻量，塞进窗口)：章节脉络 / 核心概念清单 / 主线 / 立场基调 / doc_type / source_credibility
```

**遍 2 · 带全局纲要逐块抽 KU（按 §1.4 判据）**
```
每块 + 全书纲要为上下文，要求 deepseek：
 ① 准入闸门：论据/案例→降级为 example 或 supported_by 边；背景/过渡→丢弃
 ② 判六分类(判据优先级)：why→rationale；how→procedural；学/思→metacognitive；
    是什么→ 无真值/持有者相对→positional(填stance_holder/opposing)；本质/原理→conceptual(填sub_type)；可考证→factual
 ③ 拆透：一对象有 是什么/怎么用/为什么 → 拆多个 KU，用 explains/special_case_of/prerequisite_of 连
 ④ ★主动抽 why：每个概念追问机制/原因 → rationale KU + explains 边指向概念 KU
 ⑤ 填字段：grade=unverified, grounded_by.method=default；intuition/insight；关联 concept
 ⑥ 跨块去重：语义重复 → 合并(merge_count++, sources 追加)
```

> **输出契约**：每个 KU 候选返回 §1.2 全部本体字段；每条关系返回 §1.3 受控 relation_type。
> **prompt 内嵌 §1.4 判据表**作为分类依据。
> **本地 qwen 被 [:3000] 截断 → 不用于本元素，全程 deepseek。**

## 2.2 omodul：KU 写入元素（新增 `register_ku_v2`）

旧 `register_ku` 写旧字段。新元素写六分类全字段：
```
- 写 ku 表全部本体列（六分类/立场/grade铁律/时效/intuition/insight）
- 写 ku_concept（概念关联，同名指向同一 concept）
- same_as → 不建边，走合并（更新 sources/merge_count）
- 入库校验：knowledge_type/sub_type/grade/relation_type 必在 enum；立场性必有 holder；grade 默认态不得 verified
- 违规 → 拒绝 + 记 failure_lesson（单一权威入库校验）
```

## 2.3 oskill：聚类元素（验证期复用旧 `community_cluster`）

```
验证期：先用现有 community_cluster(Leiden，不加权) 把 KC 基本聚出来
优化项(验证成立后再做)：community_cluster_weighted —— explains/subsumes/prerequisite_of/special_case_of 高权重，
    使一个概念的 what/how/why 倾向同簇。此项涉及算法改动，验证成立后单独立 SPEC。
KC/BU 综合：deepseek 生成 summary/label；BU 产出 §1.6 全字段(含 core_explanations)；强制 synthesis_marker
```

---

# 第三部分 · 验证（AII 侧消费）

## 3.1 范围
- 书：`Principles_of_Microeconomics_The_Way_We__01KVAJCX.md`（198万字符）
- **只清这一本**相关数据，其余 105 本不动
- 全程 deepseek
- 完整链路：纲要 → 六分类抽 KU → 聚 KC → 综合 BU

## 3.2 质量核对（计数 + 人工抽样）

**计数（SQL）：**
```
六分类分布(无垃圾桶、rationale≠0) / rationale数+explains边数(深度) /
case|example|observation 作独立KU数(应≈0，已降级) / 立场性都有holder /
grade全unverified / intuition·insight填充率 / KC数·avg·max(无巨簇) /
BU全字段非空(尤其 core_explanations)
```

**人工抽样（关键，不只看数）：**
- 10 个 KU：六分类判得**准**吗
- 5 个 rationale：真是"为什么/机制"，不是复述概念
- BU core_explanations：真抓到全书核心 why
- 几个 case 原文：真降级成 example/supported_by

## 3.3 判定
六项达标（无垃圾桶 / explains 建起深度 / 论据降级 / 立场有holder / core_explanations 真 / 抽样准）→ 设计成立 → 才谈全清 106 本量产。
任一不达标 → 改抽取元素对齐判据（判据已定，不改判据）。

---

## 执行边界

- 主库改动走 Owner→主库CC（§20：项目CC不碰主库）
- **新增不改旧**：旧元素保留，Helios 零影响
- AII 项目侧只做：建新表（按第一部分）+ 调用新主库元素 + 清这一本 + 跑验证
- 全程 deepseek；本地 qwen 截断不用
- 每阶段产出报告，Claude 核对再下一步
- ★命门：grade 全 unverified；KC/BU 标 synthesis_marker；论据降级；主动抽 why；enum 受控
- 真环境、报错停

