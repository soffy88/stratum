# B仓 判同/合并 对抗金集（回测地基）

把命门"宁碎片不错合"从一句原则变成**可度量验收线**。回测有罪推定:没跑过金集、给不出 precision/recall 的判同/合并逻辑,**不得灌库**（设计 §11、§13.1 金集最前）。

## 文件
- `gold_seed.jsonl` — 人工验证的对抗种子（真实 A仓 concept_id/ku_id）。金集的可信核。
- `mine_candidates.py` — 从 A仓挖易混淆对（向量近邻 + 名字模式）→ `candidates.jsonl`（label 空，待标）。
- `candidates.jsonl` — 挖掘产物；**人工填 `label`**（same/different/uncertain）后并入金集。
- `score.py` — 覆盖度报告 + 打分（merge precision / recall，按 band 分解）。

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
4. <判同逻辑> 产出 preds.jsonl          # {"pair_id":"...","predicted":"same|different"}
5. python score.py --pred preds.jsonl  # merge precision / recall
```

## 验收线（命门不对称）
- **merge precision → 1.0**（裁 same 里真 same 占比，验收线 ≥ 0.99）：错合近零是硬线。
- **recall 可低**：宁碎片，不设下限。
- **red band 错合零容忍**：高相似陷阱里 gold different 却 predicted same，出现即 FAIL。
- `uncertain` 对不参与打分（诚实：拿不准的不当标尺）。

`preds.jsonl` 由步骤2的去重/判同逻辑产出——金集先立，判同逻辑后建，每改阈值/prompt/模型跑一遍。
`方向反机制` 类依赖 M1 超边 head（超边建成后才有机制对），`跨域同名异义` 需跨学科概念，二者待挖掘/M1 后补。
