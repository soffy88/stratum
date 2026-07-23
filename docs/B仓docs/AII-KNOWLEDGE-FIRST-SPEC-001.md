# AII 知识优先增强 SPEC（God Node + Leiden + Query-First）

> **Doc ID:** AII-KNOWLEDGE-FIRST-SPEC-001
> **面向:** CC（WSL2 实施）
> **依据:** AII-BREPO-VIZ-SPEC-001（可视化审查）+ AII-INVARIANT-LAYER-001（本性路径 B：核心抽象概念直推）+ AII-LEARNING-COACH-SPEC-001 / AII-CONTEXT-REPO-SPEC-001（B/C 仓被查询使用）+ AII-FIRST-PRINCIPLES-001（原则一/二）。
> **外部印证来源:** Graphify（90k★，MIT，纯本地代码知识图谱）——其 God node / Leiden 社区 / EXTRACTED-INFERRED 标签 / query-first 钩子四个设计，独立印证 AII 判断。本 SPEC 落地其中两个可直接用的改进 + 一个新机制。
> **性质:** 三个独立小改进，可分别实施。**不改 B/C 仓数据（只读）。**

---

## 改进一 · God Node 检测（升级可视化：从"审查"到"主动发现本性候选"）

### 1.1 是什么 + 为什么对 AII 有独特价值
God node = **"什么东西被所有其他东西流经/依赖"**——图上入度/中心性极高的节点。

> ★对 AII 的独特价值（不只是可视化功能）：**一个被大量超边/KU 引用的概念，很可能是核心抽象概念** → 正是 AII-INVARIANT-LAYER-001 **路径 B（从核心抽象概念直接抽本性）的候选**。God node 检测 = **本性路径 B 候选的自动发现器**。
> 例：若"均衡""熵""反馈"在 B 仓被大量超边连接、被多学科 KU 引用 → God node 浮现 → 提示"这可能是个承载本性的核心抽象概念，值得走路径 B 抽本性"。

### 1.2 实施（补进 VIZ-SPEC 的能力）
```
数据层（Graphology 自带中心性算法，前端或 API 层算）：
  · 计算每个概念节点的：入度 / degree centrality / betweenness centrality
  · God node 判据（可调）：中心性 top-N% 或超过阈值
  · ★分学科看：一个概念若在【多个 discipline】的 KU/超边里都是高中心性
    → 更强的本性路径 B 候选（跨学科的核心抽象概念）
API（8101 新增）：
  GET /api/graph/god-nodes?min_centrality=&cross_disc_only=
    → [{concept_id, label, centrality, in_degree, disciplines:[...],
        invariant_candidate: bool}]  # cross_disc 高中心性 → invariant_candidate=true
可视化（VIZ 视图1/视图3）：
  · God node 视觉突出（大号/高亮）
  · ★invariant_candidate=true 的 → 特别标记"本性路径B候选"
  · 点开 → 看它被哪些超边/KU 引用、跨哪些学科
```

### 1.3 命门
```
· God node 只是【候选提示】，不是【本性认定】——高中心性≠有本性
  （一个概念被大量引用，可能只是基础常用，不代表有跨域不变内核）
· 是否真有本性，仍走 AII-INVARIANT-LAYER-001 四关判据 + 三层互证 + 人工确认
  （原则二：本性判定无可信裁判 → 留人）
· God node 检测是"把人的注意力引到值得看的地方"，不替人下判断
```

---

## 改进二 · Leiden 社区检测（替换/指定谱社区 KC 的算法）

### 2.1 为什么是 Leiden（不是 Louvain）
```
B 仓主题 KC = 谱社区检测的产物（master §4.3 refined_theme_kc）。
VIZ-SPEC 只写了"Graphology 自带社区检测"，未指定算法。→ 本 SPEC 指定 Leiden。
Leiden vs Louvain（实证）：
  · Louvain 会产生【断裂社区】（community 内部实际不连通）——对 KC 是硬伤
    （一个"主题 KC"里的 KU 实际不相关 = 假聚类 = 污染）
  · Leiden 保证社区内部连通（refinement 阶段），质量更高、更稳定
→ ★AII 命门角度：Louvain 的断裂社区 = 一种"看起来聚成一类实际不相关"的附会
  Leiden 从算法上避免它 → 与"宁碎片不错合"精神一致
```

### 2.2 实施
```
· 谱社区 KC 生成（B 仓 M0 后、主题 KC 构建时）用 Leiden，非 Louvain
  实现：Python igraph / leidenalg（成熟库），或 Graphology 的 leiden 实现
· 输入：概念-KU 二部图 / 概念共现图
· 输出：社区划分 → refined_theme_kc（每个社区一个主题 KC）
· ★social 标签：社区检测出的簇要人工/LLM 命名主题（community_name），
  不是留数字 id（Graphify 踩过坑：incremental rebuild 会把 name 退回数字，要防）
· 参数（resolution）影响社区粒度 → ★这是"可自动循环"的旋钮吗？
  —— 否！社区划分的"对不对"没有客观裁判（主题聚得好不好是判断）
  → 按原则二：resolution 由人看着可视化调，不自动优化（留人）
```

### 2.3 与评估集的关系
```
社区划分改动（换算法/调 resolution）→ 用 A 类回归网思路检验"别改坏"：
  · 标注一批"这些 KU 该在同一主题 / 不该在同一主题"金标准
  · 改动前后对比，看已聚对的有没有被打散
  （同 EVALSET-SPEC A 类：只防改坏，不自动优化）
```

