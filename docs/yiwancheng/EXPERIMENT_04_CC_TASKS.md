# EXPERIMENT_04_CC_TASKS.md

**项目**: Stratum 实证项 #4 — Obsidian wikilink 兼容性
**执行者**: Claude Code (FULL AUTO)
**Wiki 角色**: 启动 + 验收
**预期产物**: 测试文件 + T7 评估报告 + CONCLUSION.md (Step 5 部分填充)

---

## 总览

本指令书包含 CC 在实证项 #4 中负责的 3 段任务,与 Wiki 手动测试 (`EXPERIMENT_04_WIKI_MANUAL.md`) 配合完成完整实证。

```
Step 1 (CC, 现在)        → 生成测试文件
Step 2-3 (Wiki, 手动)    → Obsidian 内测试 T1-T6
Step 4 (CC, 并行)        → T7 自写插件可行性评估
Step 5 (CC, Wiki 测完后) → 汇总 CONCLUSION.md
```

CC 可以在 Wiki 做 Step 2-3 期间并行跑 Step 4。Step 5 必须等 Wiki 完成 Step 2-3。

---

## FULL AUTO 头部规则

**红线**:

1. 测试文件**仅放在 `experiments/04-obsidian-wikilink/` 目录下**, 不能污染 `substrate/` / `concepts/` / `notes/` 三层
2. 当前 git 分支必须是 `experiment/04-obsidian-wikilink`, 不能在 main 上跑
3. 生成的文件用**虚构 ULID** (`01HY0000000000000000000001` 这种规律性的占位 ULID),不要生成看起来真实的 ULID 污染将来的真数据
4. 不允许修改 `_hub/STRATUM_SPEC.md`,所有 SPEC 反馈累积到 Step 5 的 CONCLUSION.md 中
5. 不允许 `git push`

**stop on failure**: 任一步失败立即停止报告。

---

## Step 1: 生成测试文件 (~20 分钟)

### 1.1 前置检查

```bash
# 必须在 experiment 分支
git branch --show-current
# 期望: experiment/04-obsidian-wikilink

# 如果不在,创建并切换
git checkout -b experiment/04-obsidian-wikilink
```

### 1.2 创建目录结构

```
experiments/04-obsidian-wikilink/
├── README.md                    # 实证目的 + 文件清单
├── concepts/
│   ├── people/
│   │   ├── xiang-yu__A1B2C3D4.md
│   │   └── liu-bang__B2C3D4E5.md
│   └── events/
│       └── hongmen-yan__C3D4E5F6.md
├── notes/
│   └── readings/
│       └── on-xiang-yu-tragedy__N1O2P3Q4.md
├── substrate/
│   └── books/
│       └── shiji-007__S1T2U3V4.md
└── results/                    # 空目录, Wiki 手动测试时填
    └── .gitkeep
```

### 1.3 .gitignore 更新

在 stratum 根目录 `.gitignore` 末尾追加:

```
# 实证项工作目录 (不入主分支)
experiments/*/results/
```

注意: `experiments/04-obsidian-wikilink/` 本身入 git (在 experiment 分支), 只是 `results/` 不入 (那是 Wiki 测试的截图和私人笔记)。

### 1.4 测试文件内容规格

**虚构 ULID 表 (本次实证统一使用)**:

| 文件 | ULID | slug |
|------|------|------|
| 项羽 (concept person) | `01HY0000000000000000000001` | xiang-yu |
| 刘邦 (concept person) | `01HY0000000000000000000002` | liu-bang |
| 鸿门宴 (concept event) | `01HY0000000000000000000003` | hongmen-yan |
| 项羽悲剧 (note reading) | `01HY0000000000000000000004` | on-xiang-yu-tragedy |
| 史记·项羽本纪 (substrate book chapter) | `01HY0000000000000000000005` | shiji-007 |

**ULID 后缀 (文件名用):**

| 文件 | ULID 后缀 |
|------|----------|
| xiang-yu | A1B2C3D4 |
| liu-bang | B2C3D4E5 |
| hongmen-yan | C3D4E5F6 |
| on-xiang-yu-tragedy | N1O2P3Q4 |
| shiji-007 | S1T2U3V4 |

