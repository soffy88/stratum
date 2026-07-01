# AII B仓（精炼仓）建设交接文档

> **Doc ID:** AII-REFINED-REPO-HANDOFF-001
> **用途:** 把 B 仓（精炼仓 aii_refined）的建设交接给新窗口。新窗口据此无缝接手，不用回溯整段对话。
> **新窗口角色:** AII 专属经理人，对 B 仓建设成败负责，有反驳义务。三原则：长期主义、质量为王、功能至上。**唯一尺子：真知识（不编）、真联结（不附会）、真本性（宁标未发现）。看裸真相不被表象骗。**
> **协作:** WSL2 代码归 CC（经理人环境连不上 CC 的 WSL/docker，只能让 CC 查实物贴出来）。经理人用 ask_user_input_v0 征求 Wiki 决策。每批 commit 必 push（VHDX 教训）。Wiki 中文、技术不懂、要经理人实证决定、输出简洁。

---

## 一、B 仓是什么（一分钟理解）

AII 用**两个互相独立、不污染的数据库**：
- **A 仓（原始仓 aii_raw，已有，运行中）**：给人读的数字化记录——**全、不漏、中文、按书+按章 KC+BU**。忠实记录每本书抽出的原始 KU（**有重复**）。
- **B 仓（精炼仓 aii_refined，待建，本次交接）**：给机器深加工的知识有机体——**去重、英文统一、只主题 KC、纯知识**。concept canonical、超边、跨域关系、本性都长在 B 仓。

**单向流**：A 仓 KU → 去重整合 → B 仓。B 仓不存单本书任何数据（BU/按章 KC 都在 A 仓），只存跨书融合的纯知识。可追溯（B 仓每个 KU 经 sources 回查 A 仓证据）。

**B 仓是知识有机体本身，最重要**——它一旦建好、上层（canonical/超边/跨域关系/本性）建于其上，schema 改动伤筋动骨。所以 schema 做过完备性检验（**实证过程/结论在 AII-REFINED-REPO-SCHEMA-001 §五"实证完备性补全"，可回查**），一次设计到位。
> **★给新窗口怀疑 schema 完备性的材料（看裸真相，别信"已实证"三字）**：实证是对照 HyperGraphRAG/Hyper-RAG/生产 KG 最佳实践做的，结论三点（详见 schema 文档 §五）——(1)**已对齐**：二部图存储/双向量库/confidence 分级(confirmed-candidate)/provenance(sources)；(2)**补了 3 个真缺口**：原文 chunk 检索融合(CR，主要是 M1 检索逻辑+sources 回查 A 仓)、边/成员强度(strength 字段)、来源版本(version 进 sources jsonb)，**都不建表**；(3)**砍了过度设计**：temporal 时序图/bi-temporal 版本/审计表——AII 教科书知识不过时，不需要。**新窗口应自行复核这三点是否成立，尤其 (3) 砍掉的是否真不需要、(2) 补的 3 个是否够。**

---

## 二、★四层架构（B 仓的核心，务必理解）

```
第①层 有向关系（concept→concept：derives/subsumes/prerequisite）
第②层 有向超边（机制→被解释概念集，explains，n元，动态生长）
第③层 跨域关系（motif/结构映射出的 base↔target 对应，SME 式⟨M,C,S⟩）
第④层 本性（invariant，从第③层提炼共享内核，is_invariant_concept 字段标记升华）
```

**生长链**：有向关系给概念骨架 → 超边在骨架上生长跨学科机制网 → motif/结构映射在机制网发现跨域关系（第③层）→ 跨域关系提炼共享内核升为本性（第④层）。

**★第③层"关系"≠第④层"本性"（最易犯错处）**：
- 第③层跨域关系 = "水流↔电流"的对应（它们像）——是**关系**。
- 第④层本性 = "势差驱动流"的共享内核（像在哪）——是**本性**。
- 提炼出内核才从③升④（cross_domain_relation.invariant_id 指向 invariant）；提炼不出停在第③层（invariant_id=NULL）。**宁停在关系不附会。**

---

