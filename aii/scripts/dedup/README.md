# B仓 去重机制（A仓 → B仓 入口工序，②）

按设计 §5.1 五步：**判同(读原文)→ 内容整合(contributions 追加 + 原子性预算)→ 落库 → 概念归一(M0)→ 谱社区**。
每步决策写 `rf.decision_ledger`（append-only，可重放，B=f(A仓,台账)）。命门：**宁冗余不误删、宁碎片不错合，存疑一律判 different**。

## 模块
| 文件 | 职责 |
|---|---|
| `dict/dimensions.yaml` | 判别维度闭集词典（本质/表述 标注，与判同共用）|
| `dict/terms.yaml` | 术语规范闭集词典（原名变体 → 英文 canonical + 中文名；受控对齐非自由翻译）|
| `dictionary.py` | 词典加载/查询：`family_for` / `dimensions_hint` / `canonical` |
| `gates.py` | 程序关(确定性)：关1 判别维度 / 关2 上下位 / 关0 术语同名（LLM 关3 之前拦, DIFFERENT 关优先）|
| `ledger.py` | `DecisionLedger`：append-only `record` + `replay_lookup`（命中不重问模型）|
| `judge.py` | 判同 `judge_pair`：程序关→关3弱判→**same 才升级强模型确认**、读原文双语、台账 replay |
| `integrate.py` | `cluster_same`(union-find) / `build_contributions`(去重留出处) / `needs_split`(原子性预算) / `persist_refined_ku` |
| `candidates.py` | `ku_candidates`：A仓 ku_onto 向量近邻粗筛同点候选对（跨语种, 非静默截断）|
| `orchestrate.py` | 编排：粗筛→判同→聚簇→整合→[dry-run 报告 / `--apply` 落库]，全程台账 |
| `run_gold.py` | 金集自证：判官在对抗金集上跑 → `preds_judge.jsonl` → 调 `score.py` |

## 语言（设计 §5.3）
判同**读原文**（zh 判中文、zh-en 双语判），**内容不做 zh↔en 翻译**；名称经 `terms.yaml` 受控对齐英文 canonical。呈现层中文优先是前端事，不在此。

## 模型档（设计 §6.4，命门不对称→算力不对称；强模型只用在最需要处省钱）
三档递进，越贵的用得越少：
1. **程序关 关0/1/2**（免费, 确定性词典）——解决大多数。
2. **关3 弱判**（`--weak`, 便宜/本地: `deepseek-flash` 或 Ollama `qwen2.5:7b`）——判所有残余。
3. **升级强判**（`--strong deepseek-pro`）——**仅当关3弱判=same** 这个不可逆决策才调用；强模型不确认→宁碎片判 different。`different`/`uncertain` 安全可逆, 不升级、不花钱。

即 `deepseek-pro` 只碰"提议合并"的少数对。Ollama 可用时 `--weak default`（`ECON_LLM_PROVIDER=ollama`）令关3弱判也免费。

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
