# AII 抽取验证执行方案：一本微观经济学跑通

> **Doc ID:** AII-EXTRACT-VALIDATION-001
> **目标:** 用一本微观经济学教材，验证「本体六分类 + 通读理解 + explains + KC + BU」整套设计是否成立。
> **依据:** AII-KNOWLEDGE-ONTOLOGY-002（本体）+ AII-DATA-MODEL-001（数据设计/判据）。
> **范围:** 只验证一本，不全量重摄。验证对了再谈全清。
>
> **已定决策:**
> - 验证书：`Principles_of_Microeconomics_The_Way_We__01KVAJCX.md`（198万字符）
> - 模型：全程 **deepseek-chat**（qwen2.5:7b 被 [:3000] 截断，干不了理解，仅留作以后粗活）
> - 清表：**只清这一本相关数据**，不动其余 105 本（验证失败不毁全局）
> - 抽取：**完整链路**——通读理解 → 六分类抽 KU → 聚 KC → 综合 BU，一次验证整套

---

## 硬约束（实证确认，方案据此设计）

- deepseek 窗口 64K tokens ≈ 12–13 万字符；微观 198 万字符 = **窗口的 8–10 倍**。
- **结论：「整本一次通读」物理不可能，分块强制。** 但"通读理解"不等于"整本塞进去"——用**两遍法**实现：先快速过一遍建立全书纲要（轻量，塞得进窗口），再带纲要逐块抽。
- 本地 qwen 被 `prompt[:3000]` 截断 → 连一个块都读不全 → 验证阶段不用，全程 deepseek。

---

## 阶段一：建新表 + 只清这一本（CC 实施）

### 1.1 建新表（按 AII-DATA-MODEL-001，全新结构）

新建符合本体的表（与旧表并存或替换由 CC 判断，但新抽取必须写入新结构）：
- `ku`：六分类 knowledge_type + sub_type + is_positional/stance_holder/opposing_stance + grade/grounded_by + valid_*/superseded_by + intuition/insight/example + sources/merge_count + embedding + natural_text_zh
- `edge`：受控 relation_type（含 `explains`）+ extraction_method + evidence + grade
- `concept` + `ku_concept`：概念复用
- `kc`：知识簇（独立表，level/community_label/summary/member_ku_ids/core_concept_id/grade/synthesis_marker/parent_kc_id）
- `bu`：书级理解（独立表，BU-UPGRADE 全字段 + core_explanations，见数据设计 §4.2）

> grade 默认 `unverified`；KC/BU 强制 `synthesis_marker`。

### 1.2 只清这一本（不全清）

```
# 找到微观这本的 substrate_id
# 删它的 ku / edge / ku_concept / 它产生的 kc / bu
# ingested_substrate 里删它这一行（使其可被重摄）
# ★ 其余 105 本完全不动
```

> 验证阶段绝不全清 106 本。失败也只影响这一本。

---

## 阶段二：两遍法抽取（CC 实施，核心）

### 遍 1：建立全书理解纲要（map → 汇总）

**目的不是抽 KU，是让 AII 先读懂整本书。**

```
对每个块（~2000字）：deepseek 快速过一遍，产出该块的：
  - 涉及的核心概念（concept 候选）
  - 该块在讲什么（主题）
  - 章节归属
汇总所有块 → 一份「全书理解纲要」（轻量，塞得进 64K 窗口）：
  - 全书章节脉络
  - 核心概念清单（去重）
  - 核心论点/主线
  - 立场基调（教材→中立/权威；若有学派倾向则标）
  - doc_type 判定（textbook）+ source_credibility（教材→high）
```

> 这份纲要是遍 2 的全局上下文——**让每个块的抽取都"知道整本书在讲什么"**。这是"通读理解"在窗口限制下的可行实现。

### 遍 2：带全局上下文，逐块抽 KU（按判据表）

```
对每个块（~2000字）：把「全书理解纲要」作为上下文一起给 deepseek，要求：

  ① 准入闸门（数据设计 §六-1）：
     - 论据/案例/故事 → 不单独成 KU，降级为某 KU 的 example 或 supported_by 边
     - 纯背景/过渡 → 丢弃
     - 通过的才成 KU

  ② 判六分类（数据设计 §1.4 判据表，按优先级）：
     - "为什么/机制" → rationale
     - "怎么做" → procedural
     - "怎么学/思考" → metacognitive
     - "是什么"：无确定真值/持有者相对 → positional（填 stance_holder/opposing）
              抽象本质/原理 → conceptual（填 sub_type）
              特定可考证 → factual

  ③ 拆透：一个对象有"是什么/怎么用/为什么" → 拆成多个 KU
     概念KU(是什么) + 程序KU(怎么用) + 解释KU(为什么)
     用 explains / special_case_of / prerequisite_of 边连接

  ④ ★主动抽 why：每个概念都追问——这个概念为什么成立/机制是什么？
     有 → 抽成 rationale KU，建 explains 边指向该概念KU
     这是深度的保证，不能漏

  ⑤ 填本体字段：
     - grade 一律 unverified，grounded_by.method=default
     - intuition（为什么重要/反直觉点）、insight（深层洞察）
     - 关联 concept（写 ku_concept，同名概念指向同一 concept 节点）
     - provenance 记 chunk_id + 全书纲要版本

  ⑥ 跨块去重：新 KU 与已抽 KU 语义重复 → 合并（merge_count++，sources 追加），不新建
```