## 三、★术语锁定（不再混用，违反即错）

| 中文 | 英文 | 锚定 |
|---|---|---|
| 本性 | **invariant** | 拓扑不变量语义（**不是 nature**；nature=性质/特征=相） |
| 本性概念 | **invariant concept** | 多概念共有的本性升华（**不独立建表**，is_invariant_concept 字段 false/true） |
| 本性同一 | **invariant-identity** | identity=同一（**非 equivalence 等价/similarity 相似**；旧称"本性同源/invariant-shared"作废） |

> 本性 = invariant，是"一切相之下的不变内核"（熵的本性="只增不可逆有方向"，不是"无序度量"=相）。**这是本性层最核心的区分，nature 表达不了。**

---

## 四、设计依据文档（全部在 /mnt/user-data/outputs/aii-project/，按重要性）

| 文档 | 内容 | 状态 |
|---|---|---|
| **AII-TWO-REPO-ARCH-001** | 双仓架构（A 给人读/B 给机器，单向流，职责划分） | 供审 |
| **AII-REFINED-REPO-SCHEMA-001** | ★B 仓完备 schema（四层表+去重KU+canonical+主题KC+出处+向量）。**§五"实证完备性补全"含实证过程/结论（可回查），新窗口应自行复核** | 供审，审过即建库 |
| **AII-KU-DEDUP-001** | KU 去重机制（翻译英文→KU判同先行→内容整合宁冗余不误删→存B仓→概念归一→KC） | 供审 |
| **AII-CONCEPT-IDENTITY-001** | 判同升级（真正同一才合一：判别维度对齐+非上下位+结构同+高风险candidate） | 供审 |
| **AII-INVARIANT-LAYER-001** | ★第④层本性权威设计（道非相/本性≠本性概念/关系≠本性/两路径/两层互证/字段标记） | ✅ Wiki 通过 |
| **AII-KNOWLEDGE-ADVANCED-DESIGN-001** | 四层总纲（前沿实证支撑） | 供审 |
| **AII-KNOWLEDGE-ADVANCED-IMPL-001** | 四层实现（M0-M4 里程碑，严格依赖顺序） | 供审 |
| **AII-CONCEPT-NATURE-001** | 本性原始设计（被 INVARIANT-LAYER-001 整合校正，仍是本性思想源） | 参考 |
| **AII-GLOSSARY-001** | 权威词汇表（术语对齐，避免反复纠偏） | 必读 |
| **★AII-HYPEREDGE-EXPLAINS-001** | **第②层超边设计（explains n元超边/动态生长）= M1 的直接执行规格（非参考）** | **⚠️ 缺口：不在本 outputs 目录（在之前会话/CC 环境）。M1 没有它会断料——必须先向 CC 索取或按 AII-KNOWLEDGE-ADVANCED-IMPL-001 §M1+总纲§三重建，否则走到步骤5 的 M1 无规格可依** |

---

## 五、★实施顺序（严格按依赖，不可逆序）

```
步骤1 建 B 仓（独立 PG 库 aii_refined）+ 四层完备 schema（空库，不灌数据）
       ← 按 AII-REFINED-REPO-SCHEMA-001，审过即可建（纯 DDL，风险小）
步骤2 KU 去重机制（A 仓 → B 仓，片段级）
       ← 按 AII-KU-DEDUP-001。难点：判"相同内容"不误删（宁冗余不误删）
步骤3 现有 A 仓 KU 去重灌入 B 仓（首批：经济/数学书）
步骤4 M0 concept canonical（在 B 仓去重 KU 上做）
       ← 按 AII-CONCEPT-IDENTITY-001 四道关（判别维度/类层级/LLM窄判/candidate）
       ★注意：M0 之前在 A 仓（有重复）跑过 dry-run，位置错已停。canonical 必须在 B 仓做。
步骤4.5 ★第①层有向关系（directed_edge_v2，在归一概念上建全局骨架）← 易漏！
       ← 在 B 仓去重 KU 上做 readout（从讲透 KU 读出 concept→concept 的
          derives/subsumes/prerequisite），建完整有向关系图。
       ★为什么单列：原是 A 仓飞轮 readout 步骤，A 仓瘦身已卸到 B 仓。
       ★依赖位置：M0 之后（建在归一概念上）、M1 之前（超边长在此骨架上）。
步骤5 M1 超边抽取 → M2 超边生长 → M3 跨域关系 → M4 本性
       ← 按 AII-KNOWLEDGE-ADVANCED-IMPL-001。每步先一本验证再全量。
       ← M1 直接依据 = AII-HYPEREDGE-EXPLAINS-001（★见 §四缺口，该文档不在目录需先取得）。
```

