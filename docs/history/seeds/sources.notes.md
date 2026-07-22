# Notes · `sources.json`

> 从 JSON 本体迁出的注释（下划线键）。JSON 本体现零下划线键、committed bytes 原样过 validate（无隐形预处理）。本文件仅供人读，非契约。

### / · _meta
```json
{
  "registry": "source",
  "spec": "AII-HISTORY-KU-SPEC-001 §3.1",
  "note": "源注册表种子。战国书目按 §2.3 首批候选建；三国志+裴注、竹书/山海经/逸周书为 fixtures（官渡、E4）所涉。derivation_edges 必填字段（可空数组）。carrier_of 用于 carrier/original 独立性折算（裴注是首例）。成书年代/底本note 允许 TODO，字段结构不缺。",
  "created": "2026-07-21",
  "author": "CC (手工)"
}
```
