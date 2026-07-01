# AII 知识库高级设计 · 实现规格

> **Doc ID:** AII-KNOWLEDGE-ADVANCED-IMPL-001
> **定位:** AII-KNOWLEDGE-ADVANCED-DESIGN-001（总纲）的**实现细化**。总纲回答"是什么/为什么"，本文回答"怎么落地、按什么顺序、每步做什么数据/算法/验证、命门怎么落到代码"。给 CC 执行用。
> **原则:** 复用已有设计（concept canonical 在 AII-CONCEPT-STORAGE-001、超边在 AII-HYPEREDGE-EXPLAINS-001 已细化），本文**只补衔接和缺失实现**，不重复造。每步**先一本/小范围验证再全量**，命门贯穿。
> **现状实证（写本文前已核实）：**
> - `concept_onto` = 纯名字登记表（name 唯一/别名），**无向量、语义同概念碎成多条**（"price elasticity" 与 "Price Elasticity of Demand" 是两条）。canonical 设计已有（CONCEPT-STORAGE-001），未落地。
> - `hyperedge` / `hyperedge_member` 表 Phase 1 已建（含 status/evidence/cross_disc）。
> - explains 抽取 v1.3 误写 concept_readout_edge，待改写 edge_onto→改写超边。

---

## 〇、实现总览：五个里程碑（严格按依赖顺序）

```
M0  地基：concept canonical 落地        ← P0，上层都依赖，先做
M1  ②层：explains 超边抽取落地（n元，单本忠实）
M2  ②层：超边动态生长（跨章/跨书，严判据，candidate 池）
M3  ③层：跨域关系（motif/结构映射，SME 式⟨M,C,S⟩）  ← 第③层"关系"
M4  ④层：本性 invariant（从第③层提炼共享内核 + 向量收敛，两层互证） ← 第④层"本性"，最审慎
        + 横切：hyperedge_vdb（M1 起需要）
```

**依赖链（为什么这个顺序不能乱）：**
- canonical 不落地 → 超边跨书生长时"同概念被当不同概念" → 长不起来 → 跨域关系/本性发现不了。**所以 M0 必须先。**
- 超边（M1/M2）不积累足够 confirmed 跨学科成员 → motif 挖掘没料。**所以 M3/M4 最后。**
- ★M3（跨域关系）≠ M4（本性）：M3 出的是"base↔target 对应"（关系），M4 是从中提炼"共享内核"（本性）。提炼不出停在 M3 关系（宁停在关系不附会）。
- 每个 M 内部都"先一本验证 → 再全量"。

---

## M0 · 地基：concept canonical 落地（P0）

> 设计已在 AII-CONCEPT-STORAGE-001（扩 6 字段 + nature 表 + 向量化 + 语义归一 + discipline 硬隔离）。本节是**落地步骤 + 验证 + 命门**，不重设计。

### M0.1 步骤
1. **扩 concept_onto**：加 embedding(vector) + level + discipline + nature 关联字段（按 CONCEPT-STORAGE-001 §2.1）。保留 name/name_zh/aliases。
2. **概念向量化**：每个概念名（+ 简短上下文）算 embedding（本地 qwen3-embedding，0 成本）。
3. **语义归一（核心）**：存概念时不只字符串去重，按 §2.3：
   - 同 discipline 内，新概念 embedding 与已有概念比相似度。
   - **≥ 阈值 → 同一概念 → 认已有那条（不新建），补别名 + source 并集。**
   - < 阈值 → 新建。
4. **discipline 硬隔离**：同名不同学科（"function" 数学 vs 编程）靠 discipline 字段硬隔离，**不跨学科合并**（降错合）。
5. **回填 ku_concept_onto**：归一后多条 KU 自然挂到同一唯一概念。