### 遍 3：聚 KC + 综合 BU

```
KC（数据设计 §三）：
  - 在本书 KU 图上跑 Leiden（oskill.community_cluster）
  - ★ 强本体关系加权：explains/subsumes/prerequisite_of/special_case_of 边给高权重
    → 一个概念的 what/how/why 倾向聚到同簇
  - 每簇 deepseek 生成 summary + community_label
  - 限制每簇最大 KU 数，过大再细分（防巨簇）
  - 标 synthesis_marker，grade ≤ 成员 KU

BU（数据设计 §四，不缩水）：
  - deepseek 综合全书，产出 BU-UPGRADE 全字段：
    source_credibility / problem_statement / overview_oneline / learning_thread
    / applicability / core_takeaways / main_claims(带stance) / argument_structure(evidence不复述+boundary)
    / structure(list) / key_concept_ku_ids / concept_network / positional_summary
  - ★ + core_explanations：全书的核心"为什么"（know-why 内核）
  - 标 synthesis_marker，grade ≤ 成员 KU
```

---

## 阶段三：质量验证（CC 跑完，Claude 核对）

抽完输出**质量报告**，逐项检查设计是否成立：

```sql
-- ① 六分类分布（治 proposition 垃圾桶：不该再有一类独吞、不该有 proposition）
SELECT knowledge_type, count(*) FROM ku WHERE substrate_id=<微观> GROUP BY 1 ORDER BY 2 DESC;
-- 期望：六类都有分布，rationale 不为 0

-- ② ★rationale（why）抽出来没有——深度的关键
SELECT count(*) FROM ku WHERE knowledge_type='rationale' AND substrate_id=<微观>;
SELECT count(*) FROM edge WHERE relation_type='explains';
-- 期望：rationale 有相当数量，explains 边把它们连到概念上（不再是之前的 3 条）

-- ③ 论据降级没有（case/example 不该作为独立 KU）
SELECT count(*) FROM ku WHERE knowledge_type IN('case','example','observation') AND substrate_id=<微观>;
-- 期望：≈0（论据都降级为 example 字段或 supported_by 边）

-- ④ 立场性字段（若有学派内容）
SELECT count(*) FILTER(WHERE is_positional) positional,
       count(*) FILTER(WHERE is_positional AND stance_holder IS NOT NULL) with_holder
FROM ku WHERE substrate_id=<微观>;
-- 期望：positional 的都有 stance_holder（不能裸立场当事实）

-- ⑤ grade 全 unverified（LLM 没乱标可信度）
SELECT grade, count(*) FROM ku WHERE substrate_id=<微观> GROUP BY 1;
-- 期望：几乎全 unverified（确证是后续机制的事）

-- ⑥ 深度字段填充率（intuition/insight 有没有抽）
SELECT count(*) FILTER(WHERE intuition IS NOT NULL) has_intuition,
       count(*) FILTER(WHERE insight IS NOT NULL) has_insight, count(*) total
FROM ku WHERE substrate_id=<微观>;

-- ⑦ KC 质量
SELECT count(*) kc_count, avg(jsonb_array_length(member_ku_ids)) avg_size,
       max(jsonb_array_length(member_ku_ids)) max_size FROM kc;
-- 期望：无巨簇（max 不离谱），有合理数量的主题簇

-- ⑧ BU 完整性（不缩水 + core_explanations）
SELECT source_credibility, problem_statement IS NOT NULL,
       jsonb_array_length(core_takeaways), jsonb_array_length(main_claims),
       jsonb_array_length(core_explanations) FROM bu WHERE substrate_id=<微观>;
-- 期望：全字段都有值，core_explanations 非空（全书 why 抓到了）
```

**人工抽样核对（最关键，不只看计数）：**
- 取 10 个 KU，看六分类**判得对不对**（不是数字对，是分类准）
- 取 5 个 rationale KU，看它**真是"为什么/机制"**，不是把概念复述一遍
- 取 BU 的 core_explanations，看它**真抓到了全书的核心"为什么"**，不是论点罗列
- 取几个 case 原文，确认**降级成了 example/supported_by**，没当独立 KU

---

## 阶段四：判定

**验证成功标准（设计成立）：**
1. 六分类分布合理，无 proposition 垃圾桶，rationale 不为 0
2. explains 边把解释链建起来了（深度有了）
3. 论据降级生效（case 不再当 KU）
4. 立场性都有 holder
5. BU 的 core_explanations 真抓到全书 why
6. 人工抽样：分类准、why 真、降级对

**任一项不达标 → 不是改判据，是改抽取实现（prompt/流程），再验证。** 判据（数据设计）已定，是实现要对齐判据。

**验证成功后**：才谈全清 106 本 + 量产重摄（可能优化模型分流降成本）。

---

## 给 CC 的执行边界

- 全程 deepseek（本地 qwen 截断，不用）
- 只清微观这一本，其余 105 本不动
- 抽取 prompt 严格按数据设计 §1.4 判据表 + §六 准入
- Leiden 在 oskill（community_cluster），强本体关系加权可能要改 oskill —— 若涉及主库，按主库流程（Owner SPEC），不直接改
- 每阶段产出报告，Claude 核对后再下一步（不一口气跑完）
- ★ 命门：grade 全 unverified；KC/BU 标 synthesis_marker；论据降级不当 KU；主动抽 why
- 真环境、报错停

