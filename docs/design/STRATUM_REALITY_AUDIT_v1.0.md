# Stratum 真实状态 vs Wiki 产品愿景 — 完整差距审计

**版本**: v1.0
**日期**: 2026-06-04
**作者**: CC (advisor 视角, R-4 只读核查)
**来源**: SPEC v0.5 / v0.6 PATCH / ROADMAP v1.0 / Phase 14-17 实施代码
**性质**: 不评估"应该做不做", 只列真状态. advisor 看完后跟 Wiki 一次性对齐.

---

## §1 Wiki 真想做的 Stratum (产品愿景一段话)

Wiki 原始想法是一个**对中文用户的 AI 知识管家**: 用户把自己积累的英文书 / 论文 / 播客 / 网页放进去, Stratum 自动翻译、分类、朗读、建立概念图谱, 还能跟 hevi 出品的投资/量化专业内容融合检索 — 用户搜"凯利公式"就能同时看到自己读过的 Taleb 的书里的章节 + hevi 专栏对凯利公式的解读 + 自己写的笔记, 三层内容一次返回。同时 Stratum 不是知识孤岛: 用户文件存在自己的网盘 (Google Drive), 多设备同步; Stratum 按月收费 (¥29 Plus), 免费用工具基础, 付费看 hevi 专属内容。目标是让一个个人投资者/研究员不再"看了很多英文资料但消化不了", 而是通过 Stratum 真正把英文资料内化到自己的知识体系。

---

## §2 真完整功能清单 (按用户场景分)

> 图例: ✅ 已 ship 真可用 | 🟡 部分 (代码有但 UX 简陋/边缘 case 缺) | ❌ 完全没做 | ⚠️ 计划但 advisor 推后

### A. 用户输入资料

| 功能 | 状态 | 说明 |
|---|---|---|
| 上传文件 (PDF/markdown/epub) | 🟡 | 后端流水线通, 但 UI 只有 UploadButton, 无进度条, 无失败提示, substrate 入库有 Phase 14 DB merge bug (Phase 17 Task 1 刚修) |
| 输入 URL 服务端抓取 | 🟡 | Phase 17 刚实施 (commit 936c43b4), 未经 Wiki 真测试验证 |
| 浏览器扩展 (Chrome MV3) | 🟡 | 代码在 stratum-extension v0.3, 3 个 bug Phase 17-B 刚修, 未在真浏览器验证 |
| RSS/Atom feed 订阅跟踪 | ⚠️ | oprim.fetch_rss stub 存在但不可用; Phase 18 计划 |
| 邮件转发入库 | ❌ | 未规划实施 |
| 微信图文转发 | ❌ | 微信公众号消息处理未实施 |
| Podcast feed | ❌ | 未实施 |
| screenpipe 屏幕历史 | ⚠️ | Phase 12 计划, 未启动 |
| 录音 / 语音 | ❌ | whisper 外挂未部署 |

### B. Stratum 主动找资料

| 功能 | 状态 | 说明 |
|---|---|---|
| ResearcherAgent | ❌ | SPEC §14.2 无此 Agent, Wiki 提过概念但未入 SPEC |
| 领域跟踪 (关键词监控) | ❌ | 未规划 |
| Google Alerts 类 | ❌ | 未规划 |
| searxng 网络搜索增强 | ⚠️ | Phase 11 oprim.external.searxng_client 计划, 未部署 |
| hevi 新内容自动推送 | ❌ | hevi 平台内容流水线 Phase 3/6 未启动 |

### C. AI 加工