### M0.2 ★验证（在 microecon 现有数据上，看裸真相）
- **碎片消除**："price elasticity" / "Price Elasticity of Demand" / "需求价格弹性" → 归一为一条否？
- **不错合**：语义近但实不同的概念（"price elasticity" vs "income elasticity"）→ **没被错误合并**否？（错合比碎片更危险——错合污染所有上层）
- **阈值实测**：调到"碎片消除 + 不错合"的平衡点（宁可略碎，不可错合——对应命门：宁缺毋附会的概念版）。
- **discipline 隔离**：造同名不同学科样例 → 没合并否。

### M0.3 命门（concept canonical 的"不附会"）
- **错合 = 概念层的附会**：把两个不同概念合成一个 → 上层超边/本性全错。
- **守法**：阈值宁严勿松（错合导向"碎"而非"错合"）；跨学科一律 discipline 硬隔离不合并；存疑的不合并，标候选共指（人工/更多证据再定）。
- 这是 §M2 超边生长"宁缺毋附会"在概念层的前置——**地基就守住不附会，上层才干净。**

---

## M1 · ②层：explains 超边抽取落地（n元，单本忠实）

> 表已建（Phase 1）。本节落抽取 + 写超边 + 改 v1.3 误写。**先不做跨书生长（M2），只做单本内 n元超边忠实抽取。**

### M1.1 抽取改动（4 文件，承 v1.3）
1. **chapter_synthesize.py::_plan**：explains 字段从"单概念"→**"概念列表"**（n元）。每个 rationale 主动抽，配它**联合解释的概念集合**（1 或多）。
2. **chapter_synthesize.py：prompt**：要求 LLM 输出 rationale 的 explains 时，列出**它在本章真解释的所有概念**（n元），并对每个给原文依据。
3. **synthesize_book.py::persist**：
   - 写 `hyperedge`（head_ku_id=rationale, nl_description=机制陈述, evidence, grade=unverified）。
   - 每个被解释概念写一行 `hyperedge_member`（concept_id, source_ku_id, evidence, **status=confirmed**（单本内有原文依据）, cross_disc=false）。
   - **撤掉 v1.3 误写 concept_readout_edge 的 explains。**
4. **readout_all.py**：explains 不再走概念→概念 readout（那是 v1.3 的错）；explains 由 _plan 主动抽 + persist 写超边。readout 保留 derives/subsumes/prerequisite（第①层）。

### M1.2 ★n=1 / n>1 统一落地
- 一个 rationale 解释 1 个概念 → hyperedge_member 一行。
- 解释多个 → 多行。
- **同一份 persist 代码、同一查询**。不写"if 单概念 else 多概念"的分叉。

### M1.3 ★验证（一本书，三项）
1. **n元抽出**：rationale→{概念集合} 抽出否？n=1 和 n>1 都有否（看分布自然否）？
2. **忠于原文（命门）**：抽查几条超边成员 → 每个被解释概念，**原文真的说这个机制解释它**否？（不附会：机制没硬扩到原文没关联的概念）
3. **写对表**：explains 在 hyperedge/hyperedge_member 否（不在 concept_readout_edge、没被 normalize 丢进 ku_internal_logic）？

### M1.4 命门
- **成员只标原文真表达的**（M1 单本内，每个成员有 source_ku_id + evidence）。
- grade 一律 unverified（机制是否真成立留确证，LLM 不标可信度）。
- M1 全 confirmed（单本内有原文直接依据，不涉及跨书匹配的存疑）——**存疑只在 M2 跨书时出现。**

---

## M2 · ②层：超边动态生长（跨章/跨书，严判据，candidate 池）

> 这是超边的**本性**（不是可选）。也是最易**附会**的地方。生长积极 + 判据严，靠 §M2.2 的 5 条统一。

### M2.1 生长流程
```
新 KU 产出一条 explains 超边候选 H_new (head 机制 + 被解释概念)
  → 机制匹配：在已有 hyperedge 里找"同一机制"
       · head 概念相关 + nl_description embedding 相似 ≥ 阈值（粗筛）
       · ★粗筛只是候选，不是判定（防 NL 相似就合并）
  → 对粗筛命中的 H_old，过 5 条严判据（M2.2）
       · 全过 → 给 H_old 加成员（生长）, status 按判据定
       · 不全过 → H_new 独立新建（不强合）
```

