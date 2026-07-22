# MINERU-AII-INTEGRATION-SPEC-001（重建版 r1）

## MinerU 生态接入 AII/Stratum 全流程 · 第一批冻结（架构层）

| 项 | 值 |
|---|---|
| 原版 | v0.1 冻结于 2026-07-09 会话；原文件产出后未入仓，下载件遗失 |
| 本版 | **v0.1-r1，2026-07-22 由会话记录重建**。§0–§1 为原文逐字恢复；§2–§7 按同会话裁决与提案恢复，置信度分级标注（见 §8） |
| 效力 | 架构层条款按原裁决恢复即有效；标 `[R-委托恢复]` 处为当年 Wiki 委托 Claude 定死的参数，按提案值恢复，Wiki 过目即转正；标 `[RECONSTRUCTION-GAP]` 处需重新拍板 |
| 入仓要求 | 按 Task-0 惯例过承自 conformance + §8 delta 清单逐条处置后，方可作为 W-H1 指令的引用基。入仓销 **DEBT-3** |

**目标**：将 MinerU 生态选定组件接入 AII/Stratum 知识全流程，在**不重建、不替换**现有稳定组件的前提下，加强各环节能力。

**核心原则**（07-09 Wiki 裁决语义，推翻初稿的"替换"设计）：**新增通道而非替换；解析层能力互补由路由决定；KU 语义提取始终归 AII 自有 omodul。**

**依据**："backtest guilty until proven innocent" / "宁冗余不误删" / 3O v0.7 四命名空间 / Stratum 无云端 API 依赖。

---

## 0. 范围与非目标 【原文恢复】

### 0.1 采纳的组件

| 组件 | 角色 | 3O 封装 | 轨道 |
|---|---|---|---|
| MinerU-Document-Explorer (qmd) | 检索 + 切块 + 地址溯源 + 去重粗筛 | oskill | Track A |
| MinerU VLM (2.5-1.2B) | 结构化解析**并列通道** | omodul（四支柱） | Track B |
| MinerU-HTML | 外部资料入口正文清洗 | oskill | Track C |

### 0.2 明确拒绝（非目标）

- **qmd wiki_ingest 产 KU** — 禁止（红线 R1）
- **MinerU Cloud（mineru_open_sdk / MINERU_API_KEY）** — 禁止（红线 R2）
- **丢弃 Unlimited-OCR** — 禁止。它是并列通道，非被替换对象
- **qmd 语义层渗入 AII 语义层** — 禁止（红线 R1）
- **Flash-MinerU** — 本 spec 不含；仅当出现大批量重新摄取需求时另开 spec 评估

---

## 1. 架构：parse-once, fork-twice 【原文恢复，冻结】

现状链路的问题：MD 同时承担"人类可读产物"与"KU 提取输入"两个角色，后者导致 `二进制→MD(有损拍平)→重新解析结构→提取` 的串行且有损路径。

**冻结架构**：解析一次，双路分叉。

```
二进制文档
  → [解析通道路由] → {Unlimited-OCR | MinerU VLM}   # 两个并列通道，路由决定
      ↓ 结构化中间态（MinerU 通道产 middle_json；Unlimited-OCR 通道产其等价中间态）
      ├─→ 渲染 MD（R1–R9）──────→ Stratum 三栏阅读器 / 导出标准   [人类可读产物]
      └─→ 结构化元素（表格/公式/层级/地址）─→ KU 提取 omodul      [机器路径]
```

关键约束：

- MD 从 KU 路径的**串行瓶颈**降级为**并列兄弟产物**。KU 提取吃结构化中间态，不吃拍平后的 MD。
- 两路产物同源于一次解析，禁止"拍平成 MD 再回读解析结构"。
- Unlimited-OCR 通道若无原生结构化中间态，其 KU 路径可暂时仍走 MD（过渡态），但不得因此阻塞 MinerU 通道的直喂路径。标 `[MIGRATION-UOCR-MIDJSON]`，后续优化项，非本 spec 阻塞项。

---

## 2. 通道路由 【裁决语义恢复】

- 双通道并存后，**G0 的性质从"MinerU 够不够好到取代"改为"路由规则怎么定"**——哪类文档走哪条通道（07-09 Wiki 裁决的直接推论，原会话明文）。
- 初始路由 = 现状（存量走 Unlimited-OCR）；G0 出结果后按文档类别定路由表。
- 真正的运行时约束：**单张 10GB 卡不能同时热载两个 VLM**——这是调度问题不是架构取舍问题；调度策略挂 `[PENDING-G0-RESULT]`。

---

## 3. 落地顺序 【原文恢复】

