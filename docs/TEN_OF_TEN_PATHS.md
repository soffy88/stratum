# TEN_OF_TEN_PATHS.md — 对照代码实际 + 学术前沿/行业标杆的 10 分路径

> 首个版本：2026-08-24。本文件是《10/10 Blueprint》(`Stratum_10_of_10_Personal_
> Knowledge_Foundation_Blueprint_CN (1).docx`) 第 1 节评分表的展开版：蓝图给出的
> 是目标定义和抽象路线，本文件把每一维度钉在三件具体事情上——（1）**代码实际**
> （引用 `KNOWLEDGE_MODEL.md`/`ARCHITECTURE.md`/`TECHNICAL_DEBT.md` 已核实的
> 现状，不重复蓝图的泛泛评分）；（2）**学术前沿/行业标杆**（2026-08 检索到的
> 具体论文/基准/产品，不是"应该做类似 XX"的空泛类比）；（3）**到 10 分的路径**
> （能直接排进 `ROADMAP.md` 的动作，标注是否已有实现可复用、要不要重新发明轮子）。
>
> 判断原则：**能复用已验证的公开方法/协议/基准，就不要自己发明一套**——这是
> 贯穿全篇的一条隐藏红线，很多"10 分路径"本质是"别重造轮子，接现成标准"。

---

## 1. 产品定位与边界（8.6 → 10）

**代码实际**：`README.md` 与 `PRODUCT.md` 已统一到 Personal Knowledge Foundation
定位；WUKR 已有 telemetry/Prometheus 计算入口，并已接入管理员看板展示分子、分母和比例，
但真实用户数据与面向普通用户的产品仪表盘仍未完成验收。

**行业标杆**：NotebookLM 的公开评价是"丢进资料能聊天/总结这件事做得很好，但
一旦你想把它当成真正的知识库——裂缝就出现了"；反面对照是 Recall（明确定位
"lifelong learning 复利"）和 Readwise（明确定位"资料消化 + 间隔复习"）——
2026 年这个赛道里活得好的产品都是**窄心智、深复利**，不是大而全导航。

**到 10 分路径**：
1. README 改写，与 `PRODUCT.md` 对齐（已完成）。
2. WUKR 已从 `user_content_interaction` 计算、暴露为 telemetry 指标并接入管理员看板；
   仍需真实用户数据和普通用户产品仪表盘完成闭环。

---

## 2. 知识对象模型（8.8 → 10）

**代码实际**：`KNOWLEDGE_MODEL.md` 已核实——5 个互不相通的 Postgres 命名空间，
Concept 四表/Relation 三表仍是遗留现实；本轮新增 `stratum.concept_relations`、
`knowledge_claims`、`evidence` 作为 canonical 写入和引用面，并新增
`personal_states`/`beliefs`/`context_links` 的多用户最小写入面，旧表尚未全量合并。

**学术前沿**：HippoRAG2 用知识图谱 + Personalized PageRank（个性化网页排序算法）
模拟人类海马体记忆索引，实现单步多跳推理；GraphRAG（Microsoft）用社区级摘要做
跨文档聚合。两者代表的共同范式是：**概念合并/关系发现不该靠字符串相似度手工
规则，而应该是图算法驱动的、可解释的传播过程**。

**到 10 分路径**：
1. 已将 Concept/Relation merge 策略的 canonical 写入面固定，并实现
   Personalized PageRank（PPR）查询；`plan_legacy_knowledge_merge.py` 已提供保守候选
   和 027 ledger，但跨遗留仓的 merge 仍需人工复核后再执行。
2. `KNOWLEDGE_MODEL.md` §4 的 Concept/Relation merge 策略设计阶段，直接把
   Personalized PageRank（PPR）列为候选算法，而不是自造相似度阈值规则——PPR
   的优势正好是"可解释、可回答为什么合并"，对应蓝图第 14 节"所有图边必须能
   回答'为什么有这条边'"的要求。
3. 优先接 HippoRAG2/LightRAG 这类开源实现做技术选型评估，而不是从零训练图谱
   抽取模型——LightRAG 号称同质量下比 GraphRAG 便宜 10-30 倍、快 6-13 倍，这
   是当前监督反馈：图谱增强检索的成本已经被行业压下来了，没必要自建重方案。

---

## 3. 采集与解析（9.0 → 10）

**代码实际**：PDF 走 Docling（已入 `stratum-sl` 镜像，2026-08-01 验收 PASS）；本轮
新增 OmniDocBench 维度兼容的 parser gold-set runner，但尚未拿真实公开数据集跑分。