### M2.2 ★5 条严判据（= 本性判据的运行时版本，对应 SMT structural consistency）
扩成员到已有超边前，必须全过：
1. **不是 NL 描述相似就合并**（粗筛 embedding 相似只是候选）。
2. **内核同一机制 / 同一推理结构**（同因果结构，非措辞撞）——**由 LLM 判**（程序判不了因果同构）。判 prompt：给两个机制描述 + 各自被解释概念，问"是不是同一个底层机制/推理结构"，要 LLM 给出**结构层面的理由**（不是"听起来像"）。
3. **新成员有原文依据**（source_ku_id + evidence）。
4. **存疑 → status='candidate'**（不自动并入主网）。
5. **跨学科（cross_disc）一律先 candidate**（对应 SMT far analogy 最易附会）。

### M2.3 ★LLM 判不准的导向（关键落地）
- 判据 2（内核同机制）由 LLM 判，LLM 会错（这一段已多次见 LLM 误判）。
- **强制导向**：LLM 判 "同机制" 但**置信不足/跨学科/有疑** → 一律写 **candidate**，不写 confirmed。
- 即：**confirmed 的门槛高（确信同机制 + 原文依据 + 非跨学科或跨学科但极强证据）；其余全进 candidate 池。**
- **把"判错"导向"漏"（candidate 可后续确证/人工），不导向"附会"（错误 confirmed 污染本性网）。**

### M2.4 candidate 池机制
- candidate 成员存在 hyperedge_member（status='candidate'），**不进主网检索/不喂本性挖掘**。
- candidate 是"待确证联结池"：积累更多证据 / 人工确认 → 升 confirmed；长期无证据 → 可清理。
- **本性挖掘（M4）只用 confirmed 成员**——本性建立在确证的跨学科同机制上，不靠 candidate 凑。

### M2.5 ★验证（防附会，最关键）
- **跨章生长**：同章/跨章同机制扩成员，判据严否？抽查扩的成员——原文真支持否？
- **跨书生长**：两本书同机制（如"可替代性"在微观和另一本）→ 正确识别为同机制 confirmed 否？还是误判？
- **附会检测（红线测试）**：故意制造"表面相似实不同"的两个机制 → 系统**没合并**（或进 candidate）否？**这是 M2 的安全网验证**（类比经济飞轮启动前放坏书测拦截）。
- **跨学科保守**：跨学科机制 → 进 candidate 否（没鲁莽 confirmed）？

### M2.6 命门
- **假联结比漏联结危险**：漏的（candidate）后续能补；假的（错误 confirmed）污染整张本性网，且"看起来对"最难发现（跨学科涌现最惊艳最像真）。
- **宁缺毋附会**：确信 → confirmed；存疑 → candidate；跨学科 → 默认 candidate。生长积极但 confirmed 门槛高。

---

## 横切 · hyperedge_vdb（超边向量库，M1 起需要）

### 步骤
- nl_description 向量化（本地 embedding），存 hyperedge.embedding（Phase 1 已留列），建向量索引（pgvector）。
- **生长用**：M2.1 机制粗筛靠这个（找语义近的已有超边）。
- **检索用**：问"某概念为什么" → ① hyperedge_vdb 检索相关机制超边；② 从概念经 hyperedge_member 反查"哪些机制解释我"；③ 双向扩展（机制→它解释的全部概念）。对齐 HyperGraphRAG 双向量库 + 双向扩展。

### 验证
- 检索"弹性的机制" → 返回相关 rationale 超边 + 它联合解释的概念集合否？

---

## M3 · ③层：跨域关系（motif/结构映射，SME 式⟨M,C,S⟩）

> 等 M1/M2 积累足够 confirmed 跨学科超边后才做。**产物是"跨域关系"（base↔target 对应），不是本性**——提炼出共享内核才升 M4。

