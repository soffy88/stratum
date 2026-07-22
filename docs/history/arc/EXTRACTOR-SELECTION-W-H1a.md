# 抽取器选型定型报告（ARC-SPEC §4.4）· W-H1a-1 · 2026-07-22

> 判定人：顾问 Claude（Wiki 全权授权）。评测脚本 `tools/history/eval_extractor.py`（held-out，gold 结构不入 prompt，仅史料白文入）。D-026：云端 API 禁用，候选限本地。

## 1. VRAM 实测（记忆纠偏）

`nvidia-smi` 实测本机 = **RTX 3080 · 10240 MiB · 空闲 9488 MiB**（健康）。⚠ 与记忆 `aii-embed-shared-service`/`aii-gpu-hardware-fault` 所载『1050Ti 3GB / Xid79 故障』**不符**——那些指笔记本副机；**本机 3080 可上 8B/14B 量化档**。VRAM 非瓶颈。

## 2. 候选集（实测圈定）· ★意向候选不可得

ARC-SPEC §4.4 意向 = Qwen3 系 8B/14B 量化档。**实测：ollama registry pull 被出网代理拦**（`registry.ollama.ai` → `fault filter abort`），**Qwen3-8B/14B 无法拉取**。候选降为**在机已有本地模型**：

| 模型 | 参数/量化 | 大小 | 可用 |
|---|---|---|---|
| qwen2.5vl:7b | 7B VL（Q4） | 6.0 GB | ✅ 在机 |
| qwen2.5vl:3b | 3B VL（Q4） | 3.2 GB | ✅ 在机 |
| llama3.2:latest | 3B | 2.0 GB | ✅ 在机（文言弱） |
| ~~Qwen3-8B/14B~~ | — | — | ❌ **pull 被代理拦（PENDING·需解代理）** |

## 3. held-out 评测结果（5 段 × 3 模型，字段级命中）

防污染：prompt 仅史料白文，gold 事件结构/判定不入。5 段 = 左传哀14(F10)/通鉴命侯(F24)/左传哀9(F20)/史记晋世家(F25)/战国策魏一(F22)。

| 模型 | title | person | place | type | 字段均 | 日期 |
|---|---|---|---|---|---|---|
| qwen2.5vl:7b | 1/5 | **5/5** | **5/5** | **4/5** | 0.75 | ✗ 编造 |
| qwen2.5vl:3b | 3/5 | 4/5 | 4/5 | 4/5 | 0.75 | ✗ 编造 |
| llama3.2:latest | **5/5** | 4/5 | 5/5 | 2/5 | 0.80 | ✗ 编造 |

## 4. ★关键发现（落选数据 + 设计验证）

1. **全部模型编造/错配年份**：弑简公（前481）被判『前403』，吴城邗（前486）亦『前403』——模型把年份**幻觉锚定**。这**验证 KU-SPEC 设计**：`canonical_date` 走 **chronology 注册表 override**，**不由抽取器从白文产出**；抽取器只该产『事件+人物+地点+类型』，date 留注册表解析。评测据此判定：**date 字段不纳入抽取器验收指标**（改由注册表解析段负责）。
2. **title/type 各有短板**：qwen2.5vl:7b 常返 null title（1/5）但 person/place/type 最稳；llama3.2 title 满分却 type 仅 2/5（弑简公/公室卑/索地 误判类型）、且文言人名易错（『齐桓王』幻觉）。3B VL 最均衡但整体弱。
3. **n=5 过小**：字段均 0.75–0.80 之差无统计意义；无一模型达『可直接产 gold』的稳定度（尤其 title/type/date 三项）。

## 5. 定型裁决

- **不定型任一模型为『自动产 gold』抽取器**——三候选均未达生产基线（date 全废、title/type 不稳），且**意向候选 Qwen3-8B/14B 因代理未得**（评测仅在 fallback 档进行）。
- **定档 = 半自动（OWNER-PLAN 风险表退路）**：由 **qwen2.5vl:7b**（person/place/type 最稳者）产**抽取候选**，date 空缺留注册表解析，**顾问审重**判 gold。抽取候选**永不直接成 gold**（§4.4 红线）。
- **重开全自动条件**：① 解出网代理、拉 Qwen3-8B/14B（或更强文言模型）重评；② held-out 扩到 ≥25 段；③ title/type ≥0.9 且注册表解析段接管 date。**均 PENDING**。
- **回归网影响**：本波未以抽取候选改动任何 gold，A 类回归网**零倒退**（未触 gold）。
