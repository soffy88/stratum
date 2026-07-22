# 语料库·书目在库登记（ARC-SPEC §4.1/§4.2）· W-H1a-1

> **R5 纪律**：底本一律**维基文库白文**（CC BY-SA 3.0 + attribution），**禁对齐在版点校本**；入库文字系 WebFetch 逐字摘录（会话可溯），**非记忆备录**。抓取限开放源（wikisource / ctext）。
> **诚实覆盖标注**：本波次 = **部分入库**（首弧牵引 + 25 fixtures 被引段落之已抓子集）。§4.1『全书』全量入库属**后续波次**，未完成即标未完成。substrate ULID = SHA256(src_id) 确定性派生（稳定可复现，非时序 ULID）。

## 在库表

| 书 | src | substrate ULID | 已入段 | 字数 | §4.1 目标范围 | 覆盖 | 底本 URL | 许可 | 抓取日 |
|---|---|---|---|---|---|---|---|---|---|
| 左传 | src:zuozhuan | 4YW6S9BRHDQVDGZDYXH2E8Z7HE | 4（隐5/哀9/哀14/桓2） | 194 | 全书 | **部分** | wikisource 春秋左氏傳 | CC BY-SA 3.0 | 2026-07-22 |
| 史记 | src:shiji | 3EX2FF5S4Q1M0K27M27QVNWEYH | 3（赵/晋/田完世家） | 144 | 晋·赵韩魏世家+年表 | **部分** | wikisource 史記 | CC BY-SA 3.0 | 2026-07-22 |
| 国语 | src:guoyu | 6GB8KKM05W13RWT6A7DRMCXDVB | 2（晋语九×2） | 117 | 全书（晋语核心） | **部分** | wikisource/ctext | CC BY-SA 3.0 | 2026-07-22 |
| 战国策 | src:zhanguoce | FR8TKEM3839A5M37HD8MRBT5MP | 2（赵策一/魏策一） | 172 | 赵魏韩策 | **部分** | wikisource 戰國策 | CC BY-SA 3.0 | 2026-07-22 |
| 资治通鉴 | src:zztj | DKMGQCJ1564XCCQ1MHSAZNNEMJ | 3（周纪一×3） | 97 | 卷一 | **接近全（卷一节点）** | wikisource 資治通鑑/卷001 | CC BY-SA 3.0 | 2026-07-22 |
| 三国志 | src:sanguozhi | 7RTPSJS9QAKBREZPGTR8DSSV5T | 2（诸葛亮传裴注×2） | 157 | 首弧不涉（F8 机核用） | **点覆盖** | wikisource 三國志 | CC BY-SA 3.0 | 2026-07-22 |

**合计**：6 substrate · 16 段 · 881 字 · para_ulid 已回填 fixtures 15/60 account（25%）。

## 诚实总账

- **已完成**：首弧牵引书目的**被引段落 + arc 论点段（师服/臣光曰）**入库、可寻址（ULID）；15 条引文机核（13 一致 / 1 实质异文 / 1 双源地名异）；SPOTCHECK 两 PENDING（F8 尾段、F10）清零。
- **未完成（PENDING，非失败）**：① §4.1『全书』全量（左传/国语/史记/战国策全书）——本波只抓被引段+arc核心，全量属后续抓取波次；② design 批 F1–F18 其余 45 account 的 para_ulid（对应段落未抓）；③ 弧论点段 叔向（左传昭3）、史墨（左传昭32）——wikisource 分年 URL 404，换源待续。
- **未动**：stratum 生产入库管线（DuckDB 退役/PG 未实现，记忆在案）——本波语料库为**仓内自包含可寻址存储**（committed bytes 即真理，同契约纪律），不依赖该管线；生产管线修复属独立事项。