### M3.1 数据落地（refined_cross_domain_relation，SME 式⟨M,C,S⟩）
- **M correspondences**：base↔target 对应（跨域关系本体）。
- **C candidate_inferences**：从对应推出的候选推断（=AII candidate 池）。
- **S structure_score**：结构质量分。
- + shared_structure、member_concepts/disciplines、invariant_id（→M4，提炼出内核才指向）。
- 详见 AII-REFINED-REPO-SCHEMA-001 §2.7。

### M3.2 ★发现流程（motif 挖掘 + 结构映射）
```
输入：超边-概念二部图（只用 confirmed 成员）
  → motif 统计/高阶聚类 + 结构映射（SME 式）：找反复出现的高阶结构 / base↔target 对应
  → 候选跨域关系：跨 ≥2 学科、有结构对应
  → 落 refined_cross_domain_relation（⟨M,C,S⟩）
  → ★这是"关系"，invariant_id 暂 NULL（停在第③层），等 M4 判是否提炼出内核
```

### M3.3 命门：关系≠本性
- M3 产出的是跨域关系（对应），**不直接认定为本性**。
- 它本身有价值（跨域联结），保留自己信息（⟨M,C,S⟩）。
- 是否升 M4 本性，由 M4 严判（提炼出共享内核才升）。

---

## M4 · ④层：本性 invariant（最后，最审慎）

> 等 M3 跨域关系 + 本性向量收敛积累后做。本性 = 从第③层跨域关系提炼出的"共享抽象内核"。术语：invariant / invariant concept（is_invariant_concept 字段）/ invariant-identity。详见 AII-INVARIANT-LAYER-001。

### M4.1 数据落地（refined_invariant，按 AII-INVARIANT-LAYER-001）
- `refined_invariant`：statement（本性是什么，道非相）+ invariant_vector（带统一标记）+ **is_invariant_concept**（false 普通/true 升华，**不独立建表**）+ member_concept_ids。
- 概念→本性：concept.invariant_id 指向；第③层→本性：cross_domain_relation.invariant_id 指向。
- 本性概念 = WHERE is_invariant_concept=true。

### M4.2 ★两层独立 + 互证
```
层一 本性向量收敛（走语义）：概念抽本性→invariant_vector→收敛→升华
层二 motif 结构（第③层，走拓扑）：M3 的跨域关系
两层独立运行、各保留信息、互相印证：
  都指同一本性 → 高置信；只一层 → 存疑（双重验证防附会）
```
- 升华判据：多概念 invariant_vector 收敛到同一 invariant 且 ≥2 概念共有 → is_invariant_concept=true。

### M4.3 ★本性提取判据（比超边生长更严）
1. 跨 ≥3 个语义远领域（far analogy；单领域是规律不是本性）。
2. 形式各异内核相同（关系结构同）。
3. 两层互证（向量收敛 + motif 结构都指向）。
4. 经得起跨领域变换不变（拓扑不变量式）。
5. **每个支撑是 confirmed**（不靠 candidate 凑本性）。
6. **★抽不出留 NULL，宁标"未发现"不编**：不强凑本性；把定理/平凡组合当本性=附会；存疑→候选本性，不提取。

### M4.4 命门
- 本性是塔尖，错则污染最大 → 判据最严，默认 candidate 确证才认定。
- **关系≠本性**：M3 跨域关系提炼出共享内核才升 M4；提炼不出停在 M3（宁停在关系不附会）。
- **不为"有塔尖"而勉强提取。**

### M4.5 诚实边界
- 大规模真实语料本性自动提取**前沿无人完整做过**——M4 是 AII 最前沿最未验证的部分。
- **最后做、最小步验证、最依赖前几层干净积累。** 初期产出"候选本性"供人工审，不自动认定。

---

## 一、跨里程碑的工程纪律

