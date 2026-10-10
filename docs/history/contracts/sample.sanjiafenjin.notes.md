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
