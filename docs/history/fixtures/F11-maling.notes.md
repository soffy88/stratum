# Notes · `F11-maling.json`

> JSON 本体零下划线键、原样过 validate。仅供人读，非契约。

### / · meta
```json
{
  "fixture": "F11 · 马陵之战",
  "spec": "AII-HISTORY-KU-SPEC-001 §10 W-H0 扩展批（Tier2·战国）",
  "purpose": "六国年表 纪年override 首个实战：史记年表因魏惠王未分『后元』系年偏早→按杨宽/钱穆校正取前341。将 chronology.json 魏惠王 placeholder(TODO) 升为实证。",
  "mechanisms_exercised": [
    "系统性误差 override 实战：魏惠王后元→马陵前341(academic_source 杨宽《战国史》/钱穆《系年》, 非TODO)",
    "date 冲突：史记年表原值 vs 校正值",
    "竹书作系年校勘旁证",
    "叙事(减灶/庞涓自刭)与系年分离：主线取叙事、系年取override"
  ],
  "identity_verdict": "同事异述（系年 override；判定人=CC）",
  "identity_verdicts_see": "fixtures/JUDGMENTS.md#F11",
  "created": "2026-07-21", "author": "CC（手工，非边界 gold）"
}
```