**文件 1: `concepts/people/xiang-yu__A1B2C3D4.md`**

```markdown
---
id: "01HY0000000000000000000001"
slug: "xiang-yu"
title: "项羽"
type: "person"
aliases: ["项籍", "西楚霸王", "项王"]
born: -232
died: -202
domains: ["history.china.qin-han"]
schema_version: 1
created_at: "2026-05-16T10:00:00+08:00"
related_concepts:
  - id: "01HY0000000000000000000002"
    slug: "liu-bang"
    relation: "rival"
  - id: "01HY0000000000000000000003"
    slug: "hongmen-yan"
    relation: "participant_in"
---

# 项羽

项羽 (前232-前202),名籍,字羽,下相人。秦末农民起义领袖,西楚霸王。

主要事迹见 [[substrate/01HY0000000000000000000005/shiji-007|《史记·项羽本纪》]],
其中关键事件包括 [[concept/01HY0000000000000000000003/hongmen-yan|鸿门宴]] 和垓下之围。

最大政治对手是 [[concept/01HY0000000000000000000002/liu-bang|刘邦]]。

## 关联笔记

[[note/01HY0000000000000000000004/on-xiang-yu-tragedy|我对项羽悲剧的反领导力分析]]

## 对照: 标准 wikilink (控制组)

这是一个标准 Obsidian wikilink: [[liu-bang]]
这是按文件名引用: [[liu-bang__B2C3D4E5]]
```

**文件 2: `concepts/people/liu-bang__B2C3D4E5.md`**

```markdown
---
id: "01HY0000000000000000000002"
slug: "liu-bang"
title: "刘邦"
type: "person"
aliases: ["汉高祖", "刘季"]
born: -256
died: -195
domains: ["history.china.qin-han"]
schema_version: 1
created_at: "2026-05-16T10:00:00+08:00"
---

# 刘邦

刘邦 (前256-前195),沛县人。汉朝开国皇帝。

主要对手是 [[concept/01HY0000000000000000000001/xiang-yu|项羽]],
在 [[concept/01HY0000000000000000000003/hongmen-yan|鸿门宴]] 上险些被杀。
```

**文件 3: `concepts/events/hongmen-yan__C3D4E5F6.md`**

```markdown
---
id: "01HY0000000000000000000003"
slug: "hongmen-yan"
title: "鸿门宴"
type: "event"
date_start: "-206-12"
date_end: "-206-12"
domains: ["history.china.qin-han"]
schema_version: 1
created_at: "2026-05-16T10:00:00+08:00"
participants:
  - id: "01HY0000000000000000000001"
    slug: "xiang-yu"
    role: "主角"
  - id: "01HY0000000000000000000002"
    slug: "liu-bang"
    role: "主角"
---

# 鸿门宴

公元前 206 年,项羽与刘邦在鸿门会面的事件,被视为楚汉相争转折点。

原文记载: [[substrate/01HY0000000000000000000005/shiji-007#A1B2C3|《史记·项羽本纪》开篇段落]]
和 [[substrate/01HY0000000000000000000005/shiji-007#A1B2C4|第二段]]。

主要参与者: [[concept/01HY0000000000000000000001/xiang-yu|项羽]] 与
[[concept/01HY0000000000000000000002/liu-bang|刘邦]]。
```

**文件 4: `notes/readings/on-xiang-yu-tragedy__N1O2P3Q4.md`**

```markdown
---
id: "01HY0000000000000000000004"
slug: "on-xiang-yu-tragedy"
title: "项羽悲剧的反领导力分析"
type: "reading"
created_at: "2026-05-16T10:00:00+08:00"
last_modified_at: "2026-05-16T10:00:00+08:00"
schema_version: 1
status: "active"
domains: ["history.china.qin-han", "leadership"]
references:
  substrate:
    - id: "01HY0000000000000000000005"
      paragraph_ids: ["A1B2C3", "A1B2C4", "A1B2C5"]
  concepts:
    - id: "01HY0000000000000000000001"
    - id: "01HY0000000000000000000003"
---

# 项羽悲剧的反领导力分析

阅读 [[substrate/01HY0000000000000000000005/shiji-007|《史记·项羽本纪》]] 后,
对 [[concept/01HY0000000000000000000001/xiang-yu|项羽]] 的领导风格反思如下:

## 关键事件

[[concept/01HY0000000000000000000003/hongmen-yan|鸿门宴]] 错失杀刘邦机会,
对应原文 [[substrate/01HY0000000000000000000005/shiji-007#A1B2C3|第 1 段]] 至
[[substrate/01HY0000000000000000000005/shiji-007#A1B2C5|第 3 段]]。

## 反领导力模式

1. 缺乏决断 (鸿门宴范增三举玦)
2. 不善纳谏 (杀宋义、亚父出走)
3. 妇人之仁 (放走刘邦)

## 对照组

标准 wikilink (应工作): [[xiang-yu__A1B2C3D4]]
另一种引用方式: [[xiang-yu]]
```

