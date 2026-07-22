# AII-HISTORY-KU-SPEC-001

## 历史 KU 规范 —— 事件中心 · 多源并陈 · 直供 tongjian

| 项 | 值 |
|---|---|
| 状态 | draft v0.1 · 2026-07-21 |
| 所有者 / 执行 | Wiki / CC |
| 所属 | AII（已并入 Stratum；原 Stratum 职责在本文件中称**语料层**） |
| 依赖 | B仓四层 schema（AII-REFINED-REPO-SCHEMA-001 / MASTER-001）· 概念同一性法则（AII-CONCEPT-IDENTITY-001 · MASTER-001 第五/六部分，§5 承此）· 并陈原则（AII-DOMAIN-ONTOLOGY-SPEC-001 §2 R2）· 引用寻址（STRATUM_SPEC v0.2 §D2）· MINERU-AII-INTEGRATION-SPEC-001（解析，待入仓 DEBT-3）· AELLA-KU-EXTRACTOR-EVAL-001（抽取评测，待入仓 DEBT-4）· AII-FIRST-PRINCIPLES-001（宪法层，待入仓 DEBT-2）· 承自核验见附录 A |
| 消费者 | ① tongjian 视频线（主驱动，接口见 §8）② Mneme 历史科目（远期，只留兼容不设计）③ AII 本体检索问答 |
| 成功定义 | 任一历史事件在 AII 中表达为**一个事件 + N 个源述 + 显式冲突对象**，出处落到语料层片段；tongjian 经只读接口拉取即可装配 VisualFact，**无需二次读原文** |

---

## 0. 定位

生产线的口号是"结构只写一次，四处消费"。本 spec 把它上提一层：**抽取一次，四处消费**——事实在 KU 层确认一次，此后每一集视频、每一次检索、将来每一个 Mneme 学习卡共用，且共享同一套出处链。

脊柱从"书"换成"时间轴"：**事件是一等公民，书降级为证词提供者。** 太史公的互见法是这个模型的古代版——同一事件散见多篇，各有侧重；我们把"散见"结构化。

---

## 1. 设计原则（全部承自 AII 既有法则，无新发明）

| # | 原则 | 承自 |
|---|---|---|
| P1 | **并陈不合并**：源冲突时各述并存，主线选择是显式记录的决策，不是静默合并 | AII-DOMAIN-ONTOLOGY-SPEC-001 §2 R2（外部意见并陈；C仓专文 AII-CONTEXT-REPO-SPEC-001 待入仓 DEBT-1） |
| P2 | **冗余优于丢失**：同一性存疑时保持分立 + 候选链，不强并 | B仓 KU 去重原则 |
| P3 | **事件 = 超边**：一个事件连接多个人物 / 势力 / 地点 / 时间，落在 B仓第二层（超边层） | B仓四层 schema |
| P4 | **独立性可计算**：佐证力按源系谱折算，同源转述不算多重见证 | 本 spec §6（新机制，旧精神） |
| P5 | **断言处处带出处**：每条 claim 的 locator 落到语料层段落级 ULID | STRATUM_SPEC v0.2 §D2（可寻址性：substrate + fragment 经 ULID 精确引用；文本段落即其特例） |
| P6 | **KU 给机器读，BU 给人读**：每书 BU 照旧；本 spec 只管 KU | 既有分工 |

---

## 2. 语料层（原 Stratum 职责）

### 2.1 白文入库规则（承生产 spec R5，本层为执行者）

- 底本取开放白文源；标点自做或 AI 重标；**禁与任何在版点校本逐字对齐**。
- 每书登记底本注记（来源、许可、处理方式）。
- 公版古注可入库为独立源（杜预注、胡三省注、裴松之注——裴注地位特殊，见 §3.1）；一切现代译注不入库。

### 2.2 解析与结构

