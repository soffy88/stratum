# STRATUM_SPEC v0.2

**Stratum — Wiki 本地多模态知识库系统**

**版本**: v0.2 (大改: 多模态 + 4O 生态整合)
**创建日期**: 2026-05-17
**前序版本**: v0.1.2 (文本中心 + 项目内代码层)
**架构师**: Wiki
**草拟**: Claude (Stratum chief advisor)
**Review**: Claude (hevi chief advisor, 通过 Wiki 转交)
**状态**: 完整版 (Part 1 + Part 2 合并) — 待 hevi advisor review → Wiki sign-off → 实施
**依赖**:
- OBASE_SPEC v0.2 (4O 第 4 库)
- 4O 库 (obase / oprim / oskill / omodul) — 见 §2
- 自写 Obsidian 插件 (image region 跳转) — 见 §4
- 4O 扩充清单 v0.1 (列出 Stratum 实施需要 4O 提供的所有元素)

---

## §0 关于本 SPEC

### 0.1 v0.2 大改原因

v0.1.x 的两个根本性盲区被识别:

**盲区 1: 文本中心**

v0.1.x 把 Stratum 设计为文本中心的知识库, substrate 层只覆盖 PDF / EPUB / 网页 / 字幕 / 对话。现实中知识载体远不止文本: 播客 / 学术讲座录音 / 视频课程 / 历史照片 / 绘画 / 数据集 / 交互式演示…… 单纯文本知识库无法称为"顶级标准的现代知识库"。

**v0.2 修正**: substrate 层覆盖 **18 种 medium** (按 5 种 modality 分组: text / audio / video / image / data), 引入 **derivative** 概念处理形态转换 (例如音频→文本转录, 视频→关键帧)。

**盲区 2: 项目独立思维**

v0.1.x 设计 Stratum 时假设它有自己的 prim/skill/modul/base 层 (类似 hevi 的做法)。这违反了 Wiki 的生态愿景: **所有项目共享 4O 库 (obase + oprim + oskill + omodul), 不要每个项目重新实现**。

**v0.2 修正**: Stratum 仓库**不再含代码包**, 仓库内容是数据 + 元数据 + 配置 + 调用脚本。所有代码住在 4O 库, Stratum 通过依赖关系引用。Stratum 实施期间产生的可复用能力**直接贡献到 4O**, 不在 Stratum 仓库内保留。

### 0.2 与已有项目的关系

| 项目 | 关系 | 说明 |
|------|------|------|
| Helios 生态 (Helios/Helixa/Selene/Tide) | 平级独立 | 同 v0.1.x |
| 3O Stack (oprim/oskill/omodul) | Stratum **依赖** | Stratum 调用 4O 库实现所有功能 |
| Obase (待建) | Stratum **依赖** | obase 是 4O 第 4 库, 见 OBASE_SPEC v0.1 |
| hevi | 平级独立, 共享 4O 上游 | hevi 也将迁移到 4O, 见 OBASE_SPEC §4 |
| Obsidian | Stratum **GUI 之一** | 需要自写插件支持 image region 跳转 |
| Claude Code | Stratum **客户端之一** | 文件系统直读 |
| Hermes Agent | Stratum **远程客户端** | MCP / HTTP via Tailscale |

**关于仓库物理位置**: `~/projects/stratum/` (同 v0.1.2)。

### 0.3 命名约定

**仓库名**: `stratum`

**Stratum 不再有 Python 包**。仓库内不存在 `stratum/__init__.py`。

**三层数据**:
- `substrate/` — 原始素材层 (多 modality, 见 §3)
- `concepts/` — 概念图层
- `notes/` — 笔记层

**协调层**: `_hub/` — 元数据 / 配置 / 索引 / SPEC, 不含代码 (除少量入口脚本)

**所有代码住在 4O 库**:
- `obase.*` — 基础设施 (orchestrator / trail / cost_tracker / fs / cache / rate_limit / provider_registry)
- `oprim.*` — 原子操作 (Stratum 用到: llm / embedding / parser / media / search / asr / ocr 等子模块)
- `oskill.*` — 组合算法 (ingest_text / generate_transcript / update_concept_backrefs 等)
- `omodul.*` — 端到端业务 (ingest_substrate / reindex_knowledge_base / concept_maintenance 等)

**衍生命名**:
- MCP server 守护进程: `stratumd` (单文件入口脚本, 在 `_hub/servers/`)
- MCP / HTTP 工具命名空间: `stratum.*` (例 `stratum.search` / `stratum.fetch_fragment`)
- 环境变量根: `STRATUM_ROOT`

### 0.3.1 关于 "Stratum" 这个名字

(同 v0.1.2, 不变)

### 0.4 SPEC 变更政策

(同 v0.1.2, 不变)

---

## §1 产品定位

### 1.1 目标

Stratum 是 **Wiki 个人级、本地优先、AI 友好、长期演化** 的**多模态知识库**。

它管理 Wiki 所有形式的知识载体并提供:
- 精确寻址 (引用到 fragment 级: 文本段落 / 音频时间区间 / 视频时间区间 / 图像区域 / 数据行列)
- 多模态检索 (text/audio/image 各 modality 独立索引, 按需融合)
- 概念图谱 (跨 modality 的人物 / 事件 / 概念汇聚)
- 演化能力 (schema / 索引 / derivative 全部可重建可迁移)
- 审计能力 (任何 AI 生成的衍生物可追溯到源 + 处理链 + 工具版本)

**Stratum 实施 = 调用 4O 库 + 维护数据 + 维护元数据**。无项目内代码。

### 1.2 顶级标准的 8 个维度 (v1.0 验收标准)

| # | 维度 | v0.2 定义 |
|---|------|---------|
| D1 | 完备性 | 18 种 medium 全部 schema 就位; 流水线按 modality 优先级分批 (见 §13) |
| D2 | 可寻址性 | 任何 substrate 及其内部 fragment 可通过 ULID + fragment-identifier 精确引用 |
| D3 | 可检索性 | 每个 modality 独立索引, 跨 modality 检索按 reciprocal rank fusion 融合 |
| D4 | 可演化性 | schema 可迁移 / 索引可重建 / derivative 可用新工具重新生成 / embedding model 可换 |
| D5 | 可审计性 | 任何 AI 生成的 derivative 或 note 可追溯到 source + 处理链 + 时间戳 + 工具版本 (通过 obase.trail) |
| D6 | 可移植性 | 整库可在 60 分钟内迁到另一台机器 |
| D7 | 可消费性 | Obsidian / Claude Code / Hermes (MCP) / HTTP 四种接入方式, 多模态返回统一 fragment schema |
| D8 | 抗腐烂性 | 1 年后回看仍可信; derivative 可用更好工具重新生成不丢失原 substrate |

**v1.0 范围**:
- **schema 全部就位** (18 medium + 12 derivative + 11 concept) — 不分批, 一次到位
- **流水线分批实施**:
  - v1.0: text + audio + chats 流水线完整; image 基础流水线 (CLIP 索引 + 人工 description); 自写 Obsidian 插件
  - v1.1: video 完整流水线 + interactive-demo 流水线 + data 检索
  - v1.2+: music / code / thread 流水线

### 1.3 不在 Stratum 职责范围内

- 笔记编辑器 (用 Obsidian / VSCode)
- 长期云备份 (用户自行处理)
- 多用户协作
- 实时同步多设备
- 主动爬取
- 知识本身的真伪判断
- 媒体内容创作 (那是 hevi 的事)
- 媒体格式转换工具 (用 ffmpeg / audiblez 等独立工具)
- 实时音视频流处理 (substrate 始终是已存在的文件)
- **交互式知识演示** (例如 ChatTutor 类应用) — 当前作为 markdown-note + 外链处理, v1.x 评估是否升级为完整 medium

### 1.4 优先级与时间表

(扩大范围后调整)

- 高于: hevi
- 低于: Helios Layer 4 现金流类项目
- 并行: Helixa 生产化 / Selene 修复

**v1.0 估计 8-11 周** (含 Obase 实施 + 4O 扩充 + Stratum 数据层完工)

---

## §2 架构: 4O 整合后的形态

### 2.1 整体架构

```
┌────────────────────────────────────────────────────────────────┐
│  consumer 层 (不在 stratum 仓库内, 但本 SPEC 定义接口)         │
│  - Wiki / Claude Code / Hermes / hevi                          │
│  接口扩展: 返回结果包含 fragment-identifier (text-span /        │
│           audio-timerange / video-timerange / image-region)    │
└────────────────────────────────────────────────────────────────┘
                          ↑ 通过 MCP/HTTP/文件系统
┌────────────────────────────────────────────────────────────────┐
│  Stratum 仓库 (~/projects/stratum/)                            │
│  - _hub/ (元数据 + 配置 + 索引 + 入口脚本)                     │
│  - substrate/ concepts/ notes/ (数据)                          │
│  - 无 Python 代码包                                            │
└────────────────────────────────────────────────────────────────┘
                          ↓ 调用
┌─────────┬──────────────┬────────────────┬──────────────────────┐
│ Obase   │ Oprim        │ Oskill         │ Omodul               │
│ (基础)  │ (原子, 跨域) │ (组合, 跨域)   │ (端到端, 跨域)       │
└─────────┴──────────────┴────────────────┴──────────────────────┘
                          ↓
        基础库 (numpy/pandas/pydantic/asyncio/...)
```