| 功能 | 状态 | 说明 |
|---|---|---|
| 翻译 (英文→中文 derivative) | ✅ | translation_worker Agent 可运行, omodul/oskill 链路通 |
| 每日摘要 (daily_digest) | ✅ | Agent 可运行, 返回 findings; UI 结果展示基础 |
| 周复盘 (weekly_review) | ✅ | Agent 可运行 |
| 知识整理 (knowledge_curator) | ✅ | Agent 可运行 |
| 音频朗读 (audio_generator) | 🟡 | Agent 代码存在, 但本地 TTS (F5-TTS/fish-speech) 未部署; 调用失败 |
| 插图生成 (illustration_agent) | 🟡 | Agent 代码存在, 但 SD-webui 未部署; 调用失败 |
| 阅读伙伴 (reading_companion) | ✅ | Agent 可运行 (调 hybrid_search + LLM) |
| 知识库 lint (lint_bot) | ✅ | Agent 可运行 |
| 概念自动抽取 | ❌ | knowledge_curator 仅处理 inbox, 不自动抽 concept |
| OCR (图片文字识别) | ❌ | 未实施 |
| 多模态 (图片问答) | ⚠️ | oprim.llm.vision Phase 11 计划, 未实施 |
| 高亮 (Highlight) | 🟡 | 后端 CRUD 通, 但文档阅读器 UI 无高亮交互功能 |
| 笔记 (Notes) | ✅ | CRUD 通, 阅读页可写, 笔记列表页存在 |

### D. 用户使用

| 功能 | 状态 | 说明 |
|---|---|---|
| 基础文字搜索 (hybrid search) | 🟡 | 后端路由通, 但 corpus 隔离 bug Phase 17 Task 1 刚修; 无向量索引真内容 |
| 跨层检索 (platform + user) | ❌ | hevi 平台内容未接入; search 只查用户 substrate |
| 推荐 | ❌ | recommendations 路由是空实现, 返回空列表 |
| 视图 (Views) | 🟡 | CRUD 通, 5 个预设, 但 search 接口 view_id 过滤未实现 |
| 引用 (Citations) | ⚠️ | SPEC §10.1 有 citation 字段规范; Agent 输出有 citations 字段但内容空 |
| 反向链接 (Backlinks) | 🟡 | note→note wikilink 后端有, 前端未展示 |
| 概念图谱 | 🟡 | GET /api/v1/concepts/graph/{id} 路由存在, 前端无图谱渲染组件 |
| 时间线视图 | ❌ | 未实施 |
| MCP 工具暴露 | 🟡 | omodul.start_mcp_server 可运行, 但生产容器未挂载 |
| 文档阅读 (ODocumentReader) | 🟡 | helios-blocks 组件, 支持 markdown; 但 PDF 渲染无法对比原文 |

### E. 用户协作

| 功能 | 状态 | 说明 |
|---|---|---|
| 分享 substrate (token) | 🟡 | POST /api/v1/share 通, /share/[token] 前端页面存在; 实际内容渲染 bug 未验证 |
| 公开 substrate | ❌ | 分享是 token 私享, 无真正公开发现 |
| 关注作者 | ❌ | 未实施 |
| 评论 | ❌ | 未实施 |
| 知识广场 / 发现 | 🟡 | /discover 页面存在但显示 hevi 平台内容; 平台内容未接入所以是空页面 |

### F. 同步

| 功能 | 状态 | 说明 |
|---|---|---|
| Google Drive 同步 | ❌ | Phase 2 从未启动 (GDrive OAuth 未申请) |
| OneDrive / 阿里云盘 | ❌ | 同上 |
| 多设备同步 | ❌ | 无; 数据存服务器端 DuckDB, 多设备登录同一账号可访问, 但非真正"用户网盘同步" |
| 离线模式 | ❌ | 未实施 |
| changefeed 客户端同步 | 🟡 | 服务端 changefeed 事件存在 (14 类), WS 广播通; 客户端 ws-client.ts 已接, 但无真正"离线→重连同步"逻辑 |
| 用户网盘 substrate 存储 | ❌ | **架构偏离**: SPEC §6.1 明确"服务器不持有用户 substrate 原始 bytes", 但当前 SaaS 把 substrate 存在服务器端 inbox/ 目录 |

### G. 商业

| 功能 | 状态 | 说明 |
|---|---|---|
| 付费订阅 (Free/Plus/Pro) | ❌ | billing 路由存在但 WeChat Pay / Stripe 均未配置 (`_HAS_WECHAT = False`, `_HAS_STRIPE = False`) |
| 微信支付 | ❌ | oprim.wechat 不存在 |
| Stripe (海外) | ❌ | oprim.stripe 不存在 |
| 订阅配额管理 | ❌ | 未实施 |
| access_tier 内容控制 | ❌ | platform_content 表存在但空; 付费 tier 无实际效果 |
| 微信生态 (小程序/公众号) | ❌ | 完全未实施 |
| 学生优惠 / 早鸟 / 推荐返佣 | ❌ | 未实施 |
| 买断 | ❌ | SPEC 无此选项, 用户可能期望 |