**文件 5: `substrate/books/shiji-007__S1T2U3V4.md`**

```markdown
---
id: "01HY0000000000000000000005"
slug: "shiji-007"
title: "史记·项羽本纪 (节选)"
type: "book"
schema_version: 1
created_at: "2026-05-16T10:00:00+08:00"
authors: ["司马迁"]
note: "本文件为实证目的的节选, 非完整入库"
---

# 史记·项羽本纪 (节选)

> 本文件用于测试段落锚点 (paragraph anchor) 在 Obsidian 中的跳转能力。
> 段落 ID 用 `<a id="...">` 形式嵌入。

<a id="A1B2C3"></a>

**第 1 段**: 项籍者,下相人也,字羽。初起时,年二十四。其季父项梁,梁父即楚将项燕,为秦将王翦所戮者也。项氏世世为楚将,封于项,故姓项氏。

<a id="A1B2C4"></a>

**第 2 段**: 项籍少时,学书不成,去学剑,又不成。项梁怒之。籍曰: 「书足以记名姓而已。剑一人敌,不足学,学万人敌。」于是项梁乃教籍兵法,籍大喜,略知其意,又不肯竟学。

<a id="A1B2C5"></a>

**第 3 段**: 项梁尝有栎阳逮,乃请蕲狱掾曹咎书抵栎阳狱掾司马欣,以故事得已。项梁杀人,与籍避仇于吴中。

<a id="A1B2C6"></a>

**第 4 段**: 吴中贤士大夫皆出项梁下。每吴中有大繇役及丧,项梁常为主办,阴以兵法部勒宾客及子弟,以是知其能。

<a id="A1B2C7"></a>

**第 5 段**: 秦始皇帝游会稽,渡浙江,梁与籍俱观。籍曰: 「彼可取而代也。」梁掩其口,曰: 「毋妄言,族矣! 」梁以此奇籍。
```

**文件 6: `experiments/04-obsidian-wikilink/README.md`**

```markdown
# 实证项 #4: Obsidian wikilink 兼容性

## 目的
验证 STRATUM_SPEC §4.3 设计的扩展 wikilink 语法在 Obsidian 中是否可用。

## 测试文件

5 个测试文件构成相互引用的小型知识网:

- `concepts/people/xiang-yu__A1B2C3D4.md` — 项羽
- `concepts/people/liu-bang__B2C3D4E5.md` — 刘邦
- `concepts/events/hongmen-yan__C3D4E5F6.md` — 鸿门宴
- `notes/readings/on-xiang-yu-tragedy__N1O2P3Q4.md` — 反领导力分析
- `substrate/books/shiji-007__S1T2U3V4.md` — 史记节选 (含 5 个段落锚点)

引用关系:
```
项羽 ←→ 鸿门宴 ←→ 刘邦
  ↑        ↑
  └──────── note (反领导力)
            │
            ↓
        史记·项羽本纪 (段落 A1B2C3-A1B2C7)