### 2.2 V1 (Vertical) 规则: 引用方向

| 引用方 | 可引用 | 不可引用 |
|--------|--------|---------|
| consumer | _hub 接口 / 三层数据 / 任何 4O 库 | — |
| Stratum 入口脚本 (_hub/servers/, _hub/scripts/) | obase / oprim / oskill / omodul / 三层数据 | — |
| omodul | obase / oprim / oskill | — |
| oskill | obase / oprim | sibling oskill (H1) |
| oprim | obase | sibling oprim, oskill, omodul |
| obase | (仅外部库) | 任何 4O 业务层 |
| notes | concepts / substrate | (其他 notes 通过 concept 中转, ADR 例外见 §5) |
| concepts | substrate | notes (反链区块除外, 由流水线写) |
| substrate | (只读, 不引用) | — |

### 2.3 反向依赖红线

- substrate 不能引用 concept / note
- concept 主体不能引用 note (反链区块由流水线维护, 不算主体)
- 任何数据层不能引用 _hub 实现细节 (除引用 schema 版本号这种元数据)
- 任何 4O 库不能引用 Stratum 仓库 (Stratum 是 4O 的下游)

### 2.4 H1 (Horizontal) 规则: 同层关联

- notes 之间不直接 wikilink (通过 concept 中转), ADR 例外见 §5
- substrate 之间不引用 (除 alternate_editions 这种元数据级关联)
- concept 之间可通过 `related_concepts` 引用 (这是 concept 的核心结构)

### 2.5 derivative 边界

derivative 是 substrate 内部子目录, **不能引用其他 substrate / concept / note**。derivative.yaml 只指向自己的源 substrate。

---

## §3 目录结构

### 3.1 顶层布局 (v0.2 重写, 无代码包)

```
stratum/                              # 仓库根
├── .git/
├── .gitattributes                    # Git LFS 配置
├── .gitignore
├── README.md
├── STRATUM_VERSION                   # 当前 = 2 (v0.2 大改)
├── pyproject.toml                    # 声明对 4O 库的依赖, 无本地代码
├── uv.lock
│
├── _hub/                             # 协调层 (元数据 + 配置 + 入口)
│   ├── STRATUM_SPEC.md               # 本文件
│   ├── schemas/                      # JSON Schema 文件
│   │   ├── _meta/
│   │   │   ├── schema_versions.yaml
│   │   │   └── medium_to_modality.yaml
│   │   ├── substrate.book.schema.json
│   │   ├── substrate.paper.schema.json
│   │   ├── substrate.webpage.schema.json
│   │   ├── substrate.markdown-note.schema.json
│   │   ├── substrate.thread.schema.json           # 新增 (X/Reddit 长帖)
│   │   ├── substrate.podcast.schema.json
│   │   ├── substrate.lecture.schema.json          # 音频讲座
│   │   ├── substrate.audiobook.schema.json
│   │   ├── substrate.music.schema.json            # 新增
│   │   ├── substrate.video-lecture.schema.json
│   │   ├── substrate.interview.schema.json
│   │   ├── substrate.documentary.schema.json
│   │   ├── substrate.artwork.schema.json
│   │   ├── substrate.photograph.schema.json
│   │   ├── substrate.diagram.schema.json
│   │   ├── substrate.dataset.schema.json
│   │   ├── substrate.code.schema.json             # 新增
│   │   ├── substrate.chat.schema.json
│   │   ├── derivative.transcript.schema.json
│   │   ├── derivative.summary.schema.json
│   │   ├── derivative.translation.schema.json
│   │   ├── derivative.chapters.schema.json
│   │   ├── derivative.keyframes.schema.json
│   │   ├── derivative.ocr.schema.json
│   │   ├── derivative.description.schema.json
│   │   ├── derivative.annotation.schema.json
│   │   ├── derivative.highlights.schema.json      # 新增
│   │   ├── derivative.questions.schema.json       # 新增
│   │   ├── derivative.flashcards.schema.json      # 新增
│   │   ├── derivative.citations.schema.json       # 新增
│   │   ├── concept.person.schema.json
│   │   ├── concept.event.schema.json
│   │   ├── concept.theorem.schema.json
│   │   ├── concept.technique.schema.json
│   │   ├── concept.place.schema.json
│   │   ├── concept.domain.schema.json
│   │   ├── concept.artwork-style.schema.json
│   │   ├── concept.work.schema.json               # 新增
│   │   ├── concept.organization.schema.json       # 新增
│   │   ├── concept.system.schema.json             # 新增
│   │   ├── concept.dataset-source.schema.json     # 新增
│   │   ├── note.adr.schema.json
│   │   ├── note.postmortem.schema.json
│   │   ├── note.reading.schema.json
│   │   ├── note.idea.schema.json
│   │   └── note.daily.schema.json
│   ├── configs/                      # 4O 模块的运行时配置
│   │   ├── obase/
│   │   │   ├── pricing.yaml          # cost_tracker 用
│   │   │   ├── rate_limits.yaml      # rate_limit 用
│   │   │   └── working_dir.yaml      # fs 用
│   │   ├── embedding/
│   │   │   ├── text.yaml             # 文本 embedding 模型选择
│   │   │   ├── audio.yaml            # 音频 embedding 模型
│   │   │   └── image.yaml            # 图像 embedding 模型
│   │   ├── search/
│   │   │   └── hybrid.yaml           # 检索融合配置
│   │   ├── derivative-tools/
│   │   │   ├── asr.yaml              # ASR 模型选择
│   │   │   ├── ocr.yaml
│   │   │   └── ...
│   │   └── ...
│   ├── indexes/                      # 索引产物 (gitignore)
│   │   ├── fulltext.tantivy/
│   │   ├── vectors-text.qdrant/
│   │   ├── vectors-audio.qdrant/
│   │   ├── vectors-image.qdrant/
│   │   └── meta.duckdb
│   ├── audit/                        # 审计日志 (摘要入 git, 大文件 gitignore)
│   │   ├── changes.jsonl
│   │   └── reports/
│   ├── servers/                      # 入口脚本 (薄包装, 调 omodul)
│   │   ├── stratumd.py               # MCP server 入口
│   │   └── http_server.py            # HTTP API 入口
│   └── obsidian-plugin/              # 自写 Obsidian 插件源码
│       ├── main.ts
│       ├── manifest.json
│       └── ...
│
├── substrate/                        # Layer 1 数据 (按 medium 分子目录)
│   ├── books/
│   ├── papers/
│   ├── webpages/
│   ├── markdown-notes/
│   ├── threads/
│   ├── podcasts/
│   ├── lectures/
│   ├── audiobooks/
│   ├── music/
│   ├── video-lectures/
│   ├── interviews/
│   ├── documentaries/
│   ├── artworks/
│   ├── photographs/
│   ├── diagrams/
│   ├── datasets/
│   ├── code/
│   └── chats/
│
├── concepts/                         # Layer 2 数据
│   ├── people/
│   ├── events/
│   ├── theorems/
│   ├── techniques/
│   ├── places/
│   ├── domains/
│   ├── artwork-styles/
│   ├── works/
│   ├── organizations/
│   ├── systems/
│   └── dataset-sources/
│
├── notes/                            # Layer 3 数据
│   ├── adr/
│   ├── postmortem/
│   ├── readings/
│   ├── ideas/
│   └── daily/
│
├── scripts/                          # Stratum 仓库本地零散脚本
│   ├── new_substrate.sh              # 引导式入库 helper
│   ├── check_health.sh               # 调用 omodul 检查全库健康
│   └── ...
│
└── tests/                            # Stratum 自身集成测试
    └── integration/
        ├── test_full_ingest.py       # 调 omodul.ingest_substrate 完整流程
        └── ...
```

### 3.2 关于"无代码包"

Stratum 仓库的 `pyproject.toml` 不声明任何 Python 包, 仅声明对 4O 库的依赖:

```toml
[project]
name = "stratum-instance"              # 不是 Python 包名, 是项目标识
version = "0.0.0"                      # 数据仓库无版本概念, 跟 STRATUM_VERSION 分开
requires-python = ">=3.12"

dependencies = [
    "obase>=0.1",
    "oprim>=X.Y",                      # X.Y 待定, 看 4O 扩充后版本
    "oskill>=X.Y",
    "omodul>=X.Y",
]

# 不定义 [project.scripts], 入口在 _hub/servers/*.py 直接调用
```

`stratum/` 仓库的 git tag 表示**数据 + 配置 + SPEC 的版本**, 不是代码版本。

### 3.3 文件命名约定

同 v0.1.2: `<slug>__<ULID-suffix>` 形式, ULID 后缀 8 字符。

### 3.4 关于 substrate 的 medium 选择

同 v0.1.2 §3.3 (主形态优先, 衍生形态进 derivatives/)。

### 3.5 关于 LFS

```
*.pdf *.epub *.mobi *.djvu                  → LFS
*.mp3 *.m4a *.wav *.flac *.ogg *.opus       → LFS
*.mp4 *.mkv *.webm *.mov *.avi              → LFS
*.jpg *.jpeg *.png *.webp *.heic *.tiff     → LFS
*.parquet *.csv *.json (>1MB)               → LFS
```

