# 论文向 BU Schema(2026-07-16)

论文 ≠ 教材。教材范式(逐章讲透 → 堆概念 KU)套在论文上,约一半 KU 是概念(教材里都有,冗余)。
6 篇跨类型论文实证(理论经济 / 计量 / 博弈-不可能性 / 黎曼优化 / 预测市场金融 / ML 离散扩散),
独立收敛出同一套结论。本文档是论文入库的规范,`generate_bu.py` / `persist_bu.py` 的论文分支据此实现。

## 两层(对应"人类用1 / agent用skill")

### 「1」论文理解 —— 人类读,存 `bu_onto` 现有列(`doc_type='paper'`)
| bu_onto 列 | 放什么 |
|---|---|
| `overview_oneline` | 一句话:这论文干嘛 |
| `problem_statement` | 解决什么问题 + 已有方法的缺口 |
| `main_claims` | 关键结论/定理(`key_findings`,每条**带成立条件**) |
| `limitations` | 作者自陈局限/失效边界 |
| `positional_summary` | `{relation_to_prior}`:扩展/反驳/涵盖了谁 |
| `authors` / `venue_year` | 书目(原 bu_onto 缺,0008 补) |

### 「skill」agent 可调用对象 —— agent 用,存 `bu_onto.agent_skill` (jsonb)
| 键 | 放什么 | 为什么(6篇共识) |
|---|---|---|
| `contribution_type` | method / empirical / **impossibility** / framework / survey | 防误用第一闸:不可能性论文不能被当"我获得了保证" |
| `method` | {approach, steps, inputs, outputs} | agent 要复用的是配方 |
| `preconditions` | [{assumption, failure_if_violated}] | 该不该用的硬门 |
| `use_when` / `do_not_use_when` | 任务触发(正)/ 硬排除(负) | 召回钩子 + 误用护栏 |
| `boundary_conditions` | [{claim, direction, holds_when, reverses_when}] | 防把条件结论当无条件事实 |
| `key_results` | [{metric, value, baseline, dataset}] | 可复用量化锚点 |
| `reusable_artifacts` | [{name, what, where}] | agent 常只抠一个 trick + 代码 |
| `dependencies` | [前置组件/方法] | 别以为拿来即用 |
| `references_concepts` | [通用概念名] | **只指针,不复制** |
| `coined_terms` | [{term, definition}] | 只放本篇新造术语 |

## 概念规则(6/6 一致,最重要的一条)
- **通用概念一律只存指针**(`references_concepts`),去重发生在概念层,bu 里**绝不复述教材概念**。
- 只内联两种:①本篇**新造/重命名的术语**(`coined_terms`);②本篇**对某概念的新发现**(进 `boundary_conditions`,如"transversality 在稀疏 Stiefel r>1 会失效")。
- **判据**:参考文献里找得到 = 通用(指针);本篇为解决问题而新造/改造 = 贡献(内联)。**新颖性归属,不是"看着基不基础"**。

## 教材字段对论文留空(别硬塞)
`learning_thread` / `structure`(章节) / `concept_network`(网) / `core_explanations` / `member_kc_ids`
—— 教学导向,论文低价值。`doc_type=paper` 时保持 NULL,别逼 LLM 编教材内容污染库。

## 实现
- migration `0008_bu_paper_fields.sql`:bu_onto 加 `agent_skill` / `limitations` / `authors` / `venue_year`。
- `generate_bu.py`:`AII_MD_FILE` 带 `doc_type: paper` frontmatter → `_go_paper()` 早返回,喂论文正文(首尾+节标题)给 LLM 出论文卡 JSON;教材路径零改动。
- `persist_bu.py`:bu json 带 `_paper` → `_persist_paper()` 入 `doc_type='paper'` + 两层字段;教材 insert 不动。
- 触发:advmath_pipeline.sh 第 [5/6] 步照常调 generate_bu/persist_bu,论文分支内部自动激活,无需改管道。

## 待办(下一步,另议)
- **概念 KU 弱化**:synth 阶段对论文少抽 conceptual KU(本 schema 只管 BU 层,KU 层暂未改)。
- **skill 被 agent 调用**:`agent_skill` 如何被下游 agent 检索/调用(retrieval 接口),是"agent 用 skill"落地的下一环。