```

## 三种 wikilink 形式 (混合在测试文件内)

1. **标准** (对照组): `[[liu-bang]]` 或 `[[xiang-yu__A1B2C3D4]]`
2. **扩展无段落**: `[[concept/01HY.../xiang-yu|项羽]]`
3. **扩展含段落**: `[[substrate/01HY.../shiji-007#A1B2C3|开篇段落]]`

## 如何使用

详见 `EXPERIMENT_04_WIKI_MANUAL.md`。
```

### 1.5 Step 1 验收

- ☐ 6 个文件全部创建
- ☐ git status 显示 5 个新文件 + .gitignore 修改
- ☐ `experiments/04-obsidian-wikilink/results/.gitkeep` 存在
- ☐ commit: `experiment(04): add testfiles for Obsidian wikilink compatibility`

---

## Step 4: T7 自写插件可行性评估 (~45 分钟, 与 Step 2-3 并行)

### 4.1 任务

不实际写插件, 只输出一份可行性评估报告。

### 4.2 阅读材料

**必读** (这是 Anthropic 网络白名单内能访问的内容, 如不能直接 fetch, 用 Wiki 已知 / 训练数据):

- https://docs.obsidian.md/Plugins/Getting+started/Build+a+plugin
- https://docs.obsidian.md/Reference/TypeScript+API/Plugin
- Obsidian Plugin API 中关于 `MetadataCache` 和 `Workspace` 的部分

### 4.3 评估要点

回答以下问题, 每题简短回答 (不超过 3 段):

1. **API 支持度**: Obsidian Plugin API 是否提供 "拦截并自定义 wikilink 解析" 的能力?
   - 如有, 接口名是什么?
   - 如无, 是否有 workaround (例如 MutationObserver 监听 DOM, 或 markdown post-processor)?

2. **解析 ULID 路径的复杂度**:
   - 给定 `[[concept/01HY.../xiang-yu|项羽]]`, 写出解析这个字符串提取出 layer/ULID/slug 的伪代码
   - 估算这个解析在 Obsidian 渲染单文件时调用 1000 次的性能开销

3. **跳转目标定位**:
   - 给定 ULID, 如何在 vault 内定位对应文件?
   - 方案 A: 扫全库 frontmatter (每次跳转都扫)
   - 方案 B: 构建一次性 ID→path 索引, 缓存
   - 方案 B 在文件改名/移动时如何保持更新?

4. **graph view 集成**:
   - Obsidian graph view 的数据源来自 MetadataCache
   - 自定义 wikilink 解析后, 能否注入到 MetadataCache 让 graph 显示扩展引用?
   - 如不能, graph view 永远无法显示扩展 wikilink 关联线 — 这是 hard limitation 还是可绕过?

5. **工作量估算**:
   - MVP 版本 (只支持跳转, 不集成 graph view): 估算开发工作量 (天)
   - 完整版本 (含 graph view + hover preview + auto-complete): 估算开发工作量 (天)
   - 长期维护风险 (Obsidian API 升级导致插件失效的概率)

### 4.4 输出

`experiments/04-obsidian-wikilink/results/T7-自写评估.md`, 结构:

```markdown
# T7: 自写 Obsidian 插件可行性评估

## 1. API 支持度
[答]

## 2. 解析 ULID 路径
[答]

## 3. 跳转目标定位
[答]

## 4. graph view 集成 (关键判断)
[答]

## 5. 工作量估算

| 范围 | 工作量 | 维护风险 |
|------|--------|---------|
| MVP (跳转) | N 天 | 低/中/高 |
| 完整 (含 graph) | N 天 | 低/中/高 |

## 结论

[推荐: 自写 / 不自写 / 自写但仅 MVP]
[如自写, 是否阻塞批 3-4 启动]
```

### 4.5 Step 4 验收

- ☐ `results/T7-自写评估.md` 存在
- ☐ 5 个问题全部回答
- ☐ 工作量估算给具体数字 (不允许 "不清楚")
- ☐ 给出明确推荐

---

## Step 5: 汇总 CONCLUSION.md (~15 分钟, Wiki 完成 Step 2-3 后)

### 5.1 触发条件

Wiki 必须先告知 CC: "Step 2-3 完成, results/ 下有 T1-T6 的结果文件"。

CC 检查 `experiments/04-obsidian-wikilink/results/` 应有:
- T1-原生.md
- T2-Various-Complements.md
- T3-Better-Wikilink.md
- T4-Dataview.md
- T5-FrontMatterTitle.md
- T6-DataviewJS.md
- T7-自写评估.md (CC 自己 Step 4 已生成)

任一缺失 → 报告 Wiki 补齐, 不要自己脑补结论。

### 5.2 阅读所有 T1-T7 结果

逐份读完, 提取每份的:
- PASS / FAIL / PARTIAL 判定
- Q1-Q5 的对应答案
- 关键发现 / 限制

### 5.3 生成 CONCLUSION.md

输出到 `experiments/04-obsidian-wikilink/results/CONCLUSION.md`:

```markdown
# 实证项 #4 结论 — Obsidian wikilink 兼容性

## 1. Q1-Q5 答案汇总

| Q  | 问题                                     | 答案 | 最佳方案 (T<N>) | 证据 |
|----|----------------------------------------|------|----------------|------|
| Q1 | 标准 Obsidian 能否点击扩展 wikilink 跳转? | ?  | T?             | results/T?.md |
| Q2 | graph view 能否识别扩展 wikilink?           | ?  | T?             | ... |
| Q3 | 段落锚点 #A1B2C3 能否跳转?                  | ?  | T?             | ... |
| Q4 | 重命名文件 (改 slug) 后引用是否跟随?         | ?  | T?             | ... |
| Q5 | 哪个方案让以上 4 项都成立?                   | ?  | T?             | ... |

## 2. 推荐路径

[基于 T1-T7 结果, 选定 SPEC 落地路径]

可能的结论之一:
- A. T<N> + <插件名> 完全胜任 → SPEC §4 不变, 推荐写入 SPEC v0.2
- B. T<N> 部分胜任, 需补 X → SPEC §4.3 微调, 加注 "需配合 X 插件"
- C. T1-T6 全失败, T7 自写 MVP 工作量 N 天 → SPEC §4 保留, 批 4 加自写插件子任务
- D. T1-T7 全失败 → SPEC §4 重新设计 (降级方案 A/B/C)

## 3. 对 SPEC 的修订建议

[具体列出哪些条款需修订, 给修订草案. 例如:]
- §4.3 wikilink 语法: [保留 / 改为 ... / 完全重写]
- §13.4 (批 4 接口层): [是否新增 "自写 Obsidian 插件" 子任务]
- §14.3 (单点风险): [本风险已解除 / 仍存在 / 转移到 ...]

## 4. 对项目时间表的影响

- 对批 2 时间表: +N 天 / 不影响
- 对批 3 启动: 阻塞 / 不阻塞
- 对 hevi 集成 (HEVI_REVISION_REQUEST P0-1): 无影响 (hevi 不直接消费 wikilink)

## 5. 给 chief advisor 的反馈触发

[如有以下情况, 标 ⚠️ 让 chief advisor review:]
- 任一关键插件被废弃或不可用
- 发现了 SPEC §4.3 未考虑的语法二义性
- 工作量估算 > §13 路线图预算 50%

## 6. 附: T1-T7 完整结果索引

- [T1: 原生 Obsidian](T1-原生.md) — <一句话总结>
- [T2: Various Complements](T2-Various-Complements.md) — <一句话总结>
- ...
- [T7: 自写评估](T7-自写评估.md) — <一句话总结>
```

### 5.4 Step 5 验收

- ☐ CONCLUSION.md 存在
- ☐ Q1-Q5 全部有明确答案 (不允许 "未知")
- ☐ 给出推荐路径 (A/B/C/D 之一或自定义)
- ☐ 对 SPEC 修订建议具体 (条款编号 + 修订内容)
- ☐ 不擅自改 SPEC, 修订留给 chief advisor + Wiki review

---

## 任务末尾报告

CC 在三段任务都完成后, 在对话中输出:

```
## 实证项 #4 CC 任务完工报告

### Step 1: 测试文件生成
- 状态: ✅/❌
- 6 个文件创建情况: ...
- commit hash: ...

### Step 4: T7 自写评估
- 状态: ✅/❌
- 关键结论: <一句话>
- 推荐: <自写 / 不自写>

### Step 5: CONCLUSION 汇总
- 状态: ✅/❌ (等 Wiki 完成 Step 2-3 才能跑)
- 最终路径推荐: A/B/C/D
- SPEC 修订建议数量: N 处

### SPEC 反馈
[实证过程中发现的 SPEC 不一致, 累积到这里, 不擅自改]

### 不确定项
[需要 Wiki 或 chief advisor 决定的事]
```

---

**End of EXPERIMENT_04_CC_TASKS.md**