**行业标杆**：OmniDocBench（CVPR 2025，1651 页、10 种文档类型、5 种版式、5 种
语言，2026-04 更新到 v1.7）和 olmOCR-Bench（1400 页、7000+ 二元判定用例）是当前
文档解析质量的事实标准测试集；Docling 已被两个基准收录评测。当前 SOTA 在
olmOCR-Bench 上跑到 83.9 分，逼近 Gemini 3 Pro。

**到 10 分路径**：
1. 蓝图第 7.2 节的"解析质量 benchmark"已建立 runner，**不要自定义指标体系**，直接复用
   OmniDocBench 的分类维度（版式类型 × 语言 × 结构元素）做 gold set 设计，
   这样未来能直接对比自己的解析质量和公开榜单，而不是活在自造分数里。
2. 定期（例如每季度）用 olmOCR-Bench 跑一次新出的 SOTA 模型做 shadow 评测，
   决定 Docling 是否需要在特定文档类型上做 fallback（例如扫描件/公式密集型）。

---

## 4. PDF 阅读与笔记（8.2 → 10）

**代码实际**：高亮已同步为 `stratum.evidence` 独立 owner，带 confidence、quote_hash
和 W3C-style locator，并可由 Claim/Relation 引用；PDF/EPUB 选区弹层现在可记录
`important`、`question`、`contradict` 语义动作。动作会写入 interaction/LearningEvent，
但 Claim/Belief 自动生成与真实用户反馈仍未完成。

**行业标杆**：Readwise Reader 的核心差异化正是"高亮 → Ghostreader 问答 + 间隔
复习"闭环——这与蓝图第 8 节"用户一次高亮，后台形成 Evidence/Note/Concept/
PersonalState"是**同一个产品假设，且已被市场验证**。锚点标准方面，W3C Web
Annotation Data Model 是网页/文档批注互操作的开放标准（Hypothesis.is 等工具的
底层协议）。

**到 10 分路径**：
1. Evidence 的 `locator` 字段设计对齐 W3C Web Annotation（Selector/Target 概念），
   不要自造一套 anchor JSON 格式——对齐开放标准的直接好处是未来 Import/Export
   （见第 13 项）能直接兼容其他支持该标准的工具。
2. "高亮 → 复习"闭环不要自己发明间隔重复算法，直接用第 7 项的 FSRS。

---

## 5. 检索/RAG（9.1 → 10）

**代码实际**：BM25(tantivy) + pgvector 语义检索，RRF 融合，用户范围隔离；本轮新增
Query Intent Planner，按 A-RAG 三工具契约选择检索深度和 rerank。

**学术前沿**：
- **Agentic RAG**（A-RAG，2026-02）：agent 拿三个检索工具
  （`keyword_search`/`semantic_search`/`chunk_read`）自适应选择粒度，多跳问答
  上持续优于静态 pipeline，且检索 token 更少。
- **HippoRAG2 / LightRAG**：图谱增强检索，10-30× 更便宜、6-13× 更快，用 PPR
  代替全 LLM 图构建。
- 主流评测已经收敛到三层框架：检索层（precision/recall/MRR/hit-rate@k）、
  生成层（groundedness/faithfulness）、端到端层（correctness/helpfulness）——
  见第 12 项。

**到 10 分路径**：
1. 蓝图第 10 节的"Query Intent Planner"已按 A-RAG 的三工具模式实现（而不是
   设计一套新的检索路由协议）：intent classifier 决定用哪几个工具、按什么顺序
   调用，Reranker 在工具输出之上做统一排序。
2. 第 2 项 Concept/Relation 统一之后，"Explain 模式：mastered concepts 作为桥梁"
   可以直接用 HippoRAG2 式 PPR 在知识图上做激活扩散，而不是关键词匹配"用户已
   掌握的概念"。
3. Recall@20/citation precision 目标值的验收方法论用 RAGAS（见第 12 项），
   不要发明新指标名词。

---

## 6. Agent/Cognition（8.4 → 10）

**代码实际**：已新增共享 AgentContract，明确 working context、Recall 只读事件日志、
Archival Knowledge Foundation 和 Knowledge API 写入边界，并通过 API/MCP 暴露。

