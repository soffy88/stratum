# 语料库·书目在库登记（ARC-SPEC §4.1/§4.2）· W-H1a-1

> **R5 纪律**：底本一律**维基文库白文**（CC BY-SA 3.0 + attribution），**禁对齐在版点校本**；入库文字系 WebFetch 逐字摘录（会话可溯），**非记忆备录**。抓取限开放源（wikisource / ctext）。
> **★本表为派生视图（OP-D-063，OP-D-060 同族）：每次语料入库同轮刷新，不得滞留旧快照**。substrate ULID = SHA256(src_id) 确定性派生（稳定可复现，非时序 ULID）。**2026-07-24 刷新**：下表按 `docs/history/corpus/*.json` 实测重算（左传/史记/资治通鉴/三国志已由 D-037 zhwikisource dump 波次转全量，旧表仍记 W-H1a-1 首波 WebFetch 逐段快照，早已滞后）。

## 在库表（2026-07-24 实测）

| 书 | src | substrate ULID | 段数 | 字数 | 覆盖 | 底本 URL | 许可 | 抓取日 |
|---|---|---|---|---|---|---|---|---|
| 左传 | src:zuozhuan | 4YW6S9BRHDQVDGZDYXH2E8Z7HE | 2954 | 242692 | **12/12 页（全量，dump）** | wikisource 春秋左氏傳 | CC BY-SA 3.0 | 2026-07-22 |
| 史记 | src:shiji | 3EX2FF5S4Q1M0K27M27QVNWEYH | 2148 | 121759 | **14/14 页（全量，dump）** | wikisource 史記 | CC BY-SA 3.0 | 2026-07-22 |
| 资治通鉴 | src:zztj | DKMGQCJ1564XCCQ1MHSAZNNEMJ | 118 | 9116 | **1/1 页（全量，dump）** | wikisource 資治通鑑/卷001 | CC BY-SA 3.0 | 2026-07-22 |
| 三国志（含裴注） | src:sanguozhi | 7RTPSJS9QAKBREZPGTR8DSSV5T | 261 | 72641 | **5/5 页（全量，dump）** | wikisource 三國志 | CC BY-SA 3.0 | 2026-07-22 |
| 国语 | src:guoyu | 6GB8KKM05W13RWT6A7DRMCXDVB | 2 | 117 | 部分（首弧牵引+fixtures被引段落）；全书全量入库仍 PENDING | wikisource/ctext | CC BY-SA 3.0 | 2026-07-22 |
| 战国策 | src:zhanguoce | FR8TKEM3839A5M37HD8MRBT5MP | 3 | 172 | 部分（赵策一/魏策一/秦策一苏秦始将连横）；全书全量入库仍 PENDING | wikisource 戰國策 | CC BY-SA 3.0 | 2026-07-22 |
| 水经注 | src:shuijingzhu | YMVZ9FHEMJTEF77GB9PJ9D826Z | 1 | 162 | 部分（江水注·赤壁/乌林/蒲圻地望段，F18 被引）；全书后续波 | wikisource 水經注 | CC BY-SA 3.0 | 2026-07-23 |
| 左氏博议（东莱博议，吕祖谦） | src:zuoshiboyi | 0HA7NN34RNSZ694T5WNT1DXKHJ | 2 | 856 | 部分（四库提要 + 原序，讲史方法论前置扫描）；正文25卷全量入库仍 PENDING | wikisource 左氏博議 (四庫全書本) | CC BY-SA 3.0 + PD-old | 2026-07-24 |

**合计**：8 substrate · 5489 段 · 447515 字（harness `validate_gold.py` 实测口径：8 corpus/5489 paras，registry 222 ids）。**旧表（6 substrate·16 段·881 字）已作废、非本表基准**——旧表系 W-H1a-1 首波逐段 WebFetch 快照，D-037 起主路径改 zhwikisource 整卷 dump，左传/史记/资治通鉴/三国志已转全量，旧表未随之刷新即为 OP-D-063 所立之因。

## 诚实总账

- **已完成**：首弧牵引书目的**被引段落 + arc 论点段（师服/臣光曰）**入库、可寻址（ULID）；15 条引文机核（13 一致 / 1 实质异文 / 1 双源地名异）；SPOTCHECK 两 PENDING（F8 尾段、F10）清零。
- **未完成（PENDING，非失败）**：① §4.1『全书』全量（左传/国语/史记/战国策全书）——本波只抓被引段+arc核心，全量属后续抓取波次；② design 批 F1–F18 其余 45 account 的 para_ulid（对应段落未抓）；③ 弧论点段 叔向（左传昭3）、史墨（左传昭32）——wikisource 分年 URL 404，换源待续。
- **未动**：stratum 生产入库管线（DuckDB 退役/PG 未实现，记忆在案）——本波语料库为**仓内自包含可寻址存储**（committed bytes 即真理，同契约纪律），不依赖该管线；生产管线修复属独立事项。

## W-H1a-2 增量

- 左传 +2 段（昭3 叔向 / 昭32 史墨，ctext），史记 +1 段（项羽本纪，wikisource）。合计 **6 substrate · 19 段**。
- ★**全书全量入库仍 PENDING（诚实）**：本波续抓弧论点 + F12 段；『左传/国语/史记全书』verbatim 全量经 WebFetch **不可行**（逐页有损、体量以十万字计）——全书需 wikisource dump/bulk 导入（另立事项），非本工具链。已抓 = 首弧论点 + fixtures 高价值被引段。
