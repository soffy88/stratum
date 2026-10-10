# B仓 判同/合并 对抗金集（回测地基）

把命门"宁碎片不错合"从一句原则变成**可度量验收线**。回测有罪推定:没跑过金集、给不出 precision/recall 的判同/合并逻辑,**不得灌库**（设计 §11、§13.1 金集最前）。

## 文件
- `gold_seed.jsonl` / `gold_seed_math.jsonl` — 人工验证的对抗种子（真实 A仓 concept_id/ku_id）。金集的可信核。
- `mine_candidates.py` — 从 A仓挖易混淆对（向量近邻 + 名字模式）→ `candidates.jsonl`（label 空，待标）。
- `candidates.jsonl` — 挖掘产物；**人工填 `label`**（same/different/uncertain）后并入金集。
- `score.py` — 覆盖度报告 + 打分（merge precision / recall，按 band 分解）。单次跑的绝对验收线。
- `runs/` — 每次 `run_gold.py` 归档的带时间戳+判据版本(git rev)预测快照，**git 版本化，不 gitignore**——回归网要能跨时间比较，历史本身要可追溯。
- `compare_runs.py` — 回归对比器：拿两次 `runs/` 快照对比，报告哪些对子从"判对"变"判错"（回归）。**这是回归网存在的唯一理由**，见下方红线。

## 一行记录格式
```json
{"pair_id":"c001","kind":"concept","a_id":2824,"a_name":"...","b_id":2586,"b_name":"...",
 "label":"different","band":"red","category":"类冲突","rationale":"...","source":"seed"}
```
- `label`: `same`（该合）/ `different`（该分）/ `uncertain`（边缘，打分时排除）
- `band`: `red`（高相似陷阱，错合零容忍）/ `yellow`（边缘）/ `green`（真同该合）
- `category`: 类冲突 / 上下位 / 跨书同名 / 表述变体 / 方向反机制 / 跨域同名异义

## 工作流
```
1. python mine_candidates.py           # 挖候选 → candidates.jsonl
2. 人工标注 candidates.jsonl 的 label   # 含对抗对必须真判
3. python score.py                     # 覆盖度: 金集构成 + 对抗类别是否齐
4. python ../dedup/run_gold.py [--model xxx] [--tag 判据版本标签]
   # 真判官在金集上跑 → preds_judge.jsonl → score.py 打分
   # → 自动归档到 runs/<timestamp>_<tag>.jsonl
   # → 自动跟上一次归档比对回归(等价于手动跑 compare_runs.py)
5. (需要时) python compare_runs.py --baseline runs/<旧>.jsonl --current runs/<新>.jsonl
   # 默认不传参数则取 runs/ 里最新两次
```

## ★回归网 vs 优化目标(AII-EVALSET-SPEC-001 核心红线,务必先理解)

这批金集的金标准（`label`）来自人（Wiki/经理人）对"这两个概念是不是同一个"的本体判断——
这类判断**没有客观数字裁判**，标注者和被评估的判同逻辑本质上是同一套认知体系的两端。

- **✅ 唯一允许的用途**：判据改动前后各跑一次 `run_gold.py`，用 `compare_runs.py` 对比——
  检验"这次改动有没有把原本判对的搞坏"（回归警报），或"是不是真的变好了"（需人工确认）。
  **裁决权永远在 Wiki**，`compare_runs.py`/`score.py` 只出报告，不自动判定放行。
- **❌ 绝不允许**：把这批标注的通过率/precision 当**优化目标**去自动搜索/调参判据参数
  （阈值、prompt、模型选择等）。那等于"用人的判断当目标函数去优化人的判断"——优化器
  会找到"恰好让这 15+ 对标注全对"的参数组合，但这批标注只覆盖了想到的边界，判据在
  标注之外的真实数据上可能更糟（reward hacking）。
- **❌ 绝不允许**：让 LLM 生成金标准本身（用被测对象生成裁判 = 裁判彻底污染）。
- **❌ 绝不允许**：对外/对自己宣称"判同准确率 X%"——这个数字只对这批标注有意义，
  不代表判同真的准。
- 这套区分只适用于判同/合并这类**没有客观裁判**的评估集；B仓 M5 查询层的检索评估
  （Recall@k 有客观裁判）不受此限制，可以自动调参，但要带 held-out/噪声阈值/预算刹车/
  日志四道闸（见 AII-EVALSET-SPEC-001 §3）。

## 验收线（命门不对称）
- **merge precision → 1.0**（裁 same 里真 same 占比，验收线 ≥ 0.99）：错合近零是硬线。
- **recall 可低**：宁碎片，不设下限。
- **red band 错合零容忍**：高相似陷阱里 gold different 却 predicted same，出现即 FAIL。
- `uncertain` 对不参与打分（诚实：拿不准的不当标尺）。

`preds.jsonl` 由步骤2的去重/判同逻辑产出——金集先立，判同逻辑后建，每改阈值/prompt/模型跑一遍。
`方向反机制` 类依赖 M1 超边 head（超边建成后才有机制对），`跨域同名异义` 需跨学科概念，二者待挖掘/M1 后补。
