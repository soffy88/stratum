# Stratum Decision Log

**日期**: 2026-05-17
**对话覆盖**: 2025-05-17 全天对话
**形式**: ADR (Architecture Decision Records)

本文档汇总本次对话产生的全部架构决策, 每条含: 背景 / 选项 / 决定 / 含义。

按决策时间顺序排列。

---

## ADR-001: 批 2 实证混合模式

**日期**: 对话初期
**状态**: ✅ 已执行

### 背景
Wiki 提出做批 2 实证 (5 项: MCP 框架 / PDF 解析 / 向量库 / embedding / 用户存储层)。沙箱环境网络受限, 不能全部实测。

### 选项
- A: 全部沙箱实测 (但部分依赖 API 不可达)
- B: 全部公开调研 (但缺真实数据)
- C: 混合 — 能实测的实测, 不能的调研

### 决定
**C: 混合模式**

### 含义
- #4 MCP 框架: 沙箱实测 (3 个候选都跑通)
- #1 PDF 解析: pymupdf4llm + unstructured 沙箱实测, marker / docling / MinerU 调研 (装不下)
- #2 向量库: qdrant / chroma / lancedb 沙箱实测, pgvector 调研
- #3 embedding: 全调研 (HF / Voyage / DashScope 沙箱全 403)
- #5 用户存储: 全调研 (网盘 API 沙箱全 403)

---

## ADR-002: MCP 框架选 anthropic 官方内置 FastMCP

**日期**: 实证 #4
**状态**: ✅ 已决定

### 背景
SPEC v0.2 假设 2 个候选: anthropic 官方 SDK vs fastmcp 社区版。实证发现实际 3 个候选。

### 选项
- A: `mcp.server.Server` (anthropic 底层 API)
- B: `mcp.server.fastmcp.FastMCP` (anthropic 官方内置高阶)
- C: `fastmcp.FastMCP` (社区独立维护版)

### 决定
**B: `mcp.server.fastmcp.FastMCP`** (官方内置高阶)

### 理由
- 官方维护, 协议变化第一时间跟进
- 零额外依赖 (跟 anthropic SDK 共用)
- 代码量最少 (46 行 vs 社区版 50 vs 底层 75)
- 启动速度最快 (465ms vs 825ms)
- 跟 anthropic SDK 生态对齐

### 含义
- 4O 清单 v0.2 §2.10 oprim.mcp 锁定该选型
- pyproject.toml 加 `mcp>=1.27`
- 不引入社区 fastmcp 包

---

## ADR-003: PDF 解析分层策略

**日期**: 实证 #1
**状态**: ✅ 已决定

### 背景
SPEC v0.2 列 4 个候选 (pymupdf4llm / unstructured / marker / docling), 调研发现遗漏 MinerU (CJK 最佳)。

### 选项
- A: 单一 parser (选一个)
- B: 分层 (主 + 兜底 + 中文专用)

### 决定
**B: 分层策略**
- 默认: **pymupdf4llm** (90% 场景 + 速度最快)
- 兜底: **Marker** (扫描件 + 多格式 + LLM boost)
- 中文专用: **MinerU** (Wiki 中文知识库必需)
- 删除: unstructured (沙箱实证: 即使 fast strategy 都需视觉模型, 无独占优势)

### 理由
- Applied AI 800+ 文档评测: 没有任何 parser 超过 88% edit similarity → 不能赌单一
- Menon 2026 综合评估: pymupdf4llm 默认 + Marker 兜底 + MinerU CJK
- Wiki 重度中文场景 (古籍 + 论文 + 播客) 必需 MinerU

### 含义
- 4O 清单 §2.2 oprim.parser 三个 provider 都 P0/P1
- 加 `oprim.parser.detect_pdf_features` 用于 dispatch
- v1.0 不实施 docling (P2 延后)

---

## ADR-004: 向量库选 LanceDB (本地) + pgvector (服务端)

**日期**: 实证 #2
**状态**: ✅ 已决定

### 背景
SPEC v0.2 §7.2 假设 qdrant 是默认 backend, 但实证发现 qdrant 内嵌模式性能陷阱。

### 选项 (用户本地)
- A: qdrant 内嵌
- B: chroma
- C: lancedb

### 选项 (平台服务端)
- D: qdrant server
- E: pgvector

### 决定
**用户本地: LanceDB** + **平台服务端: pgvector**

### 实测数据 (1K 向量)

| | upsert | search | size |
|---|---|---|---|
| qdrant 内嵌 | 6354ms | 1.5ms | 3.95 MB |
| chroma | 256ms | 1.3ms | 4.26 MB |
| **lancedb** | **20ms** | 4.3ms | **1.52 MB** |

qdrant 内嵌 upsert 慢 lancedb **330 倍**。

### 理由 (本地)
- LanceDB upsert 性能最优
- 持久化最省 (跟 git LFS 友好)
- Lance 列式可演化
- 嵌入式零运维 (跟"本地优先"原则一致)