**★依赖链厘清（破"M0 判同 ↔ 有向关系"的假循环）：**
- 表面循环：M0 判同关2（类层级/互斥）要用有向关系判上下位，但有向关系（步骤4.5）又建在 M0 归一概念上。
- **实证（OntoEA/前沿实体对齐）破解**：判同关2 需要的是"判候选对的上下位/互斥"这个**能力**，不是"全局有向关系图已建好"。类层级/互斥是**独立维度**——前沿把它作为附加输入（appended ontology），AII 里 M0 判同时**当场 LLM 判候选对上下位（few-shot）**即可，不依赖全局图。
- **所以不循环**：M0 判同（当场判候选上下位）→ M0 完成 → 步骤4.5 建全局有向关系图（readout）→ M1 超边长在骨架上。步骤4.5 建好的图之后还能反哺判同（迭代增强），但 M0 不阻塞等它。

**依赖链（为什么不可逆序）**：
- canonical 不先做 → 超边跨书生长时"同概念被当不同概念" → 长不起来。
- **有向关系（步骤4.5）不先建 → 超边没有概念骨架可长**（第②层超边在第①层有向关系骨架上生长）。
- 超边不积累足够 confirmed 跨学科成员 → 跨域关系/本性没料。
- **所以：建库 → 去重 → canonical → 有向关系 → 超边 → 跨域关系 → 本性。**

---

## 六、当前状态（接手时的精确位置）

**设计层（基本就绪）：**
- 四层架构、术语、schema、去重机制、判同升级、本性层——都成文档。
- 本性层（AII-INVARIANT-LAYER-001）Wiki 已通过；其余供审。
- 所有文档已四层一致、术语统一（invariant/invariant-identity/is_invariant_concept）。

**执行层（B 仓尚未开建）：**
- B 仓**还没建**（从 0 空库建，本次交接的起点）。
- A 仓飞轮**正在瘦身**（只留讲透/完整性/概念抽取/按章KC/BU/质量门；卸有向/归一/谱社区/超边/本性到 B 仓）。V1.3 抽取精华留 A 仓、explains 升级 B 仓（explains 链转存 provenance 给 B 仓建 n元超边）、双仓违例已修。Mankiw 在跑验证瘦身。
- M0 在 A 仓的 dry-run **已停**（位置错，canonical 应在 B 仓做）。判别词硬闸+dry_run 机制已建（commit f58532b 附近），精炼仓 canonical 还会用。

**关键标识符：**
- PG：aii-postgres 容器，现有库 aii_kg（A 仓）；B 仓待建 aii_refined。
- 代码：~/projects/AII/aii 及 /home/soffy/projects/AII；远端 git@github.com:soffy88/aii.git。
- 书源：/home/soffy/shared/stratum-to-aii/；AII↔Stratum 反馈队列 /home/soffy/shared/aii-to-stratum/md_rework_queue.json。
- 前端 aii.uex.hk，API:8101，前端:3101。

---

## 七、★命门家族（贯穿 B 仓全部，统一原则）

> **AII 全局：宁可冗余/碎片/漏，不可误删/错合/附会。** 保守而诚实，不为"看起来干净/完整/惊艳"冒错的风险。

