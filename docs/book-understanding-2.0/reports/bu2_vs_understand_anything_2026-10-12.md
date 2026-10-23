# BU2 vs Understand-Anything（2026-10-12）

样本：托马斯微积分 BU2 最新 VERIFIED run br_01M4J1FJMHTR4YK9E15S6FV2EA（aii_kg.stratum），对照同济最新 VERIFIED run。

## BU2 实际产出（托马斯，18 个单元）
- 全书概念 63 个，每章 3–5 个；缺 Taylor 级数（第 10 章核心），Chain Rule/FTC 仅各出现一次。
- ch1、ch12、ch15 无论点、无概念、无证据，但整本仍 VERIFIED、coverage 1.00 → 校验过松。
- 每章证据 2–3 条，全部 is_supported=true，evidence_refs 指向已丢失原文的 ev_* id。
- 论证引用 arguments_refs 全书为 0；推理图只有 18 个 CHAPTER 节点、40 条章节依赖边（无概念/定理节点），unresolved 49。
- 全书 governing question / central thesis 是模板话（"What is the intellectual structure of this book?"）。
- concept_evolution 63 条的 definition 都是占位文本 "introduced or redefined in chX"。
- bm1（习题答案附录）被当成一章并写进论述弧。
- 已有章节论点抽查基本正确（ch3 导数=差商极限、ch8 奇偶函数对称积分为零、ch6 截面积积分）；ch10 论点"级数用来表示复数"偏题。

## 评分（1–10）
准确性 6 / 覆盖 4 / 深度 3 / 可追溯证据 2 / 跨章综合 4 / 表达能力 5
结论：只到"目录级 + 每章一句话论点"的理解，远未透彻；能复述大意，不能讲透定理链条，也无法回到原文出处。

## 与 Understand-Anything（/understand-knowledge）对比
| 项 | BU2 | UA |
|---|---|---|
| 输入 | PDF→markdown 整书，按章 LLM 阅读 | 必须是 Karpathy 式 Markdown wiki（index.md + wikilink），不读 PDF |
| 抽取粒度 | 章节问题/论点/概念/论证/机制/概念演化，schema 很深 | 实体、claims、隐含关系，按 wiki 页面 |
| 结构骨架 | 全靠 LLM | tree-sitter/wikilink 确定性解析 + LLM 语义层 |
| 关系 | 7 种带 reason 的边，但实际只填了章节依赖 | 显式链接 + LLM 隐含关系，社区聚类 |
| 证据追溯 | 设计有，实际原文丢失 | 节点即 wiki 页面，天然可回链 |
| 校验 | 质量门槛过松（空章也 PASS） | graph-reviewer 查完整性和引用一致性 |
| 可视化/问答 | 前端页、PPT 导出 | 交互图谱、导览、语义搜索、chat、diff 影响 |
| 增量 | 整书重跑 | 指纹增量 |
| 适合 | 教材/论著的深层"作者意图" | 代码库、已整理的知识库 |

## BU2 可借鉴
1. 先确定性抽骨架（标题层级、定义/定理/例题编号——A-P9 book_freeze 已有 952 个 KU），再让 LLM 只做语义层，把 BU2 概念挂到 KU 上。
2. graph-reviewer 式硬校验：空章、占位定义、悬空证据 id 一律 FAIL。
3. 节点=可点击原文片段（KU locator），证据不再是孤立 id。
4. 自动导览（按依赖排序的学习路径）和语义搜索/问答。
5. 指纹增量。

## BU2 强于 UA
- schema 针对"书"：论证、机制、情境模型、概念演化、负知识、跨书 P14，UA 没有这些。
- UA 根本不能直接吃书；把书转 wiki 这一步恰恰是最难的理解工作。

## 一句话
UA 不能替代 BU2，但 BU2 当前产出离"透彻理解"还差很远；最有效的路径是把 BU2 的语义层挂到 A 仓 KU 骨架上并收紧校验，再借 UA 的图谱/导览做呈现。