- MinerU 管线，parse-once-fork-twice：middle_json → MD 渲染（人读）+ KU 抽取（机读）。
- 章节 KC（head/body）照旧；每书 BU 照旧。
- **locator 粒度**：书 → 篇/卷 → 段 → **段落级 ULID**。历史 KU 的所有 claim 引用必须到段落级 ULID（格式 `<substrate-ULID>:<para-suffix>`，承 STRATUM_SPEC v0.2 §4.2；即 §D2「fragment」在文本 substrate 下的特例。本 spec 只涉文本源，故 fragment 术语废止，统一用「段落级 ULID」）。冲突常在**同书不同篇**之间（史记·赵世家 vs 史记·晋世家），locator 停在"书"级会把最有价值的冲突抹掉。

### 2.3 首批书目候选（灌注按断代波次，见 §10）

左传（附春秋经）· 国语 · 战国策 · 史记 · 汉书 · 后汉书 · 三国志 + 裴注 · 资治通鉴。
校勘参考源：竹书纪年——古本（辑佚）与今本（真伪有争）**分立登记**；今本默认只作参考不作证据。

---

## 3. 注册表族（两系统的共享真理源）

生产端 L2 律的上游。人名 / 地名 / 纪年 / 勢力注册表主权在此；生产端只读。

### 3.1 源注册表

```
Source {source_id, title, 成书年代, genre(编年|纪传|国别策论|注|辑佚),
        carrier_of[]          # 载体关系：裴注是载体，魏略/江表传/世语…是被载原源，
                              # 各原源独立登记、独立计独立性
        derivation_edges[]    # 派生：通鉴←史记/战国策/…；史记←左传/国语/世本/…
        genre_reliability     # 体裁可靠性注记：策士言辞（战国策）多虚托夸饰，
                              # 与编年史不同权——影响 §6 折算
        底本note}
```

**裴注机制单独强调**：裴注引书百余种、多为佚籍，是融合的金矿。但"《三国志》+ 裴注引《魏略》"是**两个源两份证词**，不是一个源说了两遍——carrier / original 区分是独立性计算的前提。

### 3.2 纪年注册表

- canonical 时间轴：共和元年（前 841）起连续纪年；之前进入 fuzzy 区（date.type = fuzzy）。
- per-source 映射：王公纪年 / 干支 / 年号 → canonical。
- **系统性误差 override**：六国年表类已知错误按学术校正传统（钱穆、杨宽一系）登记为映射覆盖，每条 override 带学术出处——这是"考据结论的工程化"，不是我们自己搞考据。
- 争议日期政策：全部候选保留，主线取值记录理由与决策人（mainline_decision 结构同 §4.3）。

### 3.3 人物注册表

`Person {person_id, names_by_source{赵孟|赵襄子|无恤…}, 谥/字/号, active_range, force_affiliations[]}`。异名归一在此完成一次，下游（立牌、检索、Mneme）永久免疫。

### 3.4 地名注册表

`Place {place_id, name_by_era{}, geo_hint, mapstate_hints[]}`。直供生产端 R3 与 MapState 命中查询。

### 3.5 勢力注册表

`Force {force_id, name_by_era{}, active_range, succession_edges}`。**色**的分配留在生产侧（视觉资产），实体在此。

---

## 4. KU 类型族

### 4.1 ku:h-event（历史事件，B仓超边层）

```
{event_id, title,
 canonical_date {type: exact|year|range|fuzzy, value, note},
 event_type ∈ {战役, 政变, 会盟, 册命, 迁都, 变法, 灾异, 制度, 人事, 其他},
 actors[{person_ref, role, force_ref}],
 geo {place_refs[], route_hint?, mapstate_hint?},
 parent_event?,        # 组合事件：三家分晋(过程) ⊃ 晋阳之战 + 命侯(403)
 accounts[] → ku:h-account,
 conflicts[] → ku:h-conflict,
 evidence_tier ∈ {E0..E4},        # §6 计算，可人工覆盖并记理由
 mainline_account_ref + mainline_decision}
```

> **★hint 不得私裁（D-017）**：`geo.route_hint` / `mapstate_hint` 等提示字段若取值涉及**源间分歧**，只有两条合法路径——①该分歧的冲突对象已建，且 hint **跟随 `mainline_decision`**（并注异说所在 cf）；②置 `null`。**hint 永不承载未裁决的选择**。首例：B06 晋阳灌城水源（route_hint 单方取『汾水』而晋水/汾水 h-conflict 未建，G1b 抓出）。