**学术前沿**：Letta（原 MemGPT）的三层记忆模型——**Core memory**（始终在
context，像 RAM）/**Recall memory**（可搜索历史，像磁盘缓存）/**Archival
memory**（长期存储，像冷存储）——与蓝图 AgentContract 的
`memory_policy = "working_only"` + `persistence_policy = "write_via_knowledge_api"`
几乎是同一个设计的两种表述。评测标准已有 LoCoMo/LongMemEval/BEAM 三个公开
benchmark 专门测长期记忆效果。MCP（Anthropic 开放标准）已是 agent-tool 接口
的行业共识。

**到 10 分路径**：
1. AgentContract 已明确映射：Core memory = 本次 working context（Agent 允许持有）；
   Recall memory = `LearningEvent`/`agent_runs_sl` 这类事件日志（只读，Agent 可查
   但不可绕过写）；Archival memory = Knowledge Foundation 本体（Source/Evidence/
   KU/Concept），只能通过 Knowledge API 写入——这条本来就是蓝图第 11 节的红线，
   现在有了对应的、已被验证的架构名词，方便团队内部对齐。
2. Knowledge API 已通过现有 **MCP server** 暴露 contract 和检索计划（蓝图第 22 节
   已提到 MCP）；具体 Claim/Relation 写入端点也已纳入 Knowledge API。
3. Knowledge API 同时实现为一个 **MCP server**（蓝图第 22 节已提到 MCP，建议
   提升为 P0 而非"生态"里的可选项）——好处是复用 Claude/其他模型生态现成的
   工具协议，而不是自造一套 Agent Contract RPC。
3. Agent 长期记忆效果的验收直接借用 LongMemEval 之类公开题库做基线测试，而不是
   纯靠人工体感判断"Agent 好像记性不错"。

---

## 7. 学习与记忆（8.8 → 10）

**代码实际**：FSRS 与 Desired Retention 已接入；复习列表现在暴露基于
`1-retrievability × personal_relevance × prerequisite_importance` 的 review priority。
Stratum 已有 JWT 隔离的 PersonalState 最小 API，且高亮会写入显式 relevance；
`stratum.learning_events` 已记录高亮、内容进度、复习、检索和 Personal Model 显式变更，
Evidence 状态会投影到所属 substrate 并提供有界个性化排序 boost；旧
`cx.learning_profile`/`learning_progress` 的跨库多用户迁移仍未完成。当前已提供
`aii/migrations/context/0006_learning_multitenancy.sql` 的可空归属列、人工映射账本、
子表 owner 保护和 `scripts/audit_cx_learning_migration.py` 的只读盘点/显式回滚入口；
真实身份映射、API JWT 隔离和旧 attempts 事件回填仍需部署验收。当前新增
`scripts/plan_personal_model_migration.py`，只能根据人工 manifest 生成
PersonalState/Belief/ContextLink/LearningEvent 候选与参数化 SQL；不自动写入。
部署侧的 `scripts/apply_personal_model_migration.py` 还会校验目标对象归属，并要求
显式确认才执行事务；LearningEvent 回滚只改导入账本状态，不删除事件。

**学术前沿**：FSRS（Free Spaced Repetition Scheduler）已经取代 SM-2 成为间隔
重复的事实标准算法；FSRS-6（2025 年底发布，基于 ~7 亿条真实复习记录训练）对
每张"知识卡片"建模三个变量——**stability（稳定性）/difficulty（难度）/
retrievability（可提取度）**——用 17 个可训练权重按个人历史优化，同等记忆效果
下比 SM-2 减少 20-30% 复习次数；"Desired Retention"（期望记忆保持率，黄金标准
90%）是用户可调参数。

**到 10 分路径**：
1. 蓝图第 12 节的 `review_priority = forgetting_risk × personal_relevance ×
   prerequisite_importance` 公式里的 `forgetting_risk` **直接换成 FSRS 的
   stability/retrievability 模型**，而不是自造遗忘曲线——FSRS 已经是被 2600 万+
   Anki 用户验证过的公开算法，重新发明只会更差。
2. 暴露 `Desired Retention` 为用户可调参数（对应蓝图"我已经会了"必须允许用户
   覆盖模型推断的原则），这正好是 FSRS 现成支持的旋钮。
3. `mastery_next` 若要进一步做认知诊断（而不只是复习调度），可以关注知识追踪
   （Knowledge Tracing，如 DKT）方向作为二期，本期不必上——FSRS 已经能覆盖
   蓝图当前的 mastery/forgetting 需求。

---

## 8. 安全与数据所有权（8.3 → 10）

**代码实际**：导出走结构化 Vault + manifest，真删已实现；legacy `:9302` CORS 已改为
显式 allowlist，支持环境变量配置并拒绝 wildcard credentials 组合；真实浏览器 preflight
仍待部署验收。

**行业标杆**：GDPR Article 20 明确要求导出必须是"**结构化、常用、机器可读**"
格式——这是一条可验收的硬指标，不是"能导出就行"。EU 数字市场法案（DMA）对
"看门人"平台的要求更严格：**实时、持续**的可迁移性，而不是"按需导出一次"。
Solid Protocol（Tim Berners-Lee 提出的个人数据自持架构，用户拥有 pod、应用只是
访问者）是"数据主权"的学术/工程标杆方向，但目前研究结论是"其规范现状尚无法
满足具体法规合规"——即：方向对，但不是能落地拿来即用的成熟方案。

**到 10 分路径**：
1. 现有导出格式对照 GDPR Art.20 的"结构化机器可读"标准逐项验收（YAML+Markdown
   基本满足，需要确认 graph/学习状态导出是否同样结构化，而不是塞进不透明
   blob）。
2. 不建议现在就上 Solid pod 架构（成熟度不够、投入产出比低于当前阶段其他 P0/
   P1 项），但可以把它记入 `ROADMAP.md` Phase 5/6 作为"数据可携带"的长期参考
   方向，而不是重新发明一套自定义的"用户自持存储"协议。
3. Legacy `:9302` 的 CORS 已完成代码收口，部署时补真实 Origin/preflight smoke test。

---

## 9. 可靠性/性能（8.5 → 10）

**代码实际**：`docs_service` 已用信号量限流 CPU 密集转换避免 `/health` 超时；本轮新增
28 天窗口 SLO targets、error budget evaluator 和 CI release gate。

**行业标杆**：Google SRE 手册的 error budget 定义（= 1 − SLO）是行业公认基线；
2026 年最新实践建议**每个关键用户旅程最多设一个"会触发寻呼"的 SLO，且该指标
必须驱动具体操作**——反对"给每个技术指标都设 SLO"的做法，因为大部分指标
（比如队列深度）只有在真正影响用户体验时才重要。

**到 10 分路径**：
1. 已定义两条关键用户旅程 SLO，不照抄蓝图第 19 节整张表；
   "关键用户旅程"（例如"上传到能问答"、"检索请求"），只为它们设会触发行动的
   SLO，其余指标做观测但不作为发布门禁。
2. error budget 耗尽 → 自动冻结非紧急发布，已写成 `check_slo_gate.py` 的机械规则
   （蓝图第 32 节 Release Gate 12 问之一），不要靠人工判断"是不是该修复优先"。

---

## 10. 可维护性/架构治理（7.6 → 10）

**代码实际**：`ARCHITECTURE.md` 记录的现状是 3 个独立 FastAPI 服务
（`:9302`/`:9304`/`docs_service`）+ 5 个 DB 命名空间，物理上已经是碎片化的。

**行业标杆**：Hexagonal（Ports & Adapters）+ DDD Bounded Context 是当前公认的
monorepo 治理标准做法；2026 年的实践共识是"**modular monolith 先行，按负载
特征逐步拆服务**"，而不是一开始就微服务化；"module 通过 Module Startup API
作为 port 初始化，只依赖必要配置参数"是具体的边界实施手法。

**到 10 分路径**：
1. 重新定性现状：3 个 FastAPI 服务 + 5 个 DB 命名空间**不是需要立刻推平重来的
   架构失误**，而是"用物理服务边界实现了逻辑 bounded context"的现实——这符合
   "modular monolith 先行"的行业建议，`KNOWLEDGE_MODEL.md` §3 已经决定"不做
   大爆炸重构"，方向是对的。
2. 真正该补的是**边界检查的自动化**：蓝图第 16 节"Domain 层不得 import
   FastAPI/psycopg2/provider SDK"这条规则目前无 CI 强制。建议引入
   import-linter 类工具（Python 生态标准做法：用声明式契约文件限制模块间
   import 关系）作为 CI 门禁——这是低成本、可以立刻做的动作，比物理重构 ROI
   高得多。

---

## 11. UX/信息架构（7.9 → 10）

**代码实际**：Web 端已把现有路由收敛到蓝图第 15 节的五个入口
（Today/Library/Ask/Learn/Map），并有导航契约测试；真实入口文案、首次使用路径和
用户测试仍未完成。

**行业标杆**：NotebookLM 的公开评价反复出现同一句话——"一旦你想把它当真正的
知识库，裂缝就出现"；反面是 Recall（"lifelong learning"）、MyMind（"creative
inspiration"）——2026 年这个赛道里，**心智收窄、单一叙事**的产品比"仪表盘
拼盘"式导航活得更好。

**到 10 分路径**：
1. 蓝图五入口收敛方向正确，关键验收标准不是"做出这五个页面"，而是每个入口
   能不能像 Recall/MyMind 一样一句话讲清楚"这里是干什么的"——如果某个入口
   需要两句话才能解释清楚定位，说明还在"功能拼盘"阶段，没到"心智收敛"。
2. 上线前找 3-5 个真实用户做"首次 onboarding 3 分钟"场景测试（蓝图第 15 节
   已定义该场景），不要只靠内部主观判断。

---

## 12. 评测与质量（9.0 → 10）

**代码实际**：已补 retrieval gold-set schema/指标 runner 和 parser gold-set runner；
真实 50-100 条 query、20-30 份文档和 baseline 数字仍待真实语料构造。

**行业标杆**：RAGAS 是当前 RAG 评测的事实标准框架——核心方法是**不需要人工
标注 ground truth**：把生成答案拆解成独立 claim，逐条对照检索到的上下文验证，
得到 faithfulness/context precision/answer relevancy 等分数。行业共识的评测
分层是：检索层（precision/recall/MRR/hit-rate@k）→ 生成层（groundedness/
faithfulness/context utilization）→ 端到端层（correctness/helpfulness/
refusal calibration）。TruLens 更适合有 Agent 编排、需要实时追踪的场景。

**到 10 分路径**：
1. `ROADMAP.md` Phase 0 遗留的 gold set 任务，当前先对齐 RAGAS/TruLens 的分层命名，
   后续接入真实 judge；直接**引入 RAGAS/TruLens 开源库**
   而不是纯手搓评测脚本——原因：RAGAS 的无需人工标注方法论可以大幅降低
   50-100 条 gold query 的标注成本（不需要每条都人工标"标准答案"，只需要
   验证 claim 是否被检索上下文支持）。
2. 蓝图第 21 节的"Citation precision""Evidence Coverage"等自定义术语，建议
   在实现时直接映射到 RAGAS 的 faithfulness/context precision 指标定义，
   保持术语和公开框架兼容，方便未来引入第三方工具校准。

---

## 13. 生态与可迁移性（7.5 → 10）

**代码实际**：`vault_sync_service` 支持 Markdown 导出/导入；本轮新增 Obsidian
双向 connector，使用 frontmatter stable ID 和最小 workspace 配置。

**行业标杆**：Readwise 的核心竞争力之一是"**双向同步** Notion/Obsidian/
Logseq/Heptabase"——不是单向导出，而是持续双向连接；协议层面，MCP（见第 6 项）
已是 agent-tool 互操作标准，GDPR/DMA（见第 8 项）定义了数据可携带的合规基线。

**到 10 分路径**：
1. Knowledge API 已实现为 MCP server（与第 6 项是同一个动作，一次交付满足
   两个维度的验收——不要分两次做）。
2. Import/Export connector 优先做 **Obsidian 双向同步**而非一次性导出：当前
   Markdown+wikilink 格式已经比较接近 Obsidian 生态，起步成本低，且 Obsidian
   用户群与 Stratum 目标用户（研究者/学习者）高度重合。

---

## 14. 商业化准备（7.4 → 10）

**代码实际**：平台内容 feed/detail/recommendation 已按 Free/Plus/Pro 累积层级过滤；
本轮已固定月度 credits 和高算力能力单位成本，并提供策略/估算 API。真实支付 provider、
订阅 webhook 和实际 tier 内容数据仍待部署验收。
（`TECHNICAL_DEBT.md` 历史记录）。

**行业标杆**：Notion 2026 年把 AI 从可选插件转为绑定 Business tier + 按用量
计费（$10/1000 credits，不结转）；Mem 走"低门槛免费额度（25 notes/月）+ Pro
$12/月"路线。两种打法分别代表"功能捆绑抬价"和"免费额度换转化"，蓝图第 23 节
"Free/Pro/高算力 credits 三层"的设计思路已经比较接近 Notion 的用量计费模型。

**到 10 分路径**：
1. 高算力能力（深度研究/图像/TTS/大规模重算）已参考 Notion 的 credit 计量模型
   设计具体计费单元，避免"无限 token"造成的成本不可控（蓝图第 23 节已提到
   这条红线，行业已有现成的计量单位设计可以参考，不需要自创计费模型）。
2. Free tier 的"有限资料量/计算量"已落成具体数字（参考 Mem 的做法：明确到
   "每月 N 篇/N MB"），而不是保持模糊表述——模糊的免费额度既不利于用户预期
   管理，也不利于内部成本测算。

---

## References（按维度分组，仅列核心来源）

**RAG / 检索**：
- [A-RAG: Scaling Agentic Retrieval-Augmented Generation via Hierarchical Retrieval Interfaces](https://arxiv.org/html/2602.03442v1)
- [RAG in 2025-2026 · State of the Art](https://techwithcolonel.com/artifact/rag-state-of-the-art-2026.html)
- HippoRAG2 / LightRAG 对比数据：综合自上述 State of the Art 汇总条目

**Agent 记忆**：
- [AI Agent Memory 2026: Progress Benchmark Report Evaluations](https://mem0.ai/blog/state-of-ai-agent-memory-2026)
- [Agent Memory: How to Build Agents That Learn and Remember | Letta](https://www.letta.com/blog/agent-memory/)
- [Best AI Agent Memory Systems in 2026: 8 Frameworks Compared](https://vectorize.io/articles/best-ai-agent-memory-systems)

**学习/间隔重复**：
- [Anki FSRS: The New Scheduling Algorithm Explained (2026)](https://studycardsai.com/blog/anki-fsrs-algorithm)
- [Best Spaced Repetition Apps 2026: FSRS vs SM-2 Ranked](https://studyglen.com/guides/best-spaced-repetition-apps)

**评测框架**：
- [RAGAS, TruLens, DeepEval: LLM Evaluation Frameworks (2026)](https://atlan.com/know/llm-evaluation-frameworks-compared/)
- [What is RAG Evaluation? Frameworks, Metrics, and Gates in 2026](https://futureagi.com/blog/what-is-rag-evaluation-2026/)

**文档解析**：
- [OmniDocBench (CVPR 2025)](https://github.com/opendatalab/OmniDocBench)
- [7 Best Open-Source PDF to JSON Extraction Models in 2026](https://www.huuphan.com/2026/07/blog-post_15.html)

**数据主权/合规**：
- [Right to Data Portability under GDPR Article 20](https://gdprlocal.com/right-to-data-portability/)
- [Assessing the Solid Protocol in Relation to Security and Privacy Obligations](https://www.mdpi.com/2078-2489/14/7/411)
- [1 THE PRESENT AND FUTURE OF DATA PORTABILITY](https://dtinit.org/assets/DTI-Data-Portability-Compendium.pdf)

**可靠性**：
- [Google SRE: Production Services Best Practices](https://sre.google/sre-book/service-best-practices/)
- [SLOs, SLIs & Error Budgets: 2026 Implementation Guide](https://performance.qa/blog/slo-sli-error-budgets-guide/)

**架构治理**：
- [4. Integrating Bounded Contexts - Learning Domain-Driven Design](https://www.oreilly.com/library/view/learning-domain-driven-design/9781098100124/ch04.html)
- [Modular Monolith: Domain-Centric Design — Kamil Grzybek](https://www.kamilgrzybek.com/blog/posts/modular-monolith-domain-centric-design)

**产品/UX 标杆**：
- [Best NotebookLM Alternatives in 2026 | Recall](https://www.recall.it/compare/best-notebooklm-alternatives)
- [7 Best NotebookLM Alternatives in 2026 (Tested) | Noverload](https://noverload.com/blog/best-notebooklm-alternatives-2026)
- [Readwise Review 2026: Pricing, Ghostreader AI & Notion Sync](https://www.linkstartai.com/en/agents/readwise)

**商业化**：
- [Notion pricing 2026: Which plan is actually worth it?](https://www.eesel.ai/blog/notion-pricing)
- [Mem AI Review 2026: Features, Pricing & Alternatives](https://workgpt.com/en/app-reviews/mem-ai)

## 参考（本仓库内）

- 各维度现状的详细依据：`PRODUCT.md` / `KNOWLEDGE_MODEL.md` / `ARCHITECTURE.md`
  / `TECHNICAL_DEBT.md`
- 具体排期：`ROADMAP.md`（本文件的路径应在下次修订 ROADMAP 时并入 Phase 1-3）
