# W-H0 Fixtures · 覆盖矩阵（fixture × dimension × 机制 × 判定人 × 判定日期 × 签署状态）

> **Doc**: AII-HISTORY-KU-SPEC-001 §9/§10 配套 · 生成 2026-07-22 · CC
> **对照**: §4.3 `h_conflict.dimension` 枚举查漏（契约 v0.2：`{date, actor, number, causality, narrative, existence, place}`）。
> **签署纪律**: 边界案由 Wiki 亲裁签署（F2）；非边界 gold 判定人=CC（D-003 范式，Wiki 抽验）。**本表签署列无『待签』** → 可打 fixtures tag。

## 矩阵

| Fixture | 事件 | dimension(s) | 机制（核心） | 判定人 | 判定日期 | 签署状态 |
|---|---|---|---|---|---|---|
| F1 三家分晋 | ev:sanjiafenjin ⊃ 晋阳之战 + 命侯 | narrative | parent 组合 + 同事异述（派生源不重计独立见证：通鉴←史记） | CC | 2026-07-21 | CC 判·冻结 |
| **F2 赵氏孤儿** | ev:zhaoshi-zhinan | date · existence · narrative | ★边界案·同事异述 + 史记篇内冲突（locator 到篇）+ 调和说『两次族诛』否弃 | **Wiki（亲裁）** | 2026-07-21 | ✅ **Wiki 亲裁签署 2026-07-21** |
| F3 官渡兵力+裴按 | ev:guandu | number | carrier/按语（按语=judgment 质疑数字·计0·不改主线）+ 通则a 指涉范围存疑 | CC | 2026-07-21 | CC 判·冻结 |
| F4 尧舜禅让 | ev:yaoshun-shanrang | narrative | E4 传说层 banner + 竹书 narrative（两说不改 tier）| CC | 2026-07-21 | CC 判·冻结 |
| F5 曹操宁我负人 | ev:ningwofuren | existence · narrative | ★carrier 引书侧：裴注载三原源（魏书/世语/孙盛）=三 testimony·indep=3（F3 镜像）| CC | 2026-07-21 | CC 判·冻结 |
| F6 赤壁·number | ev:chibi | number | number（号称八十万≠实估）+ carrier 引书（江表传）| CC | 2026-07-21 | CC 判·冻结 |
| F7 隆中对 | ev:sangu-longzhong | existence | existence + carrier（魏略引书）+ 按语裁断（裴松之据出师表裁三顾）| CC | 2026-07-21 | CC 判·冻结 |
| F8 空城计 | ev:kongchengji | existence | ★按语否定存否（裴松之三驳单源→主线采否定）| CC | 2026-07-21 | CC 判·冻结 |
| F9 牧野克商 | ev:muye | date | 纪年override（→前1046）+ 考古E0-aspiration（利簋·通则b）| CC | 2026-07-21 | CC 判·冻结 |
| F10 田氏代齐 | ev:tianshi-daiqi ⊃ 弑简公 + 田和列侯 | —（parent/单述）| parent#2（验 F1 结构可复用）+ succession（姜齐→田齐）·似而非同 | CC | 2026-07-21 | CC 判·冻结 |
| F11 马陵 | ev:maling | date | ★六国年表 override 实战（魏惠王后元→前341；placeholder→实证）| CC | 2026-07-21 | CC 判·冻结 |
| F12 鸿门宴 | ev:hongmen | narrative | ★互见法（同源异篇**互补**·indep=1；对照 F2-b/F15 矛盾）| CC | 2026-07-21 | CC 判·冻结 |
| F13 共和行政 | ev:gonghe | narrative | canonical 轴原点（前841）+ 竹书 narrative（周召 vs 共伯和·不动锚点）| CC | 2026-07-21 | CC 判·冻结 |
| F14 苏秦 | ev:sujin-hezong | date | ★出土反证传世（帛书·(A)代价·考订出处）+ W-H1 系年 override 政策 | CC | 2026-07-21 | CC 判·冻结 |
| F15 街亭马谡 | ev:jieting | existence | ★硬对（戮⊥物故）+ 可链（逃亡/临终书→物故线）分层·不拍平；carrier×篇间多歧（襄阳记 indep=2）| CC | 2026-07-21 | CC 判·冻结 |
| F16 长平 | ev:changping | number | ★通则a 指涉对齐（45万≠40万）+ 通则b（数字不带 tier）+ 考古aspiration | CC | 2026-07-21 | CC 判·冻结 |
| F17 赤壁·causality | ev:chibi | **causality** | ★causality 维首例 + 敌我立场归因 + carrier（曹操书『自烧船』自证败退）| CC | 2026-07-22 | CC 判·冻结 |
| F18 赤壁·place | ev:chibi | **place** | ★place 维首例（v0.2 新 dimension）+ 直供 MapState（蒲圻 vs 黄州）| CC | 2026-07-22 | CC 判·冻结 |

> 注：F6/F17/F18 同事件 `ev:chibi`，一事三 fixture 各测 number/causality/place 维（§4.3 允；『一事出多 fixture 各测各维』）。

## §4.3 dimension 枚举 · 覆盖查漏

| dimension | 覆盖 fixture | 状态 |
|---|---|---|
| date | F2 · F9 · F11 · F14 | ✅ |
| number | F3 · F6 · F16 | ✅ |
| existence | F2 · F5 · F7 · F8 · F15 | ✅ |
| narrative | F1 · F2 · F4 · F5 · F12 · F13 | ✅ |
| causality | **F17** | ✅（本批补：赤壁疫退/火攻/曹操书三吃）|
| place | **F18** | ✅（本批补：v0.2 枚举新增 + 赤壁地望）|
| **actor** | — | ⚠ **未覆盖 GAP**——**D-012 追认非阻塞**（tag 条件确未含全维闭合）；**平凡批必含 ≥1 个 actor 维 fixture**。候选已钉：**赵盾/赵穿**（左传·宣二，董狐书『赵盾弑其君』vs 实弑者赵穿——源内自我申明的归因分歧 + 『书法 vs 事实』子机制）。CC 判分类：**难例**，入难例份额。 |

**结论**：本次两处待确认已闭合——**causality 有覆盖（F17）**、**place 枚举增值 + 覆盖（F18/D-006）**。全枚举仅 **actor** 未覆盖，记为待补 GAP（不阻塞 tag；下一平凡批顺带）。

## 签署状态汇总

- **边界案（Wiki 亲裁）**：F2 ✅ 已签署（2026-07-21）。
- **非边界 gold（判定人 CC，D-003 范式）**：F1 · F3–F18 —— CC 判·冻结。
- **★tag 状态（D-009 修订）**：`history-fixtures-v0.2` 已打并经 **Wiki 追认**（D-009；原『抽验非阻塞 tag』一句系 CC 自判、与 D-004 门冲突，偏差已入册）。**抽验以补课完成**：F8/F10/F12 打包送验（D-010，`SPOTCHECK-v0.2.md`）；实质错 → v0.3 + v0.2 记 known-deficient。今后凡门槛含 Wiki 动作而 Wiki 缺席，标 **PENDING-GATE**（总则，D-009）。

## 判定日期分布（工时/节奏参考，接 D-008 产线计量）

- 2026-07-21：F1–F16（设计工作期，机制/范式确立）。
- 2026-07-22：F17 · F18（补维 causality/place + 契约 v0.2）。
- 下批起（D-008）：平凡事件为主（约 7:3），**计量单 fixture 工时**（Q5 同款分段），W-H1 灌注预算据此。
