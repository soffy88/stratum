# B 仓知识库健康体系改进计划（v1.0）

> 依据：pi-llm-wiki 分析 + 用户四点要求。目标：B 仓（aii_refined, rf schema）成为
> 坚不可摧的知识库终点；A 仓保留全部源 KU；所有体检/修复 100% 确定性或闭环可控。
> 日期：2026-08-06
> 状态：P0-P3 ✅ | Graphify ✅ | KU QA 闭环 ✅ | book-to-skill ✅ | **opendataloader 全面接入+3O内化 ✅（2026-08-07）**

## 现状基线（已核实）

| 维度 | 现状 |
|---|---|
| A 仓 ku_onto | 31,214 KU（sources/grounded_by 100% 空；grade 98.9% unverified） |
| B 仓 refined_ku | 29,291 KU（contributions 100% 有；孤儿 KU 19,284；重复 3,698；空壳 3,831） |
| 体检 | ku_lint.py 13 项纯 SQL（每日 05:00 timer）——**只报告不落库，healer 不消费** |
| 入库 | chapter_ingest 直落库，无 schema 强校验；onto_persist 注释"二期 enrichment" |
| 轨迹 | 失败散落日志（504/502/空壳），无结构化捕获 |
| 检索 | retrieval_engine 有 scope_uri，无 personal/global 双层 |

---

## ① 确定性体检飞轮（闭环：打标 → healer 消费 → 修复 → 清除）

**现状**：ku_lint 报告即完，无状态、无消费方。
**动作**：

- P0.1 `rf.ku_health_issues` 待办表
  ```sql
  CREATE TABLE rf.ku_health_issues (
    issue_id      bigserial PRIMARY KEY,
    ku_id         text NOT NULL,            -- 目标实体(refined_ku / 概念)
    check_name    text NOT NULL,            -- orphan_ku | dup_hash | weak_point | ...
    severity      text NOT NULL,            -- crit | warn
    detail        jsonb NOT NULL,
    first_seen    timestamptz NOT NULL DEFAULT now(),
    last_seen     timestamptz NOT NULL DEFAULT now(),
    status        text NOT NULL DEFAULT 'open',   -- open | fixed | ignored
    fixed_by      text,                     -- healer | pipeline | manual
    fixed_at      timestamptz
  );
  CREATE INDEX idx_ku_health_status ON rf.ku_health_issues(status, severity);
  ```
- P0.2 ku_lint 升级为**幂等打标器**：open 项 upsert（更新 last_seen）；消失项自动置 fixed（fixed_by='lint_auto'）
- P0.3 **healer 消费闭环**（每 15min）：
  - 读 open+crit 项 → 可安全自动修的执行（见"修复白名单"）→ 置 fixed
  - 不可自动修的（孤儿 KU 补挂概念）→ 触发 `b_repo_sync --with-judge` 或留给每日管道 → 置 `status='ignored'+reason`
  - 新增 crit 时写 healer 告警日志（飞轮停工保障的姊妹件：知识库健康保障）
- P0.4 可选：`rf.v_ku_health` materialized view 缓存检查结果，lint 读视图
- **验收**：每天 05:00 体检自动打标；healer 15min 消费；问题数单调收敛

**修复白名单（确定性、零风险）**：
| 问题 | 自动修动作 |
|---|---|
| 断链（FK 残留） | DELETE 孤儿关联行 |
| 空壳 point | 标记 ignored + 建议（不删——宁冗余不误删） |
| 重复哈希 | 生成候选对清单 → ku_dedup 管道消费（不自动并） |

---

## ② 入库管道海关检查（LLM → Schema 强校验 → 确定性后处理 → DB）

**现状**：LLM 输出直落库；grounded_by 是占位 `{"method":"default"}`。
**动作**：

- P1.1 **Source Packet Schema 实体化**（A 仓 grounded_by 标准，B 仓 contributions 对齐）：
  ```json
  {
    "substrate_id": "mankiw_principles_econ_10e",
    "chapter_anchor": "ch1",
    "text_window": [1024, 2048],
    "parser_version": "markitdown-v0.5",
    "extraction_method": "llm_summary"
  }
  ```
  B 仓 contributions 已有 `raw_ku_id/source_book_id/fragment_text` → 补 `chapter_anchor/text_window/parser_version`
