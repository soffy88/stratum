# B仓步骤2 · KU去重 SAME 人工签核清单（经济三书, v3_full）

> 来源: `refined_dedup_dryrun.py --sim 0.78 --max 200`（强化范围判例后全量147）。
> 裁决: SAME=49 · DIFFERENT=97(硬闸67) · UNCERTAIN=1。命门: 宁冗余不误删 / 宁碎片不错合。
> CC 已逐对核, 标出疑似错合。**签核通过的 SAME 才进步骤3落库整合。**

## 🔴 疑似错合（建议剔出 SAME → 保留两份）
| sim | A | B | 问题 |
|---|---|---|---|
| 0.796 | [microe]Tax incidence(概念) | [mankiw]Equivalence of taxes on sellers and buyers(命题) | **已核原文**: 一个是"税负归宿"一般概念, 一个是"征税方等价"具体结论。违判例(3) 一般概念vs具体命题 → 应 DIFFERENT |
| 0.783 | [microe]Normative analysis | [micro_]Distinction between positive and normative | 后者(实证vs规范之分)⊋前者(仅规范), 整体-部分。边缘, 建议剔 |

## 🟡 边缘可放行（核心同概念, 但范围略不齐, 倾向保留为 SAME）
| sim | A | B | 说明 |
|---|---|---|---|
| 0.823 | [microe]Production Possibilities Frontier | [mankiw]shape and position of PPF | 同讲 PPF, 后者偏形状/位置侧面 |
| 0.818 | [microe]Equilibrium Price | [micro_]Market Supply and Demand Together | 同讲市场均衡价 |
| 0.786 | [microe]Market-Clearing Price | [mankiw]Market equilibrium | 市场出清价 ≈ 市场均衡 |

## 🟢 真同点（47 - 上述 = 44 对, 跨书同概念, 建议直接通过）
Scarcity ×3 · Consumer Surplus ×6 · Producer Surplus ×3 · Derived Demand(一般)×3 · Eminent Domain ·
Monopolistic Competition · Transaction Cost ×2 · Price Floor · Price Ceiling · Supply of Labor ·
Price Taker(s) ×3 · Oligopoly · Property Rights ×2 · Long-run market equilibrium · Game theory ·
Willingness to Pay · Marginal analysis · Factors That Shift Supply · Normal vs Inferior Goods ·
Opportunity Cost ×2 · Price Controls · Absolute Advantage · Diminishing Marginal Benefit ·
Horizontal Summation→Market Demand · Economics defined · Movement vs Shift of Supply ×1 ·
From Individual to Market Supply Curve · Difference: change in demand vs movement along curve

## ⚪ UNCERTAIN（安全阀已自动保留两份, 无需动）
- 0.781 [mankiw]Opportunity Cost ? [microe]Economic cost — 两票不一致(机会成本≠经济成本), 已落 UNCERTAIN=保留。

---
**CC 结论**: harness 称职(浮出候选+硬闸挡确定性错+安全阀抓翻脸对)。SAME 里疑似错合 ~2/49 ≈ 4%, 全是"概念vs命题/整体-部分"自信错合类——prompt 调优挡不全, 按设计 §6.3 由人工门拦下。请经理人签核上表后再开步骤3。