### 4.2 ku:h-account（源述：某一源对该事件的证词）

```
{account_id, event_ref, source_id, locator(到段落级 ULID),
 白文span_refs[], 白话ref?,
 extraction {
   date_claim, actor_claims[], causal_claims[],
   number_claims[{value, unit, quote_span, display:"《X》载"}],
   dialogue_spans[]      # 演绎段素材接口：只存不消费，透传给导演流水线
 },
 genre_note}             # 策士言辞/追记/注引 等降权标记
```

### 4.3 ku:h-conflict（异说：显式的一等对象）

```
{conflict_id, event_ref,
 dimension ∈ {date, actor, number, causality, narrative, existence},
 account_refs[≥2],
 independence_analysis,   # 经 §6 折算后的真实独立见证数
 mainline_decision {choice, rationale, decided_by, date},
 presentation_hint ∈ {S12对勘, 主线+角标, banner, 仅记录}}
```

冲突是**资产不是麻烦**：presentation_hint = S12 的条目直接成为生产端的差异化内容供给。

---

## 5. 事件同一性判定（承 AII-CONCEPT-IDENTITY-001 · MASTER-001 第五/六部分）

判定框架全部承自概念同一性既有法则：真正同一才合一；判别维度对齐方可判同；
类互斥；存疑走宁碎片不错合 / 宁冗余不误删。判定流程遵 MASTER-001 第六部分（四道关）。
本节仅新增本域内容：历史事件的判别维度申明。

**事件判别维度**（判"真正同一"须全部对齐，或差异可归因）：
- D1 时间窗：canonical 化后同窗；不齐时仅当存在纪年 override 或可落为
  date 维冲突对象（且 D2–D4 强对齐、源系谱支持同述关系）方可归因
- D2 主体集：核心 actor 交集
- D3 地点
- D4 事理骨架：起因—经过—结果的骨干是否同一
辅助证据（非维度）：源系谱——B 已知派生自 A 时，倾向判同事。

**三种处置**：

| 判定 | 条件 | 处置 |
|---|---|---|
| 同述 | 全维度对齐且文本重合或明确派生 | 并入同一 account，locator 并列 |
| 同事异述 | 维度对齐，或差异全部可归因并落为冲突对象 | 同一 event 挂多 account——中心情形 |
| 似而非同 | 任一维度实质不齐且不可归因 | 禁合并；candidate-same 链备查 |

存疑默认：似而非同（宁碎片 / 宁冗余）。每次合一判定必须记录：
对齐证据 + 归因链 + 判定人——gold answers 可复核性的来源。

术语注记（非规范）：v0.1 曾以 equality / isomorphism / equivalence 命名三级。
该词汇在本仓为本性/不变量同一性专用（范畴论义），为免一词两义，
事件判定改用上表操作性命名，旧名废止。

---

## 6. 独立性折算与史料等级 E0–E4

**折算规则**：在 derivation graph 上回溯至祖源；同一祖源的 N 个转述 = 1 个独立见证。通鉴的战国部分取材史记/战国策——三源同说常常只是一重证据。carrier/original 区分（§3.1）参与折算；genre_reliability 作系数。

**等级定义**（事件级，屏幕 banner 直连生产 R9）：

| 级 | 定义 |
|---|---|
| E0 | 文献 + 考古/出土互证 |
| E1 | ≥2 个**独立**文献见证 |
| E2 | 单一近源文献 |
| E3 | 晚出追记（成书距事件远且无近源支撑） |
| E4 | 传说层（五帝夏商大部；显式标注，不假装） |

考古佐证 flag 的数据源（简帛金文）远期再接（Q3），先留字段。

---

## 7. 抽取管线与人工闸口

```
候选生成(LLM) → 注册表解析(人名/地名/纪年归一) → 同一性判定(§5) → 人工确认闸 → 入库
```

