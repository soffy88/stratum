# Notes · `F1-sanjiafenjin.json`

> 从 JSON 本体迁出的注释（下划线键）。JSON 本体现零下划线键、committed bytes 原样过 validate（无隐形预处理）。本文件仅供人读，非契约。

### / · _meta
```json
{
  "fixture": "F1 · 三家分晋",
  "spec": "AII-HISTORY-KU-SPEC-001 §10 W-H0 ①",
  "purpose": "isomorphism（同事异述）常态样本 + parent_event 组合结构。供生产端 G1b 对拍（本 fixture 装配为 §8 契约样例 sample.sanjiafenjin.json）。",
  "mechanisms_exercised": [
    "parent_event 组合（过程 ⊃ 晋阳之战 + 命侯）",
    "同事异述：一 event 挂多 account（晋阳之战 之于 通鉴/史记/战国策）",
    "策士言辞 genre 降权（战国策）",
    "命侯 date 精确"
  ],
  "identity_verdicts_see": "fixtures/JUDGMENTS.md#F1",
  "locator_note": "语料层未入库，para_ulid 一律 null 并在 note 记待补；书/篇级已定（冲突判据充分）。",
  "created": "2026-07-21",
  "author": "CC (手工，禁抽取器)"
}
```

---

## 事件注记 · 独立见证折算（indep≈1.5）· v0.3.1 移入（D-023）

> 原 `cf:jinyang-independence`（dimension=narrative，hint=主线+角标）**已撤**——三 account 系**同说**（无对立主张），该对象实为独立性折算记录，非冲突。折算依据移事件级（本注记 + `mainline_decision.rationale` + `JUDGMENTS.md#F1`），不占 cf 对象位。

- **折算**：史记 计 1 · 通鉴 派生自史记（同祖源 src:zztj←src:shiji，不另计）· 战国策 策士敷演 genre 降权（计 0.5）→ 三源同说 ≈ **1.5** 独立见证（非 3）。
- **★防倒退点（D-023）**：凡为**侧重差（F12）或折算记录（F1）**立 cf 即倒退信号；narrative cf 只挂真对立主张。
- **裁**：顾问 Claude（Wiki 授权 2026-07-22，D-023），Wiki 保留否决权。
