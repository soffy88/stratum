# Notes · `sample.sanjiafenjin.json`

> 从 JSON 本体迁出的注释（下划线键）。JSON 本体现零下划线键、committed bytes 原样过 validate（无隐形预处理）。本文件仅供人读，非契约。

### / · _meta
```json
{
  "sample": "§8 契约完整静态样例 · 三家分晋（晋阳之战 节点）",
  "spec": "AII-HISTORY-KU-SPEC-001 §8.1 / §8.4",
  "conforms_to": "history-query-response.schema.json",
  "note": "冻结样例。生产端 G1b 对拍此文件（逐字段一致或差异可解释）。取三家分晋之核心子事件『晋阳之战』作查询响应——其 3 account（史记/通鉴/战国策）即『同事异述』常态、parent_event 指向组合父事件。数据源 fixtures/F1-sanjiafenjin.json。para_ulid 语料未入库故为 null（G1a 手工装配同形数据时同置 null；G1b 实装后填 ULID 即『差异可解释』）。",
  "frozen": "v0.1 · 2026-07-21"
}
```

---

## 事件注记 · 独立见证折算移事件级 · v0.3.1 / 契约 v0.2.2（D-023）

> 本冻结样例原含 `cf:jinyang-independence`（三源同说的独立性折算记录，误作 narrative cf）。抽验同款扫描裁『折算记录不立 cf』（D-022→D-023），**已撤**——样例 `conflicts` 现为空数组、`event.conflicts` 空。折算依据（史记计1/通鉴派生不另计/战国策降权计0.5→≈1.5）见 `fixtures/F1-sanjiafenjin.notes.md` 事件注记与 `JUDGMENTS.md#F1`。
>
> **字节变更走契约纪律**：sample 字节变 → 新钉点 **`history-contract-v0.2.2`**（G1b 对拍随迁）；契约**形状**未变（schema 字节不动、`contract_version` 仍 v0.2——撤的是 conflict **实例**非 shape）。冲突形态的样例演示角色迁至 `contracts/samples/ep_sanjia_fenjin/`（cf:jinyang-shuiyuan 等 S12 富例）。见 README 沿革 + DECISIONS D-023。
> **frozen**: v0.2.2 · 2026-07-22（sha256 见 G1b 交付单权威版）。