### 理由 (服务端)
- 平台内容索引需要服务端单一数据库 (运维简单)
- pgvector 0.9 性能足够 (用户量级 < 50M 向量)
- PostgreSQL 同时承载 platform_content + 用户账号

### 含义
- STRATUM_SPEC v0.5 §7.2 修订 (qdrant → lance)
- 4O 清单 §2.5 vector_db 调整 (lancedb P0, pgvector P0, qdrant_embedded 删除, qdrant_server P1)
- chroma 加 5461 batch 限制提醒 (生产 gotcha)

---

## ADR-005: Embedding 选 Qwen3-Embedding via DashScope

**日期**: 实证 #3
**状态**: ✅ 已决定

### 背景
SPEC v0.2 列 4 候选 (bge-m3 / voyage-3 / qwen-embedding / e5-mistral)。

### 关键发现
- "qwen-embedding" 实际是 **Qwen3-Embedding** (0.6B / 4B / 8B 三规格)
- Qwen3-Embedding-8B MTEB 70.6 (开源 SOTA)
- 中文 71.5, 远超 Gemini 68.1 / OpenAI 58.7
- e5-mistral 已不在 MTEB 前 10 (被超越)
- voyage-3 无独占优势

### 选项
- A: Qwen3 via DashScope API (Wiki 已接入)
- B: BGE-M3 local self-host
- C: voyage-3 API
- D: e5-mistral

### 决定
**A: Qwen3-Embedding (DashScope API)** 主推 + **B: BGE-M3 备选**

### 理由
- 中文 SOTA (Wiki 知识库重度中文场景)
- Wiki memory 确认已接入 DashScope
- BGE-M3 备选 (本地 self-host 隐私场景)
- 删除 voyage-3 (P2 降级) 和 e5-mistral (彻底删)

### 含义
- 4O 清单 §2.3 oprim.embedding 调整
- embedding 维度推荐 1024 (精度 98.1% + 存储 4GB/1M docs)
- Qwen3 原生支持 Matryoshka, 未来可降维不重生成
- v1.0 不建 vectors-audio (audio 走 transcript 文本路径)
- image embedding 用 SigLIP-2 (跨模态语义) + DINOv2 v1.x (视觉相似)

---

## ADR-006: 数据存"用户网盘 + 本地" 架构

**日期**: 对话中段 (Wiki 校准)
**状态**: ✅ 已决定 (但有重要修正见 ADR-007)

### 背景
Wiki 提出商业化方向时, 定调"数据存在每个人的免费网盘 + 自己本地电脑"。

### 选项
- A: 数据存我们服务器 (像 Mem.ai / 印象笔记)
- B: 数据存用户网盘 + 本地 (Wiki 提出)

### 决定
**B: 数据存用户网盘 + 本地**

### 理由
- 真正"数据归用户"差异化
- 零服务器存储成本
- 强隐私
- 法规天然合规

### 代价
- 多 4-5 人月工程
- 多 1-3 秒同步延迟
- 用户网盘 quota 不够时的复杂体验

### 含义
- 需要多个网盘 SDK 适配层
- 索引存哪是新问题 (见 ADR-008)
- 跟 Mem.ai / 腾讯 IMA 形成强差异化

---

## ADR-007: 平台内容 vs 用户内容分层存储

**日期**: 对话末期 (Wiki 引入内容平台维度)
**状态**: ✅ 已决定

### 背景
ADR-006 决定"数据存用户网盘", 但后来 Wiki 引入"平台独有内容" (hevi 出品) 概念。平台内容不能存用户网盘。

### 决定
**分层数据所有权**:

| 数据 | 所有权 | 存储位置 |
|---|---|---|
| 平台内容 (hevi 出品) | 平台 | 服务器 + CDN |
| 用户原始资料 | 用户 | 用户网盘 + 本地 |
| 用户对平台内容的笔记/高亮 | 用户 | 用户网盘 + 本地 |
| 用户账号 / 订阅 | 平台 | 服务器 |

### 含义
- STRATUM_SPEC v0.5 §6 三层架构含平台层 + 用户层 + 协调层
- 用户取消订阅 → 平台内容不可访问, 用户笔记仍保留
- 防盗版: 平台内容不写入用户网盘, 客户端隐藏缓存

---

## ADR-008: 索引存储方案 C (混合)

**日期**: 实证 #5
**状态**: ✅ 已决定

### 背景
ADR-006 决定数据存用户网盘, 但索引 (向量库 / 全文 / 元数据) 存哪没明确。

### 选项
- A: 索引完全存用户网盘 (跟原始数据共存)
- B: 索引完全存我们服务器
- C: 本地索引 + 网盘备份 + 服务器 changefeed (混合)

### 决定
**C: 混合方案**

### 各方案评估
- A: 并发冲突 / 性能差 / 用户误删 → 不可行
- B: 跟 Wiki "数据归用户" 设计意图冲突
- C: 工程上最优 + 跟设计意图最贴合

