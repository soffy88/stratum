# PERSON-INTAKE 协议（抽取候选人物 → 正式注册表机械入库）· 2026-07-22

> **定位**：抽取器产的**新人物候选**（`is_gold=false`）经**机械四查**后批量入正式注册表（`seeds/persons.json`）。四查**全机械、零判定**（不涉 gold 判定）；撞名不自动并（出 candidate-same 链候裁）。**红线守**：候选不入 gold；入注册表者仅为**引用数据**，且带 intake 批次号可整批回滚。
> **执行**：`tools/history/person_intake.py`（幂等；--apply 写库）。

## 机械四查（全过者入库）

- **(a) 实存查**：候选名**逐字**在其被抽取的 `source_para_ulid` 段白文内实存（substring）。不实存＝抽取幻觉，拒。
- **(b) 泛称黑名单**：官爵/泛称**单字**（公/侯/君/王/师/子/伯/臣/民/人/氏 等）+ 势力/国名单字（晉/楚/齊/秦/鄭/宋…）+ 泛称词（大夫/諸侯/國人/群臣…）**无氏不入**，拒。
- **(c) 撞名查**：与既有 `person` 的 `names_by_source` 任一名**撞名**→**不自动并**，出 **candidate-same 链**（`{candidate, existing_person_id}`）候裁。
- **(d) 批次可回滚**：入库者标 `intake_batch`（如 `W-H1a-4-001`）；整批可 `--rollback <batch>` 移除。

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
