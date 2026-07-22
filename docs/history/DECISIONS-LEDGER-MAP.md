# 决策日志映射表（账本合并 · 裁决 3）· 2026-07-22

> **问题**：历史线曾有**两本决策日志各自从 D 号起编**，号段重叠——① KU 线 `DECISIONS.md`（D-001..D-023）② 治理线 `HISTORY-VIDEO-OWNER-PLAN-001.md` 附录 D（D-023..D-032）。`D-023`..`D-027` 在两本里**指不同决策**（如 D-024 = KU 无 / OP『Arc 命名』；D-023 = KU『F1 撤 cf』 / OP『闸口顾问化』）。
> **合并（裁决 3）**：**不重排既有正文号**（避免改动已被 commit 引用的号），改用**命名空间前缀 + 指针化 + 曾用号**：
> - **`KU-Dxxx`** = KU 线（canonical 正文在 `DECISIONS.md`，契约/gold/fixtures 层）。
> - **`OP-Dxxx`** = 治理线（canonical 正文在 OWNER-PLAN 附录 D，全权委托后的治理/管线/抽取器层）。
> - 正文内的裸 `D-xxx` **曾用号**保留原样（不改字节），语义以本表 + 前缀为准。今后新决策一律带前缀入册。

## 命名空间与指针

| 命名空间 | canonical 正文 | 号段 | 层 |
|---|---|---|---|
| `KU-D001..KU-D023` | `docs/history/DECISIONS.md` | D-001..D-023 | 契约形状 / gold 判定 / fixtures / 校验尺子 |
| `OP-D023..OP-D032` | `docs/history/HISTORY-VIDEO-OWNER-PLAN-001.md#附录-D` | D-023..D-032 | 治理（闸口顾问化）/ Arc·Thesis / 语料管线 / 抽取器 |

## 碰撞区解消（D-023..D-027 · 曾用号 → 双义）

| 曾用号 | KU 线（KU-Dxxx） | 治理线（OP-Dxxx） |
|---|---|---|
| D-023 | **KU-D023** F1 撤 cf:jinyang-independence + 契约 v0.2.2 + U7 关闭 | **OP-D023** 闸口顾问化（Wiki 闸口→顾问裁决+Wiki 终否决权） |
| D-024 | —（KU 线无 D-024） | **OP-D024** 主题簇命名定为 Arc（弧） |
| D-025 | —（KU 线无 D-025） | **OP-D025** Arc/Thesis 为仓内 schema，不进查询契约 |
| D-026 | —（KU 线无 D-026） | **OP-D026** 抽取器云端 API 默认禁 |
| D-027 | —（KU 线无 D-027） | **OP-D027** 现代考订论点自撰摘述+出处，原文不入语料层 |

> KU 线正文到 D-023 为止（其后 W-H1a 的追加以**扩写既有条目**方式并入 KU-D019/KU-D022，无新号——见 DECISIONS.md 内『W-H1a-2 追加』标注）。治理线独占 D-024 及以后。故除 D-023 外无真双义正文，D-024..D-027 仅治理线有正文。

## 治理线全表（OP-D023..D-032 · 指针至 OWNER-PLAN 附录 D）

OP-D023 闸口顾问化 · OP-D024 Arc 命名 · OP-D025 Arc/Thesis 仓内 · OP-D026 云端禁 · OP-D027 现代考订不入库 · **OP-D028 canonical_date 永不由抽取器产出** · **OP-D029 抽取器定型 qwen3-8b·半自动偏自动** · **OP-D030 抽验门全关(F12修/F8/F10)** · **OP-D031 年数cf追认成立** · **OP-D032 舒州/徐州地名variant** · OP-D033 在库源机核100%口径+豁免 · OP-D034 PERSON-INTAKE协议 · **OP-D035 决策原话须在FULL AUTO块内** · **OP-D036 P1出口判据重定域(同一性/全自动移P2)** · **OP-D037 语料主路径改zhwikisource dump** · **OP-D038 PERSON-INTAKE修订(繁简归一/X氏referent-ambiguous)**。

> **OP-D028~032 状态（W-H1a-5）**：Wiki 逐字权威文本已下达（FULL AUTO 块内，OP-D035）；**渲染稿作废、标曾用留痕**（OWNER-PLAN 附录 D 头）。⚠ 权威 D-028~032 语义与渲染稿号位不同（如权威 D-030=抽验门全关，渲染 D-030=语料库现实）——以权威为准。

## KU 线全表（KU-D001..D023 · 指针至 DECISIONS.md）

KU-D001 契约冻结 v0.1 · D002 G1b 钉点 tag · D003 F2 签署+fixtures-v0.1 · D004 扩展批 Tier1 · D005 source.genre 取(A) · D006 契约 v0.2(place) · D007 F14 三附加 · D008 剩余批次规则 · D009 tag 追认+PENDING-GATE 总则 · D010 抽验补课 · D011 工时口径四段 · D012 actor GAP · D013 DEBT-4 解耦 · D014 F2 真签 GATE 工件 · D015 校验尺子 · D016 agent 分钟=运营单位 · D017 hint 不得私裁 · D018 m0 拆弹 · D019 Gap 批(+年数 cf 追认) · D020 契约 v0.2.1 · D021 跨线通知总则 · D022 抽验裁决(+抽验门全关) · D023 F1 撤 cf+v0.2.2+U7。

> **今后**：新决策带命名空间前缀（KU-Dxxx / OP-Dxxx）入册，不再裸号；本表随新增维护。**曾用号不改字节**（历史 commit 引用稳定）。