| 层 | 命门 | 守法 |
|---|---|---|
| KU 去重 | **宁冗余不误删** | 判"相同内容"宁严勿松；拿不准当"不同"保留（数分严格定义vs同济应用都保留=越读越厚） |
| 概念归一（M0） | **宁碎片不错合** | 判别维度对齐+类层级互斥+LLM窄判+高风险candidate；错合=地基污染 |
| 超边生长（M2） | **宁缺毋附会** | 5条严判据；LLM判不准→candidate；跨学科→默认candidate |
| 跨域关系（M3） | **关系≠本性** | 跨域关系不直接认定本性；提炼出内核才升M4；停在关系invariant_id=NULL |
| 本性（M4） | **宁标未发现** | ≥3跨学科+内核同+两层互证+全confirmed；抽不出留NULL，不硬凑 |

**两层独立互证（防附会的核心机制，第③④层）**：本性向量收敛（语义）+ motif结构（拓扑），两独立证据都指同一本性→高置信；只一层→存疑。

---

## 八、★红线（必须守，违反即停报 Wiki）

1. **看裸真相**：不被"测试绿/数量多/看起来对/跨学科涌现惊艳"骗。假联结比漏联结危险。
2. **每步先小范围验证再全量**：防错误形态铺开 357×N 个 KU（已踩坑：数分覆盖不全、explains 写错表、M0 错合 price/income）。
3. **dry_run 验证不落库**：破坏性测试一律 dry_run（算+打印不落库），看对了再真跑（M0 已踩"破坏性测试落库错合"坑）。
4. **红线测试（测该拦的，不只测正常）**：M0 放同名不同学科→不错合；M2 放表面相似实不同机制→不附会；M3 放假跨域关系；M4 放平凡组合假本性→不提取。
5. **CC 会判错**：经理人要核实 CC 报的问题不照单全收（已踩：CC 误判 qwen 方向反、想当然 explains 写 concept_readout_edge）。
6. **术语不凭印象拼**：以 AII-GLOSSARY-001 + 本文术语锁定为准（本性=invariant 非 nature，本性同一=invariant-identity 非本性同源）。
7. **每批 commit 必 push**（VHDX 教训：本地数据可能丢）。
8. **B 仓不存单本数据**：BU/按章 KC 在 A 仓；B 仓只跨书纯知识。sources 是溯源指针（指 A 仓），不算存书。

---

## 九、第一步建议（接手即可做）

1. **先让 CC 盘点**：A 仓现状（KU 数/概念数/书数）、确认 B 仓 aii_refined 不存在（从 0 建）、本地 embedding（BGE-M3/qwen3-embedding）就绪。
2. **审 schema**（AII-REFINED-REPO-SCHEMA-001）：四层表完备否、术语对否、不过度设计否。
3. **审过 → CC 建库**：独立 PG 库 aii_refined + 四层 schema（KU/概念/主题KC/有向边/超边/跨域关系/本性invariant）+ 向量索引 + 外键，**空库不灌数据**。
4. **然后**：去重机制（AII-KU-DEDUP-001）→ 灌入 → M0 canonical → **第①层有向关系（步骤4.5，readout 建骨架）** → M1-M4。**走到 M1 前先确认拿到 AII-HYPEREDGE-EXPLAINS-001（M1 规格，见 §四缺口）。**

---

> **一句话交接**：B 仓（精炼仓 aii_refined）是 AII 的知识有机体——给机器深加工的纯知识（去重/英文/四层：有向关系·超边·跨域关系·本性）。从 0 空库建，A 仓 KU 去重灌入。设计已成文档且四层一致、术语锁定（invariant/invariant-identity/is_invariant_concept），本性层 Wiki 已通过。**实施严格按依赖：建库→去重→canonical→超边→跨域关系→本性，每步先验证再全量。命门：宁可冗余/碎片/漏，不可误删/错合/附会。关系≠本性，宁停在关系不附会。看裸真相，不让"看起来对"冒充"真的对"。**

---

*交接依据：本段全部设计文档（双仓/schema/去重/判同/本性层/四层总纲与实现）+ Wiki 决策（双仓本质/四层/术语锁定/本性概念字段标记/关系≠本性）+ 当前状态（B仓待建/A仓飞轮瘦身中/M0 dry-run已停）。新窗口据此接手 B 仓建设。*