- 抽取器沿 Aella 路线，**历史专用评测集另建**（§9），不复用通用集充数。
- **人工闸口分工**（与生产端闸口①衔接）：语料端确认"这个事件的史料结构真不真"（一次性资产建设）；生产端只确认"这一拍选用哪些、怎么用"（每集轻量）。确认一次，集集免疫——人工分钟红利的来源。
- 红线承 Mneme 教训：**禁 LLM 自产自证**——抽取候选的确认者不能是抽取者本身；人工确认不可少，fixtures 不可由待测模型生成。

---

## 8. tongjian 消费接口（本 spec 的存在理由）

### 8.1 查询

只读接口：按时间窗 / 人物 / 势力 / event_type / 断代查询，返回 `{event, accounts[], conflicts[], registry_bundle(人/地/纪年解析包)}`。

### 8.2 字段映射表（KU → 生产端 VisualFact）

| 生产端字段 | 来源 | 变换 |
|---|---|---|
| VisualFact.date | h-event.canonical_date | fuzzy → 取代表值 + 透传 banner |
| VisualFact.forces[] | actors[].force_ref → 勢力注册表 | 归一 id，色由生产侧配 |
| VisualFact.regions[] | geo.place_refs → 地名注册表 | (date, scope) 命中 MapState |
| VisualFact.persons[] | actors[].person_ref | → Cutout（T1/T2 由生产侧定） |
| VisualFact.quantities[] | mainline account.number_claims | 逐条带 `《X》载` display |
| VisualFact.evidence_tier | h-event.evidence_tier | E3/E4 强制 R9 banner |
| DualAccountFact | h-conflict (hint=S12) | 两 account 摘述 + 双源标注 |
| 演绎段素材 | account.dialogue_spans | **透传不消费** |

### 8.3 版本钉住

KU 版本以内容指纹标识（SHA-256，四支柱惯例）；EpisodePlan 钉指纹集。**KU 升版不追溯已发布集**；重制是显式决策，跨系统 decision_trail 闭合。

### 8.4 契约先行

本节 JSON 契约先冻结。生产端 G1a 以手工装配的同形数据先跑；KU 实装后 G1b 对拍（逐字段一致或差异可解释）。契约是两个仓库间唯一的耦合面。

---

## 9. 评测（A/B 分立，承既有区分)

- **A 类回归网**（同一性与冲突判定，防倒退）：fixtures 见 §10 W-H0；防污染裁判——fixture 答案人工定，不得由待测抽取器生成。
- **B 类优化集**（检索侧）：时间窗/人物查询 → 事件 Recall，客观指标。
- **抽取器基准**：历史专用集（文言事件抽取），沿 AELLA 评测框架另建语料。

---

## 10. 范围与波次

**Schema 按全史建，语料按断代灌。**

| 波次 | 内容 | 备注 |
|---|---|---|
| **W-H0** | fixtures 手工建 30–50 事件 | 必含：①三家分晋全套（isomorphism 常态样本，供生产端 G1b 对拍）②**赵氏孤儿**（existence/narrative 冲突：左传·成公八年下宫之难 vs 史记·赵世家程婴屠岸贾——且史记内部赵世家 vs 晋世家自相冲突，locator 到篇的必要性示范）③**官渡兵力**（number 冲突 + 裴注机制 smoke test：《三国志》"兵不满万"与裴松之按语的质疑——观点归属 R8 与 carrier/original 一箭双雕）④一个 E4 样本（传说层 banner 链路） |
| W-H1 | 首发断代全量灌注 | **阻塞于 Q1 断代决策**（生产 spec Q8 同源） |
| W-H2+ | 相邻断代扩展 | 节奏由 tongjian G2 产能反推 |

---

## 11. 未决问题

| # | 问题 | 处置 |
|---|---|---|
| Q1 | 首发断代（战国 vs 三国）——决定 W-H1 书目 | 待 Wiki（= 生产 spec Q8） |
| Q2 | 竹书纪年异文处理深度（逐条 override vs 仅重大冲突） | W-H1 前定 |
| Q3 | 考古佐证 flag 数据源 | 远期，留字段 |
| Q4 | 抽取器模型定型与历史评测集规模 | W-H0 手工期并行准备 |
| Q5 | 冲突/超边在 aii.uex.hk 可视化的画法（Sigma.js 既有 spec 下） | 缓 |

---