### 含义
- 本地索引为主 (LanceDB / Tantivy / DuckDB)
- 每日 snapshot 备份到用户网盘 _hub_backup/
- 服务器 changefeed 协调多端同步 (这层无法省)
- 新设备从最新 snapshot 初始化 (5-15 分钟)

---

## ADR-009: 国内网盘策略

**日期**: 实证 #5
**状态**: ✅ 已决定

### 背景
国内网盘 API 不友好, 需要确定支持范围。

### 决定

| Provider | 优先级 | 理由 |
|---|---|---|
| **OneDrive** | P0 | 国内可用 + SDK 成熟 |
| **本地文件夹** | P0 | 隐私敏感 / 离线 |
| **阿里云盘** (开放平台) | P1 | 需先确认拿到内测凭证 |
| **Dropbox** | P1 | 国际主选 |
| **Google Drive** | P1 | 国际备选 |
| **WPS 云空间** | P2 | 学生用户 |
| ~~百度网盘~~ | 不支持 | 合规接入路径不通 |
| ~~微信文件传输助手~~ | 不支持 | 个人微信无 API |

### 关键风险
- 阿里云盘开放平台凭证可能拿不到 (个人/初创门槛不明)
- 这是 v0.5 §18 Q2 未决问题

### 含义
- 4O 清单 §2.4 oprim.storage 按此排序实施
- 国内用户主要靠 OneDrive (慢) + 阿里云盘 (如能拿到凭证)
- 大量百度网盘用户**不能转化** (合规接入不通)

---

## ADR-010: 微信集成边界

**日期**: 实证 #5
**状态**: ✅ 已决定

### 背景
Wiki 定调"微信优先"。但微信个人号无官方 API, 第三方接入封号率 > 80% + 违规。

### 决定
合规路径只用三种:
- ✅ **微信小程序** (主入口)
- ✅ **微信公众号** (推送通知 + 兜底)
- ✅ **微信支付** (订阅)
- ❌ 个人微信 API / Hook / WeChaty / 协议模拟: 严禁

### "微信优先" 重新定义
- 不是: 用户发文件到微信文件传输助手, Stratum 监听
- 是: 微信**小程序**作为 capture 入口, 数据落到用户的**其他真正网盘** (OneDrive / 阿里云盘)

### 含义
- STRATUM_SPEC v0.5 §14 微信集成边界明确
- 4O 清单 §2.11 oprim.wechat 包含 mp / oa / pay, 不含 personal_api
- 微信小程序单文件上限 100 MB, 大文件引导桌面 app

---

## ADR-011: hevi 作为内容生产引擎

**日期**: 对话末期 (Wiki 校准)
**状态**: ✅ 已决定

### 背景
Wiki 引入 "比得到 / 喜马拉雅更优秀" 的内容平台定位, 之后明确"hevi 生产高质量独有内容"。

### 决定
**hevi 是 Stratum 平台内容的供应方**

### 内容定位
- 垂直但深: 投资 / 金融 / 量化 / 经济史 / 商业思想 (hevi 擅长领域)
- 不做: 通识 / 鸡汤 / 管理学 (得到擅长)
- 不做: UGC / 名人入驻 / 视频

### 内容形态
- 深度文章 (3000-8000 字) — 每周 1-2 篇
- 概念百科 (结构化) — 持续积累
- 音频解读 (TTS 生成) — 跟文章 1:1

### hevi ↔ Stratum 对接协议
- hevi-content-repo (私有 git repo)
- Stratum 服务端 cron 定时拉取
- 文件结构: `{year}/{month}/{slug}.md` + `{slug}.meta.yaml`
- meta.yaml 字段为协议 (v0.5 §18 Q1 未决: 详细 schema 待定)

### 含义
- STRATUM_SPEC v0.5 §4 内容体系
- 4O 清单 §3.3 oskill.knowledge.ingest_platform_content
- 4O 清单 §4.3 omodul.platform.run_content_pipeline
- 完全跳过雇内容团队的路径 (Wiki 自己 + hevi 输出已够)

---

## ADR-012: 订阅档位

**日期**: SPEC v0.5 写作时
**状态**: ✅ 已决定

### 决定

| 档位 | 价格 | 内容 |
|---|---|---|
| Free | ¥0 | 部分 hevi 免费内容 + 工具基础 (1 GB) |
| **Plus** | ¥29/月 / ¥299/年 | 全部 hevi 独有 + 工具完整 (20 GB) |
| Pro | ¥99/月 / ¥999/年 | Plus + Wiki 答疑 + 早鸟 7 天 |
| 学生 Plus | ¥149/年 (.edu) | 同 Plus |

### 跟得到对标
- 得到 ¥199-¥399/年
- 我们 Plus ¥299/年 相近
- 单一垂直领域专精

### 含义
- v1.0 简化, 不做复杂优惠
- 学生 .edu 验证 / 早鸟前 1000 用户 / 推荐返佣 (双方 1 月)

---

## ADR-013: SPEC 文档纪律