- P1.2 **强校验层**（`scripts/ku_schema.py`，Pydantic）：
  - KUPoint: point(≥5字符), ku_type(枚举), natural_text, grounded_by(必填引用链)
  - chapter_synthesize 输出先过校验 → 缺引用链 → Retry(1) → 仍缺 → 丢弃并记 trajectory
  - 落库走统一 `commit_ku()`（校验+指纹+去重+INSERT），替代散落的 INSERT
- P1.3 **A 仓 sources/grounded_by 存量补填**：ku_enrich 已填 sources → 升级为完整 packet（含 chapter_anchor 从 ku_id 解析 `::chN::`）
- **验收**：新入库 KU 100% 带引用链；A 仓 grounded_by 空率 100% → 0（存量补填后）

---

## ③ 运行轨迹 → 故障签名 → skill 规则（反哺 oskill._meta_strategy）

**现状**：失败散落日志；_meta_strategy 的 strategy_pool 无数据源。
**动作**：

- P2.1 `aii.trajectory_logs` 表
  ```sql
  CREATE TABLE aii.trajectory_logs (
    event_id     bigserial PRIMARY KEY,
    ts           timestamptz NOT NULL DEFAULT now(),
    flywheel     text NOT NULL,          -- misc | advmath | econ-zh | ...
    phase        text NOT NULL,          -- plan | synth | embed | persist | quality_gate
    failure_mode text NOT NULL,          -- llm_timeout | llm_504 | embed_502 | empty_ku | scanned_pdf | ...
    error_sig    text,                   -- 签名: 短摘要(type+阶段+关键参数)
    context      jsonb,                  -- 文件名/章节/耗时/重试次数
    outcome      text NOT NULL           -- failed | degraded | recovered
  );
  ```
- P2.2 **埋点**（轻量钩子）：
  - `_provider.py` 的 retry 耗尽处（llm_timeout/llm_504）
  - `aii_remote.embed` fallback 触发处（embed_502→recovered）
  - 各飞轮 FAILED 处（chapter FAILED / 质量门拦截 empty_ku / scanned_pdf）
- P2.3 **静态规则（立即见效，零 LLM）**：z-lib.sk 扫描版预判
  `文件名含 z-lib.sk + 无文字层(pdf 转文本 <1KB) + 大文件` → 直接进 OCR 队列，不浪费 NIM —— 落 `aii.skill_rules` 表
- P2.4 **每周离线蒸馏**（timer）：LLM 审视一周 trajectory_logs → 提炼 if-then 规则 → 合入 `aii.skill_rules` → `oskill._meta_strategy(strategy_pool=skill_rules)` 消费
- **验收**：任何飞轮失败 100% 有签名记录；静态规则命中率可统计；_meta_strategy 有真实数据源

---

## ④ 双层检索防污染（Global 权威 / Personal 草稿）

**现状**：retrieval_engine 单层；个人笔记无入口。
**动作**：

- P3.1 **命名空间**：`namespace ∈ {global, personal}`（retrieval_engine 查询参数）
  - global = B 仓 refined_ku + 项目 KU（权威，高门槛）
  - personal = `~/.stratum/notes/*.md` 低门槛草稿区（轻量向量化）
- P3.2 **联邦检索**：查询按 namespace 合并召回（权重 global > personal），响应标注来源命名空间
- P3.3 **防污染硬约束**：概念图谱构建 / 规范页更新 / ku_lint 体检 **严格排除 personal 层**（代码层强制 namespace 过滤）
- P3.4 mcp_server 查询工具加 `namespace` 参数（默认 global）
- **验收**：个人笔记可被检索但永不进入 B 仓/图谱/体检范围

---

## 阶段与依赖

| 阶段 | 内容 | 依赖 |
|---|---|---|
| **P0（本周）** | ① 闭环：ku_health_issues + 打标 + healer 消费；③ 的静态规则（z-lib 预筛）+ trajectory_logs 建表埋点 | 无 |
| **P1（下周）** | ② 海关检查：ku_schema 校验层 + source packet 升级 + A 仓存量补填 | P0 的 trajectory 埋点 |
| **P2（两周）** | ② 全管道接入 + ③ 每周蒸馏 timer + _meta_strategy 消费 | P1 |
| **P3（三周）** | ④ 双层检索 + mcp namespace | 独立，可并行 |

**风险与原则**：
- B 仓「宁冗余不误删」：所有自动修仅限零风险项（断链删除、标记），合并/删除类动作只生成候选清单
- 体检/打标/修复三阶段全确定性，LLM 只出现在"蒸馏规则"（离线、可审、可回滚）