### H. 外挂集成

| 外挂 | 状态 | 说明 |
|---|---|---|
| hevi 平台内容 | ❌ | hevi-content-repo 协议未商定, 流水线未实施 |
| screenpipe | ❌ | Phase 12 计划, 未部署 |
| whisper.cpp (ASR) | ❌ | 未部署 |
| F5-TTS / fish-speech | ❌ | 未部署; audio_generator Agent 调用失败 |
| SD-webui (插图) | ❌ | 未部署; illustration_agent 调用失败 |
| searxng (网络搜索) | ❌ | 未部署 |
| Ollama (本地 LLM) | ❌ | 未配置 |

---

## §3 真完成度

功能总数: **66 项** (§2 A-H 所有行)

| 状态 | 数量 | % |
|---|---|---|
| ✅ 真可用 | 8 | 12% |
| 🟡 部分 | 20 | 30% |
| ❌ 完全没做 | 33 | 50% |
| ⚠️ 推后计划 | 5 | 8% |

**真 ✅ 完成度: 8/66 = 12%**
**含部分 (✅+🟡): 28/66 = 42%**

注: 这是按功能数计算, 非代码量。代码量完成度更高 (4O 库约 70%), 但用户可感知功能是 12-42%。

---

## §4 真用户进来 5 分钟能跑通什么

### 能跑通的路径

1. **注册 → 登录**: ✅ 可以 (邮箱+密码, argon2 hash)
2. **上传 PDF**: ✅ 后端路由通 → 但有 2 个卡点:
   - substrate 入库的 DB 链路 bug (Phase 17 Task 1 刚修, 未经 Wiki 真验证)
   - 上传后无进度反馈, 用户不知道是在处理还是失败
3. **运行 AI Agent (daily_digest/weekly_review)**: ✅ 可以 (8 个 Agent 有 HTTP 200)
4. **搜索**: 🟡 路由通但无向量内容 (substrate 刚修, 可能空结果)
5. **写笔记**: ✅ 可以 (POST /api/v1/notes + /notes/[id] 编辑页)

### 主要卡点

1. **上传后不知道发生了什么**: 没有"入库中..."状态, 成功/失败都不显示
2. **文档列表永远是空**: Phase 17 Task 1 之前 substrates 从不写入数据库 (phantom ID bug), 用户上传了但看不到文件
3. **AI 结果无法找到相关内容**: 因为 substrates 没入库, Agent 搜索结果为空
4. **搜索返回空**: 同上, 用户的文件没有向量化入索引

**结论**: 5 分钟内用户能完成注册+上传动作, 但看不到任何有意义的结果. 极大概率会认为"这东西没用"然后离开。

---

## §5 真用户进来 30 分钟想做什么但做不了

| 场景 | 状态 | 真实体验 |
|---|---|---|
| "我想抓 URL 入库" | 🟡 | Phase 17-A 刚实施, 功能存在但未经真浏览器验证; 之前完全没入口 |
| "我想 Stratum 帮我找资料" | ❌ | ResearcherAgent 不存在; searxng 未部署; 只有用户已有资料的 hybrid_search |
| "我想跟踪某领域更新" | ❌ | 无 RSS/feed/keyword monitor; 无调度触发领域扫描 |
| "我想分享笔记给朋友" | 🟡 | share token 功能有但用户不知道入口在哪; /share/[token] 页面存在 |
| "我想多设备看到一样" | ❌ | 服务器端 DuckDB 所以多账号登录能看到; 但如果用户期望"我的文件在网盘"则完全不是这回事 |
| "我想付费解锁高级功能" | ❌ | billing 路由有但点击"订阅"返回 501 (wechat pay 未配置) |
| "我想看 hevi 专业文章" | ❌ | discover 页面空; 平台内容从未接入 |
| "我想用中文搜英文资料" | 🟡 | 翻译 Agent 可以运行生成中文 derivative, 但中英双语检索 (Qwen3 embedding) 需要 substrate 已入库且已 embed |
| "我想听朗读" | ❌ | audio_generator Agent 运行报错 (TTS 未部署) |