**日期**: 对话末期 (Wiki 多次强调)
**状态**: ✅ 已内化

### 决定
SPEC v0.5 写作纪律:

1. **对工程实施没用的不写**
   - 删: 变更摘要 / 对照表 / 产品营销定位 / 长期主义等空话
2. **不写"反向定义不做什么"**
   - 这是产品决策, 不是工程约束
3. **每条原则必须能翻译成工程约束**
   - "数据归用户" → "服务器不持有 substrate 原始 bytes"

### 应用
- SPEC v0.3 → v0.5 应用此纪律
- v0.5 1214 行 (比预估 2000-2500 行少, 因为剔除冗余)

---

## ADR-014: 商业模式 + 团队时间先不考虑

**日期**: 对话中段
**状态**: ✅ 已接受

### Wiki 原话
> Q3 商业模式 / Q4 团队时间先不考虑, 专注打磨产品到极致优秀

### 含义
- SPEC v0.5 不写商业模式细节 (只写技术上 access_tier 校验机制)
- 实施路线 §16 只写依赖关系, 不写时间
- 工程量估算 (35 人月) 给参考, 不强制按谁分配

---

## ADR-015: 单一产品体验 (不分用户群)

**日期**: 对话中段
**状态**: ✅ 已决定

### Wiki 原话
> 你不用考虑哪个为目标, 功能做到极致优秀就行
> 不需要双层设计, 一个产品一个体验, 对所有人

### 决定
- 不为"普通用户"做阉割版
- 不为"高级用户"做技术版
- 内部技术层 (18 medium / substrate / concept 等) **不暴露给用户**
- 但所有用户看到**同一个产品**, 不分级

### 含义
- SPEC v0.5 §3.2 用户不可见的内部概念 (强制 UX 隐藏)
- 但 SPEC §3 schema 完整保留 (内部使用)

---

## ADR-016: 部署全程本地, 商业化阶段单独迁云

**日期**: 对话末期 (Wiki 确认)
**状态**: ✅ 已决定 (锁定 SPEC v0.5 §18 Q3)

### 背景
SPEC v0.5 §18 Q3 列了"服务器部署区域 (中国/海外/双区)"作为 Phase 2 启动前必决问题。
Claude 提出方案建议 Phase 1-3 本地 + Phase 4 迁云, 但 Wiki 校准为完全本地。

### Wiki 原话
> 服务器部署 = 我本地电脑
> 商业化后我自己做国内服务器

### 决定
**Stratum SPEC v0.5 范围内的所有 Phase (1-12) 都部署在 Wiki 控制的本地基础设施**:
- 主力 Win11 + WSL2
- Singapore VPS (Tailscale 100.73.220.5)
- 现有 6 设备 Tailscale 网络

### 商业化 (out of scope)
- 国内服务器迁移
- 微信小程序公开版审核
- 微信支付实际接入
- 大陆 C 端用户访问
- ICP 备案 + 内容备案

**以上全部由 Wiki 在"商业化"阶段单独决策, 不属于当前 SPEC 实施范围**.

### 含义
- SPEC v0.5 §16 路线图是"产品功能完整性"路线图, 不是"商业上线"路线图
- 各 Phase 的"产出"是技术意义上的"能跑通", 不是"上线公开版"
- 例: Phase 4 "微信小程序 MVP" = 开发版可用 (最多 30 内测用户), 不含审核 + 公开版
- 例: Phase 5 "付费系统" = 技术实现完成, 不含微信支付实际接入
- ADR-014 (商业模式 + 团队时间先不考虑) 由此被扩展为更具体的边界

### 关联
- ADR-014: 扩展边界
- SPEC v0.5 §18 Q3: 锁定

---

## ADR-017: v1.0 不做 E2EE, v1.x 评估

**日期**: 对话末期 (Wiki 确认)
**状态**: ✅ 已决定 (锁定 SPEC v0.5 §18 Q8)

### 背景
SPEC v0.5 §13.4 E2EE 留作 v1.0 不实施 + v1.x 评估, 列为 §18 Q8 未决问题。
Claude 解释了 E2EE 概念 (Signal / Proton Drive 模式: 服务器永远拿不到明文), Wiki 决定采纳建议。

### 选项
- A: v1.0 做 E2EE
- B: v1.0 不做, v1.x 评估
- C: 永不做

### 决定
**B: v1.0 不做 E2EE, v1.x 评估**

### 理由
- 服务器端 LLM / embedding 是体验关键 (Wiki "极致优秀" 要求)
- 本地小模型质量差距大 (Qwen3-0.6B vs Qwen3-Max)
- E2EE 适合 Proton Drive 这类"隐私第一"产品, Stratum 是"知识平台 + 工具"
- 已通过 ADR-006 (数据存用户网盘) 提供基础隐私
- 服务器临时下载 30 分钟 TTL 已是合理妥协

