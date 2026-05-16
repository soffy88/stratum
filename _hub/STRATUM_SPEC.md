# STRATUM_SPEC v0.1.2

**Stratum — Wiki 本地知识库系统设计规范**

**版本**: v0.1.2
**创建日期**: 2026-05-16
**最后修订**: 2026-05-16 (实证项 #4 决策: 采用 Obsidian 原生兼容方案)
**架构师**: Wiki
**草拟**: Claude (chief advisor)
**状态**: Draft — 待 Wiki 批准后进入实施
**仓库**: `~/projects/stratum/` (本地, git + git-lfs)
**License**: 个人使用,推迟决定
**参考方法论**: HEVI_SPEC v0.2 / HELIOS_3O_SPEC v0.6 (架构治理风格)

---

## §0 关于本 SPEC

### 0.1 SPEC 的角色

本 SPEC 是 Stratum 的**单一真相来源 (Single Source of Truth)**。所有目录结构、yaml schema、流水线脚本、对外接口必须可追溯到本 SPEC 的某条款。

实施流程:

```
STRATUM_SPEC (本文件) 
  → 各批次启动前补充 BATCH<N>_SPEC.md 
  → 实施 (Claude Code FULL AUTO 或 Wiki 手动)
  → schema 校验 + lint 全绿 
  → audit log 完整 
  → 合并 main 
  → tag
```

### 0.2 与已有项目的关系

| 项目 | 关系 | 说明 |
|------|------|------|
| Helios 生态 (Helios/Helixa/Selene/Tide) | 平级独立 | Stratum 不依赖任何业务项目,业务项目不依赖 Stratum |
| 3O Stack | 完全独立 | 3O 输出可作为 substrate 入库,但 Stratum 不 import 3O |
| hevi | Stratum **上游** | hevi 通过 MCP / HTTP 接口消费 Stratum 内容,Stratum 不知道 hevi 存在 |
| Obsidian | Stratum **GUI 之一** | Obsidian 直接打开 Stratum 仓库作为 vault,不是必需依赖 |
| Claude Code | Stratum **客户端之一** | 通过文件系统直读或 MCP 访问 |
| Hermes Agent (Singapore VPS) | Stratum **远程客户端** | 通过 Tailscale 访问本地 MCP/HTTP 接口,只读为主 |

**关于仓库物理位置**: Stratum 位于 `~/projects/stratum/` (不在 `~/projects/_helios-platform/` 子目录下)。
理由: Stratum 服务多个上游消费者 (hevi / 未来视频项目 / 未来其他项目), 是跨项目基础设施,
不属于 Helios 平台的内部组件。挂在 `_helios-platform/` 下会暗示从属关系, 不准确。

### 0.3 命名约定

**顶层包名 / 仓库名**: `stratum`

**三层数据**:
- `substrate/` — 原始素材层 (PDF / EPUB / 网页快照 / 字幕 / 对话存档)
- `concepts/` — 概念图层 (人物 / 事件 / 定理 / 技术 / 地点)
- `notes/` — 笔记层 (你写的 ADR / 读书笔记 / 想法)

**协调层**: `_hub/` (前缀下划线表示元数据,不是知识本身)

**衍生命名**:
- MCP server 守护进程: `stratumd`
- MCP / HTTP 工具命名空间: `stratum.search` / `stratum.fetch_paragraphs` / ...
- 环境变量根: `STRATUM_ROOT`
- 当前 schema 大版本号文件: `STRATUM_VERSION`

### 0.3.1 关于 "Stratum" 这个名字

**Stratum** (拉丁语,"层") 是地质学中描述沉积岩分层结构的术语。选用此名因为它在四个维度上与本系统天然同构:

1. **结构同构**: substrate (沉积基底) / concepts (中间构造层) / notes (地表新沉积) 的三层架构,本身就是地层学结构,不是隐喻而是同形。
2. **气质对应**: 地层是**静的、深的、慢的、累积的**——这正是顶级知识库该有的气质。与 Helios 生态中 Helixa (循环)、Tide (涨落) 等动态系统形成对照。
3. **家族区分**: Helios / Selene 是天体 (天上), Stratum 是地层 (地下), 天地分明,明确传达 "这是底座基础设施,不是业务"。
4. **不污染主品牌**: Stratum 服务多个上游消费者 (hevi / 未来项目),不挂 `helios-` 前缀,避免与 Helios 主决策辅助产品概念混淆。

### 0.4 SPEC 变更政策

- v0.x 期间,小修直接改并在 commit message 注明
- 大修订 (schema 增减 / 接口改动) 出新版本号并 Wiki 批准
- 每个批次启动前 review 一次 SPEC,确认没漂移
- v1.0 = "8 维度顶级标准全部验收通过" (见 §1.2)

---

## §1 产品定位

### 1.1 目标

Stratum 是 **Wiki 个人级、本地优先、AI 友好、长期演化** 的知识库系统。

它管理 Wiki 所有形式的知识载体 (PDF / EPUB / 网页 / 字幕 / 笔记 / 对话存档),
为下游消费者 (Wiki 本人 / Claude Code / Hermes / hevi / 未来的视频系列项目) 提供:
- 精确寻址 (引用到段落级)
- 三种检索 (精确 / 语义 / 结构化)
- 概念图谱 (跨素材的人物 / 事件 / 概念汇聚)
- 演化能力 (schema 可迁移 / 索引可重建)
- 审计能力 (任何 AI 生成内容可追溯)

### 1.2 顶级标准的 8 个维度 (v1.0 验收标准)

| # | 维度 | 顶级标准长什么样 | 验证方式 |
|---|------|----------------|---------|
| D1 | 完备性 | PDF / EPUB / HTML / 字幕 / Markdown / 聊天 / 代码注释 7 种格式都能入库 | 7 种格式各试 1 个样本,入库率 100% |
| D2 | 可寻址性 | 任何一段知识可通过 ULID 精确引用 | 随机抽 20 个事实,5 秒内定位原文 |
| D3 | 可检索性 | 精确 (rg/tantivy) + 语义 (vector) + 结构化 (duckdb) 三种检索可用 | 同一查询三种方式各跑一次,对比召回 |
| D4 | 可演化性 | schema 改了不重建索引 / 加新领域不破坏旧的 / 换 embedding 可迁移 | 做 1 次 schema migration,记录耗时和错误率 |
| D5 | 可审计性 | 任何 AI 生成的内容可追溯到 source + 处理链 + 时间戳 | 抽 5 个 AI 生成 note,完整追溯 |
| D6 | 可移植性 | 整库可在 30 分钟内迁到另一台机器 | 实际做一次迁移演练 |
| D7 | 可消费性 | Obsidian / Claude Code / Hermes (MCP) / HTTP 四种接入方式都能跑 | 4 种接入各跑一个示例任务 |
| D8 | 抗腐烂性 | 1 年后回看仍可信 / 链接仍有效 / 不变垃圾堆 | 时间验证 + 预设抗腐烂机制 (见 §6) |

**v1.0 = D1-D7 全部验收通过 + D8 的所有机制就位 (时间维度不能加速验证,但机制必须就位)**

### 1.3 不在 Stratum 职责范围内

- 笔记编辑器 (用 Obsidian / VSCode / nvim)
- 长期云备份 (用户自行处理,推荐 rclone + 加密 S3)
- 多用户协作 (本知识库是单用户)
- 实时同步多设备 (Phase 1+ 可加 Syncthing)
- 主动爬取 (新素材入库由 Wiki 或 Hermes 显式触发)
- 知识本身的真伪判断 (lint 可标矛盾,但事实判断是 Wiki 责任)

### 1.4 优先级

Stratum 在 Wiki 的项目矩阵中:

- **高于**: hevi (hevi 的 v0.3 (第一个视频) 强依赖 Stratum 至少 v0.2 可用)
- **低于**: Helios Layer 4 现金流类项目
- **并行**: 与 Helixa 生产化、Selene 修复并行,不抢主线

---

## §2 三层 + Hub 架构

### 2.1 层定义

```
┌────────────────────────────────────────────────────────────────┐
│  consumer 层 (不在 Stratum 内,但本 SPEC 定义接口)             │
│  - Wiki (人,通过 Obsidian/VSCode 直接打开仓库)                 │
│  - Claude Code (本地, view + bash 直读)                        │
│  - Hermes (Singapore VPS, 通过 MCP/HTTP + Tailscale)           │
│  - hevi (未来,通过 MCP fetch substrate 作为 extra_context)     │
└────────────────────────────────────────────────────────────────┘
                            ↑ 通过接口访问
┌────────────────────────────────────────────────────────────────┐
│  _hub/ (协调层,知识库的"操作系统")                              │
│  - STRATUM_SPEC.md (本文件)                                         │
│  - schemas/ (所有 yaml schema)                                 │
│  - indexes/ (跨层索引: fulltext / vector / meta)               │
│  - pipelines/ (流水线脚本: ingest / lint / migrate / ...)      │
│  - audit/ (审计日志, jsonl)                                    │
│  - servers/ (MCP / HTTP 服务)                                  │
└────────────────────────────────────────────────────────────────┘
                            ↕ 读写
┌────────────────────────────────────────────────────────────────┐
│  Layer 1: substrate/ (原始素材, read-mostly)                   │
│  - books/ papers/ webpages/ transcripts/ chats/                │
│  - 每个素材有 ULID, 段落有 ULID 锚点                            │
│  - 原始文件 + 解析产物 + 元数据 三件套                          │
└────────────────────────────────────────────────────────────────┘
                            ↕ 被引用
┌────────────────────────────────────────────────────────────────┐
│  Layer 2: concepts/ (概念图谱)                                  │
│  - people/ events/ theorems/ techniques/ places/ domains/      │
│  - 每个 concept 有 ULID, 主体内容人维护, 反链区块流水线维护      │
│  - 是 substrate 和 notes 的桥梁                                │
└────────────────────────────────────────────────────────────────┘
                            ↕ 引用
┌────────────────────────────────────────────────────────────────┐
│  Layer 3: notes/ (你写的笔记)                                   │
│  - adr/ postmortem/ readings/ ideas/ daily/                    │
│  - 每个 note 有 ULID, frontmatter 强制 schema                  │
│  - 引用 substrate 段落 / concept 节点                          │
└────────────────────────────────────────────────────────────────┘
```

### 2.2 V1 (Vertical) 规则: 引用方向

引用只能向下,不能向上:

| 引用方 | 可引用 | 不可引用 |
|--------|--------|---------|
| consumer | _hub 接口 / 三层全部 | — |
| _hub pipelines | 三层全部 | — |
| notes | concepts / substrate | (其他 notes 通过 concept 中转,不直引) |
| concepts | substrate | notes (反链区块除外, 由流水线写) |
| substrate | (引用是只读元数据,不引用其他层) | — |

**为什么 notes 不直接相互引用**: 鼓励通过 concept 中转,让概念真正成为知识汇聚点。否则 notes 容易演化成密集私网,新人 (包括未来的你) 看不懂。

**例外**: notes 中的 ADR 内部可以引用其他 ADR (因为 ADR 之间天然有 supersede 关系)。这个例外在 §5.3 详述。

### 2.3 H1 (Horizontal) 规则: 同层关联

同层内的强关联通过 concept 中转,不直接 hardlink:

- ❌ note A 直接 wikilink 到 note B
- ✅ note A 引用 concept X,note B 也引用 concept X,通过 concept X 的反链区块互相发现

例外见 §2.2 末尾。

### 2.4 反向依赖 = 红线

- substrate 不能引用 concept / note
- concept 主体不能引用 note (反链区块由流水线维护,不算主体)
- 任何层不能引用 _hub (除了引用 schema 版本号这种元数据)

---

## §3 目录结构

### 3.1 顶层布局

```
stratum/
├── .git/
├── .gitattributes              # git-lfs 配置
├── .gitignore
├── README.md                   # 仓库说明 (面向人)
├── STRATUM_VERSION                  # 当前 KB schema 大版本号 (单行)
│
├── _hub/                       # 协调层
│   ├── STRATUM_SPEC.md              # 本文件
│   ├── schemas/                # 所有 yaml schema (JSON Schema 格式)
│   │   ├── _meta/
│   │   │   └── schema_versions.yaml
│   │   ├── substrate.book.schema.json
│   │   ├── substrate.paper.schema.json
│   │   ├── substrate.webpage.schema.json
│   │   ├── substrate.transcript.schema.json
│   │   ├── substrate.chat.schema.json
│   │   ├── concept.person.schema.json
│   │   ├── concept.event.schema.json
│   │   ├── concept.theorem.schema.json
│   │   ├── concept.technique.schema.json
│   │   ├── concept.place.schema.json
│   │   ├── concept.domain.schema.json
│   │   ├── note.adr.schema.json
│   │   ├── note.postmortem.schema.json
│   │   ├── note.reading.schema.json
│   │   ├── note.idea.schema.json
│   │   └── note.daily.schema.json
│   ├── indexes/                # 索引产物 (gitignore)
│   │   ├── fulltext.tantivy/
│   │   ├── vectors.qdrant/     # 或 pgvector / chroma, 待实证
│   │   └── meta.duckdb
│   ├── pipelines/              # 流水线脚本
│   │   ├── ingest/
│   │   ├── concept_management/
│   │   ├── indexing/
│   │   ├── lint/
│   │   ├── migration/
│   │   └── audit/
│   ├── servers/                # 对外接口
│   │   ├── mcp_server.py
│   │   └── http_server.py
│   ├── audit/                  # 审计日志 (gitignore 大文件, 保留摘要)
│   │   ├── changes.jsonl
│   │   └── reports/
│   │       └── weekly-lint-<date>.md
│   └── configs/
│       ├── embedding.yaml
│       ├── search.yaml
│       └── retention.yaml
│
├── substrate/                  # Layer 1
│   ├── books/
│   │   └── <domain>/
│   │       └── <slug>__<ULID-suffix>/
│   │           ├── meta.yaml
│   │           ├── original/
│   │           ├── parsed/
│   │           ├── embeddings/   # gitignore
│   │           └── ocr_log.yaml  # 如适用
│   ├── papers/
│   ├── webpages/
│   ├── transcripts/
│   └── chats/
│
├── concepts/                   # Layer 2
│   ├── people/
│   │   └── <slug>__<ULID-suffix>.md
│   ├── events/
│   ├── theorems/
│   ├── techniques/
│   ├── places/
│   └── domains/
│       └── _tree.yaml          # 领域树定义
│
└── notes/                      # Layer 3
    ├── adr/
    │   └── <NNN>-<slug>__<ULID-suffix>.md
    ├── postmortem/
    ├── readings/
    ├── ideas/
    └── daily/                  # 可选, 按年/月分目录
        └── 2026/05/
```

### 3.2 文件命名约定

**所有节点文件名格式**: `<slug>__<ULID-suffix>.md` 或 `<slug>__<ULID-suffix>/` (目录)

- `slug`: 人类可读, 同层同类型内唯一, 仅 `[a-z0-9-]`
- `ULID-suffix`: 完整 ULID 的后 8 位 (前 18 位是时间戳,后 8 位是随机),避免完整 ULID 太长污染文件名
- 完整 ULID 存在文件 frontmatter / yaml 的 `id` 字段
- `__` (双下划线) 作为 slug 和 ULID 的分隔符,人眼可识别

**为什么后缀只用 8 位**: 8 位随机 (base32 编码 ≈ 40 bit) 在单用户单库场景下碰撞概率 < 10^-12,远低于人为错误。前 18 位时间戳省略是因为创建时间已经在 frontmatter 里,文件名不重复。

**示例**:
- `concepts/people/xiang-yu__A1B2C3D4.md`
- `notes/adr/038-fusion-page-sub-pages__X9Y8Z7W6.md`
- `substrate/books/history/shiji-zhonghua-2014__K2J3H4G5/`

### 3.3 关于 `_hub/indexes/`

- 不入 git (索引可重建)
- 由 `_hub/pipelines/indexing/` 维护
- 路径在 `.gitignore`
- 但 schema 必须 commit (改 schema 时需要审计)

### 3.4 关于 `substrate/*/embeddings/`

- 不入 git (大,可重建)
- 由 `_hub/pipelines/indexing/reindex_vectors.py` 写入
- 格式: parquet 文件 (columns: paragraph_id, text, vector, page, ...)
- 嵌入模型变更时全库重建

### 3.5 关于 `substrate/*/original/`

- **入 git, 走 Git LFS**
- 这是知识库的不可变底座,必须有版本控制
- 大文件 (>10MB) 通过 `.gitattributes` 走 LFS
- LFS 存储后端: 初期本地, Phase 2+ 评估 self-hosted gitea 或加密 S3

---

## §4 ID 系统

### 4.1 ULID

所有节点 (substrate / concept / note) 创建时分配 **ULID** (Universally Unique Lexicographically Sortable Identifier)。

**ULID 格式**: 26 字符, Crockford's base32
- 前 10 字符: 毫秒级时间戳 (2050 年前不溢出)
- 后 16 字符: 随机
- 完整字符集: `0-9A-HJKMNP-TV-Z` (不含 I/L/O/U,避免视觉混淆)

**示例**: `01HXYZW7G5K8M2N3P4Q5R6S7T8`

**生成**: `python-ulid` 库 (`pip install python-ulid`)

### 4.2 段落级 ID

substrate 解析后, 每个段落注入一个段落级 ID:

**段落 ID 格式**: `<substrate-ULID>:<paragraph-ULID-suffix>`

- substrate-ULID = 该 substrate 的完整 ULID
- paragraph-ULID-suffix = 段落创建时分配的 6 字符随机 (单 substrate 内唯一)

**示例**: `01HXYZW7G5K8M2N3P4Q5R6S7T8:A1B2C3`

**为什么段落 ID 是 substrate 之内的,不是全局的**:
- 段落数量级 (每库 10^5-10^6),全局 ULID 浪费
- 段落引用永远伴随 substrate 出现,组合 key 更自然
- 跨 substrate 比较段落无意义

### 4.3 ID 在文件中的呈现

**frontmatter 中的 id 字段**:
```yaml
---
id: "01HXYZW7G5K8M2N3P4Q5R6S7T8"
slug: "xiang-yu"
...
---
```

**文件名格式** (§3.2 已定义): `<slug>__<ULID-suffix>.md`
- 例如: `xiang-yu__A1B2C3D4.md`
- 文件名同时承担"人类可读标识"和"ID 引用键"两个角色

**markdown 中引用其他节点 (Obsidian 原生兼容语法)**:
```markdown
昨天重读了 [[xiang-yu__A1B2C3D4|项羽]],对照原文
[[shiji-007__S1T2U3V4#para-A1B2C3|《史记·项羽本纪》开篇]]。
```

**wikilink 语法**: `[[<slug>__<ULID-suffix>[#para-<paragraph-suffix>]|<display>]]`

- `<slug>__<ULID-suffix>` = 目标文件名 (不含 `.md`)
- `#para-<paragraph-suffix>` = 段落锚点 (仅 substrate 的解析文件)
- `<display>` = 可选显示文本

**为什么用这个语法 (实证项 #4 决策)**:
- 完全 Obsidian 原生兼容,graph view / hover preview / 自动补全全部工作
- 不需要自写 Obsidian 插件或 preprocessor
- 文件改名 (改 slug 部分) 时 Obsidian 自动更新所有 wikilink
- ID 健壮性靠 ULID 后缀 + frontmatter 保证: 即使改了 slug, ULID 后缀不变, 引用仍然语义稳定

**关于"为什么不用纯 ULID 引用"**:
最初 SPEC v0.1 设计为 `[[concept/01HXYZ.../xiang-yu|项羽]]`,但实证分析显示 Obsidian
无现成插件支持此扩展语法,自写插件工作量 > 5 天且有长期维护风险 (Obsidian API
升级风险)。改用 `<slug>__<ULID-suffix>` 文件名规则,Obsidian 把它整体当文件名识别,
扩展能力完全保留 (ULID 后缀 8 字符随机依然防碰撞,frontmatter 仍存完整 ULID 用于
MCP/HTTP 接口和流水线)。

**段落锚点的实现**:

substrate parsed 文件中段落锚点用 **Obsidian heading 形式**, 而非 HTML `<a id>`:

```markdown
## para-A1B2C3
项籍者,下相人也,字羽。

## para-A1B2C4
其季父项梁,梁父即楚将项燕,为秦将王翦所戮者也。
```

理由: Obsidian 原生支持 `[[file#heading]]` 跳转, 与 wikilink 系统无缝集成。
`para-` 前缀避免与正文章节 heading (如 `## 第一章`) 冲突,且方便 lint 识别。

替代方案 (block reference): `^A1B2C3` 这种 Obsidian 原生 block reference 语法也可用,
但 block reference 不能跨段落范围引用,heading 更灵活。

### 4.4 ID 不可变, slug 可变

- ULID 一旦分配,永久不变,即使节点被删除也不复用
- slug 可随时改名,引用通过 Obsidian 原生改名机制自动跟随

**改 slug 流程**:
1. 在 Obsidian 中重命名文件 (改 slug 部分, **保留 `__<ULID-suffix>` 不变**)
2. Obsidian 自动更新所有 wikilink (原生能力)
3. 跑 `_hub/pipelines/audit/log_changes.py` 记录变更并校验
4. 反链区块和索引由流水线自动更新

**重要**: ULID 后缀 (`__A1B2C3D4`) 在改名时**必须保留**, 这是引用稳定性的根。
lint 规则 `slug_rename_check.py` (批 3 实现) 检查所有文件名都符合
`<slug>__<8-char-ULID-suffix>.md` 模式, 不符合的报错。

### 4.5 ID 碰撞处理

- ULID 碰撞概率极低 (1.21e+24 唯一值),实际不会发生
- ULID 后缀 (8 字符) 在单库内冲突概率 < 10^-12 (40-bit 空间),实际不会发生
- 段落 suffix 在单 substrate 内 6 字符随机 ≈ 10 亿空间,单文件 < 10^5 段落,碰撞 < 10^-5
- 流水线在生成时检查碰撞,撞到立即重生成
- lint 规则 `id_collision_check.py` 每周扫一次全库,发现碰撞报警

### 4.6 跨层引用的语义保持

由于文件名只含 `<slug>__<ULID-suffix>`, 不再显式标注 layer (substrate/concept/note),
跨层语义靠以下机制保持:

1. **目录结构**: 文件物理位置决定 layer (`concepts/people/xiang-yu__...` 一望可知是 concept)
2. **Obsidian 链接预览**: hover 时显示目标文件路径, 间接告知 layer
3. **流水线索引**: `_hub/indexes/meta.duckdb` 维护 `(filename, layer, type, ULID)` 表,
   MCP/HTTP 接口查询时返回完整 layer 信息
4. **可选 slug 前缀规范** (推荐, 不强制): substrate 的 slug 可加 `src-` 前缀
   (例: `src-shiji-007`), concept 加 `c-` 前缀 (例: `c-xiang-yu`), note 不加。
   这是软约定, lint 不强制, 但 Wiki 自己写 wikilink 时一眼能区分 layer。
   **本 SPEC v0.1.2 不强制此前缀, 留 Wiki 实际使用后决定**。

---

## §5 三层数据 schema (概要)

完整 schema 在 `_hub/schemas/*.schema.json`。本节给出主要字段,完整定义见 schema 文件。

### 5.1 substrate 共通字段

```yaml
id: "01HXYZ..."                  # ULID, required
slug: "shiji-zhonghua-2014"      # required, 同层同类型唯一
title: "史记 (中华书局点校本 2014 版)"  # required
type: "book"                     # book | paper | webpage | transcript | chat
created_at: "2026-05-16T10:00:00+08:00"   # 入库时间
ingested_by: "wiki" | "hermes" | "claude-code" | "pipeline"
schema_version: 1

# type-specific 字段在各 schema 中定义
```

### 5.2 substrate type 特化

**book**:
```yaml
type: book
authors: ["司马迁"]
editors: ["顾颉刚 (点校)"]
edition_key: "isbn:978-7-101-10381-7|publisher:中华书局|year:2014"
language: "zh-Hant"   # 或 zh-Hans / en / mixed
domains: ["history.china.qin-han"]
original_format: "pdf"   # 原始文件格式
total_pages: 3768
parsing:
  parser: "pymupdf4llm"   # 实证后填
  parser_version: "0.0.17"
  parsed_at: "2026-05-16T..."
  paragraph_count: 12453
  ocr_used: false
copyright_status: "public-domain"   # public-domain | copyrighted | unknown
```

**paper**:
```yaml
type: paper
authors: [...]
doi: "10.1234/..."
arxiv_id: "2406.12345"
venue: "NeurIPS 2024"
year: 2024
domains: ["cs.ml", "math.stat"]
```

**webpage**:
```yaml
type: webpage
url: "https://..."
archived_at: "2026-05-16T..."
archive_method: "single-file" | "wayback" | "self-host"
site_name: "..."         # 网站/出版方名称, required
authors: ["..."]         # 文章作者, optional (个人博客填, 企业稿可省)
domains: [...]
```

**transcript**:
```yaml
type: transcript
source_platform: "youtube" | "podcast"
source_url: "..."
source_id: "abc123xyz"
speakers: ["Andrej Karpathy", "Lex Fridman"]   # 自由字符串数组
duration_seconds: 3600
language: "zh-Hans"
domains: [...]
```

**关于 speakers 与 concept person 的关系**: speakers 是自由字符串,不强制是 concept 引用。
如果某 speaker 是知识库已有的 concept person (如 "Andrej Karpathy" 已有对应 concept),
在 note 引用此 transcript 时可通过 alias 机制建立关联,但 substrate 层不引用 concept。
理由: substrate 应保持对 concept 层的解耦,以便 substrate 可独立入库 (即使 concept
节点尚未创建)。

**event.participants 不同**: 必须是 concept 引用对象数组 (`{id, slug, role}`),因为事件的
参与者本质上就是历史人物 concept,直接 reference 更准确,且 event 通常在 concept 之后创建。

**chat**:
```yaml
type: chat
participants: ["wiki", "claude"]
platform: "claude.ai" | "telegram" | "discord"
exported_at: "2026-05-16T..."
domains: [...]
significance: "high" | "medium" | "low"
# 注: chat 入库门槛要严, 不是所有对话都进库
```

### 5.3 concept 共通字段

```yaml
id: "01HXYZ..."
slug: "xiang-yu"
title: "项羽"
type: "person"   # person | event | theorem | technique | place | domain
aliases: ["项籍", "西楚霸王"]
domains: ["history.china.qin-han"]
schema_version: 1
created_at: "..."
last_reviewed_at: "..."   # 由 lint 检查是否陈旧

related_concepts:
  - id: "01HXYZ..."
    slug: "liu-bang"
    relation: "rival"        # 自由字符串, 但 lint 推荐用受控词表
```

**type-specific 示例**:

**person**:
```yaml
type: person
born: -232    # ISO 8601 年, 公元前用负数
died: -202
nationality: "楚国"
roles: ["军事家", "诸侯"]
```

**event**:
```yaml
type: event
date_start: -206-10
date_end: -206-10
location: "..."
participants:   # 引用 concept person
  - id: "01HXYZ..."
    role: "主角"
```

**theorem**:
```yaml
type: theorem
field: "math.probability"
formal_statement: "..."     # 可含 LaTeX
prerequisites:               # 引用其他 concept
  - id: "01HXYZ..."
```

### 5.4 note 共通字段

```yaml
id: "01HXYZ..."
slug: "on-xiang-yu-tragedy"
title: "项羽悲剧的反领导力分析"
type: "reading"   # adr | postmortem | reading | idea | daily
created_at: "..."
last_modified_at: "..."
schema_version: 1
status: "draft" | "active" | "archived" | "superseded"

# 引用 (lint 校验目标存在); 所有 note 类型可选, 包括 daily
references:
  substrate:
    - id: "01HXYZ..."
      paragraph_ids: ["A1B2C3", "A1B2C4"]
  concepts:
    - id: "01HXYZ..."
```

**关于 references 适用范围**: `references` 是**所有 note 类型的可选字段**。即使是 note.daily
(日记) 也可以引用 substrate / concept,虽然实际很少这么做。lint 不强制 note 必须有 references。

**note.adr 特化**:
```yaml
type: adr
adr_number: 38   # 顺序号, 配合 helios 项目 ADR 编号
project: "helios"   # 关联到哪个项目
supersedes:   # 引用其他 ADR
  - id: "01HXYZ..."
    note: "原方案过度规范,本 ADR 撤销"
superseded_by: null
decision_status: "active" | "superseded" | "rejected"
```

**note.adr 例外规则**: ADR 内部可以直接 wikilink 到其他 ADR (不强制走 concept 中转),因为 ADR 是有序决策链,supersede / depends-on 是结构性关系。lint 规则 `adr_chain_check.py` 验证 ADR 引用链无环。

### 5.5 schema 版本管理

**`_hub/schemas/_meta/schema_versions.yaml`**:
```yaml
substrate.book: 1
substrate.paper: 1
substrate.webpage: 1
substrate.transcript: 1
substrate.chat: 1
concept.person: 1
concept.event: 1
concept.theorem: 1
concept.technique: 1
concept.place: 1
concept.domain: 1
note.adr: 1
note.postmortem: 1
note.reading: 1
note.idea: 1
note.daily: 1
```

**schema 升级流程**:
1. 修改 `*.schema.json`
2. 写 `_hub/pipelines/migration/migrate_<schema-name>_v<N>_to_v<N+1>.py`
3. 跑 dry-run: `pipeline ... --dry-run`
4. Review dry-run 报告
5. 实跑 + 全库 schema 校验 0 错误
6. 更新 `schema_versions.yaml`
7. commit

---

## §6 抗腐烂机制

D8 维度的具体落地。

### 6.1 强制 lint 规则 (每周执行)

| Lint | 触发条件 | 后果 |
|------|---------|------|
| `orphan_check` | 节点 0 入边 (没人引用) | 报 WARNING, 不阻塞 |
| `stub_concept_check` | concept 正文 < 200 字 | 报 STUB, 累积清单待补 |
| `broken_link_check` | wikilink 指向不存在的 ULID | 报 ERROR, 阻塞 commit |
| `id_collision_check` | ULID 或段落 ID 撞了 | 报 CRITICAL, 立即处理 |
| `schema_check` | yaml frontmatter 不符合 schema | 报 ERROR, 阻塞 commit |
| `adr_chain_check` | ADR supersede 链有环 | 报 ERROR, 阻塞 commit |
| `stale_concept_check` | concept `last_reviewed_at` > 1 年 | 报 STALE, 入待 review 清单 |
| `duplicate_substrate_check` | 同 `edition_key` 重复入库 | 报 ERROR, 阻塞入库 |

### 6.2 强制人 review 点

AI 不能自动:
- 修改 concept 主体内容 (反链区块除外)
- 删除任何节点 (只能标 `status: archived`)
- 改 ULID
- 修改 ADR 主体

AI 可以自动:
- 创建 substrate (走 ingest 流水线)
- 起草 concept (但需 Wiki 在 Obsidian 中确认才能去掉 `draft` 标记)
- 维护反链区块
- 写 audit log
- 跑 lint 和报告

### 6.3 review cadence

| 频率 | 任务 |
|------|------|
| 每次新入库 | schema check + lint 必须全绿才能 commit |
| 每周 | lint 全套跑一遍,报告到 `_hub/audit/reports/weekly-lint-<date>.md`, Wiki 看 5 分钟 |
| 每月 | concept stub 清单 review,补至少 5 个 stub |
| 每季度 | stale concept 清单 review,确认或更新 |
| 每年 | STRATUM_SPEC 整体 review,版本号 +1 |

### 6.4 AI 生成内容的标记

所有 AI 起草、未经 Wiki review 的内容必须带标记:

**concept 主体**:
```markdown
---
id: ...
draft: true   # 必须显式去掉才算 review 过
ai_drafted_by: "claude-opus-4-7"
ai_drafted_at: "2026-05-16T..."
---
```

**substrate 中 AI 添加的内容** (例如 OCR 后的修正):
```markdown
> [!ai-modified] OCR 修正
> 原 OCR: "项籍者,下相人世"
> 修正: "项籍者,下相人也"
> 修正者: claude-opus-4-7, 2026-05-16
```

---

## §7 检索系统

### 7.1 三种检索

| 模式 | 引擎 | 用途 | 速度目标 |
|------|------|------|---------|
| exact | tantivy (rust) + ripgrep | 找具体字符串 / 引用 | < 100ms |
| semantic | 向量库 (实证后定) | 语义相似 / 想法找回 | < 500ms |
| meta | duckdb | 按 frontmatter 过滤 | < 200ms |

### 7.2 hybrid 检索 (默认)

```
query
  ↓
exact (top-20) + semantic (top-20)
  ↓
reciprocal rank fusion
  ↓
cross-encoder rerank (top-10)
  ↓
return
```

实证项: cross-encoder 用哪个 (bge-reranker-v2-m3 / cohere-rerank / 自建)。

### 7.3 检索范围控制

所有检索支持 scope 过滤:
- 按 layer (substrate / concept / note)
- 按 type (book / paper / person / adr / ...)
- 按 domain (history / math / ...)
- 按 时间范围
- 按 status (active / draft / archived)
- 任意 frontmatter 字段

### 7.4 检索接口暴露

通过 `_hub/servers/mcp_server.py` 和 `http_server.py` 对外:

**MCP tools**:
- `stratum.search(query, mode, scope, top_k)`
- `stratum.get_by_id(id)`
- `stratum.get_concept_neighborhood(concept_id, depth)`
- `stratum.list_substrate(filter)`
- `stratum.fetch_paragraphs(substrate_id, paragraph_ids)`
- `stratum.fetch_paragraphs_by_span(substrate_id, start_id, end_id)`

**HTTP routes** (镜像 MCP):
- `GET /search?q=...&mode=...`
- `GET /node/{id}`
- `GET /concept/{id}/neighborhood?depth=2`
- ...

---

## §8 流水线规范

### 8.1 通用约定

所有 `_hub/pipelines/**/*.py` 脚本:

1. **入口**: CLI, `typer` 框架, 可 `--dry-run`
2. **输入范围**: `--scope all|<layer>|<path>`
3. **输出**: 写 `_hub/audit/changes.jsonl` (每个变更一行)
4. **幂等**: 同输入跑两次结果一致
5. **可中断**: 支持 ctrl-c 中断,下次 `--resume`
6. **报告**: 输出人可读 markdown 报告 (lint / migration 必须)
7. **错误处理**: 不静默吞错误, 累积报告末尾

### 8.2 ingest 流水线

```
_hub/pipelines/ingest/
├── pdf_to_substrate.py       # PDF → parsed/ + 段落 ID + 入库
├── epub_to_substrate.py
├── webpage_archive.py         # URL → single-file HTML + meta
├── transcript_to_substrate.py # YT/播客字幕 → substrate
├── chat_export_to_substrate.py # Claude / Telegram 对话 → substrate
└── markdown_to_note.py         # 已有 markdown → note
```

每个 ingest 脚本流程:
1. 验证输入 (格式 / 大小)
2. 抽取元数据 (尽量自动, 缺失项交互式问 Wiki)
3. 生成 ULID
4. 写 meta.yaml + 复制原始文件
5. 调用解析器 (parser) 生成 parsed/
6. 注入段落 ID
7. 触发后续流水线 (concept_extraction, indexing) 异步
8. 写 audit log

### 8.3 concept_management 流水线

```
_hub/pipelines/concept_management/
├── extract_entities.py      # 新 substrate 入库后, 抽取潜在 concept
├── concept_backref.py        # 维护 concept "出现于" 反链区块
├── alias_resolver.py         # 别名归一 (项籍 = 项羽)
└── concept_graph_build.py    # 构建 concept-concept 图, 输出可视化
```

**extract_entities 输出**: `_hub/audit/reports/extraction-<date>.md`, 列出新发现的潜在实体, Wiki 决定哪些升级为 concept。

### 8.4 indexing 流水线

```
_hub/pipelines/indexing/
├── reindex_fulltext.py    # tantivy 重建
├── reindex_vectors.py     # 向量库重建 (增量或全量)
└── reindex_meta.py        # duckdb 重建
```

**增量索引触发**: substrate / note 写入后,流水线监听文件变更 (Phase 1: cron 每小时, Phase 2+: inotify)。

### 8.5 lint 流水线

```
_hub/pipelines/lint/
├── orphan_check.py
├── stub_concept_check.py
├── broken_link_check.py
├── id_collision_check.py
├── schema_check.py
├── adr_chain_check.py
├── stale_concept_check.py
├── duplicate_substrate_check.py
└── run_all.py             # 跑全套 + 汇总报告
```

每周 cron 跑 `run_all.py`,输出报告。

### 8.6 migration 流水线

```
_hub/pipelines/migration/
├── _template.py             # migration 脚本模板
└── migrate_<from>_<to>.py
```

migration 强制 dry-run + 确认机制。

### 8.7 audit

```
_hub/pipelines/audit/
├── log_changes.py            # 写 changes.jsonl
└── generate_report.py        # 周报 / 月报
```

`changes.jsonl` 字段:
```json
{"ts":"2026-05-16T...","actor":"wiki|claude-code|hermes|pipeline:<name>","action":"create|update|delete|index","layer":"substrate|concept|note","id":"01HXYZ...","summary":"...","diff_path":"_hub/audit/diffs/<hash>.diff"}
```

---

## §9 对外接口

### 9.1 接口 A: 文件系统

- 入口: 直接打开 `stratum/` 任意路径
- 用户: Wiki / Obsidian / Claude Code / VSCode / nvim
- 协议: markdown + yaml frontmatter + Obsidian 原生 wikilink (语法见 §4.3)
- 写权限: Wiki 直接编辑文件; Claude Code 走 ingest/edit 流水线; Hermes 远程**只读**

**Obsidian vault 配置**:
- vault 根 = `stratum/` 仓库根
- 排除 `_hub/indexes/` 和 `substrate/*/embeddings/` (太大)
- 启用 graph view, dataview, 自定义 wikilink 插件

### 9.2 接口 B: MCP Server

- 入口: `_hub/servers/mcp_server.py`, 本地启动
- 用户: Hermes / hevi / 任何 LLM agent
- 协议: MCP (Model Context Protocol)
- 端口: `localhost:7777` (默认, 可配)
- 工具集: 见 §7.4

### 9.3 接口 C: HTTP API

- 入口: `_hub/servers/http_server.py` (FastAPI)
- 用户: Hermes (via Tailscale) / 未来 web UI
- 协议: REST + SSE (流式响应)
- 端口: `localhost:7780` (默认)
- 路由: 见 §7.4

**远程访问 (Hermes)**: 通过 Tailscale, Hermes 访问 `http://wiki-win11-wsl2.tail-xxxx.ts.net:7780`。只读 endpoint。写操作不通过 HTTP 暴露。

### 9.4 安全

- 三个接口默认只在 localhost (或 Tailscale internal) 暴露,不对公网
- HTTP 接口可选 token auth (Phase 2+)
- 不存敏感凭据 (API keys, passwords) 进 substrate / note (有规则在 ingest 时扫描)

---

## §10 Acceptance Criteria

### 10.1 单 element 验收 (每个 schema / pipeline / server)

| 项 | 要求 |
|----|------|
| Schema | JSON Schema 校验通过,有 1 个 valid example + 1 个 invalid example |
| Pipeline | 单元测试 ≥ 3, 集成测试 ≥ 1 (跑一遍真实数据), dry-run 输出可读 |
| Server | MCP 协议合规, HTTP routes 文档化 |
| Lint pipeline | 必须有"测试用例": 故意构造 1 个违规节点, 验证能被抓到 |
| Migration | 必有 dry-run + rollback 测试 |
| 错误处理 | 不裸 raise, 自定义异常带 retry-able flag |
| 日志 | 关键操作 emit 到 audit log |
| Docstring | 每个 public 函数有 docstring + example |

### 10.2 批次验收

每批完成时:
- 批内所有 element 全部 §10.1 验收通过
- 端到端 demo 跑通 (定义在批 SPEC 中)
- STRATUM_SPEC 中本批涉及条款无漂移
- audit log 完整
- 至少 1 次 review (Wiki) + sign-off
- 打 tag `v0.<batch>.x`

### 10.3 v1.0 验收

8 维度 (§1.2) 全部达标:
- D1-D7: 实证通过 (有可重复脚本)
- D8: 抗腐烂机制全部就位 (§6 全部实现并跑过 ≥ 4 周)

### 10.4 Bug 回填规则

(沿用 hevi SPEC §10.3) 任何 bug 修复必须同时:
1. 增加复现 test
2. test 在修复前必须 fail, 修复后必须 pass

---

## §11 Release Policy

### 11.1 分支模型

```
main          ← 永远 stable
  ↑
  PR (即使 Wiki 自己也走 PR)
  ↑
feat/<batch>-<short>   ← 单批或单 element
```

### 11.2 版本号

```
v0.0.x   批 1 (立宪) 完成
v0.1.x   批 2 (实证) 完成 + SPEC 修订
v0.2.x   批 3 (流水线 MVP) 完成
v0.3.x   批 4 (接口层) 完成
v0.4.x   批 5 (验收) 完成
v1.0.0   8 维度顶级标准全部验收通过 + 至少 90 天稳定运行 + 至少 50 个真实节点入库
```

### 11.3 STRATUM_VERSION 文件

仓库根目录的 `STRATUM_VERSION` 单行文件,记录当前 schema 大版本号 (整数)。每次大 migration +1。下游消费者可读此文件判断兼容性。

---

## §12 开发环境

### 12.1 主开发机

Win11 主机 + WSL2 (Ubuntu 22.04+), 与 hevi 同环境。

### 12.2 依赖

**包管理**: uv (与 hevi / Helios 一致)

**核心依赖** (草案, 实证后定稿):
```toml
[project]
name = "stratum"
version = "0.0.1"
requires-python = ">=3.12"

dependencies = [
    "pydantic>=2.5",
    "python-ulid>=2.0",
    "pyyaml>=6.0",
    "jsonschema>=4.0",
    "typer>=0.12",
    "structlog>=24.0",
    "tenacity>=8.0",
    "rich>=13.0",            # CLI 报告
    "fastapi>=0.110",
    "uvicorn>=0.30",
    "mcp>=0.9",              # Anthropic MCP SDK (实证待定)
    "duckdb>=1.0",
    "pyarrow>=16.0",         # parquet 读写
    "ripgrep-py>=0.1",       # 或 subprocess
]

[project.optional-dependencies]
ingest-pdf = ["pymupdf4llm", "unstructured", "marker-pdf"]  # 实证选一
ingest-epub = ["ebooklib", "beautifulsoup4"]
ingest-webpage = ["singlefile-cli", "trafilatura"]
ingest-transcript = ["yt-dlp"]
indexing-fulltext = ["tantivy"]
indexing-vector = ["qdrant-client"]   # 或 pgvector / chroma, 实证
embedding = ["sentence-transformers"]  # 或调外部 API
dev = ["pytest>=8.0", "pytest-asyncio", "ruff", "mypy"]
```

### 12.3 系统依赖

- Python 3.12+
- git ≥ 2.40 + git-lfs
- ripgrep
- (实证后追加: PDF 解析依赖 / 字体 / CUDA)

### 12.4 .env 模板

```bash
# .env.example
STRATUM_ROOT=/home/soffy/projects/stratum
ANTHROPIC_API_KEY=
ANTHROPIC_BASE_URL=
OPENAI_API_KEY=               # 备用 embedding
VOYAGE_API_KEY=               # 备用 embedding
TAILSCALE_HOSTNAME=

MCP_SERVER_PORT=7777
HTTP_SERVER_PORT=7780
```

---

## §13 批次路线图

| 批 | 目标 | 预估时长 | 关键产出 | tag |
|---|------|---------|---------|-----|
| 1 | 立宪 | 1-2 天 | STRATUM_SPEC + 全部 schema + 空目录骨架 | v0.0.x |
| 2 | 实证 | 3-5 天 | 6 个实证项报告 + SPEC 修订 | v0.1.x |
| 3 | 流水线 MVP | 1-2 周 | ingest (PDF/EPUB/MD) + indexing + lint + audit | v0.2.x |
| 4 | 接口层 | 3-5 天 | MCP + HTTP server + Obsidian 适配 | v0.3.x |
| 5 | 验收 | 2-3 天 | 8 维度全验 + 修补 | v0.4.x |

总计 ~3-5 周到 v0.4.x (顶级标准可用)。
v1.0 = v0.4.x + 90 天稳定运行 + 50+ 节点。

### 13.1 批 1 详细 (本 SPEC 完成后立刻进入)

**目标**: 把"宪法"立起来,任何后续工作都可追溯到本 SPEC。

**清单**:
- ☑ STRATUM_SPEC.md (本文件) ← 完成
- ☐ `_hub/schemas/_meta/schema_versions.yaml`
- ☐ `_hub/schemas/*.schema.json` (16 个 schema 文件, 见 §3.1)
- ☐ 每个 schema 配 `examples/<name>.valid.yaml` + `<name>.invalid.yaml`
- ☐ 顶层目录结构创建 (空)
- ☐ `README.md` (面向人, 含 quickstart)
- ☐ `.gitignore` + `.gitattributes` (LFS 配置)
- ☐ `STRATUM_VERSION` 单行文件 (内容: `0`)
- ☐ `pyproject.toml` 骨架 (依赖标注 [PENDING_VALIDATION] 占位)
- ☐ `_hub/configs/embedding.yaml.example` 等配置模板
- ☐ git init + 首次 commit + tag `v0.0.1`

**批 1 验收**:
- 所有 schema 通过 JSON Schema validator
- 每个 schema 的 valid example 通过校验, invalid example 被拒
- 目录结构与 §3.1 完全一致
- README.md 含完整 quickstart (但不要求脚本可跑, 批 3 才有真东西)

### 13.2 批 2 详细

**6 个实证项**:

1. **PDF 解析准确率对比** (pymupdf4llm / unstructured / marker / docling)
   - 测试样本: 5 本 PDF (数学公式 / 历史繁体 / 论文双栏 / 扫描件 / EPUB 转 PDF)
   - 评估维度: 段落完整性 / 公式保留 / 表格识别 / OCR 准确率
   - 输出: `_hub/audit/reports/experiment-pdf-parsing.md`

2. **向量数据库对比** (pgvector / qdrant / chroma / lancedb)
   - 测试规模: 10 万段落
   - 评估维度: 入库速度 / 查询延迟 / 混合检索能力 / 本地资源占用
   - 输出: `_hub/audit/reports/experiment-vector-db.md`

3. **embedding model 对比** (bge-m3 / voyage-3 / e5-mistral / qwen3-embedding)
   - 测试样本: 50 个查询样本 (中文 30 / 英文 15 / 数学公式 5)
   - 评估维度: top-10 召回 / 排序质量
   - 输出: `_hub/audit/reports/experiment-embedding.md`

4. **Obsidian UID 插件调研** — ⚠️ **已解除, 跳过实证**
   - v0.1.2 通过架构调整规避此风险 (改用 Obsidian 原生 wikilink, 见 §4.3 / §14.3)
   - 不需要实证

5. **MCP server 框架对比** (anthropic 官方 SDK / fastmcp)
   - 评估: 易用性 / 性能 / 文档
   - 输出: `_hub/audit/reports/experiment-mcp.md`

6. **段落锚点 (heading 形式) 在 Obsidian 内的实际表现** — 简化, 不再是核心风险
   - v0.1.2 已确定段落锚点用 `## para-<suffix>` heading 形式
   - 实证内容: 跑通 `[[file#para-A1B2C3]]` 跳转 + heading 在 Obsidian outline 中是否过度污染
   - 工作量: 30 分钟手动验证, 非阻塞
   - 输出: `_hub/audit/reports/experiment-paragraph-heading.md`
**批 2 完成时**: 根据实证修订 STRATUM_SPEC 至 v0.2, 锁定技术栈。

### 13.3 批 3 详细

**目标**: 把"流水线 MVP" 跑起来,能完成第一次真实入库。

**清单** (略, 见 §8 流水线规范, 选其中 MVP 子集):
- ingest: pdf / epub / markdown 三种
- concept_management: extract_entities + concept_backref
- indexing: 全套三个
- lint: 全套 8 个
- audit: log_changes + 周报

**批 3 验收**:
- 真实入库 1 本书 (Wiki 选一本) + 1 个 ADR (从 helios-wiki 迁过来一个)
- 触发全套流水线, 全绿
- 周报生成
- audit log 完整

### 13.4 批 4 详细

**目标**: 暴露三个接口,下游能消费。

**清单**:
- MCP server (本地)
- HTTP server (本地 + Tailscale)
- Obsidian vault 配置 + 自定义 wikilink 插件 (基于批 2 实证结果)
- 三个示例脚本:
  - Claude Code 通过文件系统访问的示例
  - Hermes 通过 MCP 远程查询的示例
  - 一个 fake "hevi" 脚本通过 HTTP 拉素材的示例

### 13.5 批 5 详细

**目标**: 跑完 §1.2 八维度验收清单, 修补不达标项。

---

## §14 风险与缓解

### 14.1 实证项失败风险

某个实证 (例如 PDF 解析没有一家足够好) 可能阻塞批 3。

**缓解**: 实证报告标注 fallback (例如 PDF 解析全失败时, 退到"扫描+OCR+人工校对"的低自动化路径)。

### 14.2 schema 设计错误风险

v0.x 阶段 schema 不可能一次设计对, 后续 migration 成本高。

**缓解**:
- v0.x 期间, schema 频繁 migration 是预期的, migration 流水线优先建设
- 每个批次结束 review schema
- v1.0 之前不对外保证 schema 兼容性

### 14.3 Obsidian wikilink 扩展兼容性风险 (v0.1.2: 已解除)

**状态**: 已解除 (v0.1.2 通过架构调整规避, 无需实证)

**原风险描述**: SPEC v0.1 / v0.1.1 设计的扩展 wikilink 语法
`[[concept/01HXYZ.../xiang-yu|项羽]]` Obsidian 默认不识别。

**解除方式**: v0.1.2 将 wikilink 语法调整为 Obsidian 原生兼容的
`[[<slug>__<ULID-suffix>|项羽]]` 形式 (详见 §4.3)。文件名同时承担"人类可读"和
"ID 引用键"两个角色, 既保留 ULID 健壮性又完全兼容 Obsidian 原生能力。

**新方案的代价**:
- ULID 不直接出现在 wikilink 文本里 (要看完整 ULID 得打开文件看 frontmatter)
- 跨层语义弱化, 靠目录结构 + 流水线索引补强 (§4.6)

这两个代价被 chief advisor 判定为可接受, 因为:
1. 人不需要手敲 26 字符 ULID, 这反而是好事
2. 跨层信息靠目录结构已经足够, 显式 layer 前缀是过度设计

### 14.4 段落 ID 在 PDF 重新解析后变化的风险

如果 PDF 重新用新版解析器解析, 段落数可能不同, 旧的引用断链。

**缓解**:
- 同 substrate 重解析必须保留旧的段落 ID 映射 (即"补充 ID"机制)
- migration 流水线提供 "重解析并保留 ID" 模式
- 极端: 旧解析产物归档到 `parsed_v<N>/`, 新解析进 `parsed/`, 引用支持版本前缀

### 14.5 与 hevi 时间线冲突

hevi v0.3 (第一个视频) 强依赖 Stratum 至少 v0.2 (流水线 MVP)。

**缓解**:
- Stratum 批 3 完成是 hevi Phase 2 启动的前提
- 时间表 (§13) 显示 Stratum 3-5 周到 v0.4, hevi 计划 Phase 0-3 共 10-13 周, 串行无冲突
- 如果 Stratum 进度超期, hevi 启动延后

### 14.6 知识库变成 "看上去很美但不用" 的风险

最大的失败模式: 架构精美, 但 Wiki 自己嫌麻烦不入库, 慢慢边缘化。

**缓解**:
- 批 3 必须降低入库摩擦 (一个命令 + 简单元数据问答, 不是填 20 个字段表单)
- 批 4 必须证明检索价值 (实测对比"用 Claude Code grep" vs "用知识库 search")
- 批 5 验收时, Wiki 必须确认"我会用"; 不会用就回去改

---

## §15 立刻执行的下一步

**SPEC v0.1 批准后**:

### Step 1 (Wiki 做):
- ☐ Review STRATUM_SPEC v0.1, sign-off 或要求修订
- ☐ 在 `~/projects/` 下创建 `stratum/` (本地, 暂不推到 GitHub)

### Step 2 (Claude / Claude Code 做):
- ☐ 起 16 个 schema (`_hub/schemas/*.schema.json`)
- ☐ 起每个 schema 的 valid + invalid example
- ☐ 起 README + .gitignore + .gitattributes
- ☐ 起 pyproject.toml 骨架
- ☐ git init + tag v0.0.1
- ☐ 完成批 1, 进入批 2 实证准备

### Step 3 (Wiki 做):
- ☐ Review 批 1 产物
- ☐ 给批 2 实证提供测试样本 (5 本 PDF / 50 个查询样本)

---

## §16 SPEC v0.1.2 → v0.2 预期变更

批 2 实证完成后, 预期修订:
- §7.1 检索系统的向量库选型
- §12.2 依赖清单 (PDF 解析器 / 向量库 / embedding model 全部定稿)
- §6.1 lint 规则集 (实战可能发现新需要的 lint)
- §0.2 项目关系表 (确认 hevi v0.3 接受了哪些 P0/P1 修订请求后回填)

**已解除的 v0.2 预期项**:
- ~~§4.3 wikilink 语法 (Obsidian 实证)~~ → v0.1.2 已通过架构调整解除

---

## §17 附录: Changelog

### v0.1.2 (2026-05-16)

**触发**: 实证项 #4 决策 — Wiki 决定跳过手动 Obsidian 测试, chief advisor 直接判断
并修订 SPEC。

**核心变更**: wikilink 语法从 "扩展自定义" 改为 "Obsidian 原生兼容"。

**修订**:
- §4.3 完全重写: wikilink 语法 `[[<slug>__<ULID-suffix>|display]]` (原生兼容)
- §4.3 段落锚点改用 `## para-<suffix>` heading 形式 (原 `<a id="">` 方案废弃)
- §4.4 改 slug 流程更新, 利用 Obsidian 原生改名能力
- §4.5 加入 ULID 后缀碰撞分析
- §4.6 新增: 跨层引用的语义保持机制 (目录结构 + duckdb 索引 + 可选前缀)
- §9.1 接口 A 描述更新, 去除"扩展语法"措辞
- §13.2 实证项 #4 标记为已解除, #6 简化为非阻塞验证
- §14.3 风险标记为已解除
- §16 移除 §4.3 修订项

**影响**:
- 已交付的 v0.0.2 schema **不需要任何修改** (schema 不涉及 wikilink 语法)
- 已生成的 16 个 valid/invalid example **不需要任何修改** (frontmatter 不含 wikilink)
- 仅 SPEC 文档变更, 无 schema/code 变更

**对实施的影响**:
- 批 3 流水线设计直接按 v0.1.2 走, 不再需要 Obsidian 插件子任务
- 批 4 接口层节省 3-5 天 (省掉自写插件评估和原型)
- 批 2 实证从 6 个减少到 4 个有效项 (PDF / 向量库 / embedding / MCP), 时间预算 -2 天

### v0.1.1 (2026-05-16)

**触发**: 批 1 (立宪) 完工反馈,4 处 SPEC 反馈处理。

**变更**:
- §5.1 `ingested_by` 枚举补 `"pipeline"` (流水线自动入库标记)
- §5.2 webpage 字段 `authors_or_site` 拆分为 `site_name` (required) + `authors` (optional)
- §5.2 transcript 加注释,明确 speakers 不引用 concept person
- §5.2 加注释,对比 event.participants (强引用 concept) vs transcript.speakers (字符串)
- §5.4 note 共通字段加注释,明确 `references` 适用于所有 note 类型

**不变**:
- 三层架构 / ID 系统 / 抗腐烂机制等核心设计未变
- 现有 16 个 schema 中除 `substrate.webpage` 和共通字段外不需修改
- 批 1 产物 (`v0.0.1` tag) 与 v0.1.1 兼容,不需要 migration

**对实施的影响**:
- 已存在的 `substrate.webpage.schema.json` 需要按 v0.1.1 修订 (拆分字段)
- 其他 schema 中 `ingested_by` 枚举需要补 `"pipeline"` (Claude Code 批 1 已先行实现,合规)
- 不需要重做批 1, 仅打 patch commit

---

## §18 附录: 术语表

| 术语 | 含义 |
|------|------|
| substrate | 原始素材,不可变,Layer 1 |
| concept | 概念节点,Layer 2,substrate 和 note 的桥 |
| note | 笔记,Wiki 写的,Layer 3 |
| ULID | 26 字符全局唯一可排序 ID |
| paragraph-ULID | 单 substrate 内的段落 ID, 6 字符 |
| wikilink | Obsidian 风格的 `[[...]]` 链接 |
| frontmatter | markdown 文件开头的 yaml 元数据 |
| schema | yaml frontmatter 的 JSON Schema 校验规则 |
| pipeline | `_hub/pipelines/` 下的自动化脚本 |
| audit log | `_hub/audit/changes.jsonl` 的不可变变更日志 |
| reachability | 一个节点是否被其他节点引用 (orphan 检测用) |
| edition_key | 同一本书不同版本的唯一识别 (ISBN + 出版社 + 译者) |
| MCP | Model Context Protocol, AI agent 与工具通信的协议 |
| LFS | Git Large File Storage |

---

**End of STRATUM_SPEC v0.1**

**待办**:
- [ ] Wiki review
- [ ] 修订 (如有)
- [ ] 批准 → 进入批 1 实施