---

## §6 跟 Obsidian 真对比

ROADMAP §1 说"vs obsidian/notion: 有 AI 增强 (翻译/TTS/Agent)"; Wiki 提过"obsidian 一半都比不上"的期望。

| 功能 | Obsidian 状态 | Stratum 当前 | 差距 |
|---|---|---|---|
| 本地文件存储, 隐私 | ✅ 核心 | ❌ 服务器存储 (架构偏离) | 根本不同 |
| 多设备同步 (iCloud/Obsidian Sync) | ✅ | ❌ | 关键缺失 |
| Markdown 编辑 | ✅ 丰富插件 | 🟡 ODocumentReader 只读 | 落后 |
| 双向链接 / 图谱 | ✅ 核心功能 | 🟡 后端有, 前端无图谱 | 落后 |
| 搜索 | ✅ 全文实时 | 🟡 有但刚修 DB bug | 可比 |
| 社区插件 | ✅ 1000+ | ❌ 无 | 不在计划 |
| 离线可用 | ✅ | ❌ | 关键缺失 |
| AI 翻译 | ❌ 无内置 | ✅ 有且可用 | **Stratum 领先** |
| AI 摘要 | ❌ 无内置 | ✅ 有 Agent | **Stratum 领先** |
| AI 阅读伙伴 (chat over notes) | 🟡 插件(Copilot) | ✅ 有 Agent | Stratum 领先 |
| 音频朗读 | ❌ | 🟡 代码有但部署缺 | 潜在领先 |
| 平台专业内容 (hevi) | ❌ | ❌ 未接入 | 无差距 (都没有) |
| 付费内容分层 | ❌ | ❌ 未实施 | 无差距 |
| 浏览器扩展 | ✅ Web Clipper | 🟡 v0.3 刚修 | 接近 |
| 手机 App | ✅ iOS/Android | ❌ | 落后 |

**结论**: Stratum 在 AI 增强层面真的比 Obsidian 强 (翻译/摘要/Agent), 但在**数据所有权** (本地存储 vs 服务器存储)、**多设备** (Obsidian Sync vs 无)、**离线** 这三个 Obsidian 的核心价值上完全落后。

按照 Wiki 原始 SPEC, Stratum 的设计是"数据存用户网盘", 是可以赢过 Obsidian 的。但当前实现已偏离到"数据存服务器", 跟 Notion 更像。

---

## §7 真按 Wiki 愿景, 引流前必修

### P0: 没这些不能引流

| 项 | 当前状态 | 必修原因 |
|---|---|---|
| substrate 入库真正写入 DB | 🟡 Phase 17 Task 1 刚修, 未验证 | 无此功能用户上传了看不到 |
| 文档列表真显示 | 🟡 同上 | 引流用户 0 内容体验 |
| URL 抓取真可用 | 🟡 Phase 17-A 刚修, 未验证 | 最低门槛的内容录入 |
| 搜索返回有意义结果 | 🟡 依赖上面 | 没结果=没产品 |
| 上传进度/结果反馈 | ❌ | 无反馈=用户以为坏了 |
| 8 个 Agent 中 4 个真可运行 | ✅ 4个 ✅, 4个调用外挂失败 | 至少不能全部失败 |
| 移动端基本可用 (手机浏览器) | 🟡 Next.js responsive 一般 | 国内用户主要手机 |

### P1: 引流时可没, 但 1 个月内必修

| 项 | 当前状态 |
|---|---|
| 浏览器扩展真可装真可用 | 🟡 代码有, 未验证 |
| 翻译结果真展示在前端 | ❌ Agent 运行完但 derivative 前端无展示页 |
| 笔记导出 (markdown/PDF) | ❌ |
| 搜索结果高亮展示 | 🟡 |
| 用户 onboarding 引导 | ❌ 无任何引导 |
| 文档阅读体验 (章节/目录) | 🟡 |
| WS toast 通知真触发 | 🟡 实现了但 WS /ws 路由未验证 |

### P2: 引流后逐步加 (1-3 个月)