### 含义
- SPEC v0.5 §13.4 状态 "v1.0 不实施" 已锁定
- 服务器可临时下载 substrate 做 embedding / LLM 处理 (30 min TTL)
- 临时文件加密 + audit log (已在 SPEC §13.3)
- v1.x 可作为高级用户选项加上 (用户选 E2EE → 接受性能损失)

### 不会做的事
- 不做 E2EE 的妥协方案 (即便有用户要求隐私, v1.0 用 §13 既有方案满足)
- 不为 E2EE 提前改架构 (架构 v1.x 加 E2EE 时再改, 现在不背包袱)

---

## ADR-018: Translation 作为 Stratum 核心能力

**日期**: Phase 1 omodul 实施期间
**状态**: ✅ 已决定 (Phase 10 实施, 不在当前范围)

### 背景
Wiki 提出: 很多英文新书 / 论文没有中文版, Stratum 应该提供高质量翻译作为 derivative。
触发 source: hydropix/TranslateBooksWithLLMs (577 star, AGPL-3.0) — 多 LLM provider 翻译 EPUB/SRT/DOCX/TXT, 保留格式 + 断点续传 + 长文档分块。

### 决定
**Translation 作为 Stratum 核心能力, Phase 10 实施**

具体:
- 新增 derivative type: `translation` (SPEC v0.5 §3.3 12 个 derivative 加第 13 个)
- 新增 `oprim.translate` (provider 抽象 + 多 LLM backend)
- 新增 `oskill.knowledge.translate_substrate`
- 配套: chunking 策略 / 格式保留 / 断点续传 / 中英对照索引

### 为什么是核心能力 (不是普通 derivative)
- Wiki 中文用户场景: 英文 paper / 英文书 / 英文 podcast 占比高, 中文翻译版往往不存在
- 跟得到 / 喜马拉雅形成关键差异化 (它们只有官方授权中文内容)
- 跟 ADR-006 (数据归用户) + 商业模式 (c) Stratum 知识管理工具定位完美对齐
- "用户上传任何英文资料 + 高质量翻译 + 中英对照检索" 是 Stratum 独有体验

### hydropix 仓库的使用边界
- **不直接 fork / 集成** — AGPL-3.0 license 传染性强, 影响商业化
- **借鉴经验**:
  - chunking 策略 (token-based + 跨 chunk 上下文)
  - 格式保留 (EPUB / SRT 完整性)
  - 断点续传 (checkpoint 设计)
  - prompt 工程 (它有 prompt_optimizer)
  - 多 provider 抽象经验
- Stratum 自己实现, 用 platform/oprim 范式

### 实施时机
- **当前 Phase 1**: 不实施 (R-4 禁止扩大范围)
- **Phase 10 LLM 增强期**: 实施
- **Phase 10 启动前**: 单独做"翻译选型实证" (Qwen3 / Claude / Gemini / DeepSeek 翻译质量对比, 论文 / 文学 / 技术不同领域)

### 含义
- SPEC v0.5 下次修订:
  - §3.3 derivative 加 translation 类型
  - §16 Phase 10 范围扩展 (含 translation pipeline)
  - §17 未决问题加 "翻译 provider 选型"
- 4O 清单 v0.2 下次修订:
  - oprim.translate 新增大类
  - oskill.knowledge.translate_substrate 新增
- 当前 Phase 1 实施**不打断**, CC 继续完成 omodul

### 未决子问题 (Phase 10 启动前)
- 翻译 provider 选型 (实证驱动)
- chunking 策略具体参数 (token 数 / 上下文窗口)
- 中英对照 UI 设计
- 自动 vs 用户触发 (用户上传英文资料自动翻译? 还是手动?)
- 成本控制 (大量 LLM token, 用户配额或定价层级)

### 关联
- 触发: hydropix/TranslateBooksWithLLMs 仓库 (Wiki 提供链接)
- 依赖: Phase 1-9 完成
- 跟 ADR-006 / 商业模式 (c) 一致

---

## ADR-019: Stratum 外挂能力架构 — 同 Docker 网络解耦集成

**日期**: Phase 1 omodul 实施期间
**状态**: ✅ 架构方向已定, 具体外挂选型在 Phase 11+ 决定

### 背景
Wiki 连续分享 7 个 GitHub 仓库, 确认架构意图: 各 AI 增强能力是**独立项目** (各有经理人), 通过**同 Docker 网络解耦集成**到 Stratum, 跟 hevi 同模式 (ADR-011 路径 C)。

仓库分类:
- **外挂能力** (Stratum 调用): whisper.cpp / F5-TTS / fish-speech / stable-diffusion-webui / searxng / hevi / TranslateBooksWithLLMs (参考, AGPL 不直接用)
- **新 substrate 输入源** (Stratum 读取): screenpipe (屏幕+音频 24/7 历史)
- **参考产品** (Stratum 借鉴优势): anything-llm (60K star, "chat with docs + AI Agents")

### 决定
**Stratum 采用"主体 + 外挂"架构**:

