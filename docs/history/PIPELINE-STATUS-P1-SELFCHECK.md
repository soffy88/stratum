# P1 出口判据自评（按 OP-D-036 新判据）· W-H1a-5 · 不自宣通过

> **判据源**：OP-D-036（W-H1a-5 权威重定域）——『同一性判定一致率』与『全自动放行』**移为 P2 入口件**，不再是 P1 门。**P1 出口 = 下列 6 项**。**PASS = 已达且有据；PENDING = 未达/部分，不粉饰**。终裁归 Wiki（据本表）。
> （前身：W-H1a-4 旧判据表 3PASS/4PENDING，随 OP-D-036 重定域作废，git 史留痕。）

| # | P1 出口判据（OP-D-036） | 自评 | 据 / 缺口 |
|---|---|---|---|
| 1 | 语料在库可寻址（ULID） | ✅ **PASS** | 左传全书 2954 段 / 史记 14 篇 2148 段 / 通鉴卷1 118 段 / 三国志 261 段 / 国语·战国策快照 = **5485 段**，para_ulid 可寻址；harness 验 ULID 格式+解析 |
| 2 | 在库源机核 100%（豁免清单显式） | ✅ **PASS** | **在库源 56/56 account 全 HIT（100%）**（三国志命名 bug 修正解锁 F3/F5/F6/F7/F8/F15/F17/F18；**2026-07-23 dump 收口再 +2**：水经注江水注/战国策苏秦策入库锚定，**PENDING 清零**，OP-D-044）；**源级豁免显式**：4 竹书古本（辑佚无 canonical 白文）。弧 5 论点全 HIT。清单 `corpus/SOURCE-MACHINE-CHECK-STATUS.md` |
| 3 | 抽取器定型（半自动档） | ✅ **PASS** | qwen3-8b 定型（OP-D-029），字段均 0.94，半自动偏自动档；报告 `arc/EXTRACTOR-SELECTION-W-H1a.md`（含落选数据/VRAM/获取路径） |
| 4 | 100 新事件送裁 | ✅ **PASS** | 三批累计 **133 唯一事件**（≥100），全 is_gold=false，抽检包送裁（`extract/*.json` + README） |
| 5 | 回归网零倒退 | ✅ **PASS** | 未触任何 gold；harness 25 fixtures+6 samples+corpus(5485)+arc ALL GREEN；抽取候选全 is_gold=false |
| 6 | PERSON-INTAKE 运转 | ✅ **PASS** | 协议成文 + 工具 + 修订（OP-D-038 繁简归一/X氏 referent-ambiguous）；批 W-H1a-4-001 入库 71 条（可回滚），解析率 5%→76% 趋势 |

**总判（自评，不自宣通过）**：**6/6 判据 PASS**（按 OP-D-036 重定域后）。**残留（2026-07-23 dump 收口后销）**：~~2 无开放白文 account（水经注/苏秦策）待 dump~~ → **dump 已完成、两 account 入库锚定、PENDING 清零（OP-D-044，56/56 机核）**；同一性一致率/全自动放行已移 P2。

> **不自宣 P1 通过**：本表 6 PASS 系 CC-B 自评，**P1 收口终裁归 Wiki**（据本表 + 各佐证件）。