*下游动作：契约（§8）冻结 → W-H0 fixtures 手工建（不依赖抽取器）→ 生产端 G1b 对拍。W-H0 与 G0/G1a 完全并行，互不阻塞。*

---

## 附录 A · 承自引用 conformance 核验（Task 0 · 2026-07-21 · CC）

> 目的：本 spec 声称"全部承自 AII 既有法则，无新发明"。逐条把 §1/§5/§6 及依赖头的"承自"解析到**仓内实文（文档名 + 节）**。
> 核验范围：`docs/B仓docs/`、`aii/docs/`、`docs/yiwancheng/`、`docs/design/`、全仓 `*.md`。
> **状态：U1–U6 已由所有者裁决（Wiki，2026-07-21）；U1–U3 落地关闭，U4–U6 转外部依赖债务（A.3）。** §8 契约冻结与 W-H0 fixtures 就此解锁。

### A.1 承自落地（全部已解析 / 已裁决）

| spec 处 | 承自表述 | 落地文档 · 节 | 状态 |
|---|---|---|---|
| §1 P1 | 并陈不合并 | `AII-DOMAIN-ONTOLOGY-SPEC-001.md` §2 R2（外部 judgment 并陈） | ✅ 改挂（U2-b） |
| §1 P2 | KU 去重（宁冗余不误删） | `AII-KU-DEDUP-001.md`（全文）+ `AII-REFINED-REPO-MASTER-001.md` 第五部分 · 命门族表 | ✅ |
| §1 P3 | 事件=第②层超边 | `AII-REFINED-REPO-SCHEMA-001.md` §2.6「⑤ 第②层 有向超边」+ `AII-KNOWLEDGE-ADVANCED-DESIGN-001.md` | ✅ |
| §1 P4 | 独立性可计算 | 本 spec §6（新机制·旧精神）；旧精神与 P1/P2 独立性同源，无外部专文 | ➖ 内部自引用 |
| §1 P5 | 断言带出处 | `docs/design/STRATUM_SPEC_v0.2.md` §D2（可寻址性）+ §4.2（段落级 ID）——见 A.2 版本注 | ✅ 钉版（U3） |
| §1 P6 | KU 机读 / BU 人读分工 | `AII-TWO-REPO-ARCH-001.md`（原始仓 vs 精炼仓）+ `AII-REFINED-REPO-MASTER-001.md` 第一部分 | ✅ |
| **§5** | 事件同一性判定框架 | **改挂 `AII-CONCEPT-IDENTITY-001.md` + `MASTER-001` 第五/六部分**（真正同一才合一 / 四道关 / 宁碎片不错合 / 宁冗余不误删）；§5 整节已换词，旧 equality/isomorphism/equivalence 命名废止（该词汇在仓内为本性/invariant 专用） | ✅ 重挂+换词（U1-b） |
| §6 | 独立性折算 + E0–E4 | 本 spec 新定义；`carrier/original`、`genre_reliability`、`derivation graph` 均 §3.1 内部件 | ➖ 内部 |

### A.2 ★U3 版本注（钉版 + 报回的实质差异）

`STRATUM_SPEC` §D2「可寻址性」在版本间**有实质差异，如约报回**：

| 版本 | §D2 终端粒度 | 表述 |
|---|---|---|
| v0.1.2（`docs/yiwancheng/STRATUM_SPEC.md`） | **段落级** | 「引用到段落级」；段落 ID = `<substrate-ULID>:<para-suffix>`（§4.2） |
| **v0.2（`docs/design/STRATUM_SPEC_v0.2.md`）** | **fragment 级（泛化）** | 「引用到 fragment 级：文本段落 / 音频区间 / 视频区间 / 图像区域 / 数据行列」，`ULID + fragment-identifier` |
| v0.6（`STRATUM_SPEC_v0.6_DELTA/PATCH.md`） | 未触 D2 | 仅加 scheduling/agent 表；寻址语义 = v0.2 |