```
┌─────────────────────────────────────────────────────┐
│                  Stratum (主体)                     │
│   入库 / 检索 / derivative / 三 souls               │
└─────────────────────────────────────────────────────┘
         ↑ 数据输入            ↓ 外挂调用 (HTTP / MCP)
┌────────────────┐     ┌──────────────────────────────┐
│ 新 substrate    │     │ AI 增强外挂 (独立 container)  │
│ 输入源          │     │                              │
│ - screenpipe   │     │ ├── whisper.cpp (ASR)        │
│   (屏幕历史)   │     │ ├── F5/fish (TTS)            │
│                │     │ ├── SD-webui (图像)          │
│                │     │ ├── searxng (元搜索)         │
│                │     │ └── hevi (动画化教学)        │
└────────────────┘     └──────────────────────────────┘

       同 Docker 网络 / 各 container 独立维护 / 各经理人负责
```

### 关键属性
1. **解耦**: 各外挂独立 container, 独立版本, 独立故障域
2. **同网络**: 内网 HTTP/MCP 通信, 低延迟, 不走公网
3. **独立经理人**: 每个外挂项目由不同 advisor 负责, Stratum 经理人只负责接入接口
4. **可替换**: 同类外挂可换 (F5 ↔ fish-speech), Stratum 抽象接口不变
5. **本地优先**: 跟 SPEC §11.1 一致, 不依赖外部 API

### 对 Stratum 设计的影响

**4O 清单新增**:
- `oprim.external.*` (新 sub-package 类) — 外挂 HTTP/MCP 客户端
  - `whisper_client` / `tts_client` / `sd_client` / `searxng_client` / `hevi_client`
- `oprim.input.screenpipe` — screenpipe 数据库读取器 (新 substrate 来源)
- `oskill.knowledge.transcribe_audio_substrate` (用 whisper 外挂)
- `oskill.knowledge.generate_audio_narration` (用 TTS 外挂)
- `oskill.knowledge.generate_illustration` (用 SD 外挂)
- `oskill.knowledge.web_search_augmented` (用 searxng + Stratum 融合检索)

**SPEC v0.5 新增**:
- §5 medium 加 `screen_event` (来自 screenpipe)
- §3.3 derivative 加 `translation` (ADR-018) / `audio_narration` / `illustration`
- §11 部署架构加"外挂能力 Docker 编排"小节
- §16 路线图加 Phase 11+ 外挂集成层

### 实施时机

**当前 Phase 1**: 不实施, R-4 禁止扩大范围
**Phase 2 (网盘 + 同步)**: 不实施 (跟外挂无关)
**Phase 10 (Translation)**: 实施 translation derivative + TTS derivative (开始引入外挂)
**Phase 11+ (外挂集成层)**: 完整实施所有外挂接口 + screenpipe 输入源

预估 Phase 11+ 工程量: 每个外挂接入 ~ 1-2 周, 5-6 个外挂 ≈ **2-3 个月**

### anything-llm 嫁接评估 (单独任务)

anything-llm 60K star 经验值得借鉴, 但**不直接集成**, 而是评估优势 + 嫁接到 Stratum 设计:

候选嫁接点 (待研究):
- Scheduled Tasks (定时任务)
- No-code AI Agent builder (用户自定义 Agent)
- Full MCP-compatibility 实现细节
- Multi-user permissioning (Stratum 商业化期需要)
- Embeddable chat widget (跟 SPEC §15 嵌入式 widget 对齐)
- AI Agent workspace 设计

Stratum 经理人 (我) 单独做研究报告, **不阻塞 Phase 1**。

### Wiki 工作模式
- 每个项目由不同经理人负责
- Stratum 经理人只管 Stratum 主体 + 接入接口
- 其他经理人管各自外挂的实施 / 部署 / 维护
- 跨项目协作通过 Wiki 转贴, 不直接通信

### 含义
- Stratum SPEC v0.5 下次修订加 §11.x "外挂能力架构" + §16 Phase 11+
- 4O 清单 v0.2 下次修订加 `oprim.external.*` / `oprim.input.*` / `oskill.knowledge.external_*`
- ADR-018 translation 是这个架构的第一个应用 (Phase 10)
- Stratum v1.0 不依赖任何外挂仍可单机运行 (向下兼容)
- 外挂全部就位 → Stratum v2.0 "AI 增强完整版"

### 不会做的事
- 不把外挂代码合并进 Stratum 主仓库 (违反解耦原则)
- 不为外挂工程实施做决策 (各经理人自己定)
- 不在 Phase 1-2 实施任何外挂集成 (R-4 范围控制)
- 不替代或包装 anything-llm 整个 (它是参考, 不是依赖)

### 关联
- 触发: Wiki 连续分享 7 个仓库 + 确认架构意图
- 跟 ADR-011 (hevi 解耦) 同模式
- 跟 ADR-016 (本地部署) 一致
- 跟 ADR-018 (translation) 是同一架构的具体应用

---

## ADR-020: Phase 10 async provider 技术债务

**日期**: 2026-05-19 (Phase 10 Gate 验收时)
**状态**: ✅ **已偿还 2026-05-19** (oprim 2.5.0 / oskill 2.5.0)