### 3.6 `_hub/indexes/` 和 derivatives 内的索引产物

均不入 git, 可由 4O 模块重建。

---

## §4 ID 系统

### 4.1 ULID

(同 v0.1.2, 不变)

### 4.2 Fragment 级 ID (v0.2 多模态扩展, 精度调整)

| Modality | Fragment 类型 | Suffix 格式 | 示例 |
|----------|--------------|------------|------|
| text | 段落 | `<6-char-random>` | `A1B2C3` |
| audio | 时间区间 | `t<start>-<end>` (秒 + 3 位小数 = 1ms 精度) | `t125.400-148.700` |
| video | 时间区间 | `t<start>-<end>` (同 audio) | `t330.000-345.200` |
| video | 关键帧 | `f<frame-index>` | `f1024` |
| image | 区域 (相对坐标) | `r<x>-<y>-<w>-<h>` (0-1 浮点, 3 位小数) | `r0.234-0.567-0.123-0.089` |
| image | 整图 | (不需要 fragment) | (用整 substrate ID) |
| data | 行范围 | `rows<start>-<end>` | `rows100-200` |
| data | 列 | `col<name>` | `col_revenue` |

**精度变化 (vs v0.1.2 上一轮提议)**:
- audio/video 时间区间: 秒 + 3 位小数 (原计划 1 位小数, 精度从 100ms 提到 1ms, 足够音乐分析需求)
- image region: 改用相对坐标 0-1 比例 (原计划像素 px), 跟分辨率无关, 重数字化不失效

### 4.3 ID 在文件中的呈现

**frontmatter 中的 id 字段**:
```yaml
---
id: "01HXYZW7G5K8M2N3P4Q5R6S7T8"
slug: "xiang-yu"
...
---
```

**文件名格式**: `<slug>__<ULID-suffix>.md` 或 `<slug>__<ULID-suffix>/` (目录)

**markdown 中引用其他节点 (Obsidian 原生 + 自写插件扩展)**:

```markdown
# text fragment (原生)
[[shiji-007__XXX#para-A1B2C3|《史记·项羽本纪》开篇]]

# audio fragment (原生)
[[lex-368__YYY#t125.400-148.700|关于 attention 机制的讨论]]

# video fragment (原生)
[[stanford-cs229-01__ZZZ#t330.000-345.200|线性回归推导]]

# image 整图 (原生)
[[xiang-yu-portrait__AAA|项羽像]]

# image 区域 (需自写插件支持视觉跳转)
[[xiang-yu-portrait__AAA#r0.234-0.567-0.123-0.089|项羽脸部特写]]
```

**为兼容 Obsidian 原生 heading anchor, derivative 文本内用 heading 标记 fragment**:

```markdown
## para-A1B2C3
[段落正文]

## t125.400-148.700
[音频该时段的 transcript]
```

**对 image region 的特殊处理**: Obsidian 原生不支持图像区域高亮, 自写插件 (在 `_hub/obsidian-plugin/`) 解析 `#r<x>-<y>-<w>-<h>` 并在图像上叠加高亮框。详见 §9.5。

### 4.4 ID 不可变, slug 可变

(同 v0.1.2, 利用 Obsidian 原生改名能力 + obase.trail 审计)

### 4.5 ID 碰撞处理

(同 v0.1.2 + 多模态扩展)
- audio fragment 1ms 精度 + 区间表达 → 碰撞概率极低
- image region 相对坐标 0-1 浮点 → 同一图允许区域重叠 (含义不同)
- data fragment 用语义 key, 强制唯一 (lint 检查)

### 4.6 跨层引用的语义保持

(同 v0.1.2, 不变)

---

## §5 三层数据 schema (v0.2 完整范围)

完整 schema 在 `_hub/schemas/*.schema.json`。本节给出主要字段。

### 5.0 medium → modality 映射

`_hub/schemas/_meta/medium_to_modality.yaml`:

```yaml
# medium: 用户视角的"这是什么类型的素材"
# modality: 系统视角的"该用什么 modality 的处理流水线"

# text modality
book: text
paper: text
webpage: text
markdown-note: text
thread: text                # X/Reddit 长帖
chat: text                  # 默认 text, 含音频在 meta.yaml 标 has_audio
code: text                  # 代码作为研究对象

# audio modality
podcast: audio
lecture: audio              # 音频讲座
audiobook: audio
music: audio

# video modality
video-lecture: video
interview: video
documentary: video

# image modality
artwork: image
photograph: image
diagram: image

# data modality
dataset: data
```

**为什么这层映射独立**: 新增 medium 不需要改 indexing 流水线 (只需在映射表添一行), modality 处理代码按 modality 写一次复用。

### 5.1 substrate 共通字段 (所有 medium 都有)

```yaml
id: "01HXYZ..."                # ULID
slug: "shiji-zhonghua-1959"
title: "..."
medium: "book"                 # required, 决定 schema 类型
modality: "text"               # required, 从 medium 推导, 也存一份方便查询
created_at: "..."
ingested_by: "wiki" | "hermes" | "claude-code" | "pipeline"
schema_version: 2              # v0.2 所有 substrate schema 版本号 = 2
domains: [...]                 # 受控词表
language: "zh-Hans" | "en" | "mixed" | "non-verbal"
duration_seconds: <number>     # 仅 audio/video
file_size_mb: <number>
original_format: "..."
copyright_status: "..."
copyright_notes: "..."
```

### 5.2 medium 特化字段 (举 6 例, 全部 18 个 schema 在文件中)

**book** (text):
```yaml
authors: [...]
editors: [...]
edition_key: "isbn:...|publisher:...|year:..."
publisher: "..."
publication_year: 2014
total_pages: 3768
parsing: {parser, parser_version, parsed_at, paragraph_count, ocr_used, ...}
```

**podcast** (audio):
```yaml
show_name: "Lex Fridman Podcast"
episode_number: 368
host: ["Lex Fridman"]
guests: ["Andrej Karpathy"]
source_platform: "spotify" | "youtube" | "rss"
source_url: "..."
published_date: "2026-04-15"
sample_rate_hz: 44100
channels: 2
bitrate_kbps: 192
```

**music** (audio):
```yaml
artist: ["..."]
album: "..."
track_number: 5
genre: "classical" | "rock" | ...
composer: ["..."]
performer: ["..."]
release_year: 2020
isrc: "..."                          # 国际标准录音代码
duration_seconds: 245.6
```

**code** (text):
```yaml
language: "python" | "rust" | ...
repository_url: "..."
commit_hash: "..."
snapshot_date: "..."
maintainers: [...]
purpose: "research-target" | "reference-implementation" | ...
loc: 12450                            # lines of code
```

**artwork** (image):
```yaml
artist: ["阎立本派 (传)"]
creation_year_approx: 800
art_movement: "唐代人物画"
medium_material: "绢本设色"
dimensions_cm: "55x40"
current_location: "故宫博物院"
source_of_image: "高清扫描" | "摄影" | "web"
image_resolution_px: "4800x6400"
```

**dataset** (data):
```yaml
dataset_format: "parquet" | "csv" | "json"
schema_description: |
  columns:
    - {name: timestamp, type: datetime}
    - {name: price, type: float}
row_count: 1500000
date_range: "2020-01-01 to 2026-04-30"
source: "Binance API export"
license: "..."
```

(其余 12 个 medium 类似, 完整 schema 见 `_hub/schemas/`)

### 5.3 derivative schema

derivative 物理上是 `substrate/<medium>/<slug>__<ULID>/derivatives/<type>/` 子目录:
- `content.<ext>` — 衍生物主体 (gitignore, 可重生)
- `derivative.yaml` — 元数据 (入 git)

**derivative.yaml 共通字段**:

```yaml
derivative_type: "transcript"     # 见下列 12 个 type
source_substrate_id: "01HXYZ..."
generated_by: "omodul:omodul.knowledge.generate_transcript"  # 调用了哪个 4O 元素
generated_at: "..."
tool: "whisperx"
tool_version: "3.1.5"
tool_config: {model: "large-v3", language: "en", ...}
manual_corrections: false
manual_corrections_at: null
content_format: "markdown" | "srt" | "json" | "txt"
content_file: "content.md"
size_bytes: 12450
quality_self_assessment: 0.85
```

**12 个 derivative type**:

| Type | 适用 modality | 用途 |
|---|---|---|
| transcript | audio / video | ASR 转录文本 |
| summary | 全部 | LLM 摘要 |
| translation | text / audio | 翻译 |
| chapters | audio / video / book | 章节切分 |
| keyframes | video | 关键帧抽取 |
| ocr | image / pdf scan | OCR 文本 |
| description | image / video | 人工或 AI 描述 |
| annotation | 全部 | 人工标注层 |
| highlights | 全部 | 人工/AI 划重点 |
| questions | text / audio / video | 基于内容生成的问题集 |
| flashcards | text | 卡片化记忆材料 |
| citations | paper | 引用列表 |

(各 type 的特化字段省略, 见 `_hub/schemas/derivative.*.schema.json`)

### 5.4 concept 共通字段