---

## 改进三 · Query-First 钩子（防 B/C 仓白建的关键机制）

### 3.1 要解决的真实风险
```
★风险：学习助手/决策辅助运行时，Claude（经理人）可能【凭训练数据/通用知识】
  直接回答，而不去查 B 仓辛苦编译的 KU / C 仓的判断资产。
  → 后果：B 仓白建了。你花大力气把多本书去重增强成"导数"的融合精华，
    结果教你时 Claude 用自己的通用知识讲了——B 仓没被用上。
Graphify 的解法：装 hook，在助手要 grep/读文件【之前】拦截，推它先查图谱。
→ AII 借这个思路：在 Claude 凭记忆答【之前】，强制先查已编译知识。
```

### 3.2 实施（分两个场景）

**场景 A：学习助手用 B 仓教学**
```
规则（写进学习助手的运行约束 / 系统提示 / 检索前置）：
  Wiki 问一个知识点 → ★必须先查 B 仓该概念的 KU（融合精华 + 多出处）
    → 用 B 仓 KU 的内容教（中文显示，术语受控，见 COACH §1.4）
    → 只有 B 仓【确实没有】该知识点，才允许经理人用通用知识补
      （且必须【明确标注】"这部分 B 仓未覆盖，来自通用知识，未经 AII 编译"）
  ★禁止：B 仓有该 KU 却不查、直接用通用知识讲
验收：教学时每个知识点可追溯到 B 仓 KU（gold_ku_ids），
  通用知识补充的部分必须显式标注来源
```

**场景 B：决策辅助用 C 仓**
```
规则：Wiki 提决策问题 → ★必须先查 C 仓相似案例/原则/反例
    → 主动投递（VISION：呈现判断光谱，各标来源+grade）
    → C 仓无相关判断资产时，才用通用知识，且标注"非你的判断历史"
  ★禁止：C 仓有相关案例却不召回、直接给通用建议
```

### 3.3 为什么这是原则问题不只是工程
```
· B/C 仓的全部价值 = 它们是【被编译过、可溯源、带 grade】的知识
· 若查询时绕过它们用通用知识 = 放弃了 AII 相对通用 LLM 的【全部优势】
  （通用知识不可溯源、无 grade、可能过时、不是"你的"判断）
· Query-first = 强制"先用编译过的真知识，通用知识只做显式标注的兜底"
  → 这是 AII"看裸真相/可溯源"在【使用】环节的落地
  （前面所有 SPEC 保证【构建】可溯源，query-first 保证【使用】也走可溯源的路）
```

### 3.4 ★与 EXTRACTED/INFERRED 精神一致（grade 铁律贯到使用侧）
```
Graphify：每条边标 EXTRACTED（源文明写）/ INFERRED（推断）。
AII 对应：教学/决策辅助的每个输出，标清来源层级：
  · 来自 B/C 仓（编译过、可溯源、带 grade）—— 优先，明示 KU/case id
  · 来自通用知识（未编译、不可溯源）—— 兜底，★必须显式标注
→ Wiki 永远知道：这句话是"AII 编译过的真知识"还是"Claude 的通用知识"
  （同 grade 铁律：永远分清硬的和软的）
```

---

## 执行顺序与红线

### 顺序
```
改进一 God node：随 VIZ 视图1/视图3 一起做（Graphology 中心性，成本低）
改进二 Leiden：M0 后、主题 KC 构建时用（换掉默认社区算法）
改进三 Query-first：学习助手/决策辅助上线时的运行约束（B/C 仓被使用时）
三者独立，可分别实施，不互相阻塞。
```

### 红线
```
1. God node 只是本性路径B【候选提示】，不认定本性（仍走四关+三层互证+人工）
2. Leiden resolution 不自动优化（社区好坏无客观裁判 → 留人，原则二）
3. Leiden 社区必须人工/LLM 命名主题，不留数字 id（Graphify 踩过的坑）
4. ★Query-first：B/C 仓有就必须先查，通用知识只做【显式标注】的兜底
5. 三个改进都【只读】B/C 仓，不改数据
6. 每批 commit 必 push（VHDX 教训）
```

---

> **一句话:** 三个来自 Graphify 的可落地改进——**① God node 检测**：把可视化从"审查工具"升级为"本性路径B候选自动发现器"（跨学科高中心性概念 = 核心抽象概念 = 本性候选，但只提示不认定）；**② Leiden 社区**：替换谱社区 KC 算法（Louvain 的断裂社区=一种附会，Leiden 保证社区连通，合"宁碎片不错合"），resolution 留人调不自动优化；**③ Query-first 钩子**：学习助手/决策辅助运行时**强制先查 B/C 仓已编译知识**，通用知识只做显式标注的兜底——防"B 仓辛苦编译却在使用时被通用知识绕过=白建"，把 grade 铁律/可溯源从【构建】贯到【使用】。

---

*依据：AII-BREPO-VIZ-SPEC-001（可视化）+ AII-INVARIANT-LAYER-001（本性路径B）+ AII-REFINED-REPO-MASTER-001（谱社区KC）+ AII-LEARNING-COACH-SPEC-001 + AII-CONTEXT-REPO-SPEC-001（B/C仓被查询）+ AII-FIRST-PRINCIPLES-001（原则一二）+ AII-EVALSET-SPEC-001（社区划分回归检验）。外部印证：Graphify（God node/Leiden/EXTRACTED-INFERRED/query-first 四设计独立印证 AII）。*