### 偿还结果
- 3 provider 全 async (DeepSeek / Claude / Qwen3)
- translate_document_async 主路径
- sync wrapper + DeprecationWarning (Phase 11 后正式删)
- oskill.knowledge.translate_substrate 切 async 路径
- 测试 78 / 97.17% 覆盖 / 0 regressions
- tag: v2.5.0-async-refactor

### 背景
Phase 10 实施指令书要求 oprim.translate provider 实施 `async def translate(...)` 接口, 同步 SDK (DashScope) 用 `asyncio.to_thread` 包装。

CC-B 实际实施: provider 保持同步 (跟 oprim.llm 层现有风格一致), `oskill.knowledge.translate_substrate` 是 async 但内部调用 sync `translate_document`。

CC-B 主动招供这是已知架构偏离, 请 advisor 决策。

### 决定
**当前 Phase 10 不阻塞 Gate 验收**, 但记入技术债务清单。

### 为什么不阻塞
- 单用户场景 (Wiki 自用), sync 跑跑没问题
- Phase 10 测试 + 端到端 demo 全部通过
- 重新打开整个 Phase 10 工程量大, 收益小
- Gate 验收的目标是功能正确性, 不是架构纯洁性

### 为什么必须解决
- **Phase 11 (Agent + Scheduled Jobs)**: 多个 Agent 并发跑翻译任务, sync provider 会阻塞 event loop, scheduled_jobs 性能严重劣化
- **Phase 14+ (商业化)**: 多用户必须 async
- **跟其他 oprim 抽象一致性**: oprim.embedding / oprim.llm.llm_call 已经有 async 版本 (Phase 1 完工的部分), 单独 translate 是 sync 不一致

### 偿还时机
**Phase 11 启动前** 必须完成 async 重构:
- oprim.translate.providers.* 改 async
- DashScope SDK 用 asyncio.to_thread 包装
- 现有 sync 接口保留为 wrapper (向后兼容 1 个版本)
- 跟 oprim.llm 同等异步风格

### 工作量
预估 3-5 天 (单独 CC 跑):
- 4 个 provider 改 async (各 0.5 天)
- 测试改写 (1 天)
- 集成测试 (1 天)

### 关联
- ADR-018 (Translation 核心能力)
- Phase 10 完工报告 (问题 1 偏离清单)
- Phase 11 启动前 ADR-020 必须先解决

---

## ADR-021: Stratum 跨机部署拓扑

**日期**: 2026-05-20
**状态**: ✅ 已决定 (Phase 11 启动前置), 由 CC 完成调研撰写

### 背景
- 设备拓扑校准: 笔记本 24G/4G GPU 主开发, 主机 32G/10G GPU 闲置
- Stratum Phase 11 外挂能力 (whisper/TTS/SD/searxng/hevi) 跟 GPU 需求强相关
- ADR-019 "同 Docker network" 在跨机场景需要修订

### 决定
**三层部署拓扑**:

| Layer | 设备 | 角色 | 组件 |
|---|---|---|---|
| Layer A | 笔记本 | Stratum 主体 + 轻外挂 | stratum-main, postgres, redis, rabbitmq, lancedb |
| Layer B | 主机 | 重外挂 (GPU) | whisper-large-Q4, F5-TTS, SD 1.5/2.1, ollama qwen3:14b-q4 |
| Layer C | Singapore VPS | 代理 + 备份 | sing-box |

**跨机通信**: Tailscale mesh + Magic DNS
**故障域**: 独立, Stratum 主体 (Layer A) 单点, 外挂可降级

### CC 调研采纳的关键校准
- **F5-TTS GPU 实际 6.4G** (不是 4-6G) → ADR 修订 6-8G
- **whisper large-v3 全精度紧贴 10G** → 指定量化版 Q4/Q5 (~4-5G)
- **fish-speech 版本依赖差异 1.8-24G** → "不部署" 决定维持, 用 F5 替代
- **ollama qwen3:14b-q4 实际 8.3-10G + 4K token context 限制**
- **Tailscale + Docker WSL2 6.8+ kernel 需 TS_USERSPACE=true 前向风险**, sidecar 比 network_mode: host 更健壮

### ADR-019 修订
**保留**: 解耦原则 / 各经理人独立 / 本地优先 / MCP 协议优先
**变更**:
- ❌ "同 Docker network" → ✅ "Tailscale mesh + Magic DNS"
- ❌ "同机 docker network 内网延迟 < 5ms" → ✅ "Tailscale 内网延迟 5-15ms (LAN 实测)"

### Phase 11 启动前置 (6 项)
1. ✅ Tailscale mesh 已配置 (Wiki 已有)
2. ⏳ 笔记本 ping 主机 Tailscale IP 实证 (Wiki 跑, 5 分钟)
3. ⏳ 主机 Ollama qwen3:14b-q4 加载验证 (Wiki 跑, 30 分钟)
4. ⏳ 外挂镜像最终选型 (Phase 11 启动时 CC)
5. ⏳ 主机 docker-compose.layer-b.yml 模板部署验证 (Phase 11 启动时 CC)
6. ⏳ 笔记本 STRATUM_*_HOST 环境变量配置 (Phase 11 启动时 Wiki + CC)