```yaml
id: "..."
slug: "..."
title: "..."
type: "person" | "event" | "theorem" | "technique" | "place" | "domain" |
      "artwork-style" | "work" | "organization" | "system" | "dataset-source"
aliases: [...]
domains: [...]
schema_version: 2
created_at: "..."
last_reviewed_at: "..."
related_concepts:
  - {id: "...", slug: "...", relation: "..."}
```

**11 个 concept type 简介**:

| Type | 含义 |
|---|---|
| person | 人物 |
| event | 事件 |
| theorem | 定理/原理 |
| technique | 技术/方法 |
| place | 地点 |
| domain | 领域节点 (用于领域树) |
| artwork-style | 艺术风格/流派 |
| work | 作品 (区别于具体 substrate 版本) |
| organization | 机构/公司/学派 |
| system | 思想体系/框架 (例: 凯尔特宗教体系 / 贝叶斯统计框架) |
| dataset-source | 数据集源 |

**concept 的"出现于"反链区块** 按 medium 分组展示 (流水线自动维护):

```markdown
## 出现于

### Substrate (按 medium 分组)

#### Books (3)
- [[shiji-007__XXX|《史记·项羽本纪》]] · 12 段落引用
- [[hanshu-001__YYY|《汉书·高帝纪》]] · 4 段落引用

#### Artworks (1)
- [[xiang-yu-portrait-tang__ZZZ|项羽像 (唐, 阎立本派)]] · 整图引用

#### Podcasts (1)
- [[history-china-podcast-ep23__AAA|历史中国播客 第23集]] · 3 处提及

(其他 medium 略)

### Notes (2)
- [[on-xiang-yu-tragedy__N1O2|反领导力分析]]
- [[reading-shiji-ch7__M3P4|史记第7卷读书笔记]]
```

### 5.5 note 共通字段 (扩展 references 支持多 modality fragment)

```yaml
id: "..."
slug: "..."
title: "..."
type: "adr" | "postmortem" | "reading" | "idea" | "daily"
created_at: "..."
last_modified_at: "..."
schema_version: 2
status: "draft" | "active" | "archived" | "superseded"
domains: [...]

references:
  substrate:
    - substrate_id: "01HXYZ..."
      medium: "book"
      fragments:
        - {type: "text-paragraph", id: "A1B2C3"}
        - {type: "text-paragraph", id: "A1B2C4"}
    - substrate_id: "01HXYZ..."
      medium: "podcast"
      fragments:
        - {type: "audio-timerange", start: 125.400, end: 148.700}
    - substrate_id: "01HXYZ..."
      medium: "artwork"
      fragments:
        - {type: "image-region", x: 0.234, y: 0.567, w: 0.123, h: 0.089}
        - {type: "whole-image"}
  concepts:
    - {id: "01HXYZ..."}
```

**ADR 例外**: ADR 内部可直接 wikilink 到其他 ADR (supersede 链), 不强制走 concept 中转。

### 5.6 schema 版本管理

`_hub/schemas/_meta/schema_versions.yaml` v0.2 整体跳到 v2:

```yaml
# v0.2: 所有 schema 大版本升级 (含新增)
# substrate (18 个)
substrate.book: 2
substrate.paper: 2
substrate.webpage: 2
substrate.markdown-note: 2
substrate.thread: 1                  # 新增
substrate.podcast: 2
substrate.lecture: 2
substrate.audiobook: 2
substrate.music: 1                   # 新增
substrate.video-lecture: 2
substrate.interview: 2
substrate.documentary: 2
substrate.artwork: 2
substrate.photograph: 2
substrate.diagram: 2
substrate.dataset: 2
substrate.code: 1                    # 新增
substrate.chat: 2

# derivative (12 个, v0.2 全新)
derivative.transcript: 1
derivative.summary: 1
derivative.translation: 1
derivative.chapters: 1
derivative.keyframes: 1
derivative.ocr: 1
derivative.description: 1
derivative.annotation: 1
derivative.highlights: 1
derivative.questions: 1
derivative.flashcards: 1
derivative.citations: 1

# concept (11 个)
concept.person: 2
concept.event: 2
concept.theorem: 2
concept.technique: 2
concept.place: 2
concept.domain: 2
concept.artwork-style: 1
concept.work: 1                      # 新增
concept.organization: 1              # 新增
concept.system: 1                    # 新增
concept.dataset-source: 1            # 新增

# note (5 个)
note.adr: 2
note.postmortem: 2
note.reading: 2
note.idea: 2
note.daily: 2
```

**v0.1.x → v0.2 migration**: 必须有 migration 脚本, 因为字段重命名 (`paragraph_ids` → `fragments`)、medium 重新分类、derivative 概念引入。migration 流水线见 §8.7。

## §6 抗腐烂规则

### 6.1 总则

知识库 1 年后仍可信, 不是靠"小心维护", 是靠**规则自动守护**。Stratum 的抗腐烂机制由两层组成:

1. **lint 规则**: 静态扫描数据层 (substrate / concepts / notes), 检测违反规则的项
2. **周期性 audit**: 跑 lint + 索引一致性检查 + 引用完整性检查, 生成报告

**lint 规则代码全部贡献到 4O** (作为 `oskill.lint_*` 系列), Stratum 仓库的 `scripts/lint_all.sh` 只是薄封装调用。

### 6.2 lint 规则集 (按 8 维度组织)

#### D1 完备性守护

**lint_orphan_substrate**: 检查每个 substrate 目录是否完整 (meta.yaml 存在 + original/ 非空 + frontmatter 校验通过)。

**lint_unknown_medium**: 检查 substrate 的 `medium` 字段在 `_hub/schemas/_meta/medium_to_modality.yaml` 中存在。

#### D2 可寻址性守护

**lint_ulid_format**: 所有节点的 ULID 符合 ULID 格式 (26 字符, Crockford base32)。

**lint_filename_match**: 文件名格式严格 `<slug>__<ULID-suffix>.md` 或 `<slug>__<ULID-suffix>/`, ULID-suffix 取 ULID 后 8 字符。

**lint_fragment_id_format**: fragment ID 符合 §4.2 的 modality-specific 格式 (text 6-char / audio t<start>-<end> / image r<x>-<y>-<w>-<h> 等)。

#### D3 可检索性守护

**lint_index_freshness**: `_hub/indexes/meta.duckdb` 的最后更新时间 < 24 小时, 否则警告。

**lint_index_coverage**: 索引覆盖率 ≥ 99% (即 substrate 总数 vs duckdb 记录数差异 ≤ 1%)。

#### D4 可演化性守护

**lint_schema_version**: 每个节点 frontmatter 的 `schema_version` 字段存在且匹配 `_hub/schemas/_meta/schema_versions.yaml` 中的当前版本。

**lint_migration_marker**: 如有 schema_version 旧版节点存在, `_hub/migration/` 必须有对应 migration 脚本。

#### D5 可审计性守护

**lint_derivative_yaml**: 每个 derivative 子目录必须有 `derivative.yaml` 且字段完整 (生成方法 / 工具版本 / 时间戳)。

**lint_ai_generated_traceback**: 凡 frontmatter 标 `generated_by` 含 AI 工具的节点, 必须能追溯到源 substrate (references 字段非空)。

#### D6 可移植性守护