## 执行记录（P2+P3 2026-08-06）
- P2a: 四个飞轮重启加载海关检查新代码（synthesize_book/advmath/math_ingest 带 grounded_by+fingerprint 落库）
- P2b: trajectory_distill.py + 每周一 03:00 timer（失败模式 → LLM 蒸馏 → skill_rules, condition 白名单校验）
- P2c: 平台 oskill._meta_strategy 加 skill_rules_to_strategy_pool（纯函数, 已验证迁移命中）
- P2d: quark_drive_sync 下载后应用 skill_rules（z-lib 扫描版 → 待OCR + hits 统计）
- P3: 双层检索 — retrieve(namespace=global|personal|all) + ~/.stratum/notes 关键词联邦检索
  (pnote:// URI, 权重≤0.6, 图谱/规范构建天然隔离); mcp retrieve_context + REST /retrieve 带 namespace


## Graphify 启发① 执行记录（2026-08-06）
- 边置信度体系: refined_directed_edge 加 edge_source(readout|explicit), 对齐 EXTRACTED/INFERRED
- readout 全量回填: A 仓 concept_readout_edge(1,704) → B 仓 533 条边(名称匹配, 含 subsumes)
- explicit 补抽: A 仓 provenance.explains(概念名) → 295 条 explains 边(EXTRACTED) + 967 条超边(0→967)
- 约束扩展: relation_type CHECK 加 explains/contrasts/example_of
- ku_lint 新增: edge_trust(INFERRED 占比 64%) + isolated_concept(9,034 孤立) 指标打标
- B 仓图: 395 → 828 条边 + 967 超边
- 遗留: 90% 概念仍孤立(9,034/10,008) —— 边抽取继续(②图遍历检索 前置条件)


## Graphify 启发② 执行记录（2026-08-06）
- 边映射增强: embedding 语义匹配(hnsw) 再补 365 条 readout 边 → B 仓图 1,193 边(295 explicit + 898 readout)
- 孤立概念: 9,034 → 8,860(仍 88%, 名称漂移主因, 已尽力——readout 源用尽)
- 图遍历引擎: src/stratum/services/graph_query.py(BGraph: 邻接表内存图 + BFS)
  - explain(concept, max_hops): seed BFS 扩散, 邻居按 KU 挂载数排序
  - path(src, dst, max_hops): 双向 BFS 最短路径, hop-by-hop
  - 纯确定性零 LLM 零向量; 实测 explain("income elasticity of demand") 扩散 14 概念(经济学概念簇语义合理)
- REST 端点: GET /graph/explain + GET /graph/path(挂 main.py)


## Graphify ③④ 执行记录（2026-08-06）
- ③ 社区检测: community_detect.py(louvain 确定性零 LLM) → 50 个新主题
  (hub 概念命名: Marginal cost/Opportunity cost 125概念880KU 等, 经济学簇语义合理)
  theme_kc 29→79 | kc_member 1,157→3,864 | graph.html 力导向社区着色可视化(自包含无CDN)
- ④ reflect: trajectory_reflect.py(确定性聚合) — 失败≥5次且0恢复 → dead_end 规则写 skill_rules
  每周一 02:30 timer(先 reflect 打标 → 03:00 distill 提炼, 同链)
- 图现状: 1,193 边(295 explicit + 898 readout) | 967 超边 | 社区主题 50 | 可视化 graph.html


## KU 质检沙箱 + Reliability Loop 执行记录（CC 规格落地 2026-08-06）
- A1-A3 Grounded 协议: ku_schema 加 extract_evidence_quotes(确定性证据抽取, 零 LLM)
  + validate_quotes(quote⊆原文子串) + check_number_alignment(数字反幻觉)
  _synth 三模块返回 evidence_quotes; 无合法 span = NO_SPAN 协议失败(签名+轨迹)
- B1-B2 解析层: block_quality.py(编码/替换字符/控制字符/正文比/重复样板) + 章节质量闸
  (低质章不进抽取, 省 NIM)
- C1/D2: 数字对齐 HALLUCINATION 检测; 8 条签名→动作映射规则入库(signature_map)
- C2 NLI: nli_app.py(DeBERTa-v3-MNLI, GPU 8103, 批推理 fp16, id2label 读 config,
  OOM 自动降 CPU) — 打标不拒模式(NOT_ENTAILED 记轨迹, 观察分布后定阈值)
- D1 软分: evaluate_ku.py(密度0.35/原子性0.25/可检索0.20/对齐0.20, 无知识信号词封顶)
- D3/E2 预算: KU_REPAIR_SOURCE_BUDGET=5 每源失败预算(跨章累计, 超限终止该书)
- F1 指标: ku_lint 加 no_span_rate / not_entailed_rate(7 天 trajectory 聚合)
- NLI 部署修正: 用户拍板笔记本 GPU → 本机 3080 被 ollama/embed 占用, OOM fallback CPU
  实测恢复 cuda; 笔记本无部署通道(SSH 无凭据) — 记录为迁移偏好


## book-to-skill 吸收执行记录（2026-08-06）
- P0: skill_export.py — B 仓 70 主题 → ~/.agents/skills/<slug>/ 标准技能包
  (SKILL.md 心智模型+核心概念+关键关系 / glossary / patterns / cheatsheet / ku_index)
  确定性零 LLM, 每日 05:10 timer(同步 04:30 → lint 05:00 → export 05:10)
- P1: 检索 token 预算 — retrieve(budget_tokens) 按 score 累计截断低分项
  (Discovery Loop Tax 吸收: 查询成本与答案成正比); mcp/REST 三层暴露
- P2: Docling 对照实验(格罗滕迪克代数几何) — 结论: 不接入
  markitdown: 104万字符/9.9s/cid污染58676处/表格0
  docling:   33万字符/169s(慢17x)/表格14/无cid但数学符号仍乱码
  → 两者对公式书都不达; docling 慢 17x + 重依赖, 性价比低;
    表格/公式需求走既有待OCR队列(n-vllm), cid 由 _clean+block_quality 治理


## opendataloader 吸收执行记录（2026-08-07）
- 对照实验: 数学书(哈工大泛函分析) — opendataloader 表格213/cid0 vs markitdown 表格0/cid58676
  vs docling 表格14/慢17x → 方案 A 接入
- 实施: math_convert.convert() PDF 优先 opendataloader(本地模式, benchmark#1 表格提取)
  失败回退 markitdown; chapters() 扩展数字编号章节识别(1.2 完备性 格式)
- 依赖: ~/jdk(Temurin 17, 用户目录免 root) + opendataloader-pdf pip; PATH 注入 sys.executable
- 验证: odl 输出 cid 0 / 表格保留 / 判定 True(dens8.7 定理233 章4) / 幂等重复跳过 ✓
- 暂缓: hybrid 公式 LaTeX(需 AI 后端), bbox 锚点(依赖接入后)


## opendataloader 全面接入 + 3O 内化执行记录（2026-08-07）
- 全面接入: math/econ/misc/advmath_convert 的 convert() PDF 优先 opendataloader(平台层), 失败回退 markitdown
- 3O 内化: oprim/parser/parse_pdf.py 加 opendataloader provider(lazy import 健壮化)
  parse_pdf(path, provider="opendataloader", hint={"hybrid": bool}) → ParsedContent(表格计数/cid 统计)
- hybrid 模式: aii-odl-hybrid service(5002, --enrich-formula); 实测 462s+/172页 极慢(3批docling)
  → 默认关(ODL_HYBRID=1 按需开, 数学书深加工)
- NIM key 接入 VLM(picture description): docling 无标准 env 注入点(需定制 stage spec) → 暂缓, 如实记录
- 验证: 平台层 odl 213表格/cid0; math_convert 195KB/cid0/判定True


## Obsidian 学习笔记 Vault（2026-08-07）
- obsidian_vault.py: B 仓 → ~/.stratum/vault(Obsidian 直接打开)
  主题79/概念325/KU711/康奈尔45 + 双链图谱(Graph View) + 05-个人笔记软链=检索personal层
- 每日 05:20 aii-vault-sync.timer 自动刷新
- 康奈尔并入: 06-康奈尔/ 概念学习卡(线索/笔记/总结/练习) + 概念页反链 + 索引区


## mneme 交互式康奈尔整合（2026-08-07）
- 发现: mneme(cornell_topics) 与 stratum(cornell_generator) 同源设计(字段契约一致)
- stratum 生成端契约适配: cues 8-12 / modules 4-8(mneme 测试要求), max_kus=12
- cornell_to_mneme.py: stratum.cornell_notes → mneme/data/cornell_topics/{topicId}/content.json
  (45 张, topicId 目录名一致性); 每日 05:25 timer
- mneme pytest test_cornell_content: 0 → 50 passed
- 学习闭环: stratum 生成(概念卡) → mneme 交互回忆(线索→闭卷→自报进度) + Obsidian Vault 浏览


## pdf-inspector 替换 opendataloader 为默认引擎（2026-08-07）
- benchmark(firecrawl/opendataloader-bench): pdf-inspector 0.875 > liteparse 0.873 > opendataloader 0.831
  > pymupdf4llm 0.735 > markitdown 0.589; 表格 TEDS 0.814 vs 0.489; 速度 0.47s vs 2.57s vs 16s
- 实测(数学书): pdf-inspector 0.76s/表格1237/cid0 vs opendataloader ~60s/213/0 vs markitdown 10s/0/58676
- 原生 CID(ToUnicode CMap) 解码 + 坏编码检测(→OCR 路由) + 多栏阅读顺序
- 3O 内化: oprim parse_pdf provider="pdf_inspector"(Rust Python API, 无 subprocess)
- convert 四脚本默认切 pdf_inspector; opendataloader 保留于 ODL_HYBRID=1(公式 LaTeX 深加工)


## 本地学习播客生成器 (qiaomu/NotebookLM 价值本地化, 2026-08-07)
- 方案: B仓主题 → LLM双人对话脚本(NIM) → edge-tts双音色 → ffmpeg合并 → vault/07-播客/
- 角色: A=讲解者(Xiaoxiao女声) / B=提问者(Yunxi男声), 一问一答推进(3-5分钟/主题)
- 技术细节:
  - NIM脚本生成(3200 max_tokens, JSON容错, 20行上限)
  - edge-tts容错: _clean_tts(emoji/控制符清理, 跳过无效行)
  - 双音色并发合成 → ffmpeg concat
- 验证: 5个主题批量生成通过 (147-201s/864K-1.2M, 有效MP3)
- 与qiaomu对比: 零外部闭源依赖, 全链路本地; NotebookLM的"音频概览"差异化价值已实现
- 用法: .venv/bin/python scripts/podcast_generator.py --theme <id> | --limit N


## 多源内容抓取集成 (qiaomu 价值本地化, 2026-08-07)
- 集成内容: oprim._content_fetcher (qiaomu/fetch_url.sh 策略 Python 化)
  + 付费墙绕过: r.jina.ai/defuddle.md → Bot UA (Googlebot/Bingbot) → Referer 伪装 → AMP → archive.today → Google Cache
  + 源适配: 微信 (jina.ai 代理), Twitter (jina.ai/agent-fetch 级联)
  + 策略层级: proxy_services → bot_ua → referer_spoof → amp → archive → google_cache → fallback_direct
- 3O 内化:
  + oprim.fetch_url_with_bypass(url, strategy="auto") — 核心引擎
  + stratum.services.web_fetch_enhanced — 增强抓取服务 (wechat/twitter/paywall 自动路由)
  + stratum.services.web_source_handlers — wechat/twitter 源抓取 (source_watcher 集成)
- Stratum 集成:
  + inbox_webclip: 增强抓取优先, SSRF-safe 直取回退
  + sources.py: 新增 wechat/twitter source_type (URL列表/用户名/关键词)
  + source_watcher_service: SCAN_INTERVALS 更新, wechat/twitter 搜索处理
  + fetch_url.py: CLI 测试工具
- ⚠ 付费墙绕过为知识管线灰色地带, 仅供个人学习研究, 不作商业分发


## Crawl4AI 集成: JS 渲染/SPA 支持 (2026-08-07)
- 新增: stratum.services.web_fetch_enhanced 支持 crawl4ai provider (Playwright 异步抓取)
- 触发条件: 自动检测 JS 重域名 (notion.so/airtable.com/medium.com/threads.net...) 或 --strategy=crawl4ai
- Crawl4AI 特性: 异步浏览器池/LLM-ready Markdown/反爬隐身(stealth)/代理轮换/深度抓取
- 依赖权衡: 轻量 (urllib/jina.ai) vs 重量 (Playwright+Chromium ~150MB)
- 集成策略: 轻量默认 + Crawl4AI 按需降级 (最佳性价比/性能平衡)
- 用法: fetch_url_enhanced(url, strategy="crawl4ai") 或 CLI: fetch_url.py --strategy=crawl4ai <url>


## Crawl4AI Stealth 模式集成 (2026-08-07 优化)
- 新增: oprim._content_fetcher._try_crawl4ai_stealth (Playwright + playwright-stealth)
- 策略: BrowserConfig(enable_stealth=True) + Crawl4AI 异步抓取
- 成功率: 80%+ (GitHub/Wired/New Yorker/Forbes/Notion 等)
- 失败站点: NYTimes/WSJ/FT/Economist (强反爬)
- 集成: web_fetch_enhanced.fetch_url_enhanced(strategy="stealth") 或 auto (自动路由)
- 性能: 2-5s/页 (相比轻量方案慢，但成功率高)
- 用法: fetch_url.py --strategy=stealth <url> 或 CLI: fetch_url.py --test


## 付费墙绕过现状评估 (2026-08-07)

### 成功站点 (Stealth 模式)
- ✅ Wired, New Yorker, Forbes, MIT Tech Review, New Scientist, GitHub, Notion, Medium
- 成功率: 80%+ (2-5s/页)

### 挑战站点 (需要更强策略)
- ❌ NYTimes, WSJ, FT, Economist (Cloudflare Turnstile + 强反爬)
- 原因: 这些站点使用:
  - Cloudflare Turnstile (高级 CAPTCHA)
  - JavaScript 动态付费墙
  - Cookie 会话管理
  - 行为分析反爬
  - IP 地理限制

### 可用策略 (已集成)
1. Jina.ai 代理 (快速但受限)
2. Bot UA 绕过 (Googlebot/Bingbot)
3. Referer 伪装
4. AMP 页面提取
5. Crawl4AI Stealth (Playwright + 隐身指纹)
6. Archive.today/Archive.is (Cloudflare 阻止)
7. Wayback Machine (返回存档页而非原文)
8. Google Cache (部分有效)

### 现实评估
- **轻量方案**: 适合 80%+ 静态内容
- **Stealth 模式**: 适合 JS 重站点，但 Cloudflare 站点仍难绕过
- **最终回退**: 订阅官方 API 或使用 RSS/Atom feeds

### 建议
- 对于研究目的: 使用 archive.today 偶尔能获取存档
- 对于批量处理: 订阅官方 API 或 RSS feeds
- 对于个人阅读: 使用浏览器扩展 (Bypass Paywalls Clean)

---

## ⑧ LightRAG 整合评估 (2026-08-08)

**触发**: 评估 [HKUDS/LightRAG](https://github.com/HKUDS/LightRAG) 是否替代或集成到 Stratum RAG 管线

**数据基线**: 31,214 KU (98.7% unverified, 0.4% moderate), 1,398 substrates (book: 217, paper: 1,176)

### 核心发现

| 维度 | Stratum | LightRAG | 结论 |
|---|---|---|---|
| 检索精度 (预估) | ~35-45% | ~70% (论文) | **LR 优** |
| 实体提取质量 | ⭐⭐⭐⭐ | ⭐⭐⭐ | **Stratum 优** (校验链) |
| 可追溯性 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | **Stratum 优** (grounded_by) |
| 成本 | ~$6/千条 | ~$12/千条 | **Stratum 优 (2x)** |
| 增量删除 | ❌ | ✅ | **LR 优** |
| 扩展性 | ~100K KU | ~1M+ Entity | **LR 优** |
| **加权总分** | **3.68** | **3.85** | **差距仅 0.17** |

### 推荐策略: 渐进式集成 (非整体替换)

1. **Phase 1** (1-2d): 部署 LightRAG Server (Docker, NIM 后端)
2. **Phase 2** (3-5d): A/B 测试 10 条查询 × 5 种模式
3. **Phase 3** (1w): 集成 LR 作为可选检索后端
4. **Phase 4** (长期): 评估用 LR 提取替换 LLM 提取

### Stratum 核心壁垒 (不可替换)
- 7 步确定性校验链 (MOJIBAKE→NLI, 零 LLM)
- Enrichment 系统 (intuition/insight/example)
- Source Packet 溯源 (grounded_by + evidence_quotes + fingerprint)
- L0/L1/L2 分层知识组织
- BM25 补充检索 (中文/术语场景)

### 详细评估文档
- 📄 [docs/research/LIGHTRAG_COMPARISON.md](../research/LIGHTRAG_COMPARISON.md) — 完整 458 行报告
- 🧪 `/tmp/lightrag_eval/` — 测试数据集 + 评估脚本