### 未决问题
- **Q14**: hevi 部署位置 → hevi 经理人决定
- **Q15**: 主机 GPU 任务调度 — Ollama + F5-TTS + SD 共享 10G, 并发排队策略
- **Q16**: 主机离线时 Scheduled Jobs 跑还是不跑?
- **Q17**: Tailscale 跨大陆延迟实测 (Wiki 笔记本 ↔ Singapore VPS)

### 治理问题披露 (R-1)
CC 在 stratum repo 中找不到 ADR-016/019 原文件 (advisor 维护单一聚合文件
DECISION_LOG.md, 未拆分到 repo 的 docs/decisions/)。CC 用 stub 补录方式就近
修复, 但根本问题: stratum repo 没有完整 ADR 目录。后续 advisor 统一补全。

### 关联
- 修订 ADR-016 (本地部署 → 三机本地)
- 修订 ADR-019 (同 network → Tailscale mesh)
- Phase 11 启动前置
- 跟 ADR-006 (用户网盘 + 本地) 一致

---

## 决策依赖关系图

```
ADR-001 (混合实证模式)
  ├── ADR-002 (MCP 框架) ← 实证 #4
  ├── ADR-003 (PDF 解析) ← 实证 #1
  ├── ADR-004 (向量库) ← 实证 #2
  ├── ADR-005 (Embedding) ← 实证 #3
  └── ADR-008 (索引方案 C) ← 实证 #5
       └── ADR-009 (国内网盘) ← 实证 #5

ADR-006 (用户网盘 + 本地)
  ├── ADR-007 (平台 vs 用户分层) ← Wiki 引入内容平台
  ├── ADR-008 (索引方案 C)
  └── ADR-009 (国内网盘)

ADR-010 (微信集成边界) ← 实证 #5
ADR-011 (hevi 内容生产) ← Wiki 校准
  ├── ADR-012 (订阅档位)
  └── [hevi-content-repo 协议需求 v0.1, 待 hevi advisor review]

ADR-013 (文档纪律) ← Wiki 多次强调
ADR-014 (先不考虑商业模式/团队) ← Wiki 校准
  └── ADR-016 (部署全程本地) ← Wiki 锁定边界
ADR-015 (单一产品体验) ← Wiki 校准
ADR-017 (v1.0 不做 E2EE) ← Wiki 校准
ADR-018 (Translation 核心能力, Phase 10) ← hydropix 仓库启发 + Wiki 确认
ADR-019 (外挂能力架构, Phase 11+) ← Wiki 确认 7 个仓库的解耦集成意图
  ├── 跟 ADR-011 (hevi 解耦) 同模式
  ├── ADR-018 是这个架构的第一个应用
  └── 跟 ADR-016 (本地部署) 一致
ADR-020 (Phase 10 async 技术债务) ← Phase 10 Gate 验收发现
  └── Phase 11 启动前必须偿还 → ✅ 已偿还 2026-05-19
ADR-021 (Stratum 跨机部署拓扑) ← Phase 11 启动前置
  ├── 修订 ADR-016 (本地部署 → 三机本地)
  ├── 修订 ADR-019 (同 Docker network → Tailscale mesh)
  └── 6 项 Phase 11 准入条件 (1 ✅ / 5 ⏳)
```

---

## 未决问题汇总 (来自 STRATUM_SPEC v0.5 §18)

### 已 resolved (本次对话末期)
- ~~**Q3**: 服务器部署区域~~ → ADR-016 (Wiki 本地基础设施, 商业化阶段单独迁云)
- ~~**Q8**: E2EE 是否纳入 v1.0~~ → ADR-017 (v1.0 不做, v1.x 评估)

### 仍未决 (按时机紧急程度排)

### 紧急 (Phase 2-3 启动前)
- **Q1**: hevi-content-repo 协议细节 (meta.yaml schema)
  - 状态: 需求草案 v0.1 已成, 待 hevi advisor review
  - 文档: /mnt/user-data/outputs/hevi-stratum-protocol/HEVI_CONTENT_REPO_PROTOCOL_REQUIREMENTS.md
- **Q9**: 内容备案合规细节 (找合规律师)
  - 状态: 待 Wiki 决策时机 (商业化阶段)

### 中期 (Phase 4-9 启动前)
- **Q2**: 阿里云盘开放平台凭证可行性
- **Q4**: 平台内容防盗版强度
- **Q5**: TTS 服务选型

### 长期 (Phase 11-12 启动前)
- **Q6**: 推荐算法 v1.x 升级 (规则 → ML)
- **Q7**: 移动端跨平台 vs 原生
- **Q10**: 公开 API 开放范围

---

**End of Decision Log**
