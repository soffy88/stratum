# Notes · `F2-zhaoshiguer.json`

> 从 JSON 本体迁出的注释（下划线键）。JSON 本体现零下划线键、committed bytes 原样过 validate（无隐形预处理）。本文件仅供人读，非契约。

### / · _meta
```json
{
  "fixture": "F2 · 赵氏孤儿（赵氏之难）",
  "spec": "AII-HISTORY-KU-SPEC-001 §10 W-H0 ②",
  "purpose": "existence/narrative 冲突 + 同书不同篇冲突（史记·赵世家 vs 史记·晋世家）→ locator 必到篇的必要性示范。★压边界案：左传（前583）与史记·赵世家（前597）时间差14年、主体集半重合——gold 判定由 Wiki 亲裁并记全理由。",
  "mechanisms_exercised": [
    "①归因链首证：史记篇内分裂（晋世家 vs 赵世家，cf:zhaonan-shiji-internal, indep=0, presentation=仅记录）——locator 必到篇",
    "②调和说『两次族诛』否弃项显式在录（rejected_alternatives）+ 否弃理由（虚构第二次族诛、违 parsimony）",
    "③冲突对象三挂（S12）：date 597/583、existence 屠岸贾灭族、narrative 搜孤救孤",
    "④mainline=左传·成八；赵世家 account 全文保留 + genre_note 晚出敷演",
    "边界同一性判定（同事异述 vs 似而非同）；★gold 由 Wiki 亲裁"
  ],
  "identity_verdicts_see": "fixtures/JUDGMENTS.md#F2",
  "boundary_case": true,
  "gold_adjudicator": "Wiki（亲裁，见 JUDGMENTS.md#F2；本 fixture 内 mainline_decision.decided_by 标 Wiki-亲裁）",
  "locator_note": "para_ulid 待补；★chapter 级为本 fixture 判据核心，不可省——冲突正在史记内部两篇之间。",
  "created": "2026-07-21",
  "author": "CC 备据 + Wiki 亲裁签署 2026-07-21（gold 冻结, tag history-fixtures-v0.1）"
}
```

---

## 四行证据定位图（2026-07-22 补交 · D-014）

> F2 四冲突对象各自的证据定位，一行一冲突。全部 locator 到**篇**级（chapter——本 fixture 判据核心，冲突正在史记内部两篇之间）；`para_ulid` 一律 null，语料层入库（DEBT-3 后）填。数据源：`F2-zhaoshiguer.json`（blob `1d23971`，@`history-fixtures-v0.1` 与 `v0.2` 同字节）。

| 冲突对象 | dimension | 甲端证据定位 | 乙端证据定位 | indep | presentation |
|---|---|---|---|---|---|
| `cf:zhaonan-shiji-internal`（★归因链首证） | narrative | 史记·**晋世家**（因袭左传，无屠岸贾/搜孤） | 史记·**赵世家**（戏剧叙事） | 0（同源两篇） | 仅记录 |
| `cf:zhaonan-date` | date | 左传·**成公八年** → 前583 | 史记·**赵世家** → 前597 | 1（仅赵世家立异） | S12 对勘 |
| `cf:zhaonan-existence`（屠岸贾灭族存否） | existence | 史记·**赵世家**（独载） | 左传·成八 / 史记·晋世家 **阙载** | 1 | S12 对勘 |
| `cf:zhaonan-narrative-souhu`（搜孤救孤存否） | narrative | 史记·**赵世家**（独载：程婴/公孙杵臼） | 左传·成八 **阙载** | 1 | S12 对勘 |

否弃项锚点：`rejected_alternatives[reject:zhaonan-tiaohe-two-purges]` = `F2-zhaoshiguer.json:281`（同 blob）。

## GATE 签署工件（A 线格式 · D-014）

> 签字记录升级到 A 线 GATE 工件格式：**被签对象不可变 ref + 裁决原文 + 日期**。

- **被签对象（不可变 ref）**：`docs/history/fixtures/F2-zhaoshiguer.json` @ blob **`1d23971fd4587222574d3f52e76e138ca092f178`**（tag `history-fixtures-v0.1` 与 `history-fixtures-v0.2` 下字节同一）；判定记录 `JUDGMENTS.md#F2` @ tag `history-fixtures-v0.2`（commit `7ef49d2`）。
- **原裁**：2026-07-21，Wiki 亲裁（同事异述；四冲突；调和说否弃）。**留痕核查结论（诚实入账）**：签署 commit `31c49c0` 仅翻转 `decided_by` 字段与 JUDGMENTS 签署字样，**裁决原文无逐字留痕**——当时入账的是 CC 备据文本承载的裁意，非 Wiki 签字工件。
- **真签（2026-07-22，Wiki）**：Wiki 裁决原文逐字引：『**F2 收尾包（一个 follow-up commit 全装）：定位图入 F2-zhaoshiguer.notes.md；签字记录升级到 A 线 GATE 工件格式（被签对象不可变 ref + 裁决原文 + 日期）——07-21 的签早于该标准，追认但补格式；调和说（两次族诛）否弃项回贴 rejected_alternatives 锚点行号。若翻不出 07-21 的裁决原文——那说明当时入账的是我的裁意而非 Wiki 的签，就地用本包补一次真签。**』
- **签署语义**：07-21 之裁**追认**；F2 gold（上述 blob 字节）自本工件起为**真签冻结**。此后 F2 任何改判走后续 commit + 新 GATE 工件，不改历史。
- **记录人**：CC · 2026-07-22。
