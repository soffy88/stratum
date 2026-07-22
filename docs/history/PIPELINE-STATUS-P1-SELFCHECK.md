# P1 出口判据逐条自评（不自宣通过）· W-H1a-4 · 2026-07-22

> 判据源：OWNER-PLAN P1 行 + ARC-SPEC §4.5。**PASS = 已达且有据；PENDING = 未达/部分，不粉饰**。总判：**P1 未收口**（多项 PENDING）。

| # | 出口判据 | 自评 | 据 / 缺口 |
|---|---|---|---|
| 1 | 语料在库可寻址（ULID） | ✅ **PASS** | 左传全书/史记13篇/通鉴卷1 raw 全文 + 国语/战国策/三国志快照 = 5210 段，para_ulid 可寻址；harness 验 ULID 格式/解析 |
| 2 | 引文机核 100% | 🟡 **PENDING** | **在库源 100%**（OP-D033 口径：20 account+5 论点全 HIT）；但**全 60 account 仅 20 backfill**——三国志（限流）/水经注/国语其余/史记卷65 **PENDING 续抓**；竹书/战国策**源级豁免**。全量非 100% |
| 3 | 抽取器定型报告（含落选数据） | ✅ **PASS** | qwen3-8b 定型（EXTRACTOR-SELECTION），含 qwen2.5vl/llama3.2 落选数据 + Qwen3 获取/VRAM 实测 |
| 4 | 抽取器 P/R 过基线 | 🟡 **PENDING** | **结构 P 达线**（valid-JSON/type-enum 双 100%，≥30 held-out）；但『P/R 基线』未正式定义，注册表解析率随覆盖浮动（22–76%）；**全自动未放行**（门槛：注册表扩容稳定 + 同一性一致率） |
| 5 | 回归网零倒退 | ✅ **PASS** | 未触任何 gold；harness 25 fixtures+6 samples+corpus+arc ALL GREEN；抽取候选全 is_gold=false |
| 6 | 首批 100 事件抽检包送裁 | 🟡 **PENDING** | **86/100**（两批累计，采样重叠）；抽检包送裁（事件+解析+同一性记录）；续跑至 100 无阻，本波预算未凑满 |
| 7 | 同一性判定一致率 | 🟡 **PENDING** | 采样非 gold 重叠段（合『非重叠优先』）故 0 匹配；正式一致率需 P2 同一性管线 + gold-passage held-out |
| （附）| PERSON-INTAKE + 解析率趋势 | ✅ **PASS** | 协议成文；76 条入库（可回滚）；person 解析率 5%→76% 趋势坐实 |

**总判（自评）**：P1 **未收口**——3 PASS / 4 PENDING。核心 PENDING = ①机核全量（三国志限流受阻）②100 事件补齐③全自动放行（注册表/同一性）。均为**受阻/续作**项，非能力缺口。**不自宣 P1 通过**，送顾问/Wiki 终裁。