**裁决落地**：钉 **v0.2**（最新的完整寻址定义；v0.6 为其增量、D2 未改）。本 spec 只涉**文本** substrate，故取 v0.2「fragment」在文本下的特例 = **段落级 ULID `<substrate-ULID>:<para-suffix>`**；据 U3 指令「fragment 术语废止」，全 spec（§2.2 / §4.2 / P5）统一改用「段落级 ULID」。语义与 §D2 一致，仅收窄到文本域并采用精确术语——非与 §D2 相悖。

### A.3 外部依赖债务表（U4–U6 + U2 之 C仓专文；均不阻塞 §8 / fixtures）

| 债务 | 文档 | 需于何时入仓 | 裁 | 备注 |
|---|---|---|---|---|
| DEBT-1 | **AII-CONTEXT-REPO-SPEC-001**（C仓专文） | 尽快 | U2 | 一单两修：入仓即修复 `DOMAIN-ONTOLOGY-SPEC-001` §2 R2 自身「同 C仓 §2.4」悬空引用 |
| DEBT-2 | **AII-FIRST-PRINCIPLES-001**（宪法层） | 尽快（卫生问题） | U4 | 被多篇引用却无文件 |
| DEBT-3 | **MINERU-AII-INTEGRATION-SPEC-001**（解析） | **W-H1 灌注前（硬需）** | U5 | — |
| DEBT-4 | **AELLA-KU-EXTRACTOR-EVAL-001**（抽取评测） | 抽取器评测启动前 | U6 | ★D-013 解耦：评测集与候选模型解耦——框架文档照入仓，Aella-Qwen3-14B 段标 historical（已放弃，硬件现实）；抽取器候选 needed-by 时点重选（本地/API 皆开放）。近期零阻塞。 |
| DEBT-5 | **出土文献 Source 化**（简帛/金文/出土成一等 Source + 契约扩 `source.genre`） | **Q3 考古管线落地时**（= D-005 的 (B) 触发） | D-007 | 现走 (A) aspiration-note（F9/F14/F16 考古/帛书作 E0-候选注记，不作 Source）；Q3 落地→(B) 契约 bump。 |

> 红线遵守：A.1 的改挂（P1/P5/§5）均由所有者裁决授权（U1-b / U2-b / U3），非自行改挂；DEBT-1–4 标外部、未伪造落地。

### A.4 Open questions（U 协议报回·候裁，不私设）

| # | 问题 | 来源 | 现状 |
|---|---|---|---|
| U7 | **互见/互补关系是否需要一等对象（非 cf）**——F12 抽验裁『侧重差不立 cf』（D-022）后，互见互补仅存于 `mainline_decision` 拼合说明与 account `genre_note`，无可检索对象；若生产端/回归网需查询『互见关系』，须契约增对象（形状变更 = `contract_version` bump + 双端同步） | D-022（F12 修订牵出） | ✅ **已关（D-023，2026-07-22）**——见下裁决 |

**U7 裁决（原文，顾问 Claude · Wiki 授权 2026-07-22 · Wiki 保留否决权）**：
> 『互见/互补关系**暂不设一等对象**。理由：(1) 互见互补是**同源同说的叙事侧重差**，不是冲突、也非独立实体——事件级 `mainline_decision.rationale`（拼合说明）+ account `genre_note`（侧重注记）已完整承载，无信息丢失；(2) 增一等对象＝契约形状变更（bump + 双端同步 + G1b 风险），当前无 live 消费者需求（生产端拼合读 mainline，无需查询「互见关系」实体）；(3) 与 F1 折算记录同理——**凡非对立主张者一律事件级表达，不铸对象**。』
>
> **★防倒退点升级（D-023，并入通则）**：**凡为侧重差（F12）或折算记录（F1）立 cf 即倒退信号**——`dimension=narrative` 的 cf 只挂**真对立主张**（现存正例 F2×2/F4/F5/F13）。
>
> **重开条件（三者任一）**：① 生产端出现需**按互见关系检索/装配**的 live 需求（非拼合即可满足）；② 回归网需将「互见 vs 矛盾」做成**可查询判据对象**（非仅 gold 文字判定）；③ Mneme/第三消费者要求互见关系一等可寻址。触发则作一次协调的 `contract_version` bump（走 D-006 同款流程）。在此之前一律事件级文字表达，不私设新对象/新字段。
