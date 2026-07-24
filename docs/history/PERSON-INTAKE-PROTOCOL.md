# PERSON-INTAKE 协议（抽取候选人物 → 正式注册表机械入库）· 2026-07-22

> **定位**：抽取器产的**新人物候选**（`is_gold=false`）经**机械四查**后批量入正式注册表（`seeds/persons.json`）。四查**全机械、零判定**（不涉 gold 判定）；撞名不自动并（出 candidate-same 链候裁）。**红线守**：候选不入 gold；入注册表者仅为**引用数据**，且带 intake 批次号可整批回滚。
> **执行**：`tools/history/person_intake.py`（幂等；--apply 写库）。

## 机械四查（全过者入库）

- **(a) 实存查**：候选名**逐字**在其被抽取的 `source_para_ulid` 段白文内实存（substring）。不实存＝抽取幻觉，拒。
- **(b) 泛称黑名单**：官爵/泛称**单字**（公/侯/君/王/师/子/伯/臣/民/人/氏 等）+ 势力/国名单字（晉/楚/齊/秦/鄭/宋…）+ 泛称词（大夫/諸侯/國人/群臣…）**无氏不入**，拒。
- **(c) 撞名查**：与既有 `person` 的 `names_by_source` 任一名**撞名**→**不自动并**，出 **candidate-same 链**（`{candidate, existing_person_id}`）候裁。
- **(d) 批次可回滚**：入库者标 `intake_batch`（如 `W-H1a-4-001`）；整批可 `--rollback <batch>` 移除。

## referent-ambiguous 占位机制（D-038 + G4 收尾，2026-07-24）

> **适用**：泛称/职称型条目（如『翼侯』『晋侯』『郑伯』等无指名的头衔——(b) 泛称黑名单拒入类）在源文本**确实未指名**具体个体时。**不建独立 person**（D-038 原意不变）；具体落地方式（本次修订）：`actors`（或其他需 `person_ref` 的结构化字段）用共享哨兵值 `per:referent-ambiguous`，`role` 字段补充『具体头衔 + 未指名理由（附 locator）』。

- **为何不是"干脆不填这个 actor"**：省略会让『此处确有一位头衔持有者』这一事实从结构化层完全消失，对下游解析（H4 或其他消费方）不友好——哨兵占位显式结构化"有持有者、身份不明"本身，比静默省略更诚实、信息量更完整。
- **红线**：本机制**不得**用于掩盖『本可查实而未查』的懒惰——仅当源文本原文本身未指名（如左传『翼侯奔隨』不言何人）方可使用；若源文本本身指名（即便需交叉比对多源才能确认，如『汾隰』『汾旁』地名互证锁定具体人），仍须落到具体 `person_id`，不得偷懒占位。
- **哨兵值形态**（`seeds/persons.json` 内唯一一条，供全局复用，非逐案新建）：
  ```
  {person_id: "per:referent-ambiguous", names_by_source: {},
   谥字号: "★哨兵占位值（非真实人物）……", active_range: "N/A（哨兵值）",
   force_affiliations: [], intake: {batch, method: "协议扩定，非四查产物", status: "sentinel-placeholder"}}
  ```
- **供 H4 解析用**：本仓（stratum）未见 H4 相关规格文档（下游消费方定义），本占位机制为**本仓自定的通用惯例**，供后续跨仓对齐；若下游对占位形态有既定期望，以下游规格为准、本仓再行调整。
- **首例**：`arc/events/s1-quwo.json` · `ev:zhuangbo-lei-fa-yi` · 左传 `:0083`『翼侯奔隨』（未指名具体是哪位翼侯）。
- **★H4 来源说明（OP-D-068，2026-07-24 补注）**：『H4』= **hevi 侧 `R-hard` 第四门『名从注册表』**（hevi 工作树内规格，本仓不持有、不可访问）。本仓当时查无此规格，如实报告『未见』、未推测对齐（OP-D-068 所立"跨仓术语须附来源仓与含义、查无即报"之正例）。**追认（OP-D-068）**：`per:referent-ambiguous` 哨兵设计已经 Wiki/CC-A 核对，**适配 H4，无需调整**——本占位机制与 hevi 侧『名从注册表』门的消费预期一致，本条为事后确认，非本仓自行验证（本仓仍不可访问 hevi，无法自证，仅记录追认结果）。

## 入库形态

```
{person_id: "per:i4-NNN", names_by_source: {<名>: [<源 src>]},
 谥字号: "(候选·待考)", active_range: "(候选)", force_affiliations: [],
 intake: {batch, source_para_ulid, method: "qwen3-8b 抽取候选·四查过", status: "candidate-verified"}}
```

- `person_id` = `per:i<批>-NNN`（机械唯一，不强求罗马化；正式命名待考订）。
- `intake.status`：`candidate-verified`（四查过入库，抽样送裁）；candidate-same 项不入库、单列候裁。

## 送裁（不自代裁）

- 入库批**抽样 15 条** + **全部 candidate-same 项**列入汇报送顾问/Wiki 裁；裁定后转正式命名或回滚。
- OP-D033 关联：本协议是『在库源机核 100%』后**注册表扩容**的受控入口，person 解析率复测据此。