| 项 | 当前状态 |
|---|---|
| 音频朗读 (部署 TTS) | ❌ |
| 插图生成 (部署 SD) | ❌ |
| 双向链接图谱前端 | ❌ |
| 手机 App | ❌ (原 Phase 11) |
| 付费系统 (哪怕只有微信支付) | ❌ |
| 多设备同步 | ❌ (原 Phase 2) |
| hevi 平台内容 (核心差异化) | ❌ (原 Phase 3/6) |

---

## §8 Advisor 推迟的真清单

> 每项列: 推后理由 vs Wiki 是否明确同意

### 8.1 Phase 17-A URL 抓取 — 推到 Phase 17

**真实情况**: 这应该是 Phase 1 的基础功能 (SPEC §3.1 `POST /api/v1/inbox/submit` 已包含), 但直到 Phase 17 才有真正的服务端 URL fetch。

**推后理由**: Phase 14 先做 SaaS web 框架, 后补功能。
**Wiki 同意了吗**: 未见明确 sign-off, 但 Wiki 接受了 Phase 16 P0 的 web-clip 后端 `_HAS_INBOX=True` 就认为"通了"。实际上那个实现直到 Phase 17 Task 1 才修好 DB 入库 bug。

---

### 8.2 17-C RSS 跟踪 — 推 Phase 18

**真实情况**: SPEC v0.5/v0.6 从未提到 RSS 作为计划功能。Wiki 在 Phase 17 任务书里提到, advisor 在 Phase 17 预核查中确认"SPEC 没有, 属纯新增"。

**推后理由**: 工作量大 (~1周), SPEC 无规划, 依赖不存在的 omodul RSS agent。
**Wiki 同意了吗**: Phase 17 任务书明确说"17-C RSS/Feed 跟踪", 但 advisor 推后了。Wiki 对推后的态度未明确表示。`oprim.fetch_rss` 是 stub 存在。

---

### 8.3 17-D ResearcherAgent — 推 Phase 17 P1

**真实情况**: SPEC §14.2 的 6 个预定义 Agent 中**无** ResearcherAgent。Wiki 在 Phase 17 任务书中提到"Stratum 主动找资料"场景, 但 SPEC 没有定义此 Agent。

**推后理由**: 不在 SPEC, 需要 searxng 外挂 + 新 Agent 实现。
**Wiki 同意了吗**: 未明确。这是 Wiki 期望但 SPEC 漏写的功能。

---

### 8.4 illustration_agent + audio_generator 外挂部署 — 推后

**真实情况**: Agent 代码存在可运行, 但调用时因 SD-webui 和 TTS 外挂未部署而失败。SPEC §14.2 明确 Audio Generator / Illustration 是 Phase 11 的 Agent。

**推后理由**: 跨机部署 (ADR-020 未决), TTS 选型 (Q5 未决), GPU 资源分配。
**Wiki 同意了吗**: ADR-020 明确是 Phase 11 启动前必决定的, 但 ADR-020 从未做。这个延误是 advisor 没有主动推进 ADR-020 的结果。

---

### 8.5 微信生态 5 个 endpoint — 未做

**SPEC 计划**: 微信小程序 (Phase 4) + 微信公众号 (Phase 7) + 微信支付 (Phase 5)。

**真实情况**: 无一实施。billing.py 有 `/billing/callback/wechat` 路由但 `_HAS_WECHAT = False`。

**推后理由**: 需要微信开发者账号 (ROADMAP §11.1 明确是 Phase 4 前的 Wiki 待决项), 微信小程序审核流程, 备案。
**Wiki 同意了吗**: 这是整个 Phase 4-7 的未启动, 原计划 2026-06 就要启动。现在已是 2026-06-04, 理论上应该在做。但 GDrive OAuth (Phase 2 前置) 从未申请, 所以 Phase 4 也无法启动。整个 Phase 2→4→5→6→7 链全部推迟, 无明确 Wiki 同意。

---

### 8.6 网盘同步 (Phase 2 全部) — 完全未启动

**SPEC 计划**: Phase 2 是 Google Drive 同步, 工程量 6 周, 2026-05 启动 (ROADMAP §8.1)。

