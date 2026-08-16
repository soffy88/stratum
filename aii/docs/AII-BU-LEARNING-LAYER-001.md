# AII-BU-LEARNING-LAYER-001 · BU 升级（按 su-learning-map 标准）

版本：2026-08-14
范围：`aii.bu_onto`（doc_type='textbook'）；论文路径（doc_type='paper'）不受影响。

## 问题

1. 原七项书级抽象（soul/positioning/…）是 LLM 单次调用的无据口号：无依据、无定位、无可核验性。
2. 原 BU 没有学习层：只回答“书是什么”，不回答“人怎么学”，无练习、无路径、无证据分级。

## 升级一：七项 → 证据挂接版（迁移 0012）

`facets_grounded` 列：每项 = `{key,text,basis,ku_ids[],evidence,grades[],excerpts[{text,ku_id,locator}]}`。

- `basis`：判断依据（依据哪些 KC/枢纽/KU 的什么内容，≥30 字）——这就是“不再口号化”的核心。
- `evidence` 由代码按 KU grade 重算（LLM 无权）：verified → primary；≥2 KU → corroborated；单条 → primary。
- `excerpts` 为逐字原文切片（代码从 grounded_by quote 或 0-LLM 抠原文注入）。
- 无 KU 支撑的项：skeleton 必须引用 ≥2 个枢纽概念（数据算出），其余必须显式对冲（“从结构推断，未见直接论述”），否则门丢弃；坏源 KU（refuted/contradicted/low）剥除，全坏则丢项。
- 兼容：facets_zh/en 保留扁平文本；新前端读 facets_grounded 渲染依据+证据徽章+原文切片+定位。

## 升级二：学习层（迁移 0011）

| 列 | 内容 |
|---|---|
| `learning_paths` | 3–7 条能力转变路径 `{id,no,name,promise,card_ids[]}`（学完能做什么，非原书章节名） |
| `deep_cards` | 深卡（su-learning-map 学习内容 Schema）：`id,name,path,ku_ids[],evidence,desc,excerpt,context,arguments[],source_digest[],boundary,connections[],practice,source_excerpts[],grounding_grades[]` |
| `bu_quality` | 质量门记录 `{status: ok|partial|insufficient_data, checks[], dropped[], stats}` |

## 证据规则（代码权威，LLM 无权决定）

- **证据分级**（`bu_learning_gate.evidence_class_for`）：grade=verified → `primary`；≥2 条独立 KU → `corroborated`；单条 → `primary`。grade ∈ {refuted, contradicted, low} → 整卡丢弃（坏源）。grade=unverified → 允许，但逐卡透明记录 `grounding_grades`（铁律：未核实≠坏，必须可见）。
- **逐字切片**（`resolve_verbatim`，0-LLM 注入）：
  - 优先 `grounded_by.evidence_quotes`（LLM 书，NO_SPAN 已验证）；
  - 其次 `extraction_method ∈ {program_extract, legacy_ingest}` 时 `natural_text` 本身（0-LLM 数学书定理原文）；
  - LLM 综合书无 quote → 无逐字来源 → 卡丢弃。LLM 只写内容字段，**不写 quote**。

## 深卡下限（与 build_learning_map.py deep 模式对齐）

context≥50 字；arguments≥3 条且合计≥100 字；source_digest≥2 段且合计≥220 字；boundary≥40 字；
practice 含动作词且≥10 字；connections 解析且不动点修剪后非空；路径 card_ids 全体分区。

证据底限不过 → 诚实 `insufficient_data`（对齐 0-KU 短路哲学：不够就缩小范围，不编造确定性）。

## 生成与持久化

- `scripts/generate_bu.py`：共享采样器 `_fetch_ku_meta()`（按 KC 覆盖采样 ≤60 KU，含逐字来源）→ 七项证据挂接 + 学习层两次 LLM 调用（都只写内容字段）→ 代码注入切片/证据 → 门修剪。
- `scripts/persist_bu.py`：教材分支持久化四列（learning_paths/deep_cards/bu_quality/facets_grounded，ALTER 守卫 + INSERT 扩展）。
- `scripts/bu_learning_gate.py`：门（`validate_bu_facets` + `validate_learning_layer` + `resolve_verbatim` + `evidence_class_for`）+ 审计 CLI。
- 环境开关 `AII_BU_LEARNING=0` 可跳过学习层（默认 1）；七项证据挂接始终开启。

## 验证

- 单元：证据分级映射 / verbatim 解析 / 学习层端到端修剪 / 七项门（坏源→all_ku_bad_grade、无据无对冲→丢、枢纽骨架与对冲推断→inference 存活）全部 PASS。
- 集成：真实 DB（math_prog_1f660086ff，1479 KU）+ LLM 桩：七项 7/7 存活（excerpt 为真实定理原文）、学习层 6 卡/3 路径。
- 迁移 0011/0012 已在本地 dev DB 应用；审计 CLI 对旧 BU 返回 insufficient_data（重跑生成后生效）。
- 前端：/book 页渲染 basis + 证据徽章 + 原文切片 + 定位（aii-web 类型零新增错误；存量 @helios/blocks 工作区解析错误与本次无关）。

## 待办

- [x] 任选一本已抽 KU 的书重跑 `generate_bu.py && persist_bu.py` 生成首批证据挂接七项 + 学习层。
      **已生成两本真实批次(2026-08-16, 真实 LLM)**：
      - `econ_zh_2726f38224`（产业经济学, 177 KU, legacy_ingest 逐字分支）：七项 7/7 primary、5 路径/10 卡、ok。
      - `math_prog_2ee1b2936e`（凸优化压缩通信讲义, 53 KU, **evidence_quotes 逐字分支**）：七项 7/7、5 路径/10 卡、ok。
- [x] 旧书重跑后由审计 CLI 复核每本的七项/学习层质量记录：两本均 `ok`，exit 0。
- [x] 前端学习层已实现(components/LearningLayer.tsx, /book 与 /books 共用, 4/4 组件测试通过)；
      已部署: stratum-sl 重启载入新 display.py（book/bu + bu/{id} 返回 facets_grounded/learning_paths/deep_cards/bu_quality），
      aii-web 镜像重建（含 LearningLayer chunk），线上经 aii-web 代理验证 7/5/10 全通。

## 本轮修复（真实运行暴露, 2026-08-16）

- **quote 路径逐字注入截断错位**：`generate_bu.py` 注入 excerpt 时 `v["text"][:150]`，而 gate 要求
  excerpt ∈ verbatim 完整原文集合（quote 可达 200+ 字）→ 全部 `no_verbatim` 误杀。text_head 路径因
  resolve_verbatim 已截 150 而侥幸通过。修复：注入不再截断（存储时 gate 统一截 150）。
- **落库复验幂等**：gate 输出卡时 source_excerpts 截到 MAX_EXCERPT，审计 CLI 复验用完整 verbatim
  集合 → 截断文本不再是成员 → 误报 `no_verbatim_grounding`。修复：匹配容忍「截断前缀」
  （`st in allowed or any(a.startswith(st))`），七项与学习层两处同改。
- **审计 CLI jsonb 解析**：asyncpg 把 jsonb 返回为 str，CLI 未解析就入门 → 有数据的书误报
  `deep_cards 为空`。修复：`_loads()` 解析后传入。
- 回归断言（证据分级映射 / verbatim 解析 / 前缀幂等 / 坏源剥除）全部 PASS。
