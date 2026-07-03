# B仓 去重机制（A仓 → B仓 入口工序，②）

按设计 §5.1 五步：**判同(读原文)→ 内容整合(contributions 追加 + 原子性预算)→ 落库 → 概念归一(M0)→ 谱社区**。
每步决策写 `rf.decision_ledger`（append-only，可重放，B=f(A仓,台账)）。命门：**宁冗余不误删、宁碎片不错合，存疑一律判 different**。

## 模块
| 文件 | 职责 |
|---|---|
| `dict/dimensions.yaml` | 判别维度闭集词典（本质/表述 标注，与判同共用）|
| `dict/terms.yaml` | 术语规范闭集词典（原名变体 → 英文 canonical + 中文名；受控对齐非自由翻译）|
| `dictionary.py` | 词典加载/查询：`family_for` / `dimensions_hint` / `canonical` |
| `ledger.py` | `DecisionLedger`：append-only `record` + `replay_lookup`（命中不重问模型）|
| `judge.py` | 判同 `judge_pair`：读原文双语判、维度提示、宁冗余(uncertain→different)、台账 replay、强模型档 |
| `integrate.py` | `cluster_same`(union-find) / `build_contributions`(去重留出处) / `needs_split`(原子性预算) / `persist_refined_ku` |
| `run_gold.py` | 金集自证：判官在对抗金集上跑 → `preds_judge.jsonl` → 调 `score.py` |

## 语言（设计 §5.3）
判同**读原文**（zh 判中文、zh-en 双语判），**内容不做 zh↔en 翻译**；名称经 `terms.yaml` 受控对齐英文 canonical。呈现层中文优先是前端事，不在此。

## 模型档（设计 §6.4，命门不对称→算力不对称）
- 粗筛/candidate：本地小模型（0 成本）。
- **不可逆 confirmed 合并：最强可用模型**（`deepseek-pro` 等）。`run_gold.py --model` 选档。
- 本地 `qwen2.5:7b`(Ollama) 仅作 harness 自证/粗筛档，不用于不可逆 confirmed。

## 回测有罪推定（设计 §11、§13.1）
判同逻辑改动后先过金集：
```
ECON_LLM_PROVIDER=... uv run python scripts/dedup/run_gold.py --model <judge>
# → preds_judge.jsonl → score.py: merge precision 必 →1，red band 错合零容忍
```
未过金集不得碰真数据/灌库。

## 落库路线（后续 步骤3）
`candidates(粗筛) → judge_pair(逐对，台账) → cluster_same → build_contributions → persist_refined_ku`，
全程写台账；错合修复 = 改台账 + 重放受影响子图。**先过金集再全量。**