1. **每个 M 先一本/小范围验证再全量**——防错误形态铺开 357×N 个 KU（已多次踩坑：数分覆盖不全、explains 写错表）。
2. **每个 M 有"红线测试"**（不只测正常，测它该拦的）：
   - M0：放同名不同学科 → 不错合。
   - M2：放表面相似实不同机制 → 不附会（进 candidate/不合并）。
   - M4：放"平凡组合假本性" → 不提取（关系≠本性，不把跨域关系当本性）。
3. **现有表/管道不动**：M0 扩 concept_onto（加字段）、M1-M4 新增表，KU/8步编排/KC/BU 不动。
4. **数学线保持现状**：超边改造在经济线；数学 explains 二元边不强制迁移。
5. **LLM 判断处一律"判错导向漏不导向附会"**：M2 机制同构、M4 本性同构，LLM 判不准→candidate/不提取，绝不→confirmed/本性。
6. **grade 全程 unverified**：机制/本性是否真成立留"确证机制"，抽取阶段 LLM 不标可信度。

---

## 二、依赖关系总图

```
M0 concept canonical ──┬──► M1 超边抽取（同概念跨书才认得出）
（P0 地基）             │
                       └──► M2 超边生长（同概念跨书才合得对）
                                  │
                       hyperedge_vdb（M1起，生长粗筛+检索）
                                  │
                                  ▼
                            M3 跨域关系（motif/结构映射，⟨M,C,S⟩）
                                  │ 提炼出共享内核才升
                                  ▼
                            M4 本性 invariant
                            （两层互证，只用 confirmed，最后做）
```

- **不可逆序**：canonical 不先做，超边生长在错误的概念碎片上跑，越长越错。
- **关系≠本性**：M3 出跨域关系，M4 从中提炼内核才升本性；提炼不出停在 M3（宁停在关系不附会）。
- **本性等积累**：M3/M4 要 M1/M2 产出足够 confirmed 跨学科超边，否则 motif 挖掘没料、挖出来的是噪声。

---

## 三、命门落到代码的清单（实现自检）

| 里程碑 | 命门 | 代码层落地 |
|---|---|---|
| M0 | 概念不错合 | 阈值宁严勿松；discipline 硬隔离；存疑标候选共指 |
| M1 | 成员忠于原文 | 每个 hyperedge_member 有 source_ku_id+evidence；写对表（hyperedge 非 concept_readout_edge） |
| M2 | 联结不附会 | 5 条严判据；LLM 判不准→candidate；跨学科→默认 candidate；红线测试（假相似不合并） |
| M3 | 关系≠本性 | 跨域关系（⟨M,C,S⟩）不直接认定为本性；提炼出内核才升 M4；停在关系 invariant_id=NULL |
| M4 | 本性不编 | ≥3 跨学科+内核同+两层互证+全 confirmed 支撑；抽不出留 NULL，宁标"未发现" |
| 全局 | 看裸真相 | 每 M 先验证再全量；红线测试（测该拦的）；假联结比漏联结危险 |

---

> **一句话**：实现按 **M0 地基（concept canonical）→ M1 超边抽取 → M2 超边生长 → M3 跨域关系 → M4 本性挖掘** 严格依赖顺序推进；每步先小范围验证再全量、每步有红线测试、LLM 判断处一律把判错导向"漏"而非"附会"。地基（概念归一）和塔尖（本性）都守住不附会——中间的超边生长才干净，整个有机体才可置信。

---

*依据：AII-KNOWLEDGE-ADVANCED-DESIGN-001（总纲）+ AII-CONCEPT-STORAGE-001（canonical 设计）+ AII-HYPEREDGE-EXPLAINS-001（超边设计）+ AII-CONCEPT-NATURE-001（本性判据）+ 现状实证（concept_onto 纯名字表/hyperedge 已建/v1.3 误写待改）。前沿：HyperGraphRAG（双向量库/_merge_nodes）、Structure-Mapping Theory（candidate inferences/systematicity）、超图 motif 挖掘（emergent mechanistic patterns）。*