1. **Track A 全量**：qmd 索引 MD 语料 + MCP 接 CC。零 GPU 成本，立刻收益：减少畸形 KU、上溯源、去重粗筛。
2. **观察 2 周**：看 KU 候选质量、去重命中率、CC 循环是否真省了中转。
3. **G0 基准闸门**：MinerU VLM vs Unlimited-OCR 解析对比 + KU 质量终判 → 产出**路由表**。
4. **过闸才上 Track B**：接 parse-once-fork-twice。
5. **Track C（MinerU-HTML）**：等 AII 主动检索线真正启用时再接，不提前上。

---

## 4. G0 基准闸门结构 【结构原文恢复；样本数与抽检人为 R-委托恢复】

- **样本集**：从 351 本中挑 Stratum 现役解析质量差者，三类——密集表格 / 含公式 / 扫描件复杂版式；每类 10 份、共 30 份 `[R-委托恢复]`。
- **V1 结构保真**：表格单元格准确率、公式 LaTeX 可编译率、阅读顺序正确率。MinerU 须在至少两类上显著优。
- **V2 KU 终判（权重最高）**：同批文档两条解析路各自跑到 KU 候选，人工抽检完整性/歧义率。**终判**——解析指标好但 KU 没变好，不算过。执行方式：另一 Claude 实例初筛 + Wiki 终审 `[R-委托恢复]`。
- **V3 成本**：单文档解析延迟、VRAM 峰值。超预算直接否。
- **通过判定**：V1（≥2 类显著优）+ V2 明确更好 + V3 不超预算，三者同时满足；产出物 = 分类路由表（并存语义下，"部分类别过"即该类入 MinerU 路由，非全有全无）。

---

## 5. 红线 【原文恢复】

| # | 红线 |
|---|---|
| R1 | qmd 只做检索/切块/溯源/去重粗筛，**不做 KU 提取**，其语义层不得渗入 AII 语义层 |
| R2 | **MinerU Cloud 碰不得**（违反 Stratum 无云端原则）；qmd doc-reading.json 的 provider 必须配本地 VLM，不用 mineru_cloud，也不退化到 pymupdf 纯文本 |
| R3 | 单卡 VRAM 争用是 Track B 真瓶颈，不得低估（调度见 §2） |
| R4 | MinerU 许可 = Apache 2.0 + 附加条款；Hevi/Stratum 商业化前必读附加条款 |
| R5 | qmd / MinerU 均为独立 Docker 容器，与 aii_refined 同款隔离方式 |

---

## 6. 3O 封装映射 【原文恢复】

qmd → oskill；MinerU 解析 → omodul（fingerprint / decision_trail / report / cost 四支柱）；HTML 清洗 → oskill。

---

## 7. 第二批 open items 【原文恢复】

| 项 | 标记 |
|---|---|
| G0 各指标具体数值通过线 | `[PENDING-G0-DRYRUN]` |
| 去重粗筛阈值（方向已裁：宁可多判、设低偏保守；起始值 RRF 归一化 0.3） | `[PENDING-TRACK-A-2W]` |
| 双通道运行时调度策略 | `[PENDING-G0-RESULT]` |
| Unlimited-OCR 中间态迁移 | `[MIGRATION-UOCR-MIDJSON]` |

---

## 8. 重建状态与 delta 清单 【r1 新增】

### 8.1 置信度分级

- **原文恢复**：§0、§1、§3、§5、§6、§7 主体——自 07-09 会话记录逐字/近逐字恢复，含当年 Wiki 的关键裁决（新增通道不替换）。
- **裁决语义恢复**：§2、§4 判定语义——按同会话明文裁决与其直接推论恢复。
- **[R-委托恢复]**：G0 样本数（10/类）与 V2 抽检执行人——当年 Wiki 明言"你自己定"，按 Claude 当场提案值恢复；Wiki 过目即转正，改亦无碍（参数层本就属第二批）。
- **[RECONSTRUCTION-GAP]**：无。原文件若被寻回，以原文件为准、本版作废。

### 8.2 冻结后 delta（入仓 conformance 必办，逐条处置后 W-H1 方可引用）

| # | delta | 处置 |
|---|---|---|
| D1 | Aella-Qwen3-14B 已放弃（硬件）；DEBT-4 已裁"评测与候选模型解耦" | 本 spec 涉 KU 抽取器的表述一律按解耦口径读 |
| D2 | fragment 术语已废止 → 段落级 ULID（STRATUM_SPEC v0.2 §D2 钉定，U3 裁决） | 本 spec 涉切块/寻址处按映射读；qmd 切块粒度条款与 ULID 寻址对齐 |
| D3 | 新消费场景：W-H1 历史白文摄取。白文非 PDF，**不走 VLM 解析前端**，只用下游半段（结构化→ULID→KC/BU）+ Track A 索引 | 入仓时由 CC 出"三轨对白文的适用性判定"一节，W-H1 引用以该节为准 |
| D4 | Track A"观察 2 周"的执行状态未知 | 入仓时核实：已执行则附观察结论，未执行则 PENDING 照挂 |
| D5 | 语料底数：本 spec 成文时口径 351 本 | 入仓时对齐当前真实底数，差异注记 |