**lint_no_absolute_paths**: 数据层文件中 (yaml / markdown) 不含本机绝对路径 (例 `/home/wiki/` 或 `C:\Users\`)。

**lint_no_external_deps**: derivative content 不引用本机环境特定路径 (例 conda env / venv / docker bind)。

#### D7 可消费性守护

**lint_wikilink_resolvable**: 所有 wikilink `[[X__YYY]]` 能在 `_hub/indexes/meta.duckdb` 解析到目标节点 (否则 broken link)。

**lint_fragment_anchor_exists**: wikilink 含 fragment `#para-X` / `#t125.400-148.700` 等, 对应的 anchor 在目标文件中实际存在。

#### D8 抗腐烂性守护 (跨维度)

**lint_circular_concept_ref**: concept 的 `related_concepts` 不形成循环引用 (A → B → C → A)。

**lint_orphan_concept**: concept 节点至少被 1 个 substrate 或 1 个 note 引用 (否则成孤儿)。

**lint_stale_review**: concept 节点的 `last_reviewed_at` < 1 年前则警告 (鼓励定期重看)。

### 6.3 周期性 audit

**频率**: 每周一次, 由 `scripts/audit_weekly.sh` 触发 (用户手动跑或 cron)。

**audit 内容**:
1. 跑全套 lint 规则 (§6.2)
2. 索引完整性检查 (duckdb 与文件系统差异)
3. derivative 重生成测试 (随机抽 5 个 substrate, 用最新工具重新生成 transcript 等, 验证可重生)
4. 引用统计 (concept 出现次数 / substrate 入库速度 / orphan 数量)
5. 输出报告到 `_hub/audit/reports/weekly-<date>.md`

**audit 失败处理**:
- 红色 (broken link / missing derivative.yaml / ulid 重复) → 立即阻塞所有 ingest, Wiki 必须先修
- 黄色 (orphan concept / stale review) → 报告但不阻塞
- 绿色 → 正常

### 6.4 数据丢失检测

`_hub/audit/changes.jsonl` 记录所有 substrate / concept / note 的增删改, 每条 entry:

```jsonl
{"ts": "2026-05-17T...", "action": "create", "node_type": "substrate", "id": "01HY...", "slug": "...", "actor": "wiki"}
{"ts": "...", "action": "delete", "node_type": "concept", "id": "01HY...", "slug": "...", "actor": "pipeline", "reason": "merge_with_<other-id>"}
```

任何节点删除强制走流水线 (不允许直接 `rm`), 流水线先检查反链, 有反链则阻塞 (除非 actor 显式 `--force` 并提供 reason)。

---

## §7 检索系统

### 7.1 三种检索类型

| 类型 | 引擎 | 用途 |
|------|------|------|
| 精确匹配 | duckdb (`_hub/indexes/meta.duckdb`) | 按 ULID / slug / 元数据字段查 |
| 全文检索 | tantivy (`_hub/indexes/fulltext.tantivy`) | 文本内容关键字 |
| 语义检索 | 多个 qdrant 集合 (按 modality 分) | 向量相似度 |

### 7.2 多 modality 独立索引

按 §2.1 架构, 三个独立 qdrant collection:

```
_hub/indexes/
├── vectors-text.qdrant/        # 文本 embedding (book/paper/webpage/transcript 等)
├── vectors-audio.qdrant/       # 音频 embedding (CLAP / ImageBind)
├── vectors-image.qdrant/       # 图像 embedding (CLIP / SigLIP)
└── (data modality 暂不语义索引, v1.x 加)
```

每个 collection 的 schema 含:
- `id` (ULID, 主键)
- `vector` (固定维度, 由该 modality 的 embedding 模型决定)
- `payload`: substrate_id / medium / fragment_id (如适用) / domains / language / created_at

### 7.3 检索接口 (统一 schema)

调用方 (Wiki / Claude Code / Hermes) 通过 MCP / HTTP 调用 `stratum.search`:

```python
# 调用语义
result = stratum.search(
    query="项羽的悲剧性格分析",
    modalities=["text", "image"],           # 可选, 默认全部
    media_filter=["books", "podcasts"],     # 可选, 限定 medium
    domains_filter=["history-china"],       # 可选, 限定领域
    top_k=10,
    fusion="rrf",                            # reciprocal rank fusion
    include_concepts=True,                   # 是否同时返回 concept 命中
)
```

**返回 schema** (跨 modality 统一):

```yaml
results:
  - substrate_id: "01HY..."
    medium: "book"
    modality: "text"
    title: "《史记·项羽本纪》"
    fragment:
      type: "text-paragraph"
      id: "A1B2C3"
      preview: "项籍者, 下相人也..."
    score: 0.87
    source_index: "vectors-text"
  - substrate_id: "01HY..."
    medium: "artwork"
    modality: "image"
    title: "项羽像 (唐, 阎立本派)"
    fragment:
      type: "image-region"
      x: 0.234
      y: 0.567
      w: 0.123
      h: 0.089
      preview_image_url: "..."
    score: 0.81
    source_index: "vectors-image"
  - ...

concepts:                                    # 如 include_concepts=True
  - concept_id: "01HY..."
    slug: "xiang-yu"
    title: "项羽"
    type: "person"
    relevance: "direct-match"

total: 23
fusion_method: "rrf-k60"
```

### 7.4 Reciprocal Rank Fusion (RRF)

跨 modality 检索结果合并:

```
score_rrf(d) = Σ_i  1 / (k + rank_i(d))
```

- k = 60 (经典默认值)
- rank_i(d) 是文档 d 在第 i 个 modality 检索中的排名
- 出现在多个 modality 中的文档自然得分高

**实施**: 用 4O 中的 `omodul.knowledge.hybrid_search` 实现。

### 7.5 索引重建

完整重建命令:

```bash
# Stratum 仓库内
./scripts/reindex_all.sh
```

内部调用 `omodul.knowledge.reindex_knowledge_base`, 流程:
1. 扫描所有 substrate / concept / note
2. 重生成 embedding (按 modality 用对应模型)
3. 写入 qdrant + tantivy + duckdb
4. 报告 (节点总数 / embedding 覆盖率 / 失败列表)

**增量索引**: 流水线 ingest 时同步更新索引, 不需要全量重建。全量重建只在以下场景:
- 换 embedding 模型
- duckdb / qdrant 损坏
- schema migration

---

## §8 流水线规范

### 8.1 流水线分类

Stratum 有 6 类流水线, **全部住在 4O 库**, Stratum 仓库通过 `scripts/` 调用:

| 类别 | 代表流水线 | 4O 命名空间 |
|------|----------|-----------|
| ingest | ingest_pdf / ingest_epub / ingest_audio / ingest_video / ingest_image / ingest_dataset / ingest_code | `omodul.knowledge.ingest_*` |
| derivative-generation | generate_transcript / generate_summary / generate_keyframes / generate_description | `oskill.knowledge.generate_*` |
| concept-management | extract_entity_candidates / concept_backref_update / concept_merge | `oskill.knowledge.concept_*` |
| indexing | reindex_fulltext / reindex_vectors_text / reindex_vectors_audio / reindex_vectors_image / reindex_meta | `oskill.knowledge.reindex_*` |
| lint | lint_<规则名> (§6.2 全套) | `oskill.lint_*` |
| migration | migrate_v0_1_to_v0_2 / migrate_schema_v1_to_v2 | `omodul.knowledge.migrate_*` |

### 8.2 流水线共通规范

所有流水线**必须**:

1. **接 Pydantic config 入参** (非裸字典)
2. **跑在 obase.orchestrator Pipeline 框架内** (即使是单 stage 流水线)
3. **emit trail 事件** (通过 obase.trail) — 关键事件类型在 §8.6 列出
4. **记 cost** (如调外部 API, 用 obase.cost_tracker)
5. **失败抛 obase 异常体系内的异常** (§1.7 失败不静默)
6. **返回结构化 result Pydantic 模型** (含 success/failed 状态 + 产物路径 + 统计)

### 8.3 ingest 流水线规范

#### 输入

```python
class IngestConfig(BaseModel):
    source_path: Path                    # 原始文件或 URL
    target_medium: str                   # 'book' / 'paper' / 'podcast' / ...
    slug: str | None = None              # 不指定则自动生成
    initial_domains: list[str] = []
    initial_meta: dict = {}              # 用户预填的 meta.yaml 字段
    generate_derivatives: list[str] = [] # 入库后立即生成哪些 derivative
                                         # e.g. ['transcript', 'summary']
    add_to_index: bool = True
```

#### 输出

```python
class IngestResult(BaseModel):
    success: bool
    substrate_id: str | None             # 成功则有 ULID
    substrate_path: Path | None
    derivatives_generated: list[str]     # 成功生成的 derivative type
    derivatives_failed: list[dict]       # 失败的 derivative + 失败原因
    indexing_status: Literal["success", "partial", "skipped", "failed"]
    cost_usd: float                      # 本次 ingest 累计花费
    duration_seconds: float
    errors: list[dict]
```

#### 行为规范

1. **校验源文件**: 存在 + 格式匹配 target_medium (例如 ingest_pdf 收到 mp3 直接抛 `IngestFormatMismatch`)
2. **分配 ULID**: 用 `oprim.fragment.generate_ulid()` (待加进 4O)
3. **创建 substrate 目录**: `substrate/<medium>/<slug>__<ULID-suffix>/`
4. **拷贝原始文件**: 到 `original/`, 走 Git LFS
5. **写 meta.yaml**: schema 严格校验
6. **生成 derivative** (如指定): 按 type 调对应 oskill, 失败的 derivative 列在 result.derivatives_failed, 不阻塞 substrate 入库
7. **更新索引** (如 `add_to_index=True`): 调 indexing 流水线
8. **emit trail**: `substrate_created` / `derivative_generated` / `indexing_complete`

#### medium 特化的 ingest 流水线

每个 medium 一个流水线, 共 18 个 (v1.0 实施 P0+P1 medium 的 ingest, P2 推 v1.x):

| 流水线 | 用到的 4O 元素 | v1.0 状态 |
|---|---|---|
| ingest_book | oprim.parser.parse_pdf / parse_epub + oskill.knowledge.generate_paragraph_anchors | P0 |
| ingest_paper | oprim.parser.parse_pdf + oskill.knowledge.extract_citations (derivative) | P0 |
| ingest_webpage | oprim.parser.archive_webpage + oprim.parser.html_to_markdown | P0 |
| ingest_markdown_note | (浅, 直接拷贝 + 加 frontmatter) | P0 |
| ingest_thread | oprim.parser.parse_thread (新, 处理 X/Reddit 结构) | P0 |
| ingest_podcast | oprim.media.audio_normalize + (可选) oskill.knowledge.generate_transcript | P0 |
| ingest_lecture | 同 ingest_podcast | P0 |
| ingest_audiobook | 同 ingest_podcast + (可选) chapters derivative | P0 |
| ingest_music | oprim.media.audio_metadata_extract (轻量) | P1 |
| ingest_video_lecture | oprim.media.video_metadata + (可选) transcript + keyframes | P1 |
| ingest_interview | 同 ingest_video_lecture | P1 |
| ingest_documentary | 同 ingest_video_lecture | P1 |
| ingest_artwork | oprim.media.image_metadata + (可选) description + OCR | P1 |
| ingest_photograph | 同 ingest_artwork | P1 |
| ingest_diagram | 同 ingest_artwork + 加 layer 标记 (含有结构信息) | P1 |
| ingest_dataset | oprim.parser.parse_dataset (元数据 + 行列统计) | P2 |
| ingest_code | (浅, 文件树扫描 + license 检测 + LOC 统计) | P2 |
| ingest_chat | oprim.parser.parse_chat_export (多平台支持) | P0 |

### 8.4 derivative-generation 流水线规范

derivative 是 substrate 的内部产物 (§5.3), generation 流水线**只读 substrate, 只写其 derivatives/ 子目录**:

```python
class DerivativeConfig(BaseModel):
    substrate_id: str                # 目标 substrate
    derivative_type: str             # 'transcript' / 'summary' / ...
    force_regenerate: bool = False   # 已存在则覆盖
    tool: str | None = None          # 不指定走默认 (例 transcript 默认 whisperx)
    tool_config: dict = {}

class DerivativeResult(BaseModel):
    success: bool
    derivative_path: Path | None
    tool_used: str
    quality_self_assessment: float | None
    cost_usd: float
    duration_seconds: float
    errors: list[dict]
```

**derivative 重生成**: `force_regenerate=True` 时, 旧产物移动到 `derivatives/<type>/_archived_<timestamp>/`, 新产物写入, 旧 derivative.yaml 保留在 archived 目录。这是 D4 可演化性的实施保障。

### 8.5 concept-management 流水线规范

#### extract_entity_candidates (从 substrate 抽取 concept 候选)

```python
class EntityExtractionConfig(BaseModel):
    substrate_ids: list[str] | None = None     # None = 全库
    extraction_types: list[str] = ["person", "event", "place", "work", "organization"]
    llm_provider: str = "anthropic"
    confidence_threshold: float = 0.8

class EntityExtractionResult(BaseModel):
    candidates: list[dict]                      # 候选 concept (未入库)
    suggested_links: list[dict]                 # 建议的 substrate ↔ concept 反链
    cost_usd: float
```

**重要**: 此流水线**只产候选, 不自动入库**。Wiki 审查 `_hub/staging/concept-candidates-<date>.md`, 决定哪些升为正式 concept。

#### concept_backref_update

每次 substrate 入库或更新, 触发此流水线扫描 concept 的"出现于"反链区块, 重新生成。详见 §5.4 反链格式。

### 8.6 trail 事件类型 (Stratum 业务事件)

Stratum 在 obase.trail 上 emit 以下业务事件 (除 obase 标准事件外):

| event | 含义 | 字段 |
|---|---|---|
| `substrate_created` | 新 substrate 入库 | id / medium / slug / source_path |
| `substrate_updated` | substrate 元数据更新 | id / changed_fields |
| `derivative_generated` | derivative 成功生成 | substrate_id / derivative_type / tool |
| `derivative_failed` | derivative 生成失败 | substrate_id / derivative_type / error |
| `concept_created` | 新 concept | id / type / slug |
| `concept_merged` | 两个 concept 合并 | source_id / target_id / reason |
| `concept_backref_updated` | concept 反链区块更新 | concept_id / substrate_count |
| `note_created` | 新 note | id / type / slug |
| `index_updated` | 索引增量更新 | index_name / nodes_added / nodes_removed |
| `lint_violation` | lint 规则检测到违反 | rule_name / node_id / severity |
| `migration_complete` | schema migration 完成 | from_version / to_version / nodes_migrated |

### 8.7 migration 流水线

每次 schema 大版本升级 (例 v0.1 → v0.2) 必须有 migration 流水线:

```python
class MigrationConfig(BaseModel):
    from_version: int
    to_version: int
    dry_run: bool = True              # 默认 dry-run, 不真改文件
    backup: bool = True               # 改前自动 git stash

class MigrationResult(BaseModel):
    success: bool
    nodes_migrated: int
    nodes_failed: list[dict]
    backup_ref: str | None            # git stash 引用
    report_path: Path
```

**v0.1.x → v0.2 migration** 必须处理:
- substrate 重新分类 (按 medium → modality 映射)
- 字段重命名 (`paragraph_ids` → `fragments`)
- 引入 derivative 概念 (transcript / chat 等原 substrate 部分场景重归 derivative)
- schema_version 全部跳到 2

详细 migration 步骤在 `_hub/migration/v0_1_to_v0_2/` (含 SPEC + 脚本入口 + 回归测试)。

---

## §9 消费者接口

### 9.1 接口 A: 文件系统

- **入口**: 直接打开 `~/projects/stratum/` 任意路径
- **用户**: Wiki / Obsidian / Claude Code / VSCode / nvim
- **协议**: markdown + yaml frontmatter + Obsidian 原生 wikilink (§4.3 语法)
- **写权限**: Wiki 直接编辑文件; Claude Code 走 ingest/edit 流水线; Hermes 远程**只读**

### 9.2 接口 B: Obsidian

**vault 配置**:
- vault 根 = `~/projects/stratum/` 仓库根
- 启用核心插件: Graph view / Outgoing links / Backlinks / Tag pane
- 安装自写插件 `stratum-region-jump` (位于 `_hub/obsidian-plugin/`, 见 §9.5)
- 推荐 community 插件: Templater / Dataview / Advanced URI (可选)

**Stratum 特化体验**:
- substrate / concepts / notes 三个根目录在 file explorer 一目了然
- concept 页面的"出现于"反链区块由流水线自动维护, Wiki 不需手写
- substrate 文件夹结构: `original/` (LFS) / `derivatives/` (gitignore 但可见) / `meta.yaml`

### 9.3 接口 C: MCP server

**入口**: `_hub/servers/stratumd.py` (薄包装, 调 omodul)

**启动**:
```bash
cd ~/projects/stratum
python _hub/servers/stratumd.py
```

入口脚本内部:
```python
from obase import bootstrap
from omodul.knowledge import start_mcp_server

bootstrap(env_path=Path(".env"), working_dir=Path(".obase/stratum/"))
start_mcp_server(stratum_root=Path("."), port=7777)
```

**暴露的 MCP tools**:

| tool | 功能 |
|---|---|
| `stratum.search` | 检索, schema 见 §7.3 |
| `stratum.fetch_substrate` | 按 ULID 取 substrate (元数据 + derivative 列表) |
| `stratum.fetch_fragment` | 按 (substrate_id + fragment_id) 取片段内容 |
| `stratum.fetch_concept` | 按 ULID 或 slug 取 concept (含反链) |
| `stratum.list_notes` | 列 notes (可选 type / domain / status 过滤) |
| `stratum.search_concepts` | 按文本搜 concept (slug / title / aliases) |
| `stratum.recent_changes` | 列最近的 substrate / concept / note 变更 |

**远程访问**: Hermes 通过 Tailscale 调用此 MCP server (只读), 走 Singapore VPS (`100.73.220.5`)。

### 9.4 接口 D: HTTP API

**入口**: `_hub/servers/http_server.py`

**用途**: 给将来 Web GUI / 其他工具用, MVP 阶段不强求。

**v1.0 范围**: 至少暴露 `GET /search` / `GET /substrate/<id>` / `GET /concept/<slug>` 三个端点, schema 跟 MCP tools 对齐。

### 9.5 自写 Obsidian 插件 `stratum-region-jump`

**目的**: 让 image region 引用 `[[xiang-yu-portrait__AAA#r0.234-0.567-0.123-0.089]]` 在 Obsidian 中实际跳到图像区域并高亮。

**实现要点**:
- 监听 wikilink 解析事件, 检测 fragment 含 `r<x>-<y>-<w>-<h>` 模式
- 打开目标图像文件, 在图像上叠加红框高亮该区域
- 提供右键菜单"复制 fragment ID"等辅助操作

**位置**: `_hub/obsidian-plugin/stratum-region-jump/`
- main.ts (TypeScript 源码)
- manifest.json (Obsidian 插件 manifest)
- styles.css

**v1.0 范围**: image region 跳转 + 高亮; v1.1 加 video region (视频画面区域+时间) 跳转。

---

## §10 验收标准

### 10.1 8 维度硬指标 (v1.0 验收)

| D | 验收硬指标 |
|---|----------|
| D1 完备性 | 18 个 medium schema 全部存在 + 12 个 derivative schema 全部存在 + 11 个 concept schema 全部存在; P0 + P1 medium 的 ingest 流水线全部跑通至少 1 个真实样本 |
| D2 可寻址性 | 100% substrate 有 ULID + frontmatter 校验通过; 100% wikilink 可解析到目标节点 (lint_wikilink_resolvable 全部通过) |
| D3 可检索性 | 每个 modality (text/audio/image) 至少 1 次真实检索成功 (语义 + 全文 + 元数据三种); RRF 跨 modality 融合 demo 跑通 |
| D4 可演化性 | v0.1.x → v0.2 migration 流水线跑通且全部节点成功迁移; 随机抽 5 个 substrate 用最新工具重新生成 derivative 成功 |
| D5 可审计性 | 100% derivative 有 derivative.yaml 且字段完整; 抽样 10 个 derivative 能追溯到完整生成链 (工具 + 版本 + 时间戳 + 调用 trail) |
| D6 可移植性 | 在测试机重新 clone + LFS fetch + reindex_all 在 60 分钟内完成且 lint 全过 |
| D7 可消费性 | 4 种接入方式 (文件系统 + Obsidian + MCP + HTTP) 全部跑通 smoke test; MCP 7 个 tool 全部返回非空合法结果 |
| D8 抗腐烂性 | 全套 lint 规则 (§6.2) 全部通过; weekly audit 报告生成成功; 模拟 1 个 substrate 删除场景, 反链阻塞机制工作 |

### 10.2 实施过程性指标

每个批次完工时验收:

- 批 1 完成 (v0.0.3): 立宪期, schema 16 个 + 各自 example, 已完成
- 批 2 完成: 实证 4 项 (PDF / 向量库 / embedding / MCP) + obase 实施 + hevi cut-over
- 批 3 完成: 流水线 MVP (P0 + P1 ingest 跑通 + concept 反链 + 索引)
- 批 4 完成: 接口层 (MCP server + HTTP server + Obsidian 插件)
- 批 5 完成: 抗腐烂规则全套 lint + weekly audit
- 批 6 完成: v1.0 verification (8 维度硬指标全过)

### 10.3 Bug 回填规则

任何 bug 修复时必须:
1. 增加复现 test (在 4O 库内, 因为 Stratum 没自己代码)
2. test 在修复前 fail, 修复后 pass
3. 如 bug 是 SPEC 漏洞, 同时修 SPEC 并 bump SPEC 小版本号

### 10.4 验收红线

以下情况**v1.0 不允许**发布:

- 任一 lint 规则失败但被忽略
- 任一 derivative 缺 derivative.yaml
- 任一 wikilink broken
- 任一 medium 的 ingest 流水线"基本可用但有已知 bug"
- Obsidian 插件未完成

宁可推迟 v1.0, 不发布带已知严重瑕疵的版本 (质量为王)。

---

## §11 安全与隐私

### 11.1 本地优先

- 数据物理存储位置: `~/projects/stratum/` (Wiki 本机)
- 索引存储位置: 同上, `_hub/indexes/`
- 备份: Wiki 自行处理 (建议 git remote + LFS 后端 / 本地 NAS / 加密云盘)

### 11.2 Hermes 远程访问

- 协议: Tailscale 私有网络
- 路径: Wiki 本机 ↔ Singapore VPS (`100.73.220.5`) ↔ Hermes
- 权限: **只读** (Hermes 不写)
- 鉴权: Tailscale ACL + MCP server token (随机 32 字节, 配置在 .env)

### 11.3 敏感信息

**入库前必须脱敏**:
- 个人身份证号 / 银行卡号 / 信用卡 / 护照号
- API key / token / 私钥 (无论是 Wiki 自己的还是第三方的)
- 第三方对话中对方个人信息 (如对方未授权公开)

**lint 规则 `lint_sensitive_pattern`**: 静态扫描 substrate / notes, 检测疑似敏感信息 pattern (正则)。检测到立即阻塞 commit 并报告 Wiki。

### 11.4 4O 库的 secret 处理

所有 secret 通过 `.env` 文件管理, **绝不入 git** (`.gitignore` 包含 `.env`)。Stratum 仓库提供 `.env.example` 列必需的 env var 名称 (无 value)。

obase.bootstrap.load_env() 加载 .env 时按 §2.8 处理 (剥离行内注释 / 空值不注入 / URL 校验)。

---

## §12 开发环境

### 12.1 操作系统

- 主开发机: Win11 + WSL2 (Ubuntu 24.04)
- 备用: macOS / Linux 原生

### 12.2 Python 环境

- 版本: ≥ 3.12
- 包管理: `uv` (推荐) 或 `pip`
- 依赖锁: `uv.lock` 入 git

### 12.3 pyproject.toml

```toml
[project]
name = "stratum-instance"
version = "0.0.0"
description = "Wiki's personal multimodal knowledge base (data + config layer)"
requires-python = ">=3.12"
license = {text = "Personal use only"}

dependencies = [
    "obase>=0.1",
    "oprim>=X.Y",                # X.Y 待 4O 扩充后版本号
    "oskill>=X.Y",
    "omodul>=X.Y",
]

[project.optional-dependencies]
dev = ["pytest", "ruff", "mypy"]
```

### 12.4 Git LFS

`.gitattributes`:
```
*.pdf filter=lfs diff=lfs merge=lfs -text
*.epub filter=lfs diff=lfs merge=lfs -text
*.mobi filter=lfs diff=lfs merge=lfs -text
*.djvu filter=lfs diff=lfs merge=lfs -text
*.mp3 filter=lfs diff=lfs merge=lfs -text
*.m4a filter=lfs diff=lfs merge=lfs -text
*.wav filter=lfs diff=lfs merge=lfs -text
*.flac filter=lfs diff=lfs merge=lfs -text
*.ogg filter=lfs diff=lfs merge=lfs -text
*.opus filter=lfs diff=lfs merge=lfs -text
*.mp4 filter=lfs diff=lfs merge=lfs -text
*.mkv filter=lfs diff=lfs merge=lfs -text
*.webm filter=lfs diff=lfs merge=lfs -text
*.mov filter=lfs diff=lfs merge=lfs -text
*.avi filter=lfs diff=lfs merge=lfs -text
*.jpg filter=lfs diff=lfs merge=lfs -text
*.jpeg filter=lfs diff=lfs merge=lfs -text
*.png filter=lfs diff=lfs merge=lfs -text
*.webp filter=lfs diff=lfs merge=lfs -text
*.heic filter=lfs diff=lfs merge=lfs -text
*.tiff filter=lfs diff=lfs merge=lfs -text
*.parquet filter=lfs diff=lfs merge=lfs -text
```

CSV/JSON 视大小决定, lint 规则 `lint_large_file_lfs` 检查超过 1MB 的 csv/json 是否进 LFS。

### 12.5 Obsidian 插件开发

`_hub/obsidian-plugin/stratum-region-jump/`:
- Node.js + TypeScript
- 用 esbuild 打包到 `main.js`
- 测试: 拷贝到任一 Obsidian vault 的 `.obsidian/plugins/` 启用

### 12.6 .env 模板

`.env.example` (入 git):
```
# Anthropic
ANTHROPIC_API_KEY=
ANTHROPIC_BASE_URL=

# embedding providers (示例)
VOYAGE_API_KEY=
BGE_M3_LOCAL_PATH=

# MCP server
STRATUM_MCP_TOKEN=

# Singapore VPS (Hermes 入口)
HERMES_TAILSCALE_IP=100.73.220.5
```

---

## §13 路线图

### 13.1 当前位置 (2026-05-17)

- ✅ 批 1 (立宪 v0.0.1-v0.0.3) 完成
- 🟡 OBASE_SPEC v0.2 完成, 待 hevi advisor 二次 review
- 🟡 STRATUM_SPEC v0.2 (本文档) 完整版完成, 待 hevi advisor review + Wiki sign-off
- ⬜ 批 2 实证 (剩 4 项): PDF / 向量库 / embedding / MCP

### 13.2 v1.0 路径

```
当前
  ↓
批 2 实证 (4 项, ~5 天) + obase 实施 (~2 周) + hevi cut-over (~2 周) [并行]
  ↓
4O 扩充 #1 (Stratum P0 medium 需要的 prim/skill/modul 加进 4O, ~2-3 周)
  ↓
批 3 流水线 MVP (P0 ingest 全跑通, ~3 周)
  ↓
4O 扩充 #2 (P1 medium 需要的元素加进 4O, ~1-2 周)
  ↓
批 4 接口层 (MCP server + HTTP + Obsidian 插件, ~2 周)
  ↓
批 5 抗腐烂 (lint 全套 + weekly audit, ~1 周)
  ↓
批 6 v1.0 verification (8 维度硬指标, ~1 周)
  ↓
v1.0 发布
```

**总时间估算: 12-15 周** (含 obase 实施 + 4O 扩充 + Stratum 数据层 + 接口)

### 13.3 v1.x 路线 (v1.0 后)

- v1.1: video 深度流水线 + interactive-demo medium + data 检索
- v1.2: music / code / thread 流水线完善
- v1.3: 跨 modality 统一语义空间 (CLIP-like, Q3 设计点)
- v1.4: GUI dashboard (基于 HTTP API)

### 13.4 关键里程碑标记

| 里程碑 | 触发条件 |
|---|---|
| M1: obase v0.1 发布 | obase 库 §5.2 PB 专项验收全过 |
| M2: hevi cut-over 完成 | hevi v0.0.x 发布 (cut-over 后) |
| M3: 4O 扩充 #1 完成 | Stratum P0 ingest 流水线全部就位于 4O |
| M4: Stratum 第一次真实入库 | 至少 1 本 book + 1 个 podcast + 1 个 chat 入库, 反链生成, 索引更新 |
| M5: Stratum v1.0 | 8 维度硬指标全过 |

---

## §14 风险登记册

### 14.1 高风险

#### R1: 4O 库 v0.x 期间接口变化导致 Stratum 反复调整

**概率**: 高 (4O 在 v0.x 期间允许 breaking change)
**影响**: Stratum 批 3 流水线建设期间, 4O 接口若变, Stratum 调用代码需调整

**缓解**:
- Stratum 仓库不写代码, 只写"调用 4O 的 yaml config", 接口变更影响小
- obase / 4O 任何 breaking change 必须发 release notes + 提前通知 Stratum
- 重大变更等 obase v1.0 (接口 frozen) 后再做

#### R2: obase 实施延期阻塞 Stratum 启动

**概率**: 中
**影响**: 高 (Stratum 批 3 启动条件)

**缓解**:
- obase 实施由专人主导 (Wiki 协调)
- §4.2 cut-over 模式 hevi 业务推进期间停, 但 obase 实施可全力推进
- 实施期间允许暴露 SPEC 漏洞, 走 v0.2.1 修订

#### R3: hevi cut-over 失败导致 obase v0.1 验收受阻

**概率**: 中
**影响**: 高 (cut-over 同时是 obase 验收)

**缓解**:
- cut-over 期间发现的 obase bug 优先修, 不绕过
- 191 unit test 大部分通过, 失败的逐个分析 (不允许 silent skip)
- 极端情况 cut-over 卡住, obase 单独发布 + 验证, hevi cut-over 延后

### 14.2 中风险

#### R4: 自写 Obsidian 插件实施延期

**概率**: 中 (插件开发对 Wiki 是新领域)
**影响**: 中 (image region 跳转不可用, 但其他功能不受影响)

**缓解**:
- 插件 MVP 范围严格控制 (仅 image region 跳转 + 高亮, 不做额外功能)
- 实施作为批 4 一部分, 不影响批 3 主线
- v1.0 验收硬指标含插件就位, 不允许跳过

#### R5: 多模态 schema 设计在实际入库时发现不合理需要 migration

**概率**: 中-高 (schema 凭直觉设计, 18 个 medium 难以一次到位)
**影响**: 中 (走 v0.2 → v0.3 migration)

**缓解**:
- v0.2 schema 设计基于 §5 充分讨论, 已避免主要问题
- 批 3 入库第一批真实数据时密切观察 schema 适配情况
- migration 流水线 (§8.7) v1.0 必备, 应对未来 schema 演进

### 14.3 低风险

#### R6: PDF 解析器选型不达标

**概率**: 低 (4 个候选都是成熟工具)
**影响**: 高 (substrate 文本质量决定整个知识库基础)

**缓解**: 批 2 实证 #1 充分对比, recommendation 明确

#### R7: 向量库 / embedding 模型变化导致索引重建

**概率**: 低
**影响**: 中

**缓解**: 索引非主数据, 重建脚本 (`reindex_all.sh`) v1.0 必备

---

## §15 决策日志

记录重大决策的演进过程, 便于将来回看"为什么这么决定":

### D-001: 不允许 Stratum 自动结论性判断

**日期**: v0.0.1 (2026-05)
**决策**: Stratum 是"view + judge + record"工具, 不输出结论性判断 (不像 Helios)
**理由**: 知识库目标是支撑思考, 不替代思考

### D-002: 三层架构 (substrate / concepts / notes)

**日期**: v0.0.1
**决策**: 不用单层"all-notes" Obsidian 风格, 而是三层独立图
**理由**: 抗腐烂的关键, source 与 thought 必须分离

### D-003: ULID + slug 双轨命名

**日期**: v0.0.2
**决策**: ULID 不变 + slug 可变, 文件名 `<slug>__<ULID-suffix>`
**理由**: ID 稳定 + 人类可读

### D-004: Obsidian 原生 wikilink 兼容 (放弃扩展语法)

**日期**: v0.0.3
**决策**: 用 `<slug>__<ULID-suffix>` 文件名, wikilink 走 Obsidian 原生
**理由**: 自写 wikilink 解析器 5-8 天 + 长期维护风险, 用 Obsidian 原生能力替代

### D-005: 多模态扩展为 substrate 第一公民

**日期**: v0.2 (2026-05-17)
**决策**: substrate 不只是文本, 含 audio/video/image/data
**理由**: Wiki 校准: 知识载体不限于文本, 顶级标准不能掉这个

### D-006: 4O 生态整合 (Stratum 无项目内代码)

**日期**: v0.2
**决策**: Stratum 仓库不含 Python 包, 代码全部贡献到 4O (oprim/oskill/omodul/obase)
**理由**: Wiki 拍板: 4O 是生态共享库, 项目无所有权, 命名空间统一

### D-007: 自写 Obsidian 插件实现 image region

**日期**: v0.2
**决策**: 不接受"图像区域引用 Obsidian 跳不到"的局限, 自写插件
**理由**: 顶级标准 + 长期主义 + 功能至上, 三原则一致指向

### D-008: v1.0 范围 schema 全到位 + 流水线分批

**日期**: v0.2
**决策**: 18 个 medium schema v1.0 必须就位, 但流水线按 P0/P1/P2 分批实施
**理由**: 长期主义保证架构永久完整, 功能至上保证 v1.0 不爆时间表

---

## §16 v0.2 → v0.3 预期变更

实施过程中, 以下点预期会产生 SPEC 修订:

- §5 medium schema 字段在第一次真实入库后微调 (R5 缓解)
- §7 检索系统在批 2 实证 #2 (向量库) / #3 (embedding) 完成后锁定具体技术栈
- §8.3 ingest 流水线在 4O 扩充完成后, 4O 元素名称定型
- §10 验收硬指标在批 5 lint 实施期间可能加新规则
- §13 路线图按实际进度调整时间估算

v0.3 触发条件: 批 3 流水线 MVP 完成。

---

## §17 Changelog + 术语表

### 17.1 Changelog

#### v0.2 (2026-05-17)

**触发**: Wiki 多轮校准 — 多模态盲区 + 4O 生态整合 + 三原则确立 (长期主义 / 质量为王 / 功能至上)

**变更**:
- 范围: 文本中心 → 多模态 (text/audio/video/image/data)
- substrate medium 从 5 个扩展到 18 个 (新增 thread/music/code 等)
- 引入 derivative 概念 (12 type), 处理形态转换
- concept type 从 7 个扩展到 11 个 (新增 work/organization/system/dataset-source)
- Fragment ID 系统扩展为多 modality 通用
- 代码组织从 "Stratum 有自己的代码层" 改为 "Stratum 调用 4O 共享库"
- Stratum 仓库不再有 Python 包, 全部代码贡献到 oprim/oskill/omodul/obase
- Obase 作为 4O 第 4 库新建, SPEC 独立 (OBASE_SPEC v0.2)
- 自写 Obsidian 插件 `stratum-region-jump` 实现 image region 跳转
- v1.0 时间表从 3-5 周延后到 12-15 周, 含 obase 实施 + 4O 扩充

#### v0.1.2 (2026-05-16)
**触发**: 实证项 #4 决策 (Wiki 跳过手动 Obsidian 测试, chief advisor 判断)
- §4.3 完全重写: wikilink 改为 Obsidian 原生兼容 `[[<slug>__<ULID-suffix>|display]]`
- 段落锚点改用 `## para-<suffix>` heading 形式
- 实证项 #4 (Obsidian 兼容性) 通过架构调整解除

#### v0.1.1 (2026-05-16)
**触发**: 批 1 (立宪) 完工反馈, 4 处 SPEC 反馈处理
- webpage authors_or_site 拆 site_name + authors
- ingested_by 加 "pipeline"
- references 适用范围澄清
- wikilink 改 Obsidian 原生兼容

#### v0.1.0 (2026-05-16)
**触发**: 立宪期完工
- 16 个 schema (substrate × 5, concept × 6, note × 5)
- 各 schema 配 valid/invalid examples
- schema_selfcheck.py 自检脚本

### 17.2 术语表

| 术语 | 含义 |
|---|---|
| Substrate | 原始素材层 (Layer 1), 18 种 medium |
| Concept | 概念图层 (Layer 2), 11 种 type |
| Note | 笔记层 (Layer 3), 5 种 type |
| Medium | substrate 的载体类型 (book / podcast / artwork / dataset / ...) |
| Modality | substrate 的根本形态 (text / audio / video / image / data) |
| Derivative | substrate 的衍生物 (transcript / summary / keyframes / ...) |
| Fragment | substrate 的内部片段 (段落 / 音频时段 / 视频时段 / 图像区域 / 数据行列) |
| Fragment ID | fragment 的稳定标识符, 格式按 modality 不同 |
| 4O | oprim + oskill + omodul + obase 四个共享库 |
| _hub | Stratum 仓库的协调层 (元数据 + 配置 + 索引 + 入口脚本) |
| Trail | obase.trail 维护的决策日志, 每次流水线运行产一份 |
| RRF | Reciprocal Rank Fusion, 跨 modality 检索融合算法 |
| Cut-over | 不留兼容 alias 的直接替换迁移模式 (来自 OBASE_SPEC §4.2) |

---

**End of STRATUM_SPEC v0.2**

**待办**:
- [ ] hevi advisor 二次 review (OBASE_SPEC v0.2 + STRATUM_SPEC v0.2 + 4O 扩充清单 v0.1 联合 review)
- [ ] Wiki sign-off
- [ ] obase 库实施启动 (见独立的 obase 实施指令书)
- [ ] hevi cut-over (待 obase v0.1.0 发布后启动)
- [ ] 4O 扩充实施 (Stratum 需要的 ~80 个新元素分 Phase 推进)
- [ ] Stratum 数据层批 2 实证完成
- [ ] Stratum 批 3 流水线 MVP 启动 (依赖 obase + 4O 扩充 Phase 1 完成)