**真实情况**: GDrive OAuth 从未申请, Phase 2 从未启动, 整条链 (Phase 2→4→5→6→7→9) 全部 blocked。

**推后理由**: GDrive OAuth client_id 申请被 Wiki 遗忘/推迟, advisor 未追踪。
**Wiki 同意了吗**: ROADMAP 明确 "Wiki 申请 GDrive OAuth client" 是🔴立即待决项。没有明确推后决定, 但事实上没做, 已推迟 1 个月以上。

**这是整个产品最大的单点偏离**: 原架构是"用户数据存自己网盘", 现在是"用户数据存我们服务器"。SPEC §6.1 明确"我们服务器不持有用户 substrate 原始 bytes", 当前实现完全违反此约束。

---

### 8.7 架构大偏离 (未在 ROADMAP 的, 实际做了的)

以下是 advisor/CC 实施了但在 ROADMAP v1.0 里没有规划的重大工作:

| 实际做的 | ROADMAP 里的位置 | 说明 |
|---|---|---|
| stratum-web Next.js SaaS 前端 | Phase 4 (微信小程序), 无 Web 规划 | ROADMAP v1.0 没有 Web frontend; Web 不是原始计划 |
| stratum-sl / stratum-api 双服务架构 | ROADMAP 只有 "stratum-main" 单服务 | SaaS layer 是 Phase 14 新增的, 不在 ROADMAP |
| 公网部署 (stratum.uex.hk) | 未在 ROADMAP | ROADMAP 认为 Phase 1 完工时 Wiki 是单用户本地使用 |
| PostgreSQL 会话/账号系统 | 简单提及但属于 Phase 4+ | 完整多用户账号系统是大工程 |
| Cloudflare Tunnel + nginx | 未提及 | 是部署需要 |
| Phase 14 SaaS 全套 (Phase 14-17) | 原来 Phase 14 = "发布闭环 v2.0" | CC 把 Phase 14 改成了 SaaS 建设 |

**最重要的偏离**: 原 ROADMAP 的 Phase 14 是"Stratum→hevi→多平台发布闭环 (v2.0, 不在 v1.0 范围)", 但 CC 实施了完全不同的 Phase 14 = "SaaS web app + 多用户账号 + 公网部署"。这个决策显然经过了 Wiki 同意 (因为持续了多个 Phase), 但没有正式修订 ROADMAP。

---

## §9 Wiki 现在需要对齐的核心问题清单

> advisor 认为以下问题 Wiki 和 advisor 从未正式对齐, 但执行中隐含了某些选择:

1. **架构模式**: 用户数据继续存服务器 (当前 SaaS) 还是恢复原设计 (用户网盘)?
   - 恢复原设计 = Phase 2 (6周工程) 必须做, 否则 SPEC §6.1 永久违反
   - 维持服务器存储 = SPEC 需要修订, 但简化了实施

2. **引流准备**: 何时引流? 功能状态 (42% 部分可用) 是否够?
   - 最短路径: 修 substrate 入库 + 上传反馈 + onboarding 引导 → 约 1-2 周
   - 完整路径: 加 Phase 2 同步 + 付费 + hevi 内容 → 至少 3-4 个月

3. **hevi 平台内容**: 是否还是核心差异化? 什么时候对接?
   - 无 hevi 内容 = Stratum 跟普通 RAG 工具无本质区别
   - 接入 hevi = 需要 hevi-content-repo 协议商定 (§18 Q1 从未决定)

4. **付费时间点**: 先引流再付费? 还是引流时直接有付费?
   - 无付费 = 引流成本不可持续
   - 有付费 = 需要微信支付 + 备案 + 内容可见 (至少 4-8 周工程)

5. **ADR-020 跨机部署**: TTS/SD 外挂何时部署?
   - 不部署 = audio_generator 和 illustration_agent 永远调用失败
   - 部署 = 需要主力机 GPU 资源 + 跨机网络配置

---

**End of STRATUM_REALITY_AUDIT_v1.0.md**

*生成: CC Phase 17 预核查后 真状态审计, 2026-06-04*
*来源: SPEC v0.5 (1215行) + v0.6 PATCH (615行) + ROADMAP v1.0 (754行) + 代码库直接核查*
